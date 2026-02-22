#!/usr/bin/env python3
from __future__ import annotations
import csv
import sys
from collections import OrderedDict
from html import escape
from pathlib import Path

INPUT_NAME = "the_poppy_board_v7.csv"
OUTPUT_NAME = "tags_list.html"
CLUSTER_INFO_NAME = "cluster_table.csv"   # optional
DEFAULT_COLOR = "#ff1447"                 # poppy-red fallback

def find_col(header_row, candidates):
    if not header_row:
        return None
    normalized = {str(h or "").strip().lower(): h for h in header_row}
    for cand in candidates:
        key = cand.strip().lower()
        if key in normalized:
            return normalized[key]
        for k in normalized:
            if key and key in k:
                return normalized[k]
    return None

def normalize_hex(val: str) -> str:
    s = (val or "").strip()
    if not s:
        return ""
    if not s.startswith("#"):
        s = "#" + s
    return s

def read_cluster_info(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rdr = csv.DictReader(f)
        if not rdr.fieldnames:
            return {}
        name_col = find_col(rdr.fieldnames, ["name", "cluster", "universe"])
        color_col = find_col(rdr.fieldnames, ["hex code color", "hex", "color"])
        desc_col  = find_col(rdr.fieldnames, ["description", "desc", "blurb", "summary"])
        if not name_col:
            return {}
        out = {}
        for row in rdr:
            name = (row.get(name_col) or "").strip()
            if not name:
                continue
            color = normalize_hex((row.get(color_col) or "").strip()) if color_col else ""
            desc = (row.get(desc_col) or "").strip() if desc_col else ""
            out[name] = {"color": color, "desc": desc}
        return out

def read_rows(csv_path: Path):
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rdr = csv.DictReader(f)
        if not rdr.fieldnames:
            raise SystemExit("CSV has no header row.")

        name_col = find_col(rdr.fieldnames, ["name", "title", "label"])
        tag_col  = find_col(rdr.fieldnames, ["tag", "tags", "category", "cluster"])
        url_col  = find_col(rdr.fieldnames, ["content url", "url", "link", "href", "permalink"])
        chars_col = find_col(rdr.fieldnames, ["characters", "character", "cast", "who"])

        if not name_col or not tag_col:
            raise SystemExit("Need NAME and TAG/CLUSTER columns (case-insensitive).")

        by_cluster: OrderedDict[str, list[dict]] = OrderedDict()

        for row in rdr:
            raw_name = (row.get(name_col) or "").strip()
            raw_cluster = (row.get(tag_col) or "").strip()
            raw_url = (row.get(url_col) or "").strip() if url_col else ""
            raw_chars = (row.get(chars_col) or "").strip() if chars_col else ""

            if not raw_name or not raw_cluster:
                continue

            by_cluster.setdefault(raw_cluster, [])
            url = raw_url if raw_url else ""
            chars_list = [c.strip() for c in raw_chars.split(",") if c.strip()] if raw_chars else []
            by_cluster[raw_cluster].append({"name": raw_name, "url": url, "chars": chars_list})

        return by_cluster

def build_html(by_cluster, cluster_info):
    parts = []

    # Tumblr-safe wrapper note (optional)
    parts.append(
        '<div style="font-family: Arial, sans-serif; font-size:14px; line-height:1.45; color:#ffffff;">'
        '<div style="opacity:0.85; margin-bottom:14px;">'
        'Static TOC generated from the same CSV as the 3D map. '
        'If something looks wrong, blame the multiverse.'
        "</div>"
        "</div>"
    )

    for cluster, items in by_cluster.items():
        info = cluster_info.get(cluster, {})
        color = info.get("color") or DEFAULT_COLOR
        desc = info.get("desc") or ""

        # Cluster header
        parts.append(
            f'<div style="margin:22px 0 8px;">'
            f'<div style="font-family: Arial, sans-serif; font-size:20px; font-weight:800; letter-spacing:0.4px; color:{escape(color)};">'
            f'{escape(cluster)}</div>'
        )
        if desc:
            parts.append(
                f'<div style="font-family: Arial, sans-serif; font-size:13px; line-height:1.5; color:#d7d7df; '
                f'margin-top:6px; margin-bottom:10px; border-left:3px solid {escape(color)}; padding-left:10px;">'
                f'{escape(desc)}</div>'
            )
        parts.append('</div>')

        # Table with cluster-colored grid
        table_style = (
            f'width:100%; border-collapse:collapse; font-family: Arial, sans-serif; '
            f'font-size:13px; line-height:1.4; color:#ffffff; '
            f'border:1px solid {escape(color)};'
        )
        th_style = (
            f'padding:8px 10px; text-align:left; font-weight:800; '
            f'border-bottom:1px solid {escape(color)}; '
            f'color:#ffffff;'
        )
        td_style = (
            f'padding:7px 10px; vertical-align:top; '
            f'border-bottom:1px solid {escape(color)};'
        )
        name_style = 'font-weight:800;'
        chars_style = 'color:#bdbdc7;'
        link_style = f'color:{escape(color)}; font-weight:800; text-decoration:underline;'

        parts.append(f'<table style="{table_style}">')
        parts.append('<thead><tr>')
        parts.append(f'<th style="{th_style}">Name</th>')
        parts.append(f'<th style="{th_style}">Characters</th>')
        parts.append(f'<th style="{th_style}">Link</th>')
        parts.append('</tr></thead>')
        parts.append('<tbody>')

        for entry in items:
            name = escape(entry["name"])
            chars = entry["chars"]
            chars_txt = ", ".join(escape(c) for c in chars) if chars else "—"

            url = (entry["url"] or "").strip()
            if url:
                safe_url = escape(url, quote=True)
                link_cell = f'<a href="{safe_url}" target="_blank" rel="noopener" style="{link_style}">READ MORE</a>'
            else:
                link_cell = f'<span style="opacity:0.65;">—</span>'

            parts.append('<tr>')
            parts.append(f'<td style="{td_style} {name_style}">{name}</td>')
            parts.append(f'<td style="{td_style} {chars_style}">{chars_txt}</td>')
            parts.append(f'<td style="{td_style}">{link_cell}</td>')
            parts.append('</tr>')

        parts.append('</tbody></table>')

        # small spacer between clusters
        parts.append('<div style="height:12px;"></div>')

    return "\n".join(parts)

def main():
    here = Path(__file__).resolve().parent

    csv_path = here / INPUT_NAME
    if not csv_path.exists():
        print(f"Cannot find {INPUT_NAME} in {here}", file=sys.stderr)
        sys.exit(1)

    by_cluster = read_rows(csv_path)
    if not by_cluster:
        print("No valid rows found.", file=sys.stderr)
        sys.exit(1)

    cluster_info = read_cluster_info(here / CLUSTER_INFO_NAME)

    html = build_html(by_cluster, cluster_info)
    out_path = here / OUTPUT_NAME
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path.name}: {sum(len(v) for v in by_cluster.values())} items, {len(by_cluster)} clusters.")

if __name__ == "__main__":
    main()