#!/usr/bin/env python3
# build_html_toc.py
#
# Reads `table.csv` in the same folder and outputs `tags_list.html`
# with a plain HTML table-of-contents: one table per cluster, rows show
# Name, Characters, and Link (if present).

from __future__ import annotations
import csv
import sys
from collections import OrderedDict
from html import escape
from pathlib import Path

INPUT_NAME = "table.csv"
OUTPUT_NAME = "tags_list.html"

def find_col(header_row, candidates):
    """
    Case-insensitive, whitespace-tolerant column resolver.
    Returns the actual column name from the CSV or None.
    """
    if not header_row:
        return None
    normalized = {str(h or "").strip().lower(): h for h in header_row}
    for cand in candidates:
        key = cand.strip().lower()
        if key in normalized:
            return normalized[key]
        # allow substring contains (e.g., "name (clean)")
        for k in normalized:
            if key and key in k:
                return normalized[k]
    return None

def read_rows(csv_path: Path):
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rdr = csv.DictReader(f)
        if not rdr.fieldnames:
            raise SystemExit("CSV appears to have no header row.")

        # Resolve columns (case-insensitive)
        name_col = find_col(rdr.fieldnames, ["name", "title", "label"])
        tag_col  = find_col(rdr.fieldnames, ["tag", "tags", "category", "cluster"])
        url_col  = find_col(rdr.fieldnames, ["content url", "url", "link", "href", "permalink"])
        chars_col = find_col(rdr.fieldnames, ["characters", "character", "cast", "who"])

        if not name_col or not tag_col:
            raise SystemExit(
                f"Missing required columns. Found: {rdr.fieldnames}\n"
                "Need at least NAME and TAG/CLUSTER (case-insensitive). URL is optional."
            )

        # Ordered mapping: cluster -> list of rows, preserving CSV order
        by_cluster: OrderedDict[str, list[dict[str, str | list[str] | None]]] = OrderedDict()

        for row in rdr:
            raw_name = (row.get(name_col) or "").strip()
            raw_cluster  = (row.get(tag_col)  or "").strip()
            raw_url  = (row.get(url_col)  or "").strip() if url_col else ""
            raw_chars = (row.get(chars_col) or "").strip() if chars_col else ""

            if not raw_name or not raw_cluster:
                # Skip rows missing essential fields
                continue

            if raw_cluster not in by_cluster:
                by_cluster[raw_cluster] = []

            url = raw_url if raw_url else None
            chars_list = [
                c.strip() for c in raw_chars.split(",") if c.strip()
            ] if raw_chars else []

            by_cluster[raw_cluster].append(
                {"name": raw_name, "url": url, "chars": chars_list}
            )

        return by_cluster

def build_html(by_cluster: OrderedDict[str, list[dict[str, str | list[str] | None]]]) -> str:
    # Minimal HTML: one table per cluster with Name, Characters, Link
    parts: list[str] = []
    parts.append('<h2>We try to keep this static story map in sync with the <a href="https://programminginpoppyfields.github.io/poppyverse-interactive-map/index.html">chaotic 3D one.</a> Emphasis on try. Reality is subjective and version control is a myth.</h2>')
    parts.append("<h1>Table of Contents</h1>")

    for cluster, items in by_cluster.items():
        parts.append(f"<h2>{escape(cluster)}</h2>")
        parts.append('<table border="0" cellspacing="0" cellpadding="6" style="border-collapse:collapse;">')
        parts.append('<thead><tr><th style="padding:6px 10px; text-align:left;">Name</th><th style="padding:6px 10px; text-align:left;">Characters</th><th style="padding:6px 10px; text-align:left;">Link</th></tr></thead>')
        parts.append("<tbody>")
        for entry in items:
            name = escape(entry["name"])  # type: ignore[index]
            chars = entry["chars"] or []  # type: ignore[index]
            chars_txt = ", ".join(escape(c) for c in chars) if chars else "—"
            url = entry["url"]  # type: ignore[index]
            if url:
                safe_url = escape(url, quote=True)
                link_cell = f'<a href="{safe_url}" target="_blank" rel="noopener">Content available</a>'
            else:
                link_cell = "—"
            parts.append(
                "<tr>"
                f'<td style="padding:6px 10px; font-weight:700; color:#fff;">{name}</td>'
                f'<td style="padding:6px 10px; font-weight:400; color:#b5b5b5;">{chars_txt}</td>'
                f'<td style="padding:6px 10px;">{link_cell}</td>'
                "</tr>"
            )
        parts.append("</tbody></table>")

    return "\n".join(parts)

def main():
    here = Path(__file__).resolve().parent
    csv_path = here / INPUT_NAME
    if not csv_path.exists():
        print(f"Cannot find {INPUT_NAME} in {here}", file=sys.stderr)
        sys.exit(1)

    by_cluster = read_rows(csv_path)
    if not by_cluster:
        print("No valid rows found (need NAME and TAG/CLUSTER).", file=sys.stderr)
        sys.exit(1)

    html = build_html(by_cluster)
    out_path = here / OUTPUT_NAME
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path.name} with {sum(len(v) for v in by_cluster.values())} items across {len(by_cluster)} clusters.")

if __name__ == "__main__":
    main()
