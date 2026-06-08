#!/usr/bin/env python3
"""
Build the 2D Poppyverse map.

Source files:
- SRC_clusters.csv
- SRC_toc.csv

Output:
- 2d_map.html

2D drawer table intentionally shows only:
- Name
- Sub-parts
- Description
- Characters
- Content URL

It intentionally excludes:
- ID
- Cluster
- Sub-cluster
- Size
- Collisions
- (X) Relativity
- (Y) Relatability
- (Z) Depth
"""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parent

CLUSTERS_CSV = ROOT / "SRC_clusters.csv"
TOC_CSV = ROOT / "SRC_toc.csv"
OUTPUT_HTML = ROOT / "2d_map.html"

POPPY_PINK = "#FF1447"
TUMBLR_ARCHIVE_URL = "https://inpoppyfields.tumblr.com/"

VISIBLE_TOC_COLUMNS = [
    "Name",
    "Sub-parts",
    "Description",
    "Characters",
    "Content URL",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path.name}")

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows: list[dict[str, str]] = []

        for raw_row in reader:
            clean_row: dict[str, str] = {}
            for key, value in raw_row.items():
                if key is None:
                    continue
                clean_key = str(key).strip()
                clean_value = "" if value is None else str(value).strip()
                clean_row[clean_key] = clean_value
            rows.append(clean_row)

    return rows


def normalize_key(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace("\ufeff", "")
        .replace("_", " ")
        .replace("-", " ")
    )


def get_first(row: dict[str, str], candidates: list[str], default: str = "") -> str:
    normalized = {normalize_key(k): k for k in row.keys()}

    for candidate in candidates:
        real_key = normalized.get(normalize_key(candidate))
        if real_key is not None:
            return row.get(real_key, default).strip()

    return default


def clean_hex_color(value: str, fallback: str = POPPY_PINK) -> str:
    value = (value or "").strip()
    if not value:
        return fallback

    if not value.startswith("#"):
        value = "#" + value

    if len(value) not in (4, 7):
        return fallback

    return value


def normalize_url(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""

    if not value.lower().startswith(("http://", "https://")):
        return ""

    try:
        parts = urlsplit(value)
        path = quote(parts.path, safe="/:%")
        query = quote(parts.query, safe="=&?/%:+,#[]@!$'()*;")
        fragment = quote(parts.fragment, safe="")
        return urlunsplit((parts.scheme, parts.netloc, path, query, fragment))
    except Exception:
        return value


def make_nav(active: str) -> str:
    items = [
        ("Home", "index.html", "home"),
        ("About", "about.html", "about"),
        ("2D Map", "2d_map.html", "2d"),
        ("3D Map", "3d_map.html", "3d"),
        ("Tumblr Archive", TUMBLR_ARCHIVE_URL, "archive"),
    ]

    links: list[str] = []
    for label, href, key in items:
        active_class = " active" if key == active else ""
        external_attrs = ""
        if href.startswith("http"):
            external_attrs = ' target="_blank" rel="noopener"'

        links.append(
            f'<a class="top-nav-link{active_class}" href="{html.escape(href, quote=True)}"{external_attrs}>'
            f"{html.escape(label)}"
            f"</a>"
        )

    return f"""
<nav class="top-nav" aria-label="Main navigation">
  <div class="top-nav-inner">
    {"".join(links)}
  </div>
</nav>
""".strip()


def favicon_html() -> str:
    return """
<link rel="icon" href='data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><text y="50%" x="50%" dominant-baseline="middle" text-anchor="middle" font-size="52">🌷</text></svg>'>
""".strip()


def build_data() -> dict[str, Any]:
    cluster_rows = read_csv(CLUSTERS_CSV)
    toc_rows = read_csv(TOC_CSV)

    clusters: list[dict[str, Any]] = []

    for idx, row in enumerate(cluster_rows):
        name = get_first(row, ["Name", "Cluster", "Cluster Name"])
        if not name:
            continue

        color = clean_hex_color(
            get_first(row, ["Hex Code Color", "Hex Color", "Color", "Hex"])
        )

        description = get_first(row, ["Description", "Desc"])
        cover_url = normalize_url(get_first(row, ["Cover URL", "Cover", "Image URL", "Image"]))

        clusters.append(
            {
                "name": name,
                "color": color,
                "description": description,
                "coverUrl": cover_url,
                "order": idx,
            }
        )

    cluster_names = {cluster["name"] for cluster in clusters}

    entries_by_cluster: dict[str, list[dict[str, str]]] = {
        cluster["name"]: [] for cluster in clusters
    }

    for row in toc_rows:
        cluster = get_first(row, ["Cluster", "Tags"])
        if not cluster or cluster not in cluster_names:
            continue

        visible_row: dict[str, str] = {}

        for col in VISIBLE_TOC_COLUMNS:
            value = get_first(row, [col])
            if col == "Content URL":
                value = normalize_url(value)
            visible_row[col] = value

        if not visible_row.get("Name"):
            continue

        entries_by_cluster.setdefault(cluster, []).append(visible_row)

    return {
        "clusters": clusters,
        "entriesByCluster": entries_by_cluster,
        "visibleColumns": VISIBLE_TOC_COLUMNS,
    }


def json_script(data: dict[str, Any]) -> str:
    raw = json.dumps(data, ensure_ascii=False, indent=2)
    raw = raw.replace("</", "<\\/")
    return f'<script id="poppy-data" type="application/json">\n{raw}\n</script>'


def build_html(data: dict[str, Any]) -> str:
    nav = make_nav("2d")
    data_blob = json_script(data)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Poppyverse 2D Map</title>
  {favicon_html()}
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Michroma&display=swap" rel="stylesheet">

  <style>
    :root {{
      --poppy-pink: {POPPY_PINK};
      --bg: #09090f;
      --panel: rgba(10, 10, 16, 0.92);
      --panel-soft: rgba(255, 255, 255, 0.075);
      --text: rgba(255, 255, 255, 0.94);
      --muted: rgba(255, 255, 255, 0.68);
      --line: rgba(255, 255, 255, 0.14);
      --nav-height: 58px;
      --active-color: {POPPY_PINK};
    }}

    * {{
      box-sizing: border-box;
    }}

    html,
    body {{
      margin: 0;
      min-height: 100%;
      background:
        radial-gradient(circle at 20% 0%, rgba(255, 20, 71, 0.16), transparent 32%),
        radial-gradient(circle at 80% 20%, rgba(145, 80, 255, 0.12), transparent 35%),
        linear-gradient(135deg, #050507 0%, #0b0b12 48%, #11111d 100%);
      color: var(--text);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}

    body {{
      overflow-x: hidden;
    }}

    a {{
      color: inherit;
    }}

    .top-nav {{
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      z-index: 1000;
      padding: 10px 16px;
      pointer-events: none;
    }}

    .top-nav-inner {{
      width: max-content;
      max-width: calc(100vw - 32px);
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 8px;
      border: 1px solid rgba(255, 255, 255, 0.18);
      border-radius: 999px;
      background: rgba(0, 0, 0, 0.58);
      backdrop-filter: blur(12px);
      box-shadow: 0 0 28px rgba(0, 0, 0, 0.42);
      pointer-events: auto;
      overflow-x: auto;
    }}

    .top-nav-link {{
      flex: 0 0 auto;
      padding: 8px 13px;
      border-radius: 999px;
      color: rgba(255, 255, 255, 0.82);
      text-decoration: none;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      transition:
        color 160ms ease,
        background 160ms ease,
        box-shadow 160ms ease;
    }}

    .top-nav-link:hover,
    .top-nav-link.active {{
      color: #fff;
      background: var(--poppy-pink);
      box-shadow: 0 0 18px rgba(255, 20, 71, 0.44);
    }}

    .page {{
      min-height: 100vh;
      padding: calc(var(--nav-height) + 38px) 28px 56px;
    }}

    .hero {{
      max-width: 1180px;
      margin: 0 auto 34px;
      text-align: center;
    }}

    .eyebrow {{
      margin: 0 0 12px;
      color: var(--poppy-pink);
      font-family: "Michroma", sans-serif;
      font-size: 12px;
      letter-spacing: 0.24em;
      text-transform: uppercase;
      text-shadow: 0 0 14px rgba(255, 20, 71, 0.42);
    }}

    h1 {{
      margin: 0;
      color: #fff;
      font-family: "Michroma", sans-serif;
      font-size: clamp(30px, 5vw, 64px);
      line-height: 1.05;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      text-shadow: 0 0 28px rgba(255, 20, 71, 0.22);
    }}

    .subtitle {{
      max-width: 760px;
      margin: 18px auto 0;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.65;
    }}

    .cluster-grid {{
      max-width: 1320px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: repeat(auto-fit, 300px);
      justify-content: center;
      gap: 22px;
    }}

    .cluster-card {{
      position: relative;
      width: 300px;
      height: 200px;
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.22);
      border-radius: 22px;
      background: var(--cluster-color);
      box-shadow:
        0 16px 50px rgba(0, 0, 0, 0.42),
        0 0 26px color-mix(in srgb, var(--cluster-color) 38%, transparent);
      cursor: pointer;
      isolation: isolate;
      transform: translateY(0);
      transition:
        transform 180ms ease,
        border-color 180ms ease,
        box-shadow 180ms ease;
    }}

    .cluster-card:hover {{
      transform: translateY(-5px);
      border-color: rgba(255, 255, 255, 0.48);
      box-shadow:
        0 24px 70px rgba(0, 0, 0, 0.5),
        0 0 34px color-mix(in srgb, var(--cluster-color) 58%, transparent);
    }}

    .cluster-bg {{
      position: absolute;
      inset: 0;
      background-position: center;
      background-size: cover;
      opacity: 0.72;
      filter: saturate(1.04) contrast(1.05);
      z-index: -3;
    }}

    .cluster-color {{
      position: absolute;
      inset: 0;
      background:
        linear-gradient(
          135deg,
          color-mix(in srgb, var(--cluster-color) 88%, black 12%),
          color-mix(in srgb, var(--cluster-color) 54%, black 46%)
        );
      opacity: 0.86;
      z-index: -2;
    }}

    .cluster-card.has-cover .cluster-color {{
      mix-blend-mode: multiply;
      opacity: 0.78;
    }}

    .cluster-vignette {{
      position: absolute;
      inset: 0;
      background:
        radial-gradient(circle at 50% 20%, rgba(255,255,255,0.22), transparent 36%),
        linear-gradient(to bottom, rgba(0,0,0,0.04), rgba(0,0,0,0.72));
      z-index: -1;
    }}

    .cluster-content {{
      height: 100%;
      display: flex;
      flex-direction: column;
      justify-content: flex-end;
      padding: 18px;
    }}

    .cluster-name {{
    color: white;
      margin: 0;
      font-family: "Michroma", sans-serif;
      font-size: 18px;
      line-height: 1.18;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      text-shadow: 0 0 16px rgba(0, 0, 0, 0.86);
    }}

    .cluster-count {{
      margin-top: 8px;
      color: rgba(255, 255, 255, 0.78);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}

    .drawer-backdrop {{
      position: fixed;
      inset: 0;
      z-index: 1090;
      background: rgba(0, 0, 0, 0.48);
      opacity: 0;
      pointer-events: none;
      transition: opacity 180ms ease;
    }}

    .drawer-backdrop.open {{
      opacity: 1;
      pointer-events: auto;
    }}

    .drawer {{
      position: fixed;
      top: 0;
      right: 0;
      z-index: 1100;
      width: min(900px, 94vw);
      height: 100vh;
      background: #09090f;
      border-left: 1px solid rgba(255, 255, 255, 0.18);
      box-shadow: -24px 0 70px rgba(0, 0, 0, 0.62);
      transform: translateX(105%);
      transition: transform 220ms ease;
      overflow-y: auto;
    }}

    .drawer.open {{
      transform: translateX(0);
    }}

    .drawer-header {{
      position: relative;
      padding: calc(var(--nav-height) + 26px) 28px 24px;
      background:
        radial-gradient(circle at top left, color-mix(in srgb, var(--active-color) 36%, transparent), transparent 38%),
        linear-gradient(
          135deg,
          color-mix(in srgb, var(--active-color) 30%, #09090f 70%),
          #09090f 68%
        );
      border-bottom: 1px solid rgba(255, 255, 255, 0.14);
    }}

    .drawer-close {{
      position: absolute;
      top: calc(var(--nav-height) + 16px);
      right: 20px;
      width: 38px;
      height: 38px;
      border: 1px solid rgba(255, 255, 255, 0.24);
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.08);
      color: #fff;
      font-size: 20px;
      font-weight: 900;
      cursor: pointer;
    }}

    .drawer-title {{
      max-width: calc(100% - 58px);
      margin: 0;
      color: var(--active-color);
      font-family: "Michroma", sans-serif;
      font-size: clamp(22px, 3vw, 36px);
      line-height: 1.18;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      text-shadow: 0 0 20px color-mix(in srgb, var(--active-color) 38%, transparent);
    }}

    .drawer-description {{
      max-width: 760px;
      margin: 16px 0 0;
      color: rgba(255, 255, 255, 0.82);
      font-size: 14px;
      line-height: 1.65;
    }}

    .drawer-body {{
      padding: 24px 28px 44px;
    }}

    .table-wrap {{
      width: 100%;
      overflow-x: auto;
      border: 1px solid rgba(255, 255, 255, 0.13);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.045);
    }}

    table {{
      width: 100%;
      min-width: 760px;
      border-collapse: collapse;
    }}

    th,
    td {{
      padding: 13px 14px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.105);
      vertical-align: top;
      text-align: left;
    }}

    th {{
      position: sticky;
      top: 0;
      z-index: 2;
      color: #fff;
      background: color-mix(in srgb, var(--active-color) 22%, #11111d 78%);
      font-size: 11px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}

    td {{
      color: rgba(255, 255, 255, 0.84);
      font-size: 13px;
      line-height: 1.5;
    }}

    tr:last-child td {{
      border-bottom: 0;
    }}

    .empty {{
      color: rgba(255, 255, 255, 0.6);
      font-style: italic;
    }}

    .content-link {{
      display: inline-block;
      padding: 7px 10px;
      border-radius: 999px;
      background: var(--active-color);
      color: #fff;
      text-decoration: none;
      font-size: 11px;
      font-weight: 900;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      white-space: nowrap;
    }}

    .no-entries {{
      margin: 0;
      padding: 18px;
      color: rgba(255, 255, 255, 0.66);
      font-style: italic;
    }}

    @media (max-width: 760px) {{
      .page {{
        padding-left: 16px;
        padding-right: 16px;
      }}

      .top-nav {{
        padding-left: 8px;
        padding-right: 8px;
      }}

      .top-nav-inner {{
        justify-content: flex-start;
      }}

      .drawer-header {{
        padding-left: 20px;
        padding-right: 20px;
      }}

      .drawer-body {{
        padding-left: 20px;
        padding-right: 20px;
      }}
    }}
  </style>
</head>

<body>
  {nav}

  <main class="page">
    <section class="hero">
      <p class="eyebrow">Static Story Map</p>
      <h1>THE POPPYVERSE</h1>
      <p class="subtitle">
        A calmer, saner cluster-first table of contents for a multiverse that remains,
        despite best efforts, profoundly unserious about linear structure.
      </p>
    </section>

    <section id="clusterGrid" class="cluster-grid" aria-label="Poppyverse clusters"></section>
  </main>

  <div id="drawerBackdrop" class="drawer-backdrop"></div>

  <aside id="drawer" class="drawer" aria-hidden="true">
    <header id="drawerHeader" class="drawer-header">
      <button id="drawerClose" class="drawer-close" type="button" aria-label="Close drawer">×</button>
      <h2 id="drawerTitle" class="drawer-title"></h2>
      <p id="drawerDescription" class="drawer-description"></p>
    </header>

    <div id="drawerBody" class="drawer-body"></div>
  </aside>

  {data_blob}

  <script>
    "use strict";

    const rawData = document.getElementById("poppy-data").textContent;
    const DATA = JSON.parse(rawData);

    const clusterGrid = document.getElementById("clusterGrid");
    const drawer = document.getElementById("drawer");
    const drawerBackdrop = document.getElementById("drawerBackdrop");
    const drawerClose = document.getElementById("drawerClose");
    const drawerTitle = document.getElementById("drawerTitle");
    const drawerDescription = document.getElementById("drawerDescription");
    const drawerBody = document.getElementById("drawerBody");

    function escapeHtml(value) {{
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }}

    function isUrl(value) {{
      return /^https?:\\/\\//i.test(String(value || "").trim());
    }}

    function renderCell(column, value) {{
      const text = String(value || "").trim();

      if (!text) {{
        return '<span class="empty">—</span>';
      }}

      if (column === "Content URL" && isUrl(text)) {{
        return `<a class="content-link" href="${{escapeHtml(text)}}" target="_blank" rel="noopener">Read</a>`;
      }}

      return escapeHtml(text);
    }}

    function renderTable(entries) {{
      const columns = DATA.visibleColumns || ["Name", "Sub-parts", "Description", "Characters", "Content URL"];

      if (!entries || entries.length === 0) {{
        return '<p class="no-entries">No entries in this cluster yet. The void remains administratively unfilled.</p>';
      }}

      const thead = columns
        .map(col => `<th>${{escapeHtml(col)}}</th>`)
        .join("");

      const rows = entries
        .map(entry => {{
          const cells = columns
            .map(col => `<td>${{renderCell(col, entry[col])}}</td>`)
            .join("");
          return `<tr>${{cells}}</tr>`;
        }})
        .join("");

      return `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>${{thead}}</tr>
            </thead>
            <tbody>
              ${{rows}}
            </tbody>
          </table>
        </div>
      `;
    }}

    function openDrawer(cluster) {{
      const entries = DATA.entriesByCluster[cluster.name] || [];

      document.documentElement.style.setProperty("--active-color", cluster.color || "#FF1447");

      drawerTitle.textContent = cluster.name || "";
      drawerDescription.textContent = cluster.description || "";
      drawerBody.innerHTML = renderTable(entries);

      drawer.classList.add("open");
      drawerBackdrop.classList.add("open");
      drawer.setAttribute("aria-hidden", "false");
    }}

    function closeDrawer() {{
      drawer.classList.remove("open");
      drawerBackdrop.classList.remove("open");
      drawer.setAttribute("aria-hidden", "true");
    }}

    function renderClusters() {{
      clusterGrid.innerHTML = "";

      DATA.clusters.forEach(cluster => {{
        const entries = DATA.entriesByCluster[cluster.name] || [];
        const hasCover = Boolean(cluster.coverUrl);

        const card = document.createElement("button");
        card.type = "button";
        card.className = `cluster-card${{hasCover ? " has-cover" : ""}}`;
        card.style.setProperty("--cluster-color", cluster.color || "#FF1447");
        card.setAttribute("aria-label", `Open ${{cluster.name}}`);

        const bg = hasCover
          ? `<div class="cluster-bg" style="background-image: url('${{escapeHtml(cluster.coverUrl)}}');"></div>`
          : "";

        card.innerHTML = `
          ${{bg}}
          <div class="cluster-color"></div>
          <div class="cluster-vignette"></div>
          <div class="cluster-content">
            <h2 class="cluster-name">${{escapeHtml(cluster.name)}}</h2>
            <div class="cluster-count">${{entries.length}} entr${{entries.length === 1 ? "y" : "ies"}}</div>
          </div>
        `;

        card.addEventListener("click", () => openDrawer(cluster));
        clusterGrid.appendChild(card);
      }});
    }}

    drawerClose.addEventListener("click", closeDrawer);
    drawerBackdrop.addEventListener("click", closeDrawer);

    window.addEventListener("keydown", event => {{
      if (event.key === "Escape") {{
        closeDrawer();
      }}
    }});

    renderClusters();
  </script>
</body>
</html>
"""


def main() -> None:
    data = build_data()
    html_text = build_html(data)
    OUTPUT_HTML.write_text(html_text, encoding="utf-8")

    cluster_count = len(data["clusters"])
    entry_count = sum(len(v) for v in data["entriesByCluster"].values())

    print(f"Built {OUTPUT_HTML.name}")
    print(f"Clusters: {cluster_count}")
    print(f"Visible 2D entries: {entry_count}")
    print(f"Visible 2D columns: {', '.join(VISIBLE_TOC_COLUMNS)}")


if __name__ == "__main__":
    main()