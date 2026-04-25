#!/usr/bin/env python3
# build_html_toc.py
#
# Reads `table.csv` in the same folder and outputs `tags_list.html`
# with a plain HTML table-of-contents: one table per cluster, rows show
# Name, Universe Description, Characters, and Link (if present).

from __future__ import annotations
import csv
import sys
import re
import hashlib
from collections import OrderedDict
from html import escape

CLUSTER_META_NAME = "cluster_table.csv"

def normalize_hex(s: str) -> str | None:
    s = (s or "").strip()
    if not s:
        return None
    if not s.startswith("#"):
        s = "#" + s
    if len(s) == 4:  # #abc -> #aabbcc
        s = "#" + "".join(ch*2 for ch in s[1:])
    if re.fullmatch(r"#[0-9a-fA-F]{6}", s):
        return s.lower()
    return None

def rel_luminance(hex_color: str) -> float:
    # WCAG relative luminance for sRGB
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    def to_lin(u: float) -> float:
        return u/12.92 if u <= 0.04045 else ((u+0.055)/1.055) ** 2.4
    r, g, b = to_lin(r), to_lin(g), to_lin(b)
    return 0.2126*r + 0.7152*g + 0.0722*b

def best_text_color(bg_hex: str) -> str:
    # return black on light backgrounds, else white
    return "#000" if rel_luminance(bg_hex) > 0.55 else "#fff"

def blend_hex(a: str, b: str, t: float) -> str:
    """Blend hex colors a->b by fraction t in [0,1]."""
    a = a.lstrip('#'); b = b.lstrip('#')
    ar, ag, ab = int(a[0:2],16), int(a[2:4],16), int(a[4:6],16)
    br, bg, bb = int(b[0:2],16), int(b[2:4],16), int(b[4:6],16)
    rr = round(ar + (br - ar) * t)
    rg = round(ag + (bg - ag) * t)
    rb = round(ab + (bb - ab) * t)
    return f"#{rr:02x}{rg:02x}{rb:02x}"

def hash_color(name: str) -> str:
    # deterministic fallback if cluster_table.csv missing
    h = hashlib.md5(name.encode("utf-8")).hexdigest()
    # keep it dark-ish so white text works
    r = int(h[0:2], 16) // 2
    g = int(h[2:4], 16) // 2
    b = int(h[4:6], 16) // 2
    return f"#{r:02x}{g:02x}{b:02x}"

def load_cluster_meta(here: Path) -> dict[str, dict[str, str]]:
    """Load cluster_table.csv if present. Expected columns: name/cluster, hex code color/color, description."""
    meta: dict[str, dict[str, str]] = {}
    p = here / CLUSTER_META_NAME
    if not p.exists():
        return meta
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        rdr = csv.DictReader(f)
        if not rdr.fieldnames:
            return meta
        name_col = find_col(rdr.fieldnames, ["name", "cluster", "universe"])
        color_col = find_col(rdr.fieldnames, ["hex code color", "hex", "color", "colour"])
        desc_col = find_col(rdr.fieldnames, ["description", "desc", "blurb"])
        for row in rdr:
            name = (row.get(name_col) or "").strip() if name_col else ""
            if not name:
                continue
            color = normalize_hex((row.get(color_col) or "").strip()) if color_col else None
            desc = (row.get(desc_col) or "").strip() if desc_col else ""
            meta[name] = {}
            if color:
                meta[name]["color"] = color
            if desc:
                meta[name]["desc"] = desc
    return meta

from pathlib import Path

INPUT_NAME = "the_poppy_board.csv"
OUTPUT_NAME = "toc.html"

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
        uni_desc_col = find_col(rdr.fieldnames, ["description", "desc", "universe description", "universe desc", "cluster description"])

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
            raw_uni_desc = (row.get(uni_desc_col) or "").strip() if uni_desc_col else ""

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
                {"name": raw_name, "url": url, "uni_desc": (raw_uni_desc if raw_uni_desc else None), "chars": chars_list}
            )

        return by_cluster

def build_html(by_cluster: OrderedDict[str, list[dict[str, str | list[str] | None]]], cluster_meta: dict[str, dict[str, str]]) -> str:
    # Minimal HTML: one table per cluster with Name, Characters, Link
    parts: list[str] = []
    parts.append('<h2>We try to keep this static story map in sync with the <a href="https://programminginpoppyfields.github.io/poppyverse-interactive-map/index.html">chaotic 3D one.</a> Emphasis on try. Reality is subjective and version control is a myth.</h2>')
    parts.append("<h1>Table of Contents</h1>")

    for cluster, items in by_cluster.items():
        meta = cluster_meta.get(cluster, {})
        bg = meta.get("color") or hash_color(cluster)
        fg = best_text_color(bg)
        # softer secondary text
        if fg == "#fff":
            fg2 = "rgba(255,255,255,0.78)"
            fg3 = "rgba(255,255,255,0.62)"
            border = "rgba(255,255,255,0.20)"
            link = "rgba(255,255,255,0.92)"
        else:
            fg2 = "rgba(0,0,0,0.78)"
            fg3 = "rgba(0,0,0,0.62)"
            border = "rgba(0,0,0,0.22)"
            link = "rgba(0,0,0,0.92)"


        # Alternating row stripes (Tumblr-safe inline styles)
        # Slightly lift/dim the cluster background for readability.
        if rel_luminance(bg) > 0.55:
            row_bg_a = blend_hex(bg, "#000000", 0.06)
            row_bg_b = blend_hex(bg, "#000000", 0.12)
        else:
            row_bg_a = blend_hex(bg, "#ffffff", 0.06)
            row_bg_b = blend_hex(bg, "#ffffff", 0.12)
        # Universe description (prefer cluster_table.csv description; fallback to first row Description)
        section_desc = (meta.get("desc") or "")
        if not section_desc:
            for it in items:
                d = (it.get("uni_desc") or "")
                if d:
                    section_desc = str(d)
                    break

        parts.append(f'<h2 style="margin:22px 0 6px; color:{bg}; font-weight:900;">{escape(cluster)}</h2>')
        if section_desc:
            parts.append(f'<div style="margin:0 0 10px; padding:10px 12px; border:1px solid {border}; background:rgba(0,0,0,0.18); color:{fg2}; border-radius:10px;">{escape(section_desc)}</div>')

        parts.append(f'<table border="0" cellspacing="0" cellpadding="6" style="border-collapse:collapse; width:100%; background:{bg}; color:{fg}; border-radius:12px; overflow:hidden; border:1px solid {border};">')
        parts.append(f'<thead><tr><th style="padding:10px 12px; text-align:left; color:{fg}; border-bottom:1px solid {border};">Name</th><th style="padding:10px 12px; text-align:left; color:{fg}; border-bottom:1px solid {border};">Universe</th><th style="padding:10px 12px; text-align:left; color:{fg}; border-bottom:1px solid {border};">Characters</th><th style="padding:10px 12px; text-align:left; color:{fg}; border-bottom:1px solid {border};">Link</th></tr></thead>')
        parts.append("<tbody>")
        for ridx, entry in enumerate(items):
            name = escape(entry["name"])  # type: ignore[index]
            chars = entry["chars"] or []  # type: ignore[index]
            chars_txt = ", ".join(escape(c) for c in chars) if chars else "—"
            url = entry["url"]  # type: ignore[index]
            if url:
                safe_url = escape(url, quote=True)
                link_cell = f'<a href="{safe_url}" target="_blank" rel="noopener" style="color:{link}; font-weight:800; text-decoration:underline;">Content available</a>'
            else:
                link_cell = f'<span style="color:{fg3};">—</span>'
            parts.append(
                f"<tr style=\"border-bottom:1px solid {border}; background:{row_bg_a if (ridx % 2 == 0) else row_bg_b};\">"
                f'<td style="padding:8px 12px; font-weight:800; color:{fg};">{name}</td>'
                f'<td style="padding:8px 12px; font-weight:500; color:{fg3};">{escape((entry.get("uni_desc") or "—"))}</td>'
                f'<td style="padding:8px 12px; font-weight:500; color:{fg2};">{chars_txt}</td>'
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

    cluster_meta = load_cluster_meta(here)
    html = build_html(by_cluster, cluster_meta)
    out_path = here / OUTPUT_NAME
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path.name} with {sum(len(v) for v in by_cluster.values())} items across {len(by_cluster)} clusters.")

if __name__ == "__main__":
    main()
