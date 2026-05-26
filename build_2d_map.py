#!/usr/bin/env python3
"""
build_cluster_dashboard.py

Generate a static Poppyverse cluster dashboard from two source-of-truth CSV files:

- SRC_clusters.csv  : cluster tiles / descriptions / colors / optional covers
- SRC_toc.csv       : table-of-contents entries shown in the click-open side panel

Output:
- poppy_cluster_dashboard.html

Expected page:
- Main page = grid of 300px x 200px cluster rectangles.
- One rectangle per row in SRC_clusters.csv.
- Each rectangle shows the cluster name and entry count.
- If the cluster row has a Cover URL, the image is used as the card background
  with the cluster hex color overlaid.
- Otherwise, the card is a solid colored rectangle.
- Clicking a cluster opens a right-side panel.
- The panel shows the cluster description at top.
- Below that, it shows a table of matching SRC_toc.csv rows.
- Cover image columns from SRC_toc.csv are ignored in the panel table.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_CLUSTERS_CSV = "SRC_clusters.csv"
DEFAULT_TOC_CSV = "SRC_toc.csv"
DEFAULT_OUTPUT_HTML = "2d_map.html"

# Columns from SRC_toc.csv that should never appear in the drawer table.
IGNORED_TOC_COLUMNS = {
    "cover",
    "cover url",
    "cover_url",
    "image",
    "image url",
    "image_url",
    "thumbnail",
    "thumbnail url",
    "thumbnail_url",
}


TUMBLR_ARCHIVE_URL = "https://inpoppyfields.tumblr.com/"
TWO_D_MAP_HREF = "2d_map.html"
THREE_D_MAP_HREF = "3d_map.html"


def common_nav_css() -> str:
    return """
    .poppy-nav {
      position: fixed;
      top: 14px;
      left: 50%;
      transform: translateX(-50%);
      z-index: 100;
      display: flex;
      gap: 8px;
      align-items: center;
      padding: 7px;
      border: 1px solid rgba(255, 255, 255, 0.18);
      border-radius: 999px;
      background: rgba(8, 8, 14, 0.66);
      box-shadow: 0 16px 42px rgba(0,0,0,.32), 0 0 22px rgba(255,20,71,.10);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
    }

    .poppy-nav a {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 34px;
      padding: 0 13px;
      border-radius: 999px;
      color: rgba(255,255,255,.82);
      text-decoration: none;
      font-size: 12px;
      font-weight: 850;
      letter-spacing: .35px;
      border: 1px solid transparent;
      transition: background .16s ease, border-color .16s ease, color .16s ease, box-shadow .16s ease;
      white-space: nowrap;
    }

    .poppy-nav a:hover {
      color: #fff;
      background: rgba(255,255,255,.08);
      border-color: rgba(255,255,255,.18);
    }

    .poppy-nav a.active {
      color: #fff;
      background: var(--poppy-red, #ff1447);
      border-color: color-mix(in srgb, var(--poppy-red, #ff1447) 72%, white);
      box-shadow: 0 0 18px color-mix(in srgb, var(--poppy-red, #ff1447) 44%, transparent);
    }

    @media (max-width: 560px) {
      .poppy-nav {
        top: 10px;
        width: calc(100vw - 20px);
        justify-content: center;
        overflow-x: auto;
        border-radius: 18px;
      }

      .poppy-nav a {
        padding: 0 10px;
        font-size: 11px;
      }
    }
    """


def common_nav_html(active: str) -> str:
    two_d_class = ' class="active" aria-current="page"' if active == "2d" else ""
    three_d_class = ' class="active" aria-current="page"' if active == "3d" else ""
    return (
        '<nav class="poppy-nav" aria-label="Poppyverse map navigation">\n'
        f'    <a href="{TWO_D_MAP_HREF}"{two_d_class}>2D Map</a>\n'
        f'    <a href="{THREE_D_MAP_HREF}"{three_d_class}>3D Map</a>\n'
        f'    <a href="{TUMBLR_ARCHIVE_URL}" target="_blank" rel="noopener">Tumblr Archive</a>\n'
        '  </nav>'
    )

def normalize_header(value: str | None) -> str:
    """Normalize CSV headers, including accidental BOMs."""
    return (value or "").replace("\ufeff", "").strip()


def normalize_key(value: str | None) -> str:
    """Normalize for fuzzy column lookup."""
    return re.sub(r"[\s_\-]+", " ", normalize_header(value).lower()).strip()


def clean_cell(value: Any) -> str:
    """Clean CSV cell text while preserving intentional newlines."""
    if value is None:
        return ""

    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def normalize_hex(value: str | None, fallback: str = "#555555") -> str:
    """Return a valid #rrggbb hex color."""
    text = clean_cell(value)
    if not text:
        return fallback

    if not text.startswith("#"):
        text = f"#{text}"

    if re.fullmatch(r"#[0-9a-fA-F]{3}", text):
        text = "#" + "".join(ch * 2 for ch in text[1:])

    if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
        return text.lower()

    return fallback


def find_column(fieldnames: list[str], candidates: list[str]) -> str | None:
    """
    Find a column by normalized exact match first, then by loose containment.
    Keeps the original CSV header spelling when returning the match.
    """
    normalized_to_original = {normalize_key(name): name for name in fieldnames}

    for candidate in candidates:
        key = normalize_key(candidate)
        if key in normalized_to_original:
            return normalized_to_original[key]

    for candidate in candidates:
        key = normalize_key(candidate)
        if not key:
            continue
        for existing_key, original in normalized_to_original.items():
            if key in existing_key or existing_key in key:
                return original

    return None


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read a CSV as a list of cleaned dictionaries."""
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"{path.name} does not appear to have a header row.")

        fieldnames = [normalize_header(name) for name in reader.fieldnames]
        rows: list[dict[str, str]] = []

        for raw_row in reader:
            row: dict[str, str] = {}
            for raw_name, raw_value in raw_row.items():
                if raw_name is None:
                    # Extra unheaded CSV cells. Ignore them.
                    continue
                row[normalize_header(raw_name)] = clean_cell(raw_value)
            rows.append(row)

    return fieldnames, rows


def load_clusters(path: Path) -> list[dict[str, str]]:
    """Load cluster metadata from SRC_clusters.csv."""
    fieldnames, rows = read_csv(path)

    name_col = find_column(fieldnames, ["Name", "Cluster", "Cluster Name"])
    cover_col = find_column(fieldnames, ["Cover URL", "Cover_URL", "Cover", "Image URL", "Image"])
    desc_col = find_column(fieldnames, ["Description", "Desc", "Blurb"])
    color_col = find_column(fieldnames, ["Hex Code Color", "Hex", "Color", "Colour"])

    if not name_col:
        raise ValueError(f"{path.name} needs a cluster name column, such as 'Name'.")
    if not color_col:
        print(f"Warning: {path.name} has no color column; using fallback colors.", file=sys.stderr)

    clusters: list[dict[str, str]] = []
    seen_names: set[str] = set()

    for row_number, row in enumerate(rows, start=2):
        name = row.get(name_col, "").strip()
        if not name:
            continue

        if name in seen_names:
            print(f"Warning: duplicate cluster skipped on row {row_number}: {name}", file=sys.stderr)
            continue

        seen_names.add(name)
        clusters.append(
            {
                "name": name,
                "cover_url": row.get(cover_col, "") if cover_col else "",
                "description": row.get(desc_col, "") if desc_col else "",
                "color": normalize_hex(row.get(color_col, "") if color_col else ""),
            }
        )

    if not clusters:
        raise ValueError(f"{path.name} did not contain any usable cluster rows.")

    return clusters


def load_toc(path: Path) -> tuple[str, list[str], list[dict[str, str]]]:
    """Load TOC rows from SRC_toc.csv and resolve the cluster column."""
    fieldnames, rows = read_csv(path)

    cluster_col = find_column(fieldnames, ["Cluster", "Category", "Group"])
    if not cluster_col:
        raise ValueError(f"{path.name} needs a 'Cluster' column.")

    table_columns = [
        col
        for col in fieldnames
        if normalize_key(col) not in IGNORED_TOC_COLUMNS
    ]

    usable_rows = [row for row in rows if row.get(cluster_col, "").strip()]

    return cluster_col, table_columns, usable_rows


def group_rows_by_cluster(rows: list[dict[str, str]], cluster_col: str) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        cluster_name = row.get(cluster_col, "").strip()
        if cluster_name:
            grouped.setdefault(cluster_name, []).append(row)
    return grouped


def make_safe_json_script_payload(value: Any) -> str:
    """
    Safely embed JSON inside a script tag.

    Do not html.escape() the JSON; that produces &quot; and breaks JSON.parse()
    inside script text. Escaping closing script tags and risky line separators is enough.
    """
    text = json.dumps(value, ensure_ascii=False)
    return (
        text
        .replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def build_payload(
    clusters: list[dict[str, str]],
    toc_columns: list[str],
    toc_rows: list[dict[str, str]],
    toc_cluster_col: str,
) -> dict[str, Any]:
    grouped = group_rows_by_cluster(toc_rows, toc_cluster_col)

    cluster_payload: list[dict[str, Any]] = []
    for cluster in clusters:
        rows = grouped.get(cluster["name"], [])
        cluster_payload.append(
            {
                **cluster,
                "count": len(rows),
                "rows": rows,
            }
        )

    return {
        "clusters": cluster_payload,
        "columns": toc_columns,
    }


def build_html(payload: dict[str, Any]) -> str:
    payload_json = make_safe_json_script_payload(payload)
    nav_css = common_nav_css()
    nav_html = common_nav_html("2d")

    return fr'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Poppyverse Cluster Dashboard</title>
  <style>
    :root {{
      --poppy-red: #ff1447;
      --bg: #0d0d10;
      --panel: #17171d;
      --panel-2: #21212b;
      --text: #f7f1ee;
      --muted: rgba(247, 241, 238, 0.68);
      --line: rgba(255, 255, 255, 0.14);
      --shadow: rgba(0, 0, 0, 0.42);
      --drawer-width: min(820px, 90vw);
    }}

    * {{
      box-sizing: border-box;
    }}

{nav_css}

    body {{
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at 8% 0%, rgba(255, 20, 71, 0.16), transparent 32rem),
        radial-gradient(circle at 90% 95%, rgba(94, 23, 235, 0.15), transparent 34rem),
        var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}

    .page {{
      width: min(1440px, calc(100vw - 48px));
      margin: 0 auto;
      padding: 88px 0 72px;
    }}

    header {{
      margin-bottom: 28px;
    }}

    h1 {{
      margin: 0 0 10px;
      font-size: clamp(2.25rem, 4.2vw, 4.8rem);
      line-height: 0.92;
      letter-spacing: -0.07em;
    }}

    .subtitle {{
      max-width: 760px;
      margin: 0;
      color: var(--muted);
      font-size: 1rem;
      line-height: 1.55;
    }}

    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, 300px);
      gap: 18px;
      align-items: start;
    }}

    .cluster-card {{
      position: relative;
      width: 300px;
      height: 200px;
      border: 1px solid var(--line);
      border-radius: 22px;
      overflow: hidden;
      cursor: pointer;
      padding: 18px;
      color: white;
      background-color: var(--cluster-color);
      box-shadow: 0 18px 44px var(--shadow);
      text-align: left;
      isolation: isolate;
      transition: transform 160ms ease, filter 160ms ease, border-color 160ms ease;
    }}

    .cluster-card:hover,
    .cluster-card:focus-visible {{
      transform: translateY(-4px);
      filter: brightness(1.08) saturate(1.08);
      border-color: rgba(255, 255, 255, 0.36);
      outline: none;
    }}

    .cluster-card.has-cover {{
      background-image: var(--cover-url);
      background-size: cover;
      background-position: center;
    }}

    .cluster-card::before {{
      content: "";
      position: absolute;
      inset: 0;
      background: var(--cluster-color);
      opacity: var(--overlay-opacity, 0.94);
      z-index: -2;
    }}

    .cluster-card::after {{
      content: "";
      position: absolute;
      inset: 0;
      background:
        linear-gradient(135deg, rgba(255,255,255,0.18), transparent 38%, rgba(0,0,0,0.38)),
        radial-gradient(circle at 70% 15%, rgba(255,255,255,0.22), transparent 16rem);
      z-index: -1;
    }}

    .cluster-count {{
      display: inline-flex;
      align-items: center;
      border: 1px solid rgba(255, 255, 255, 0.30);
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 0.75rem;
      font-weight: 850;
      letter-spacing: 0.045em;
      text-transform: uppercase;
      background: rgba(0, 0, 0, 0.18);
      backdrop-filter: blur(8px);
      text-shadow: 0 1px 10px rgba(0,0,0,0.35);
    }}

    .cluster-name {{
      position: absolute;
      left: 18px;
      right: 18px;
      bottom: 17px;
      margin: 0;
      font-size: 1.55rem;
      line-height: 1.02;
      font-weight: 950;
      letter-spacing: -0.048em;
      text-shadow: 0 2px 20px rgba(0,0,0,0.52);
    }}

    .backdrop {{
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.52);
      opacity: 0;
      pointer-events: none;
      transition: opacity 180ms ease;
      z-index: 20;
    }}

    .backdrop.open {{
      opacity: 1;
      pointer-events: auto;
    }}

    .drawer {{
      position: fixed;
      top: 0;
      right: 0;
      width: var(--drawer-width);
      height: 100vh;
      background: linear-gradient(180deg, var(--panel), #101015);
      border-left: 1px solid var(--line);
      box-shadow: -28px 0 70px rgba(0,0,0,0.55);
      transform: translateX(104%);
      transition: transform 220ms ease;
      z-index: 30;
      display: flex;
      flex-direction: column;
    }}

    .drawer.open {{
      transform: translateX(0);
    }}

    .drawer-top {{
      padding: 24px 24px 18px;
      border-bottom: 1px solid var(--line);
      background:
        linear-gradient(135deg, var(--active-color, #444), rgba(255,255,255,0.035) 62%),
        var(--panel);
    }}

    .drawer-kicker {{
      margin: 0 0 8px;
      color: rgba(255,255,255,0.75);
      font-size: 0.78rem;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }}

    .drawer-title-row {{
      display: flex;
      gap: 16px;
      justify-content: space-between;
      align-items: flex-start;
    }}

    .drawer-title {{
      margin: 0;
      font-size: clamp(1.8rem, 3vw, 3.2rem);
      line-height: 0.96;
      letter-spacing: -0.065em;
    }}

    .close-button {{
      appearance: none;
      border: 1px solid rgba(255,255,255,0.28);
      background: rgba(0,0,0,0.2);
      color: white;
      border-radius: 999px;
      width: 40px;
      height: 40px;
      cursor: pointer;
      font-size: 1.35rem;
      line-height: 1;
      flex: 0 0 auto;
    }}

    .close-button:hover {{
      background: rgba(255,255,255,0.13);
    }}

    .drawer-desc {{
      margin: 14px 0 0;
      color: rgba(255,255,255,0.84);
      line-height: 1.55;
      white-space: pre-wrap;
      max-width: 68ch;
    }}

    .table-wrap {{
      overflow: auto;
      padding: 18px 24px 30px;
      flex: 1;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 1040px;
      font-size: 0.9rem;
    }}

    th,
    td {{
      border-bottom: 1px solid rgba(255,255,255,0.1);
      padding: 10px 12px;
      vertical-align: top;
      text-align: left;
    }}

    th {{
      position: sticky;
      top: 0;
      z-index: 1;
      background: var(--panel-2);
      color: rgba(255,255,255,0.92);
      font-size: 0.76rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      white-space: nowrap;
    }}

    td {{
      color: rgba(255,255,255,0.78);
      line-height: 1.45;
      white-space: pre-wrap;
    }}

    tr:hover td {{
      background: rgba(255,255,255,0.045);
    }}

    a {{
      color: #fff;
      font-weight: 850;
    }}

    .empty-state {{
      margin: 0;
      color: var(--muted);
      padding: 22px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255,255,255,0.04);
    }}

    @media (max-width: 720px) {{
      .page {{
        width: min(100vw - 28px, 360px);
        padding-top: 28px;
      }}

      .grid {{
        grid-template-columns: 1fr;
      }}

      .cluster-card {{
        width: 100%;
      }}

      .drawer {{
        width: 100vw;
      }}

      .drawer-top {{
        padding: 20px 18px 16px;
      }}

      .table-wrap {{
        padding: 16px 18px 28px;
      }}
    }}
  </style>
</head>
<body>
  {nav_html}
  <main class="page">
    <header>
      <h1>Poppyverse Clusters</h1>
      <p class="subtitle">A cluster-first control board. Click a rectangle to open the side panel and inspect the matching source-of-truth rows.</p>
    </header>

    <section id="clusterGrid" class="grid" aria-label="Poppyverse cluster grid"></section>
  </main>

  <div id="backdrop" class="backdrop" aria-hidden="true"></div>

  <aside id="drawer" class="drawer" aria-hidden="true" aria-label="Cluster contents panel">
    <div id="drawerTop" class="drawer-top">
      <p id="drawerKicker" class="drawer-kicker">Cluster</p>
      <div class="drawer-title-row">
        <h2 id="drawerTitle" class="drawer-title"></h2>
        <button id="closeButton" class="close-button" type="button" aria-label="Close panel">×</button>
      </div>
      <p id="drawerDesc" class="drawer-desc"></p>
    </div>
    <div id="tableWrap" class="table-wrap"></div>
  </aside>

  <script id="dashboard-data" type="application/json">{payload_json}</script>
  <script>
    const data = JSON.parse(document.getElementById('dashboard-data').textContent);

    const grid = document.getElementById('clusterGrid');
    const drawer = document.getElementById('drawer');
    const backdrop = document.getElementById('backdrop');
    const drawerTop = document.getElementById('drawerTop');
    const drawerKicker = document.getElementById('drawerKicker');
    const drawerTitle = document.getElementById('drawerTitle');
    const drawerDesc = document.getElementById('drawerDesc');
    const tableWrap = document.getElementById('tableWrap');
    const closeButton = document.getElementById('closeButton');

    function escapeHtml(value) {{
      return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
    }}

    function cssUrl(value) {{
      return `url("${{String(value).replaceAll('"', '%22')}}")`;
    }}

    function linkifyCell(column, value) {{
      const text = String(value ?? '').trim();
      if (!text) {{
        return '<span style="opacity:0.45">—</span>';
      }}

      const isUrlColumn = /url|link|href/i.test(column);
      if (isUrlColumn && /^https?:\/\//i.test(text)) {{
        const safe = escapeHtml(text);
        return `<a href="${{safe}}" target="_blank" rel="noopener noreferrer">open</a>`;
      }}

      return escapeHtml(text);
    }}

    function renderGrid() {{
      grid.innerHTML = '';

      data.clusters.forEach((cluster, index) => {{
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'cluster-card' + (cluster.cover_url ? ' has-cover' : '');
        button.style.setProperty('--cluster-color', cluster.color || '#555555');
        button.style.setProperty('--overlay-opacity', cluster.cover_url ? '0.74' : '0.96');

        if (cluster.cover_url) {{
          button.style.setProperty('--cover-url', cssUrl(cluster.cover_url));
        }}

        button.innerHTML = `
          <span class="cluster-count">${{cluster.count}} entr${{cluster.count === 1 ? 'y' : 'ies'}}</span>
          <h2 class="cluster-name">${{escapeHtml(cluster.name)}}</h2>
        `;

        button.addEventListener('click', () => openDrawer(index));
        grid.appendChild(button);
      }});
    }}

    function renderTable(cluster) {{
      const rows = cluster.rows || [];
      const columns = data.columns || [];

      if (!rows.length) {{
        tableWrap.innerHTML = '<p class="empty-state">No TOC entries found for this cluster.</p>';
        return;
      }}

      const thead = columns.map(col => `<th>${{escapeHtml(col)}}</th>`).join('');
      const tbody = rows.map(row => {{
        const cells = columns.map(col => `<td>${{linkifyCell(col, row[col])}}</td>`).join('');
        return `<tr>${{cells}}</tr>`;
      }}).join('');

      tableWrap.innerHTML = `
        <table>
          <thead><tr>${{thead}}</tr></thead>
          <tbody>${{tbody}}</tbody>
        </table>
      `;
    }}

    function openDrawer(index) {{
      const cluster = data.clusters[index];

      drawerTop.style.setProperty('--active-color', cluster.color || '#555555');
      drawerKicker.textContent = `${{cluster.count}} TOC entr${{cluster.count === 1 ? 'y' : 'ies'}}`;
      drawerTitle.textContent = cluster.name;
      drawerDesc.textContent = cluster.description || 'No cluster description provided. The void declined to comment.';

      renderTable(cluster);

      drawer.classList.add('open');
      backdrop.classList.add('open');
      drawer.setAttribute('aria-hidden', 'false');
      backdrop.setAttribute('aria-hidden', 'false');
      closeButton.focus();
    }}

    function closeDrawer() {{
      drawer.classList.remove('open');
      backdrop.classList.remove('open');
      drawer.setAttribute('aria-hidden', 'true');
      backdrop.setAttribute('aria-hidden', 'true');
    }}

    closeButton.addEventListener('click', closeDrawer);
    backdrop.addEventListener('click', closeDrawer);

    window.addEventListener('keydown', event => {{
      if (event.key === 'Escape') {{
        closeDrawer();
      }}
    }});

    renderGrid();
  </script>
</body>
</html>
'''


def warn_about_cluster_mismatches(
    clusters: list[dict[str, str]],
    toc_rows: list[dict[str, str]],
    toc_cluster_col: str,
) -> None:
    cluster_names = {cluster["name"] for cluster in clusters}
    toc_cluster_names = {
        row.get(toc_cluster_col, "").strip()
        for row in toc_rows
        if row.get(toc_cluster_col, "").strip()
    }

    orphan_toc_clusters = sorted(toc_cluster_names - cluster_names)
    empty_clusters = sorted(cluster_names - toc_cluster_names)

    if orphan_toc_clusters:
        print("Warning: SRC_toc.csv references clusters missing from SRC_clusters.csv:", file=sys.stderr)
        for name in orphan_toc_clusters:
            print(f"  - {name}", file=sys.stderr)

    if empty_clusters:
        print("Warning: SRC_clusters.csv contains clusters with no SRC_toc.csv rows:", file=sys.stderr)
        for name in empty_clusters:
            print(f"  - {name}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the static Poppyverse cluster dashboard HTML.")
    parser.add_argument("--clusters", default=DEFAULT_CLUSTERS_CSV, help=f"Cluster CSV path. Default: {DEFAULT_CLUSTERS_CSV}")
    parser.add_argument("--toc", default=DEFAULT_TOC_CSV, help=f"TOC CSV path. Default: {DEFAULT_TOC_CSV}")
    parser.add_argument("--out", default=DEFAULT_OUTPUT_HTML, help=f"Output HTML path. Default: {DEFAULT_OUTPUT_HTML}")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    script_dir = Path(__file__).resolve().parent
    clusters_path = Path(args.clusters)
    toc_path = Path(args.toc)
    output_path = Path(args.out)

    if not clusters_path.is_absolute():
        clusters_path = script_dir / clusters_path
    if not toc_path.is_absolute():
        toc_path = script_dir / toc_path
    if not output_path.is_absolute():
        output_path = script_dir / output_path

    clusters = load_clusters(clusters_path)
    toc_cluster_col, toc_columns, toc_rows = load_toc(toc_path)

    payload = build_payload(
        clusters=clusters,
        toc_columns=toc_columns,
        toc_rows=toc_rows,
        toc_cluster_col=toc_cluster_col,
    )

    html = build_html(payload)
    output_path.write_text(html, encoding="utf-8")

    warn_about_cluster_mismatches(clusters, toc_rows, toc_cluster_col)

    print(f"Wrote {output_path}")
    print(f"Clusters: {len(clusters)}")
    print(f"TOC rows: {len(toc_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
