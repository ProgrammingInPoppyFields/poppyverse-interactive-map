#!/usr/bin/env python3
# build_tag_list.py
#
# Reads `table.csv` in the same folder and outputs `tags_list.html`
# with a plain nested bullet list: Tag -> [Names], linking Names if URL present.

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
        tag_col  = find_col(rdr.fieldnames, ["tag", "tags", "category"])
        url_col  = find_col(rdr.fieldnames, ["url", "link", "href", "permalink"])

        if not name_col or not tag_col:
            raise SystemExit(
                f"Missing required columns. Found: {rdr.fieldnames}\n"
                "Need at least NAME and TAG (case-insensitive). URL is optional."
            )

        # Ordered mapping: tag -> list of (name, url), preserving CSV order
        by_tag: OrderedDict[str, list[tuple[str, str | None]]] = OrderedDict()

        for row in rdr:
            raw_name = (row.get(name_col) or "").strip()
            raw_tag  = (row.get(tag_col)  or "").strip()
            raw_url  = (row.get(url_col)  or "").strip() if url_col else ""

            if not raw_name or not raw_tag:
                # Skip rows missing essential fields
                continue

            # Do NOT split tags — tags may contain spaces/slashes/commas by design.
            if raw_tag not in by_tag:
                by_tag[raw_tag] = []

            url = raw_url if raw_url else None
            by_tag[raw_tag].append((raw_name, url))

        return by_tag

def build_html(by_tag: OrderedDict[str, list[tuple[str, str | None]]]) -> str:
    # Minimal, Tumblr-safe HTML (no external CSS/JS, just nested <ul>)
    parts = []
    parts.append("<div>")
    parts.append("<h1>Index by Tag</h1>")
    parts.append("<ul>")

    for tag, items in by_tag.items():
        parts.append(f"  <li><strong>{escape(tag)}</strong>")
        parts.append("    <ul>")
        for name, url in items:
            if url:
                safe_url = escape(url, quote=True)
                parts.append(
                    f'      <li><a href="{safe_url}" target="_blank" rel="noopener">{escape(name)}</a></li>'
                )
            else:
                parts.append(f"      <li>{escape(name)}</li>")
        parts.append("    </ul>")
        parts.append("  </li>")

    parts.append("</ul>")
    parts.append("</div>")
    return "\n".join(parts)

def main():
    here = Path(__file__).resolve().parent
    csv_path = here / INPUT_NAME
    if not csv_path.exists():
        print(f"Cannot find {INPUT_NAME} in {here}", file=sys.stderr)
        sys.exit(1)

    by_tag = read_rows(csv_path)
    if not by_tag:
        print("No valid rows found (need NAME and TAG).", file=sys.stderr)
        sys.exit(1)

    html = build_html(by_tag)
    out_path = here / OUTPUT_NAME
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path.name} with {sum(len(v) for v in by_tag.values())} items across {len(by_tag)} tags.")

if __name__ == "__main__":
    main()
