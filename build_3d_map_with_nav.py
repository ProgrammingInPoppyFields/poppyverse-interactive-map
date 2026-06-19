#!/usr/bin/env python3
"""
Build the 3D Poppyverse map.

Source files:
- SRC_clusters.csv
- SRC_toc.csv

Output:
- 3d_map.html

3D visual rules:
- Keep graph nodes.
- Keep collision links if resolvable.
- Keep click drawer.
- Keep top nav.
- Keep Multiverse Color Legend.
- Do NOT show axes.
- Do NOT show axis labels.
  (Both axes and axis labels are hidden by default, but can be revealed via
  the "Show axes" toggle at the bottom-left of the page.)
- Do NOT show hover labels.
- Do NOT show HUD title/subtitle.
- Do NOT show content ratings in clicked cards.
- Do NOT show bounding cube.
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
OUTPUT_HTML = ROOT / "3d_map.html"

POPPY_PINK = "#FF1447"
TUMBLR_ARCHIVE_URL = "https://inpoppyfields.tumblr.com/"


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


def parse_float(value: str, fallback: float = 0.0) -> float:
    value = str(value or "").strip()

    if not value:
        return fallback

    if value.startswith("(") and ")" in value:
        value = value[1:value.index(")")]

    try:
        return float(value)
    except ValueError:
        return fallback


def parse_bool(value: str) -> bool:
    return str(value or "").strip().lower() in {"yes", "true", "1", "y"}


def parse_list(value: str) -> list[str]:
    value = str(value or "").strip()
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


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
    cluster_by_name: dict[str, dict[str, Any]] = {}

    for idx, row in enumerate(cluster_rows):
        name = get_first(row, ["Name", "Cluster", "Cluster Name"])

        if not name:
            continue

        color = clean_hex_color(
            get_first(row, ["Hex Code Color", "Hex Color", "Color", "Hex"])
        )

        description = get_first(row, ["Description", "Desc"])
        cover_url = normalize_url(get_first(row, ["Cover URL", "Cover", "Image URL", "Image"]))

        cluster = {
            "name": name,
            "color": color,
            "description": description,
            "coverUrl": cover_url,
            "order": idx,
        }

        clusters.append(cluster)
        cluster_by_name[name] = cluster

    nodes: list[dict[str, Any]] = []

    for row_index, row in enumerate(toc_rows, start=1):
        node_id = get_first(row, ["ID", "Id", "id"]) or str(row_index)
        name = get_first(row, ["Name", "Title"])

        if not node_id:
            node_id = str(row_index)

        if not name:
            continue

        cluster_name = get_first(row, ["Cluster", "Tags"], "(unclustered)")
        cluster = cluster_by_name.get(cluster_name)

        color = cluster["color"] if cluster else POPPY_PINK
        cluster_description = cluster["description"] if cluster else ""

        node = {
            "id": str(node_id),
            "label": name,
            "cluster": cluster_name,
            "clusterDescription": cluster_description,
            "color": color,
            "description": get_first(row, ["Description", "Desc"]),
            "subparts": get_first(row, ["Sub-parts", "Subparts", "Parts"]),
            "characters": parse_list(get_first(row, ["Characters"])),
            "collisions": parse_list(get_first(row, ["Collisions", "Collision"])),
            "contentUrl": normalize_url(get_first(row, ["Content URL", "URL", "Url"])),
            "coverUrl": normalize_url(get_first(row, ["Cover URL", "Cover", "Image URL", "Image"])),
            "featured": parse_bool(get_first(row, ["Featured"])),
            "size": max(1.0, parse_float(get_first(row, ["Size", "Value"]), 1.0)),
            "xValue": parse_float(get_first(row, ["(X) Relativity", "X", "Relativity"]), 0.0),
            "yValue": parse_float(get_first(row, ["(Y) Relatability", "Y", "Relatability"]), 0.0),
            "zValue": parse_float(get_first(row, ["(Z) Depth", "Z", "Depth"]), 0.0),
        }

        nodes.append(node)

    id_lookup = {str(node["id"]): node for node in nodes}
    numeric_lookup: dict[str, dict[str, Any]] = {}

    for node in nodes:
        raw_id = str(node["id"]).strip()
        try:
            numeric_lookup[str(int(float(raw_id)))] = node
        except ValueError:
            pass

    links: list[dict[str, Any]] = []
    seen_links: set[tuple[str, str]] = set()

    for node in nodes:
        source_id = str(node["id"])

        for raw_target in node["collisions"]:
            target_key = str(raw_target).strip()

            if not target_key or target_key == "0":
                continue

            target_node = id_lookup.get(target_key)

            if target_node is None:
                try:
                    target_node = numeric_lookup.get(str(int(float(target_key))))
                except ValueError:
                    target_node = None

            if target_node is None:
                continue

            target_id = str(target_node["id"])

            if source_id == target_id:
                continue

            link_key = tuple(sorted((source_id, target_id)))

            if link_key in seen_links:
                continue

            seen_links.add(link_key)

            links.append(
                {
                    "source": source_id,
                    "target": target_id,
                    "color": "#FFFFFF",
                    "width": 1.3,
                }
            )

    return {
        "clusters": clusters,
        "nodes": nodes,
        "links": links,
    }


def json_script(data: dict[str, Any]) -> str:
    raw = json.dumps(data, ensure_ascii=False, indent=2)
    raw = raw.replace("</", "<\\/")
    return f'<script id="poppy-data" type="application/json">\n{raw}\n</script>'


def build_html(data: dict[str, Any]) -> str:
    nav = make_nav("3d")
    data_blob = json_script(data)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Poppyverse 3D Map</title>
  {favicon_html()}

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Michroma&display=swap" rel="stylesheet">

  <style>
    :root {{
      --poppy-pink: {POPPY_PINK};
      --active-color: {POPPY_PINK};
      --nav-height: 58px;
      --text: rgba(255, 255, 255, 0.94);
      --muted: rgba(255, 255, 255, 0.68);
      --line: rgba(255, 255, 255, 0.14);
    }}

    * {{
      box-sizing: border-box;
    }}

    html,
    body {{
      margin: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      color: var(--text);
      background: #06060a;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}

    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      z-index: 0;
      background:
        radial-gradient(circle at 20% 12%, rgba(255, 20, 71, 0.16), transparent 32%),
        radial-gradient(circle at 80% 30%, rgba(112, 68, 255, 0.14), transparent 34%),
        linear-gradient(135deg, #050507 0%, #0b0b12 48%, #11111d 100%);
    }}

    body::after {{
      content: "";
      position: fixed;
      inset: 0;
      z-index: 0;
      pointer-events: none;
      background:
        radial-gradient(circle at center, transparent 0%, rgba(0, 0, 0, 0.38) 72%, rgba(0, 0, 0, 0.72) 100%);
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

    #graph {{
      position: relative;
      z-index: 1;
      width: 100vw;
      height: 100vh;
    }}

    .legend {{
      position: fixed;
      bottom: 18px;
      right: 18px;
      z-index: 22;
      display: flex;
      flex-direction: column-reverse;
      width: min(320px, calc(100vw - 36px));
      max-height: calc(100vh - var(--nav-height) - 40px);
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.18);
      border-radius: 18px;
      background: rgba(0, 0, 0, 0.54);
      backdrop-filter: blur(12px);
      box-shadow: 0 0 28px rgba(0, 0, 0, 0.42);
    }}

    .legend-toggle {{
      width: 100%;
      padding: 12px 14px;
      border: 0;
      background: transparent;
      color: #fff;
      font-family: "Michroma", sans-serif;
      font-size: 12px;
      letter-spacing: 0.08em;
      text-align: left;
      text-transform: uppercase;
      cursor: pointer;
    }}

    .legend-rows {{
      display: none;
      max-height: calc(100vh - var(--nav-height) - 100px);
      overflow-y: auto;
      padding: 0 14px 14px;
    }}

    .legend.open .legend-rows {{
      display: block;
    }}

    .legend-row {{
      display: grid;
      grid-template-columns: 14px 1fr;
      gap: 9px;
      padding: 9px 0;
      border-top: 1px solid rgba(255, 255, 255, 0.1);
    }}

    .legend-swatch {{
      width: 12px;
      height: 12px;
      margin-top: 3px;
      border-radius: 4px;
      border: 1px solid rgba(255, 255, 255, 0.24);
      box-shadow: 0 0 10px currentColor;
    }}

    .legend-name {{
      margin: 0;
      font-weight: 800;
      font-size: 13px;
      line-height: 1.25;
    }}

    .legend-desc {{
      margin: 3px 0 0;
      color: rgba(255, 255, 255, 0.66);
      font-size: 11px;
      line-height: 1.45;
    }}

    .axes-toggle {{
      position: fixed;
      bottom: 18px;
      left: 18px;
      z-index: 22;
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 9px 14px;
      border: 1px solid rgba(255, 255, 255, 0.18);
      border-radius: 999px;
      background: rgba(0, 0, 0, 0.54);
      backdrop-filter: blur(12px);
      box-shadow: 0 0 28px rgba(0, 0, 0, 0.42);
      cursor: pointer;
      user-select: none;
    }}

    .axes-toggle input {{
      position: absolute;
      opacity: 0;
      width: 0;
      height: 0;
    }}

    .axes-toggle-track {{
      position: relative;
      width: 34px;
      height: 18px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.16);
      transition: background 0.18s ease;
      flex: none;
    }}

    .axes-toggle-thumb {{
      position: absolute;
      top: 2px;
      left: 2px;
      width: 14px;
      height: 14px;
      border-radius: 50%;
      background: #fff;
      transition: transform 0.18s ease;
    }}

    .axes-toggle input:checked + .axes-toggle-track {{
      background: var(--poppy-pink);
    }}

    .axes-toggle input:checked + .axes-toggle-track .axes-toggle-thumb {{
      transform: translateX(16px);
    }}

    .axes-toggle input:focus-visible + .axes-toggle-track {{
      outline: 2px solid rgba(255, 255, 255, 0.6);
      outline-offset: 2px;
    }}

    .axes-toggle-label {{
      color: #fff;
      font-family: "Michroma", sans-serif;
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}

    .wormhole-btn {{
      position: fixed;
      bottom: 18px;
      left: 50%;
      transform: translateX(-50%);
      z-index: 22;
      padding: 11px 20px;
      border: 1px solid rgba(255, 255, 255, 0.18);
      border-radius: 999px;
      background: rgba(0, 0, 0, 0.54);
      backdrop-filter: blur(12px);
      box-shadow: 0 0 28px rgba(0, 0, 0, 0.42);
      color: #fff;
      font-family: "Michroma", sans-serif;
      font-size: 12px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      text-decoration: none;
      white-space: nowrap;
      transition: border-color 0.18s ease, box-shadow 0.18s ease, color 0.18s ease;
    }}

    .wormhole-btn:hover {{
      color: var(--poppy-pink);
      border-color: color-mix(in srgb, var(--poppy-pink) 60%, transparent);
      box-shadow: 0 0 28px color-mix(in srgb, var(--poppy-pink) 30%, transparent);
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
      width: min(560px, 94vw);
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
      padding: calc(var(--nav-height) + 26px) 24px 22px;
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
      right: 18px;
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
      max-width: calc(100% - 54px);
      margin: 0;
      color: var(--active-color);
      font-family: "Michroma", sans-serif;
      font-size: clamp(20px, 3vw, 32px);
      line-height: 1.18;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      text-shadow: 0 0 20px color-mix(in srgb, var(--active-color) 38%, transparent);
    }}

    .drawer-cluster {{
      display: inline-block;
      margin-top: 14px;
      padding: 5px 9px;
      border-radius: 999px;
      background: var(--active-color);
      color: #fff;
      font-size: 11px;
      font-weight: 900;
      letter-spacing: 0.09em;
      text-transform: uppercase;
    }}

    .drawer-body {{
      padding: 22px 24px 44px;
    }}

    .drawer-body img {{
      display: block;
      width: 100%;
      max-height: 260px;
      object-fit: cover;
      margin-bottom: 18px;
      border-radius: 16px;
      border: 1px solid rgba(255, 255, 255, 0.14);
    }}

    .drawer-section {{
      margin: 0 0 18px;
      padding-bottom: 18px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.12);
    }}

    .drawer-section:last-child {{
      border-bottom: 0;
    }}

    .drawer-section h3 {{
      margin: 0 0 8px;
      color: #fff;
      font-family: "Michroma", sans-serif;
      font-size: 12px;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }}

    .drawer-section p {{
      margin: 0;
      color: rgba(255, 255, 255, 0.78);
      font-size: 14px;
      line-height: 1.65;
    }}

    .collision-link {{
      color: var(--active-color);
      text-decoration: none;
      border-bottom: 1px solid color-mix(in srgb, var(--active-color) 45%, transparent);
      transition: border-color 0.15s ease;
    }}

    .collision-link:hover {{
      border-bottom-color: var(--active-color);
    }}

    .read-link {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 40px;
      padding: 10px 14px;
      border-radius: 999px;
      background: var(--active-color);
      color: #fff;
      text-decoration: none;
      font-size: 12px;
      font-weight: 900;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }}

    @media (max-width: 760px) {{
      .legend {{
        display: none;
      }}

      .top-nav {{
        padding-left: 8px;
        padding-right: 8px;
      }}

      .top-nav-inner {{
        justify-content: flex-start;
      }}
    }}
  </style>
</head>

<body>
  {nav}

  <div id="graph"></div>

  <aside id="legend" class="legend">
    <button id="legendToggle" class="legend-toggle" type="button">Multiverse Color Legend ▴</button>
    <div id="legendRows" class="legend-rows"></div>
  </aside>

  <div id="drawerBackdrop" class="drawer-backdrop"></div>

  <aside id="drawer" class="drawer" aria-hidden="true">
    <header class="drawer-header">
      <button id="drawerClose" class="drawer-close" type="button" aria-label="Close drawer">×</button>
      <h2 id="drawerTitle" class="drawer-title"></h2>
      <div id="drawerCluster" class="drawer-cluster"></div>
    </header>
    <div id="drawerBody" class="drawer-body"></div>
  </aside>

  <label class="axes-toggle" for="axesToggle">
    <input type="checkbox" id="axesToggle" />
    <span class="axes-toggle-track"><span class="axes-toggle-thumb"></span></span>
    <span class="axes-toggle-label">Show axes</span>
  </label>

  <a class="wormhole-btn" href="https://programminginpoppyfields.github.io/engine-codex/" target="_blank" rel="noopener">Wormhole</a>

  {data_blob}

  <script src="https://unpkg.com/three@0.148.0/build/three.min.js"></script>
  <script src="https://unpkg.com/three@0.148.0/examples/js/controls/OrbitControls.js"></script>
  <script src="https://unpkg.com/3d-force-graph@1.72.0/dist/3d-force-graph.min.js"></script>

  <script>
    "use strict";

    const DATA = JSON.parse(document.getElementById("poppy-data").textContent);

    const CLUSTER_SPREAD = 150;
    const DEPTH_SCALE = 35;
    const NODE_SCATTER = 50;

    const graphEl = document.getElementById("graph");
    const legend = document.getElementById("legend");
    const legendToggle = document.getElementById("legendToggle");
    const legendRows = document.getElementById("legendRows");

    const drawer = document.getElementById("drawer");
    const drawerBackdrop = document.getElementById("drawerBackdrop");
    const drawerClose = document.getElementById("drawerClose");
    const drawerTitle = document.getElementById("drawerTitle");
    const drawerCluster = document.getElementById("drawerCluster");
    const drawerBody = document.getElementById("drawerBody");

    let hoveredNode = null;
    let selectedNode = null;

    function escapeHtml(value) {{
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }}

    function hash32(str) {{
      let h = 0;
      for (let i = 0; i < str.length; i++) {{
        h = ((h << 5) - h) + str.charCodeAt(i);
        h |= 0;
      }}
      return Math.abs(h);
    }}

    function rand(seed) {{
      const x = Math.sin(seed) * 10000;
      return x - Math.floor(x);
    }}

    function makeGlowSprite(colorHex) {{
      const canvas = document.createElement("canvas");
      canvas.width = 128;
      canvas.height = 128;

      const ctx = canvas.getContext("2d");
      const grad = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);

      grad.addColorStop(0, colorHex);
      grad.addColorStop(0.5, colorHex + "80");
      grad.addColorStop(1, colorHex + "00");

      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, 128, 128);

      const tex = new THREE.CanvasTexture(canvas);

      return new THREE.Sprite(
        new THREE.SpriteMaterial({{
          map: tex,
          transparent: true,
          depthWrite: false
        }})
      );
    }}

    function resetNodeVisual(node) {{
      if (!node || !node.__glow) return;

      const s = node.__idleSize * 0.98;
      node.__glow.scale.set(s, s, 1);
      node.__glow.material.opacity = 0.32;
    }}

    function setHighlightedNode(node) {{
      if (!node || !node.__glow) return;

      const r = Math.min(node.__idleSize, 22);
      node.__glow.scale.set(r, r, 1);
      node.__glow.material.opacity = 0.82;
    }}

    function renderList(items) {{
      if (!items || !items.length) return "<p>—</p>";
      return `<p>${{items.map(escapeHtml).join(", ")}}</p>`;
    }}

    function renderCollisions(items) {{
      if (!items || !items.length) return "<p>—</p>";
      const parts = items.map(item => {{
        const label = escapeHtml(item.label || "");
        return item.url
          ? `<a class="collision-link" href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener">${{label}}</a>`
          : label;
      }});
      return `<p>${{parts.join(", ")}}</p>`;
    }}

    function openDrawer(node) {{
      selectedNode = node;
      setHighlightedNode(node);

      const accent = node.color || "#FF1447";
      document.documentElement.style.setProperty("--active-color", accent);

      drawerTitle.textContent = node.label || node.id || "";
      drawerCluster.textContent = node.cluster || "";

      const cover = node.coverUrl
        ? `<img src="${{escapeHtml(node.coverUrl)}}" alt="">`
        : "";

      const contentLink = node.contentUrl
        ? `<a class="read-link" href="${{escapeHtml(node.contentUrl)}}" target="_blank" rel="noopener">Read More</a>`
        : `<p>Content not ready.</p>`;

      const subpartsHtml = node.subparts
        ? `
          <section class="drawer-section">
            <h3>Sub-parts</h3>
            <p>${{escapeHtml(node.subparts)}}</p>
          </section>
        `
        : "";

      drawerBody.innerHTML = `
        ${{cover}}

        <section class="drawer-section">
          <h3>Description</h3>
          <p>${{escapeHtml(node.description || "No description yet.")}}</p>
        </section>

        ${{subpartsHtml}}

        <section class="drawer-section">
          <h3>Characters</h3>
          ${{renderList(node.characters)}}
        </section>

        <section class="drawer-section">
          <h3>Collisions</h3>
          ${{renderCollisions(node.collisionLinks || [])}}
        </section>

        <section class="drawer-section">
          <h3>Content</h3>
          ${{contentLink}}
        </section>
      `;

      drawer.classList.add("open");
      drawerBackdrop.classList.add("open");
      drawer.setAttribute("aria-hidden", "false");
    }}

    function closeDrawer() {{
      drawer.classList.remove("open");
      drawerBackdrop.classList.remove("open");
      drawer.setAttribute("aria-hidden", "true");

      if (selectedNode) {{
        resetNodeVisual(selectedNode);
      }}

      selectedNode = null;
    }}

    function buildLegend() {{
      legendRows.innerHTML = "";

      DATA.clusters.forEach(cluster => {{
        const row = document.createElement("div");
        row.className = "legend-row";

        row.innerHTML = `
          <div class="legend-swatch" style="background:${{escapeHtml(cluster.color)}}; color:${{escapeHtml(cluster.color)}};"></div>
          <div>
            <p class="legend-name" style="color:${{escapeHtml(cluster.color)}};">${{escapeHtml(cluster.name)}}</p>
            <p class="legend-desc">${{escapeHtml(cluster.description || "")}}</p>
          </div>
        `;

        legendRows.appendChild(row);
      }});
    }}

    function prepareGraphData() {{
      const clusterOrder = DATA.clusters.map(c => c.name);
      const clusterIndex = new Map(clusterOrder.map((name, index) => [name, index]));

      const nodeById = new Map(DATA.nodes.map(node => [String(node.id), node]));

      DATA.nodes.forEach(node => {{
        const idx = clusterIndex.has(node.cluster) ? clusterIndex.get(node.cluster) : clusterOrder.length;
        const seed = hash32(String(node.id) + "|" + String(node.cluster));

        const angle = rand(seed) * Math.PI * 2;
        const radius = rand(seed + 1) * NODE_SCATTER + 20;

        node.x = node.xValue * 40 + Math.cos(angle) * radius;
        node.y = -node.zValue * DEPTH_SCALE;
        node.z = idx * CLUSTER_SPREAD + Math.sin(angle) * radius;

        node.fx = node.x;
        node.fy = node.y;
        node.fz = node.z;

        node.val = node.size;
      }});

      // Resolve link endpoints from string ids to node-object references.
      // The layout's "link" force (which normally does this) is disabled to
      // keep the fixed fx/fy/fz layout frozen, so we must resolve manually or
      // the renderer skips any link whose endpoints aren't objects.
      DATA.links.forEach(link => {{
        const source = nodeById.get(String(link.source));
        const target = nodeById.get(String(link.target));
        if (source) link.source = source;
        if (target) link.target = target;
      }});

      // Build each node's collision list from the (already de-duped, undirected)
      // links so the drawer shows a collision on BOTH endpoints, not just the
      // node whose CSV cell happened to name the other. Each entry carries the
      // partner's title and story URL for a clickable link.
      DATA.nodes.forEach(node => {{ node.collisionLinks = []; }});
      DATA.links.forEach(link => {{
        const a = link.source;
        const b = link.target;
        if (typeof a !== "object" || typeof b !== "object") return;
        a.collisionLinks.push({{ label: b.label, url: b.contentUrl }});
        b.collisionLinks.push({{ label: a.label, url: a.contentUrl }});
      }});

      return {{
        nodes: DATA.nodes,
        links: DATA.links
      }};
    }}

    function start() {{
      buildLegend();

      legendToggle.addEventListener("click", () => {{
        const isOpen = legend.classList.toggle("open");
        legendToggle.textContent = isOpen
          ? "Multiverse Color Legend ▾"
          : "Multiverse Color Legend ▴";
      }});

      drawerClose.addEventListener("click", closeDrawer);
      drawerBackdrop.addEventListener("click", closeDrawer);

      window.addEventListener("keydown", event => {{
        if (event.key === "Escape") closeDrawer();
      }});

      const graphData = prepareGraphData();

      const Graph = ForceGraph3D()(graphEl)
        .enablePointerInteraction(true)
        .graphData(graphData)
        .showNavInfo(false)
        .d3Force("link", null)
        .d3Force("charge", null)
        .enableNodeDrag(false)
        .cooldownTicks(0)
        .nodeLabel(() => "")
        .nodeThreeObject(node => {{
          const colorHex = node.color || "#FF1447";
          const color = new THREE.Color(colorHex);

          const core = new THREE.Mesh(
            new THREE.SphereGeometry(5, 24, 24),
            new THREE.MeshStandardMaterial({{
              color,
              metalness: 0.12,
              roughness: 0.38
            }})
          );

          const sizeVal = Number(node.size) || 1;
          const scale = 0.6 + sizeVal * 0.09;
          core.scale.set(scale, scale, scale);

          const glow = makeGlowSprite(colorHex);
          glow.raycast = () => {{}};
          glow.material.depthTest = false;
          glow.renderOrder = 10;

          const idleSize = Math.max(42, 5 * scale * 5.4);
          glow.scale.set(idleSize * 0.98, idleSize * 0.98, 1);
          glow.material.opacity = 0.32;
          core.add(glow);

          node.__core = core;
          node.__glow = glow;
          node.__idleSize = idleSize;

          return core;
        }})
        .linkColor(() => "#FFFFFF")
        .linkWidth(0)
        .linkOpacity(1);

      const renderer = new THREE.WebGLRenderer({{
        antialias: true,
        alpha: true
      }});

      renderer.setPixelRatio(window.devicePixelRatio || 1);
      renderer.setSize(window.innerWidth, window.innerHeight);
      renderer.setClearColor(0x000000, 0);
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.05;

      Graph.renderer(renderer);
      Graph.width(window.innerWidth).height(window.innerHeight);
      Graph.backgroundColor("rgba(0,0,0,0)");

      const scene = Graph.scene();
      scene.background = null;

      scene.add(new THREE.AmbientLight(0xffffff, 0.36));

      const dir = new THREE.DirectionalLight(0xffffff, 0.7);
      dir.position.set(60, 80, 40);
      scene.add(dir);

      const controls = Graph.controls();
      controls.enableRotate = true;
      controls.enablePan = true;
      controls.minDistance = 20;
      controls.maxDistance = 1600;

      const bounds = (() => {{
        let minX = Infinity;
        let minY = Infinity;
        let minZ = Infinity;
        let maxX = -Infinity;
        let maxY = -Infinity;
        let maxZ = -Infinity;

        graphData.nodes.forEach(node => {{
          minX = Math.min(minX, node.x);
          minY = Math.min(minY, node.y);
          minZ = Math.min(minZ, node.z);
          maxX = Math.max(maxX, node.x);
          maxY = Math.max(maxY, node.y);
          maxZ = Math.max(maxZ, node.z);
        }});

        if (!Number.isFinite(minX)) {{
          minX = minY = minZ = -100;
          maxX = maxY = maxZ = 100;
        }}

        const pad = 45;
        minX -= pad;
        minY -= pad;
        minZ -= pad;
        maxX += pad;
        maxY += pad;
        maxZ += pad;

        return {{
          minX, minY, minZ,
          maxX, maxY, maxZ,
          cx: (minX + maxX) / 2,
          cy: (minY + maxY) / 2,
          cz: (minZ + maxZ) / 2
        }};
      }})();

      controls.target.set(bounds.cx, bounds.cy, bounds.cz);

      const spanX = bounds.maxX - bounds.minX;
      const spanY = bounds.maxY - bounds.minY;
      const spanZ = bounds.maxZ - bounds.minZ;
      const diag = Math.max(spanX, spanY, spanZ);

      Graph.cameraPosition(
        {{
          x: bounds.cx - diag * 1.15,
          y: bounds.cy + diag * 0.55,
          z: bounds.cz + diag * 1.35
        }},
        {{
          x: bounds.cx,
          y: bounds.cy,
          z: bounds.cz
        }},
        1200
      );

      // --- Axes overlay (hidden by default; toggled via the "Show axes" switch) ---
      // Axes are labeled with the three source columns: X = Depth,
      // Y (up) = Relatability, Z = Relativity.
      const axesGroup = new THREE.Group();
      axesGroup.visible = false;

      function makeAxisLabel(text, colorHex) {{
        const canvas = document.createElement("canvas");
        canvas.width = 256;
        canvas.height = 64;

        const ctx = canvas.getContext("2d");
        ctx.font = "600 32px Michroma, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = colorHex;
        ctx.fillText(text, 128, 34);

        const tex = new THREE.CanvasTexture(canvas);

        const sprite = new THREE.Sprite(
          new THREE.SpriteMaterial({{
            map: tex,
            transparent: true,
            depthWrite: false,
            depthTest: false
          }})
        );

        sprite.scale.set(150, 37, 1);
        sprite.renderOrder = 20;
        return sprite;
      }}

      function addAxis(from, to, colorHex, labelText) {{
        const geom = new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(from.x, from.y, from.z),
          new THREE.Vector3(to.x, to.y, to.z)
        ]);

        const line = new THREE.Line(
          geom,
          new THREE.LineBasicMaterial({{ color: colorHex, transparent: true, opacity: 0.8 }})
        );
        axesGroup.add(line);

        const label = makeAxisLabel(labelText, colorHex);
        label.position.set(to.x, to.y, to.z);
        axesGroup.add(label);
      }}

      const axisOrigin = {{ x: bounds.minX, y: bounds.minY, z: bounds.minZ }};
      addAxis(axisOrigin, {{ x: bounds.maxX, y: bounds.minY, z: bounds.minZ }}, "#FF6B6B", "Depth");
      addAxis(axisOrigin, {{ x: bounds.minX, y: bounds.maxY, z: bounds.minZ }}, "#6BCB77", "Relatability");
      addAxis(axisOrigin, {{ x: bounds.minX, y: bounds.minY, z: bounds.maxZ }}, "#4D96FF", "Relativity");

      scene.add(axesGroup);

      const axesToggle = document.getElementById("axesToggle");
      axesToggle.checked = false;
      axesGroup.visible = false;
      axesToggle.addEventListener("change", () => {{
        axesGroup.visible = axesToggle.checked;
      }});

      Graph.onNodeHover((node, prev) => {{
        const prevNode = prev || hoveredNode;

        if (prevNode && prevNode !== node && prevNode !== selectedNode) {{
          resetNodeVisual(prevNode);
        }}

        hoveredNode = node || null;

        if (!hoveredNode) {{
          graphData.nodes.forEach(n => {{
            if (n !== selectedNode) resetNodeVisual(n);
          }});
          return;
        }}

        setHighlightedNode(hoveredNode);
      }});

      Graph.onNodeClick(node => {{
        openDrawer(node);
      }});

      renderer.setAnimationLoop(() => {{
        const t = performance.now() * 0.012;
        const pulse = 0.70 + 0.30 * (0.5 + 0.5 * Math.sin(t));

        if (hoveredNode && hoveredNode.__glow && hoveredNode !== selectedNode) {{
          hoveredNode.__glow.material.opacity = pulse;
        }}

        if (selectedNode && selectedNode.__glow) {{
          selectedNode.__glow.material.opacity = 0.62;
          const r = Math.min(selectedNode.__idleSize, 22);
          selectedNode.__glow.scale.set(r, r, 1);
        }}

        renderer.render(scene, Graph.camera());
      }});

      window.addEventListener("resize", () => {{
        renderer.setSize(window.innerWidth, window.innerHeight);
        Graph.width(window.innerWidth).height(window.innerHeight);
      }});
    }}

    start();
  </script>
</body>
</html>
"""


def main() -> None:
    data = build_data()
    html_text = build_html(data)
    OUTPUT_HTML.write_text(html_text, encoding="utf-8")

    print(f"Built {OUTPUT_HTML.name}")
    print(f"Clusters: {len(data['clusters'])}")
    print(f"Nodes: {len(data['nodes'])}")
    print(f"Links: {len(data['links'])}")


if __name__ == "__main__":
    main()