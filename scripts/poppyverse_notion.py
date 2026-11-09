#!/usr/bin/env python3
"""Shared, read-only Notion access for the Poppyverse map generators.

The secret is intentionally accepted only through the NOTION_TOKEN environment
variable. It is sent in the private Authorization header to api.notion.com and
is never printed or written into generated HTML.
"""

from __future__ import annotations

import html
import json
import math
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_FULL_DATA_SOURCE = "3b599d3f-e3d2-8343-925a-879eb54fe721"
DEFAULT_CLUSTER_DATA_SOURCE = "41199d3f-e3d2-8033-964b-000ba93df5fd"
NOTION_VERSION = "2026-03-11"

# These catalogue records were deleted intentionally. Keeping their old IDs
# here prevents a stale snapshot from resurrecting them in a generated map.
EXCLUDED_CATALOG_IDS = {"96", "745"}
EXCLUDED_TITLES = {
    "f for effort",
    "[meta] working notes: lalah's counterattack",
    "[meta] working notes: lalah’s counterattack",
}


class NotionError(RuntimeError):
    """A concise, user-facing Notion fetch failure."""


def clean_id(value: object) -> str:
    match = re.search(r"([0-9a-fA-F]{32})", str(value or "").replace("-", ""))
    if not match:
        return ""
    raw = match.group(1).lower()
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


def number(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def first(row: dict[str, Any], *names: str, default: Any = "") -> Any:
    lowered = {str(key).casefold(): key for key in row}
    for name in names:
        real = lowered.get(name.casefold())
        if real is not None:
            return row.get(real, default)
    return default


def clean_display_text(value: object, *, preserve_paragraphs: bool = False) -> str:
    """Remove accidental HTML wrappers and Notion/Markdown escape debris."""
    text = html.unescape(str(value or ""))
    text = re.sub(r"\\([^\w\s])", r"\1", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"<[^>]*>", "", text)
    if preserve_paragraphs:
        parts = [re.sub(r"\s+", " ", part).strip() for part in re.split(r"\n\s*\n", text)]
        return "\n\n".join(part for part in parts if part)
    return re.sub(r"\s+", " ", text).strip()


def parse_json_array(value: object) -> list[Any]:
    if isinstance(value, list):
        return value
    text = str(value or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def parse_tokens(value: object) -> list[str]:
    if isinstance(value, list):
        return [clean_display_text(item) for item in value if clean_display_text(item)]
    parsed = parse_json_array(value)
    if parsed:
        return [clean_display_text(item) for item in parsed if clean_display_text(item)]
    return [
        clean_display_text(part)
        for part in re.split(r"[\n;,|]+", str(value or ""))
        if clean_display_text(part)
    ]


def relation_ids(value: object) -> list[str]:
    values = value if isinstance(value, list) else parse_json_array(value)
    result: list[str] = []
    for item in values:
        candidate = item.get("id", "") if isinstance(item, dict) else item
        normalized = clean_id(candidate)
        if normalized:
            result.append(normalized)
    return result


def rich_text_plain(items: object) -> str:
    if not isinstance(items, list):
        return ""
    return "".join(
        str(item.get("plain_text") or item.get("text", {}).get("content") or "")
        for item in items
        if isinstance(item, dict)
    )


def normalize_property(prop: dict[str, Any]) -> Any:
    kind = prop.get("type")
    if kind in {"title", "rich_text"}:
        return rich_text_plain(prop.get(kind))
    if kind == "number":
        return prop.get("number")
    if kind in {"url", "email", "phone_number"}:
        return prop.get(kind) or ""
    if kind in {"select", "status"}:
        selected = prop.get(kind)
        return selected.get("name", "") if isinstance(selected, dict) else ""
    if kind == "multi_select":
        return [item.get("name", "") for item in prop.get("multi_select", [])]
    if kind == "relation":
        return [clean_id(item.get("id", "")) for item in prop.get("relation", [])]
    if kind == "date":
        date = prop.get("date")
        return date.get("start", "") if isinstance(date, dict) else ""
    if kind == "checkbox":
        return bool(prop.get("checkbox"))
    if kind == "formula":
        formula = prop.get("formula") or {}
        formula_type = formula.get("type")
        return formula.get(formula_type) if formula_type else ""
    if kind == "files":
        urls: list[str] = []
        for item in prop.get("files", []):
            if not isinstance(item, dict):
                continue
            source = item.get(item.get("type"), {})
            if isinstance(source, dict) and source.get("url"):
                urls.append(str(source["url"]))
        return urls
    return prop.get(kind, "")


def normalize_api_page(page: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "__page_id": clean_id(page.get("id", "")),
        "__url": page.get("url", ""),
    }
    for name, prop in (page.get("properties") or {}).items():
        if isinstance(prop, dict):
            row[name] = normalize_property(prop)
    return row


def normalize_snapshot_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    page_url = str(first(row, "__url", "url", default=""))
    normalized["__url"] = page_url
    normalized["__page_id"] = clean_id(first(row, "__page_id", default=page_url))
    for name in ("Cluster", "Cluster connections", "Full Catalogue entries", "Public Catalogue entries"):
        if name in normalized:
            normalized[name] = relation_ids(normalized[name])
    for name in ("Characters", "Content warnings", "Canon crossovers"):
        if name in normalized and isinstance(normalized[name], str):
            normalized[name] = parse_json_array(normalized[name])
    return normalized


def load_snapshot(path: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if path == "-":
        payload = json.load(sys.stdin)
    else:
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    return (
        [normalize_snapshot_row(row) for row in payload.get("full", [])],
        [normalize_snapshot_row(row) for row in payload.get("clusters", [])],
    )


class NotionClient:
    def __init__(self, token: str) -> None:
        self.token = token
        self.ca_bundle = "system certificate store"
        try:
            import certifi

            self.ca_bundle = certifi.where()
            self.ssl_context = ssl.create_default_context(cafile=self.ca_bundle)
        except ImportError:
            self.ssl_context = ssl.create_default_context()

    def request(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"https://api.notion.com/v1{path}",
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
                "User-Agent": "poppyverse-interactive-map/2",
            },
        )
        for attempt in range(6):
            try:
                with urllib.request.urlopen(request, timeout=45, context=self.ssl_context) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                if exc.code == 429 or 500 <= exc.code < 600:
                    retry_after = number(exc.headers.get("Retry-After"), 0.0)
                    delay = max(retry_after, 0.75 * (2**attempt))
                    print(f"  Notion returned HTTP {exc.code}; retrying in {delay:.1f}s ({attempt + 1}/6)…", file=sys.stderr, flush=True)
                    time.sleep(delay)
                    continue
                raise NotionError(f"Notion API {exc.code}: {detail}") from exc
            except urllib.error.URLError as exc:
                if isinstance(exc.reason, ssl.SSLCertVerificationError):
                    raise NotionError(
                        "HTTPS certificate verification failed. Install/update certifi with "
                        "`python3 -m pip install --upgrade certifi`, then rerun the generator."
                    ) from exc
                if attempt == 5:
                    raise NotionError(f"Could not reach Notion: {exc}") from exc
                delay = 0.75 * (2**attempt)
                print(f"  Network error; retrying in {delay:.1f}s ({attempt + 1}/6)…", file=sys.stderr, flush=True)
                time.sleep(delay)
        raise NotionError("Notion request failed after retries")

    def query_data_source(self, data_source_id: str, label: str) -> list[dict[str, Any]]:
        source_id = clean_id(data_source_id)
        if not source_id:
            raise NotionError(f"Invalid data-source ID: {data_source_id!r}")
        rows: list[dict[str, Any]] = []
        cursor: str | None = None
        page_number = 0
        while True:
            body: dict[str, Any] = {"page_size": 100}
            if cursor:
                body["start_cursor"] = cursor
            response = self.request(f"/data_sources/{source_id}/query", body)
            page_number += 1
            batch = response.get("results", [])
            rows.extend(batch)
            print(f"  {label}: page {page_number} fetched {len(batch)} rows ({len(rows)} total)", flush=True)
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
            if not cursor:
                raise NotionError("Notion reported more rows without a cursor")
        return [normalize_api_page(page) for page in rows]


def fetch_catalogues(
    full_data_source: str = DEFAULT_FULL_DATA_SOURCE,
    cluster_data_source: str = DEFAULT_CLUSTER_DATA_SOURCE,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    token = os.environ.get("NOTION_TOKEN") or os.environ.get("NOTION_API_KEY")
    if not token:
        raise NotionError(
            "Set NOTION_TOKEN to a Notion token with read access to both catalogues. "
            "See README.md for the safe zsh command."
        )
    client = NotionClient(token)
    print(f"Using HTTPS CA bundle: {client.ca_bundle}", flush=True)
    print("Fetching The Full Catalogue from Notion…", flush=True)
    full_rows = client.query_data_source(full_data_source, "Full Catalogue")
    print("Fetching The Cluster Catalogue from Notion…", flush=True)
    cluster_rows = client.query_data_source(cluster_data_source, "Cluster Catalogue")
    if not full_rows:
        raise NotionError("The Full Catalogue query returned no rows; refusing to overwrite the map.")
    if not cluster_rows:
        raise NotionError("The Cluster Catalogue query returned no rows; refusing to overwrite the map.")
    return full_rows, cluster_rows
