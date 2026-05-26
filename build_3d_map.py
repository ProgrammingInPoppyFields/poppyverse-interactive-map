#!/usr/bin/env python3
"""
build_3d_map.py

Generate a static 3D Poppyverse map from:
  - SRC_clusters.csv
  - SRC_toc.csv

Output:
  - 3d_map.html

The CSVs stay the source of truth. Python handles parsing, cleanup, grouping,
cluster colors, collision resolution, and JSON embedding. The HTML stays focused
on rendering and interaction.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

DEFAULT_CLUSTER_CSV = "SRC_clusters.csv"
DEFAULT_TOC_CSV = "SRC_toc.csv"
DEFAULT_OUTPUT_HTML = "3d_map.html"

IGNORE_TABLE_COLUMNS = {"cover url", "cover", "image", "image url", "thumbnail", "thumbnail url"}


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

def clean_header(value: Any) -> str:
    return str(value or "").replace("\ufeff", "").strip()


def norm(value: Any) -> str:
    return clean_header(value).lower()


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows: List[Dict[str, str]] = []
        for raw in reader:
            row = {clean_header(k): ("" if v is None else str(v).strip()) for k, v in raw.items() if k is not None}
            if any(v.strip() for v in row.values()):
                rows.append(row)
        return rows


def first_key(row: Dict[str, str], candidates: Iterable[str]) -> Optional[str]:
    lower_to_actual = {norm(k): k for k in row.keys()}
    for c in candidates:
        if norm(c) in lower_to_actual:
            return lower_to_actual[norm(c)]
    return None


def get_value(row: Dict[str, str], candidates: Iterable[str], default: str = "") -> str:
    key = first_key(row, candidates)
    return row.get(key, default).strip() if key else default


def parse_number(value: Any, default: float = 0.0) -> float:
    s = str(value or "").strip()
    if not s:
        return default
    paren = re.search(r"\(([^)]+)\)", s)
    if paren:
        s = paren.group(1)
    match = re.search(r"-?\d+(?:\.\d+)?", s)
    if not match:
        return default
    try:
        return float(match.group(0))
    except ValueError:
        return default


def parse_size(value: Any) -> float:
    n = parse_number(value, 5.0)
    return max(1.0, n)


def parse_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"yes", "true", "1", "y", "featured"}


def parse_list(value: Any) -> List[str]:
    s = str(value or "").strip()
    if not s:
        return []
    return [part.strip() for part in s.split(",") if part.strip()]


def ensure_hex(value: str, fallback: str = "#ff1447") -> str:
    s = str(value or "").strip()
    if not s:
        return fallback
    if not s.startswith("#"):
        s = "#" + s
    if re.fullmatch(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", s):
        return s.lower()
    return fallback


def safe_text(value: Any) -> str:
    return str(value or "").strip()


def build_payload(cluster_rows: List[Dict[str, str]], toc_rows: List[Dict[str, str]]) -> Tuple[Dict[str, Any], List[str]]:
    warnings: List[str] = []

    clusters: List[Dict[str, Any]] = []
    cluster_by_name: Dict[str, Dict[str, Any]] = {}

    for idx, row in enumerate(cluster_rows):
        name = get_value(row, ["Name", "Cluster", "Cluster Name"])
        if not name:
            warnings.append(f"Skipping cluster row {idx + 2}: missing Name.")
            continue
        color = ensure_hex(get_value(row, ["Hex Code Color", "Color", "Hex", "Hex Color"]))
        cluster = {
            "name": name,
            "coverUrl": get_value(row, ["Cover URL", "Cover", "Image URL", "Image"]),
            "description": get_value(row, ["Description", "Desc"]),
            "color": color,
            "order": len(clusters),
        }
        clusters.append(cluster)
        cluster_by_name[name] = cluster

    if not clusters:
        warnings.append("No clusters found. The output will still render, but it will be sad and empty.")

    entries: List[Dict[str, Any]] = []
    ids_seen: set[str] = set()

    for idx, row in enumerate(toc_rows):
        entry_id = get_value(row, ["ID", "Id", "id"])
        name = get_value(row, ["Name", "Title"])
        cluster_name = get_value(row, ["Cluster", "Tags"])
        if not entry_id and not name:
            warnings.append(f"Skipping TOC row {idx + 2}: missing ID and Name.")
            continue
        if not entry_id:
            entry_id = name
        if not name:
            name = entry_id
        if entry_id in ids_seen:
            warnings.append(f"Duplicate TOC ID found: {entry_id}")
        ids_seen.add(entry_id)
        if cluster_name and cluster_name not in cluster_by_name:
            warnings.append(f"TOC entry '{name}' uses unknown cluster '{cluster_name}'.")
        if not cluster_name:
            cluster_name = "(unclustered)"

        table_row = {}
        for k, v in row.items():
            if norm(k) in IGNORE_TABLE_COLUMNS:
                continue
            table_row[k] = v

        entries.append({
            "id": entry_id,
            "name": name,
            "cluster": cluster_name,
            "description": get_value(row, ["Description", "Desc"]),
            "characters": parse_list(get_value(row, ["Characters"])),
            "size": parse_size(get_value(row, ["Size", "Value"])),
            "xRelativity": parse_number(get_value(row, ["(X) Relativity", "X", "Relativity"]), 0.0),
            "yRelatability": parse_number(get_value(row, ["(Y) Relatability", "Y", "Relatability"]), 0.0),
            "zDepth": parse_number(get_value(row, ["(Z) Depth", "Z", "Depth"]), 0.0),
            "collisions": parse_list(get_value(row, ["Collisions", "Collision"])),
            "contentUrl": get_value(row, ["Content URL", "URL", "Url", "Link"]),
            "coverUrl": get_value(row, ["Cover URL", "Cover"]),
            "featured": parse_bool(get_value(row, ["Featured"])),
            "tableRow": table_row,
        })

    cluster_names_in_entries = {e["cluster"] for e in entries}
    for cluster in clusters:
        if cluster["name"] not in cluster_names_in_entries:
            warnings.append(f"Cluster has no TOC entries: {cluster['name']}")

    # Add any orphan clusters to keep the graph renderable.
    for orphan in sorted(cluster_names_in_entries - set(cluster_by_name)):
        clusters.append({
            "name": orphan,
            "coverUrl": "",
            "description": "Cluster found in SRC_toc.csv but not SRC_clusters.csv.",
            "color": "#999999",
            "order": len(clusters),
        })

    payload = {
        "title": "INTO THE POPPYVERSE",
        "generatedFrom": {
            "clusters": DEFAULT_CLUSTER_CSV,
            "toc": DEFAULT_TOC_CSV,
        },
        "clusters": clusters,
        "entries": entries,
        "warnings": warnings,
    }
    return payload, warnings


def script_json(payload: Dict[str, Any]) -> str:
    # Safe for embedding in a normal <script> tag.
    raw = json.dumps(payload, ensure_ascii=False, indent=2)
    return raw.replace("</", "<\\/")


def generate_html(payload: Dict[str, Any]) -> str:
    data_json = script_json(payload)
    warning_comment = "\n".join(f"  - {w}" for w in payload.get("warnings", [])) or "  - none"
    nav_css = common_nav_css()
    nav_html = common_nav_html("3d")

    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Into the Poppyverse — 3D Map</title>
  <link rel=\"icon\" href='data:image/svg+xml,<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 64 64\"><text y=\"50%\" x=\"50%\" dominant-baseline=\"middle\" text-anchor=\"middle\" font-size=\"52\">🌷</text></svg>'>
  <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">
  <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>
  <link href=\"https://fonts.googleapis.com/css2?family=Michroma&display=swap\" rel=\"stylesheet\">
  <!--
  Generated by build_3d_map.py.
  Source warnings:
{html.escape(warning_comment)}
  -->
  <style>
    :root {{
      --poppy-red: #ff1447;
      --panel: rgba(8, 8, 15, .86);
      --panel-strong: rgba(8, 8, 15, .96);
      --line: rgba(255,255,255,.22);
      --text: rgba(255,255,255,.94);
      --muted: rgba(255,255,255,.68);
    }}
    * {{ box-sizing: border-box; }}
{nav_css}
    html, body {{
      margin: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: #08080f;
      color: var(--text);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif;
    }}
    #bg {{
      position: fixed;
      inset: 0;
      z-index: 0;
      background:
        radial-gradient(circle at 20% 20%, rgba(255,20,71,.22), transparent 26%),
        radial-gradient(circle at 80% 30%, rgba(160,90,255,.16), transparent 28%),
        linear-gradient(135deg, #07070e, #11111d 50%, #07070e);
      filter: saturate(1.1) contrast(1.08);
    }}
    #bg::after {{
      content: \"\";
      position: absolute;
      inset: 0;
      background-image:
        linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px);
      background-size: 52px 52px;
      mask-image: radial-gradient(circle at center, black, transparent 75%);
    }}
    #g {{ position: fixed; inset: 0; z-index: 1; }}
    #hud {{ position: fixed; inset: 0; z-index: 10; pointer-events: none; }}
    #topbar {{
      display: grid;
      grid-template-columns: minmax(300px, 1fr) auto;
      gap: 18px;
      align-items: start;
      padding: 68px 18px 60px;
      background: linear-gradient(to bottom, rgba(0,0,0,.68), rgba(0,0,0,0));
    }}
    #title {{
      margin: 0;
      font-family: 'Michroma', sans-serif;
      font-size: clamp(18px, 2.1vw, 28px);
      letter-spacing: 2px;
      color: var(--poppy-red);
      text-shadow: 0 0 14px rgba(255,20,71,.72);
    }}
    #subtitle {{ margin: 6px 0 0; color: var(--muted); font-size: 13px; max-width: 720px; }}
    #legend {{
      pointer-events: auto;
      width: min(390px, 35vw);
      max-height: calc(100vh - 36px);
      overflow: hidden;
      background: rgba(0,0,0,.46);
      border: 1px solid var(--line);
      border-radius: 14px;
      backdrop-filter: blur(8px);
      box-shadow: 0 16px 40px rgba(0,0,0,.28);
    }}
    #legend.collapsed .legend-body {{ display: none; }}
    #legend-toggle {{
      margin: 0;
      padding: 10px 13px;
      cursor: pointer;
      user-select: none;
      font-size: 13px;
      font-weight: 800;
      letter-spacing: .7px;
    }}
    .legend-body {{ padding: 0 13px 12px; max-height: 76vh; overflow-y: auto; }}
    .legend-row {{ display: grid; grid-template-columns: 14px 1fr; gap: 9px; margin: 10px 0; align-items: start; }}
    .legend-swatch {{ width: 13px; height: 13px; border-radius: 5px; margin-top: 2px; border: 1px solid rgba(255,255,255,.3); }}
    .legend-name {{ font-size: 13px; font-weight: 800; }}
    .legend-desc {{ margin-top: 2px; font-size: 11px; color: var(--muted); line-height: 1.35; }}
    #hover-tip {{
      position: fixed;
      left: 18px;
      bottom: 78px;
      z-index: 14;
      opacity: 0;
      transform: translateY(6px);
      transition: opacity .14s ease, transform .14s ease;
      font-family: 'Michroma', sans-serif;
      font-size: clamp(15px, 2vw, 23px);
      letter-spacing: 1.2px;
      text-transform: uppercase;
      text-shadow: 0 0 18px rgba(0,0,0,.92);
      pointer-events: none;
      max-width: min(720px, calc(100vw - 420px));
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    #hover-tip.visible {{ opacity: 1; transform: translateY(0); }}
    #static-link-bar {{
      position: fixed;
      left: 18px;
      bottom: 18px;
      z-index: 13;
      pointer-events: auto;
      padding: 9px 12px;
      border-radius: 12px;
      background: rgba(0,0,0,.55);
      border: 1px solid var(--line);
      color: #fff;
      font: 13px/1.35 sans-serif;
      backdrop-filter: blur(6px);
      box-shadow: 0 0 18px rgba(0,0,0,.45);
      max-width: 520px;
    }}
    #static-link-bar a {{ color: var(--poppy-red); font-weight: 800; text-decoration: underline; }}
    #axis-explainer {{
      position: fixed;
      right: 18px;
      bottom: 18px;
      z-index: 12;
      color: white;
      text-align: right;
      font-size: 10px;
      line-height: 1.45;
      letter-spacing: .8px;
      pointer-events: none;
      text-shadow: 0 0 10px rgba(0,0,0,.9);
    }}
    #drawer {{
      position: fixed;
      top: 0;
      right: 0;
      z-index: 30;
      width: min(640px, 94vw);
      height: 100vh;
      transform: translateX(105%);
      transition: transform .22s ease;
      background: var(--panel-strong);
      border-left: 2px solid var(--drawer-accent, var(--poppy-red));
      box-shadow: -22px 0 60px rgba(0,0,0,.52), 0 0 28px color-mix(in srgb, var(--drawer-accent, var(--poppy-red)) 38%, transparent);
      pointer-events: auto;
      display: flex;
      flex-direction: column;
    }}
    #drawer.open {{ transform: translateX(0); }}
    .drawer-cover {{
      min-height: 156px;
      background-position: center;
      background-size: cover;
      position: relative;
      border-bottom: 1px solid var(--line);
    }}
    .drawer-cover::after {{
      content: \"\";
      position: absolute;
      inset: 0;
      background: linear-gradient(180deg, color-mix(in srgb, var(--drawer-accent, var(--poppy-red)) 55%, transparent), rgba(0,0,0,.74));
    }}
    .drawer-head {{ position: relative; z-index: 1; padding: 18px 20px; margin-top: auto; }}
    #drawer-title {{ margin: 0; font-family: 'Michroma', sans-serif; font-size: 22px; color: #fff; text-shadow: 0 0 14px rgba(0,0,0,.8); }}
    #drawer-cluster {{ display: inline-block; margin-top: 9px; padding: 4px 8px; border-radius: 8px; background: var(--drawer-accent, var(--poppy-red)); font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: .7px; }}
    #drawer-close {{
      position: absolute;
      top: 14px;
      right: 14px;
      z-index: 2;
      width: 34px;
      height: 34px;
      border-radius: 11px;
      border: 1px solid rgba(255,255,255,.25);
      background: rgba(255,255,255,.10);
      color: white;
      font-weight: 900;
      cursor: pointer;
    }}
    #drawer-body {{ overflow-y: auto; padding: 16px 20px 24px; }}
    .meta-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 9px; margin-bottom: 14px; }}
    .meta-box {{ border: 1px solid rgba(255,255,255,.15); background: rgba(255,255,255,.055); border-radius: 12px; padding: 10px; }}
    .meta-label {{ color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: .6px; }}
    .meta-value {{ margin-top: 2px; font-size: 16px; font-weight: 900; }}
    .drawer-section {{ margin: 14px 0; }}
    .drawer-section h3 {{ margin: 0 0 7px; font-size: 12px; color: var(--drawer-accent, var(--poppy-red)); text-transform: uppercase; letter-spacing: .8px; }}
    .drawer-section p {{ margin: 0; line-height: 1.48; color: rgba(255,255,255,.88); }}
    .pill-row {{ display: flex; flex-wrap: wrap; gap: 7px; }}
    .pill {{ padding: 5px 8px; border-radius: 999px; background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.14); font-size: 12px; }}
    .button-row {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }}
    .action-link {{ display: inline-block; border: 2px solid var(--drawer-accent, var(--poppy-red)); color: white; background: var(--drawer-accent, var(--poppy-red)); border-radius: 10px; padding: 8px 12px; font-size: 12px; font-weight: 900; text-decoration: none; }}
    .action-link:hover {{ background: transparent; }}
    .muted {{ color: var(--muted); }}
    #warning-panel {{
      position: fixed;
      left: 18px;
      top: 92px;
      z-index: 18;
      pointer-events: auto;
      max-width: 520px;
      background: rgba(20, 12, 12, .76);
      border: 1px solid rgba(255,255,255,.18);
      border-radius: 14px;
      padding: 10px 12px;
      font-size: 12px;
      color: rgba(255,255,255,.82);
      display: none;
    }}
    #warning-panel.visible {{ display: block; }}
    @media (max-width: 850px) {{
      #topbar {{ grid-template-columns: 1fr; }}
      #legend {{ width: min(500px, calc(100vw - 36px)); justify-self: start; }}
      #hover-tip {{ max-width: calc(100vw - 36px); }}
      #axis-explainer {{ display: none; }}
      .meta-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  {nav_html}
  <div id=\"bg\"></div>
  <div id=\"g\"></div>

  <div id=\"hud\">
    <div id=\"topbar\">
      <div>
        <h1 id=\"title\">INTO THE POPPYVERSE</h1>
        <p id=\"subtitle\">A generated 3D story map from <strong>SRC_clusters.csv</strong> and <strong>SRC_toc.csv</strong>. Click a node to inspect the damage.</p>
      </div>
      <div id=\"legend\" class=\"collapsed\">
        <h3 id=\"legend-toggle\">Multiverse Color Legend ▸</h3>
        <div class=\"legend-body\" id=\"legend-body\"></div>
      </div>
    </div>
    <div id=\"warning-panel\"></div>
    <div id=\"hover-tip\"></div>
    <div id=\"static-link-bar\">Use the top bubble bar to jump between the calmer 2D board, this haunted 3D snow globe, and the Tumblr archive dump.</div>
    <div id=\"axis-explainer\">
      <div><strong>MULTIVERSE POSITIONING SYSTEM</strong></div>
      <div><strong>QUANTUM ENTANGLEMENT:</strong> contained → meta bleed</div>
      <div><strong>EMOTIONAL GRAVITY:</strong> light ↓ heavy</div>
      <div><strong>CLUSTERS:</strong> stacked through map-space</div>
    </div>
  </div>

  <aside id=\"drawer\" aria-hidden=\"true\">
    <button id=\"drawer-close\" type=\"button\" aria-label=\"Close details\">✕</button>
    <div class=\"drawer-cover\" id=\"drawer-cover\">
      <div class=\"drawer-head\">
        <h2 id=\"drawer-title\"></h2>
        <span id=\"drawer-cluster\"></span>
      </div>
    </div>
    <div id=\"drawer-body\"></div>
  </aside>

  <script src=\"https://unpkg.com/three@0.148.0/build/three.min.js\"></script>
  <script src=\"https://unpkg.com/three@0.148.0/examples/js/controls/OrbitControls.js\"></script>
  <script src=\"https://unpkg.com/3d-force-graph@1.72.0/dist/3d-force-graph.min.js\"></script>

  <script>
  'use strict';
  const POPPY_DATA = {data_json};

  const CLUSTER_SPREAD = 150;
  const DEPTH_SCALE = 35;
  const REL_SCALE = 40;
  const NODE_SCATTER = 50;

  let Graph = null;
  let selectedNode = null;
  let hoveredNode = null;
  let lastHovered = null;

  const clusterByName = new Map(POPPY_DATA.clusters.map(c => [c.name, c]));
  const nodeById = new Map();
  const nodeByNum = new Map();

  function escapeHtml(value) {{
    return String(value ?? '').replace(/[&<>\"']/g, ch => ({{
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '\"': '&quot;', "'": '&#39;'
    }}[ch]));
  }}

  function safeUrl(value) {{
    const s = String(value || '').trim();
    if (!s) return '';
    if (/^(https?:|mailto:)/i.test(s)) return s;
    return '';
  }}

  function hash32(str) {{
    let h = 0;
    str = String(str || '');
    for (let i = 0; i < str.length; i++) {{ h = ((h << 5) - h) + str.charCodeAt(i); h |= 0; }}
    return Math.abs(h);
  }}

  function rand(seed) {{
    const x = Math.sin(seed++) * 10000;
    return x - Math.floor(x);
  }}

  function makeGlowSprite(colorHex) {{
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 128;
    const ctx = canvas.getContext('2d');
    const grad = ctx.createRadialGradient(64,64,0, 64,64,64);
    grad.addColorStop(0, colorHex);
    grad.addColorStop(.5, colorHex + '88');
    grad.addColorStop(1, colorHex + '00');
    ctx.fillStyle = grad;
    ctx.fillRect(0,0,128,128);
    const tex = new THREE.CanvasTexture(canvas);
    return new THREE.Sprite(new THREE.SpriteMaterial({{ map: tex, transparent: true, depthWrite: false }}));
  }}

  function resetNodeVisual(node) {{
    if (!node || !node.__glow) return;
    node.__hovered = false;
    const s = node.__idleSize * 0.98;
    node.__glow.scale.set(s, s, 1);
    node.__glow.material.opacity = 0.32;
  }}

  function setHighlightedNode(node) {{
    if (!node || !node.__glow) return;
    node.__hovered = true;
    const r = Math.min(node.__idleSize, 24);
    node.__glow.scale.set(r, r, 1);
    node.__glow.material.opacity = 0.85;
  }}

  function showHoverTip(node) {{
    const el = document.getElementById('hover-tip');
    if (!node || selectedNode) {{
      el.classList.remove('visible');
      el.textContent = '';
      return;
    }}
    el.textContent = node.name || node.id;
    el.style.color = node.color || '#ff1447';
    el.classList.add('visible');
  }}

  function hideHoverTip() {{
    const el = document.getElementById('hover-tip');
    el.classList.remove('visible');
    el.textContent = '';
  }}

  function resolveCollisionName(raw) {{
    const s = String(raw || '').trim();
    if (!s) return null;
    let target = null;
    const num = Number(s);
    if (Number.isFinite(num)) target = nodeByNum.get(num);
    if (!target) target = nodeById.get(s);
    return target ? (target.name || target.id) : s;
  }}

  function openDrawer(node) {{
    selectedNode = node;
    hideHoverTip();
    setHighlightedNode(node);

    const cluster = clusterByName.get(node.cluster) || {{ name: node.cluster, color: node.color || '#ff1447', description: '' }};
    const accent = cluster.color || node.color || '#ff1447';
    const drawer = document.getElementById('drawer');
    const cover = document.getElementById('drawer-cover');

    drawer.style.setProperty('--drawer-accent', accent);
    document.getElementById('drawer-title').textContent = node.name || node.id;
    document.getElementById('drawer-cluster').textContent = node.cluster;

    const coverUrl = safeUrl(node.coverUrl) || safeUrl(cluster.coverUrl);
    if (coverUrl) {{
      cover.style.backgroundImage = `linear-gradient(180deg, color-mix(in srgb, ${{accent}} 55%, transparent), rgba(0,0,0,.72)), url('${{coverUrl.replace(/'/g, "%27")}}')`;
    }} else {{
      cover.style.backgroundImage = `linear-gradient(135deg, ${{accent}}, rgba(0,0,0,.72))`;
    }}

    const collisions = (node.collisions || []).map(resolveCollisionName).filter(Boolean);
    const chars = node.characters || [];
    const url = safeUrl(node.contentUrl);

    const body = document.getElementById('drawer-body');
    body.innerHTML = `
      <div class=\"meta-grid\">
        <div class=\"meta-box\"><div class=\"meta-label\">Relativity / X</div><div class=\"meta-value\">${{escapeHtml(node.xRelativity)}}</div></div>
        <div class=\"meta-box\"><div class=\"meta-label\">Depth / Z</div><div class=\"meta-value\">${{escapeHtml(node.zDepth)}}</div></div>
        <div class=\"meta-box\"><div class=\"meta-label\">Size</div><div class=\"meta-value\">${{escapeHtml(node.size)}}</div></div>
      </div>
      ${{cluster.description ? `<section class=\"drawer-section\"><h3>Cluster Description</h3><p>${{escapeHtml(cluster.description)}}</p></section>` : ''}}
      ${{node.description ? `<section class=\"drawer-section\"><h3>Entry Description</h3><p>${{escapeHtml(node.description)}}</p></section>` : ''}}
      ${{chars.length ? `<section class=\"drawer-section\"><h3>Characters</h3><div class=\"pill-row\">${{chars.map(c => `<span class=\"pill\">${{escapeHtml(c)}}</span>`).join('')}}</div></section>` : ''}}
      ${{collisions.length ? `<section class=\"drawer-section\"><h3>Collisions</h3><div class=\"pill-row\">${{collisions.map(c => `<span class=\"pill\">${{escapeHtml(c)}}</span>`).join('')}}</div></section>` : ''}}
      <div class=\"button-row\">
        ${{url ? `<a class=\"action-link\" href=\"${{escapeHtml(url)}}\" target=\"_blank\" rel=\"noopener\">READ MORE</a>` : `<span class=\"muted\">Content link not ready.</span>`}}
      </div>
    `;

    drawer.classList.add('open');
    drawer.setAttribute('aria-hidden', 'false');
  }}

  function closeDrawer() {{
    document.getElementById('drawer').classList.remove('open');
    document.getElementById('drawer').setAttribute('aria-hidden', 'true');
    if (selectedNode) resetNodeVisual(selectedNode);
    selectedNode = null;
  }}

  function makeTextSprite(text, x, y, z, scale = 120) {{
    const c = document.createElement('canvas');
    c.width = 1024;
    c.height = 256;
    const ctx = c.getContext('2d');
    ctx.clearRect(0, 0, c.width, c.height);
    const str = String(text);
    let fontSize = 96;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#ffffff';
    while (fontSize > 24) {{
      ctx.font = `bold ${{fontSize}}px Arial`;
      if (ctx.measureText(str).width <= c.width - 80) break;
      fontSize -= 4;
    }}
    ctx.font = `bold ${{fontSize}}px Arial`;
    ctx.shadowBlur = 12;
    ctx.shadowColor = 'rgba(0,0,0,.9)';
    ctx.fillText(str, c.width / 2, c.height / 2);
    const tex = new THREE.CanvasTexture(c);
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({{ map: tex, transparent: true, depthWrite: false }}));
    sprite.scale.set(scale, scale * 0.25, 1);
    sprite.position.set(x, y, z);
    return sprite;
  }}

  function addAxes(scene, nodes) {{
    if (!nodes.length) return {{ axisZ: -120 }};
    let minZ = Infinity;
    nodes.forEach(n => {{ if (n.z < minZ) minZ = n.z; }});
    const AXIS_Z = Number.isFinite(minZ) ? minZ - 120 : -120;

    const axisMat = new THREE.LineBasicMaterial({{ color: 0xffffff, transparent: true, opacity: 0.72 }});
    const tickMat = new THREE.LineBasicMaterial({{ color: 0xffffff, transparent: true, opacity: 0.48 }});
    const relToX = v => v * REL_SCALE;
    const depToY = v => -v * DEPTH_SCALE;
    const x0 = relToX(0) - 40;
    const x1 = relToX(10) + 40;
    const y0 = depToY(10) - 40;
    const y1 = depToY(0) + 40;

    scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(x0, 0, AXIS_Z), new THREE.Vector3(x1, 0, AXIS_Z)]), axisMat));
    scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, y0, AXIS_Z), new THREE.Vector3(0, y1, AXIS_Z)]), axisMat));

    scene.add(makeTextSprite('QUANTUM ENTANGLEMENT', (x0 + x1) / 2, y0 - 28, AXIS_Z, 300));
    scene.add(makeTextSprite('EMOTIONAL GRAVITY', x0 - 32, (y0 + y1) / 2, AXIS_Z, 300));

    for (let i = 0; i <= 10; i++) {{
      const rx = relToX(i);
      scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(rx, 0, AXIS_Z), new THREE.Vector3(rx, -10, AXIS_Z)]), tickMat));
      scene.add(makeTextSprite(i, rx, -34, AXIS_Z, 70));

      const dy = depToY(i);
      scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, dy, AXIS_Z), new THREE.Vector3(-10, dy, AXIS_Z)]), tickMat));
      scene.add(makeTextSprite(i, -55, dy, AXIS_Z, 70));
    }}
    return {{ axisZ: AXIS_Z }};
  }}

  function addBoundingCube(scene, nodes) {{
    let minX = Infinity, minY = Infinity, minZ = Infinity;
    let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
    nodes.forEach(n => {{
      minX = Math.min(minX, n.x); maxX = Math.max(maxX, n.x);
      minY = Math.min(minY, n.y); maxY = Math.max(maxY, n.y);
      minZ = Math.min(minZ, n.z); maxZ = Math.max(maxZ, n.z);
    }});
    if (!Number.isFinite(minX)) {{ minX = minY = minZ = -100; maxX = maxY = maxZ = 100; }}
    const pad = 45;
    minX -= pad; minY -= pad; minZ -= pad;
    maxX += pad; maxY += pad; maxZ += pad;
    const v = (x,y,z) => new THREE.Vector3(x,y,z);
    const pts = [
      v(minX,minY,minZ),v(maxX,minY,minZ), v(maxX,minY,minZ),v(maxX,maxY,minZ), v(maxX,maxY,minZ),v(minX,maxY,minZ), v(minX,maxY,minZ),v(minX,minY,minZ),
      v(minX,minY,maxZ),v(maxX,minY,maxZ), v(maxX,minY,maxZ),v(maxX,maxY,maxZ), v(maxX,maxY,maxZ),v(minX,maxY,maxZ), v(minX,maxY,maxZ),v(minX,minY,maxZ),
      v(minX,minY,minZ),v(minX,minY,maxZ), v(maxX,minY,minZ),v(maxX,minY,maxZ), v(maxX,maxY,minZ),v(maxX,maxY,maxZ), v(minX,maxY,minZ),v(minX,maxY,maxZ)
    ];
    const cube = new THREE.LineSegments(
      new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({{ color: 0xffffff, transparent: true, opacity: 0.26 }})
    );
    scene.add(cube);
    return {{ minX, minY, minZ, maxX, maxY, maxZ, cx: (minX+maxX)/2, cy: (minY+maxY)/2, cz: (minZ+maxZ)/2 }};
  }}

  function buildGraphData() {{
    const clusterOrder = POPPY_DATA.clusters.map(c => c.name);
    const clusterIndex = new Map(clusterOrder.map((name, idx) => [name, idx]));
    const nodes = POPPY_DATA.entries.map(entry => {{
      const cluster = clusterByName.get(entry.cluster) || {{ color: '#999999', order: clusterIndex.size }};
      const idx = clusterIndex.has(entry.cluster) ? clusterIndex.get(entry.cluster) : clusterIndex.size;
      const seed = hash32(entry.id + '|' + entry.cluster);
      const angle = rand(seed) * Math.PI * 2;
      const radius = rand(seed + 1) * NODE_SCATTER + 20;
      const x = (Number(entry.xRelativity) || 0) * REL_SCALE + Math.cos(angle) * radius;
      const y = -(Number(entry.zDepth) || 0) * DEPTH_SCALE;
      const z = idx * CLUSTER_SPREAD + Math.sin(angle) * radius;
      return {{ ...entry, color: cluster.color || '#ff1447', x, y, z, fx: x, fy: y, fz: z, val: Math.max(1, Number(entry.size) || 1) }};
    }});

    nodes.forEach(n => {{
      nodeById.set(String(n.id), n);
      const num = Number(n.id);
      if (Number.isFinite(num)) nodeByNum.set(num, n);
    }});

    const links = [];
    const added = new Set();
    function addLink(source, target) {{
      if (!source || !target || source.id === target.id) return;
      const ids = [String(source.id), String(target.id)].sort();
      const key = ids.join('::');
      if (added.has(key)) return;
      added.add(key);
      links.push({{ source: source.id, target: target.id, color: '#ffffff', width: 1.6 }});
    }}
    nodes.forEach(n => {{
      (n.collisions || []).forEach(raw => {{
        const s = String(raw).trim();
        const num = Number(s);
        const target = Number.isFinite(num) ? (nodeByNum.get(num) || nodeById.get(s)) : nodeById.get(s);
        addLink(n, target);
      }});
    }});
    return {{ nodes, links }};
  }}

  function renderLegend() {{
    const legend = document.getElementById('legend');
    const toggle = document.getElementById('legend-toggle');
    const body = document.getElementById('legend-body');
    body.innerHTML = POPPY_DATA.clusters.map(c => `
      <div class=\"legend-row\">
        <div class=\"legend-swatch\" style=\"background:${{escapeHtml(c.color)}}; box-shadow: 0 0 8px ${{escapeHtml(c.color)}}\"></div>
        <div>
          <div class=\"legend-name\" style=\"color:${{escapeHtml(c.color)}}\">${{escapeHtml(c.name)}}</div>
          ${{c.description ? `<div class=\"legend-desc\">${{escapeHtml(c.description)}}</div>` : ''}}
        </div>
      </div>
    `).join('');
    toggle.addEventListener('click', () => {{
      legend.classList.toggle('collapsed');
      toggle.textContent = legend.classList.contains('collapsed') ? 'Multiverse Color Legend ▸' : 'Multiverse Color Legend ▾';
    }});
  }}

  function renderWarnings() {{
    const warnings = POPPY_DATA.warnings || [];
    if (!warnings.length) return;
    const panel = document.getElementById('warning-panel');
    panel.innerHTML = `<strong>Source warnings</strong><br>${{warnings.slice(0, 5).map(escapeHtml).join('<br>')}}${{warnings.length > 5 ? '<br>…' : ''}}`;
    panel.classList.add('visible');
  }}

  function init() {{
    renderLegend();
    renderWarnings();
    document.getElementById('drawer-close').addEventListener('click', closeDrawer);
    document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeDrawer(); }});

    const {{ nodes, links }} = buildGraphData();
    const elem = document.getElementById('g');

    Graph = ForceGraph3D()(elem)
      .enablePointerInteraction(true)
      .graphData({{ nodes, links }})
      .showNavInfo(false)
      .d3Force('link', null)
      .d3Force('charge', null)
      .enableNodeDrag(false)
      .cooldownTicks(0)
      .nodeThreeObject(n => {{
        const colorHex = n.color || '#ff1447';
        const color = new THREE.Color(colorHex);
        const sizeVal = Math.max(1, Number(n.val) || 1);
        const s = 0.6 + sizeVal * 0.09;
        const core = new THREE.Mesh(
          new THREE.SphereGeometry(5, 24, 24),
          new THREE.MeshStandardMaterial({{ color, metalness: .12, roughness: .38 }})
        );
        core.scale.set(s, s, s);
        const glow = makeGlowSprite(colorHex);
        glow.raycast = () => {{}};
        glow.material.depthTest = false;
        glow.renderOrder = 10;
        const idleSize = Math.max(42, 5 * s * 5.4);
        glow.scale.set(idleSize * 0.98, idleSize * 0.98, 1);
        glow.material.opacity = 0.32;
        core.add(glow);
        n.__core = core;
        n.__glow = glow;
        n.__idleSize = idleSize;
        return core;
      }})
      .nodeLabel(() => '')
      .linkColor(l => l.color || '#ffffff')
      .linkWidth(l => l.width || 1.6)
      .linkOpacity(0.65)
      .onNodeHover((node, prev) => {{
        const prevNode = prev || lastHovered;
        if (prevNode && prevNode !== node && prevNode !== selectedNode) resetNodeVisual(prevNode);
        hoveredNode = node || null;
        lastHovered = hoveredNode;
        if (!hoveredNode) {{
          hideHoverTip();
          nodes.forEach(n => {{ if (n !== selectedNode) resetNodeVisual(n); }});
          return;
        }}
        showHoverTip(hoveredNode);
        setHighlightedNode(hoveredNode);
      }})
      .onNodeClick(node => openDrawer(node));

    const w = window.innerWidth;
    const h = window.innerHeight;
    const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    renderer.setSize(w, h);
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    Graph.renderer(renderer);
    Graph.width(w).height(h);
    Graph.backgroundColor('rgba(0,0,0,0)');

    const scene = Graph.scene();
    scene.background = null;
    scene.add(new THREE.AmbientLight(0xffffff, .36));
    const dir = new THREE.DirectionalLight(0xffffff, .7);
    dir.position.set(60, 80, 40);
    scene.add(dir);

    addAxes(scene, nodes);
    const cube = addBoundingCube(scene, nodes);

    const controls = Graph.controls();
    controls.enableRotate = true;
    controls.enablePan = true;
    controls.minDistance = 20;
    controls.maxDistance = 1400;
    controls.target.set(cube.cx, cube.cy, cube.cz);
    controls.update();

    const spanX = cube.maxX - cube.minX;
    const spanY = cube.maxY - cube.minY;
    const spanZ = cube.maxZ - cube.minZ;
    const diag = Math.max(spanX, spanY, spanZ);
    Graph.cameraPosition(
      {{ x: cube.cx - diag * 1.15, y: cube.cy + diag * 0.55, z: cube.cz + diag * 1.35 }},
      {{ x: cube.cx, y: cube.cy, z: cube.cz }},
      1000
    );

    renderer.setAnimationLoop(() => {{
      const t = performance.now() * 0.012;
      const pulse = 0.70 + 0.30 * (0.5 + 0.5 * Math.sin(t));
      if (hoveredNode && hoveredNode.__glow && hoveredNode !== selectedNode) hoveredNode.__glow.material.opacity = pulse;
      if (selectedNode && selectedNode.__glow) {{
        selectedNode.__glow.material.opacity = 0.62;
        const r = Math.min(selectedNode.__idleSize, 24);
        selectedNode.__glow.scale.set(r, r, 1);
      }}
      renderer.render(scene, Graph.camera());
    }});

    window.addEventListener('resize', () => {{
      const nw = window.innerWidth, nh = window.innerHeight;
      renderer.setSize(nw, nh);
      Graph.width(nw).height(nh);
    }});
  }}

  init();
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a static 3D Poppyverse map HTML from source CSVs.")
    parser.add_argument("--clusters", default=DEFAULT_CLUSTER_CSV, help="Path to SRC_clusters.csv")
    parser.add_argument("--toc", default=DEFAULT_TOC_CSV, help="Path to SRC_toc.csv")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_HTML, help="Output HTML path")
    args = parser.parse_args()

    cluster_path = Path(args.clusters)
    toc_path = Path(args.toc)
    output_path = Path(args.output)

    if not cluster_path.exists():
        raise FileNotFoundError(f"Cluster CSV not found: {cluster_path}")
    if not toc_path.exists():
        raise FileNotFoundError(f"TOC CSV not found: {toc_path}")

    cluster_rows = read_csv(cluster_path)
    toc_rows = read_csv(toc_path)
    payload, warnings = build_payload(cluster_rows, toc_rows)
    output_path.write_text(generate_html(payload), encoding="utf-8")

    print(f"Wrote {output_path}")
    print(f"Clusters: {len(payload['clusters'])}")
    print(f"Entries: {len(payload['entries'])}")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"  - {warning}")


if __name__ == "__main__":
    main()
