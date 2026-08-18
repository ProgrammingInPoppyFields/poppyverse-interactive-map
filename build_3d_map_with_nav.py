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
- Keep connection links if resolvable, but only render them when the "Show links"
  toggle is on (they're hidden by default, and toggle independently of the
  axes/frame via their own control next to "Show axes").
- Keep click drawer.
- Keep top nav.
- Keep Multiverse Color Legend.
- Do NOT show axes.
- Do NOT show axis labels.
  (The reference frame — axes through the origin, the 0,0,0 center marker, and
  the publish-divide plane at z=0 (separating published nodes (+Z) from
  unpublished nodes (-Z)) — is hidden by default, but can be revealed via the
  "Show axes" toggle at the bottom-left.)
- Do NOT show hover labels.
- Do NOT show HUD title/subtitle.
- Do NOT show content ratings in clicked cards.
- A glowing wireframe bounding box (the max reach of every axis) is hidden by
  default, revealed via the same "Show axes" toggle as the rest of the frame.
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


def parse_list(value: str, delimiter: str = ",") -> list[str]:
    value = str(value or "").strip()
    if not value:
        return []
    return [item.strip() for item in value.split(delimiter) if item.strip()]


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
            "characters": parse_list(get_first(row, ["Characters"]), delimiter=";"),
            "connections": parse_list(get_first(row, ["Connections", "Connection"])),
            "contentUrl": normalize_url(get_first(row, ["Content URL", "URL", "Url"])),
            "coverUrl": normalize_url(get_first(row, ["Cover URL", "Cover", "Image URL", "Image"])),
            "featured": parse_bool(get_first(row, ["Featured"])),
            "isIntro": "intro" in name.lower(),
            "isManga": name.strip().upper().startswith("[MANGA]"),
            "isMeta": name.strip().upper().startswith("[META]"),
            "isTrailer": name.strip().upper().startswith("[TRAILER]"),
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

        for raw_target in node["connections"]:
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
      --control-height: 42px;
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
      height: calc(var(--control-height) - 2px);
      box-sizing: border-box;
      display: flex;
      align-items: center;
      padding: 0 16px;
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

    .bottom-toggles {{
      position: fixed;
      bottom: 18px;
      left: 18px;
      z-index: 22;
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
    }}

    .axes-toggle {{
      display: flex;
      align-items: center;
      gap: 10px;
      height: var(--control-height);
      box-sizing: border-box;
      padding: 0 16px;
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
      display: inline-flex;
      align-items: center;
      justify-content: center;
      height: var(--control-height);
      box-sizing: border-box;
      padding: 0 22px;
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

    /* Narrow viewports: the four bottom controls can't sit side by side
       (the legend bar alone is 320px), so stack them centered -- legend on
       top, wormhole next, then the axes toggle, then the links toggle on
       the bottom. Each step is one control-height plus a 10px gap. The two
       toggles are forced into a column (rather than relying on flex-wrap)
       so this math stays exact instead of guessing whether they wrapped. */
    @media (max-width: 820px) {{
      .bottom-toggles {{
        left: 50%;
        right: auto;
        transform: translateX(-50%);
        bottom: 18px;
        flex-direction: column;
        align-items: center;
      }}

      .wormhole-btn {{
        bottom: calc(18px + 2 * (var(--control-height) + 10px));
      }}

      .legend {{
        left: 50%;
        right: auto;
        transform: translateX(-50%);
        bottom: calc(18px + 3 * (var(--control-height) + 10px));
        max-height: calc(100vh - var(--nav-height) - 190px);
      }}

      .legend-rows {{
        max-height: calc(100vh - var(--nav-height) - 230px);
      }}
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
      padding: calc(var(--nav-height) + 54px) 24px 22px;
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
      top: calc(var(--nav-height) + 10px);
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
      background: color-mix(in srgb, var(--active-color) 55%, #000);
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

    .coord-meters {{
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}

    .coord-meter-label {{
      display: flex;
      justify-content: space-between;
      margin-bottom: 6px;
      color: rgba(255, 255, 255, 0.78);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}

    .coord-meter-track {{
      height: 6px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.12);
      overflow: hidden;
    }}

    .coord-meter-fill {{
      height: 100%;
      border-radius: 999px;
      background: var(--active-color);
    }}

    .connection-link {{
      color: var(--active-color);
      text-decoration: none;
      border-bottom: 1px solid color-mix(in srgb, var(--active-color) 45%, transparent);
      transition: border-color 0.15s ease;
    }}

    .connection-link:hover {{
      border-bottom-color: var(--active-color);
    }}

    .tag-chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin: 0;
    }}

    .tag-chip {{
      display: inline-block;
      padding: 4px 9px;
      border-radius: 6px;
      background: color-mix(in srgb, var(--active-color) 18%, transparent);
      border: 1px solid color-mix(in srgb, var(--active-color) 45%, transparent);
      color: #fff;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.08em;
      line-height: 1.3;
      text-transform: uppercase;
      text-decoration: none;
      white-space: nowrap;
    }}

    a.tag-chip {{
      cursor: pointer;
      transition: background 0.15s ease, border-color 0.15s ease;
    }}

    a.tag-chip:hover {{
      background: color-mix(in srgb, var(--active-color) 34%, transparent);
      border-color: var(--active-color);
    }}

    .read-link {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 40px;
      padding: 10px 14px;
      border-radius: 5px;
      background: color-mix(in srgb, var(--active-color) 55%, #000);
      color: #fff;
      text-decoration: none;
      font-size: 12px;
      font-weight: 900;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }}

    @media (max-width: 760px) {{
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

  <div class="bottom-toggles">
    <label class="axes-toggle" for="axesToggle">
      <input type="checkbox" id="axesToggle" />
      <span class="axes-toggle-track"><span class="axes-toggle-thumb"></span></span>
      <span class="axes-toggle-label">Show axes</span>
    </label>
    <label class="axes-toggle" for="linksToggle">
      <input type="checkbox" id="linksToggle" />
      <span class="axes-toggle-track"><span class="axes-toggle-thumb"></span></span>
      <span class="axes-toggle-label">Show links</span>
    </label>
  </div>

  <a class="wormhole-btn" href="https://programminginpoppyfields.github.io/engine-codex/" target="_blank" rel="noopener">Wormhole</a>

  {data_blob}

  <script src="https://unpkg.com/three@0.148.0/build/three.min.js"></script>
  <script src="https://unpkg.com/3d-force-graph@1.72.0/dist/3d-force-graph.min.js"></script>

  <script>
    "use strict";

    // Loaded separately from THREE above: we build custom node meshes by hand.
    // 3d-force-graph bundles its own internal copy of Three.js too -- hence
    // the harmless "multiple instances of Three.js" console warning.
    // (CDN version-skew makes consolidating these unsafe -- see git history.)

    const DATA = JSON.parse(document.getElementById("poppy-data").textContent);

    // Simple 3D scatter layout, centered at 0,0,0. X/Y come straight from
    // Relativity/Relatability; Z's magnitude comes from Depth but its SIGN is
    // forced by publish status, so published/unpublished nodes always land on
    // opposite sides of the z=0 divide plane.
    const AXIS_MAX = 10;        // CSV metrics (Relativity / Relatability / Depth) are scored 0..10
    const AXIS_SCALE = 560;     // half-extent of the X/Y spread (bigger = dots spread further apart)
    const DEPTH_GAP = 70;       // minimum distance any node sits from the z=0 divide plane
    const DEPTH_SPAN = 560;     // additional Z distance added on top of DEPTH_GAP, scaled by Depth score
    const JITTER = 0.4;         // seeded spread so nodes with identical scores don't stack
    const POINT_JITTER = 70;    // absolute (Cartesian) units of random nudge -- breaks up the integer-rating grid into something organic

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
    let nodeById = new Map();

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

    // Many-stop gradient for a long, gradual falloff -- a simple 3-stop
    // gradient bands/edges visibly once rendered with AdditiveBlending
    // (used for every node's glow), so this is worth the extra stops.
    function makeSoftGlowSprite(colorHex) {{
      const canvas = document.createElement("canvas");
      canvas.width = 128;
      canvas.height = 128;

      const ctx = canvas.getContext("2d");
      const grad = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);

      grad.addColorStop(0, colorHex + "FF");
      grad.addColorStop(0.1, colorHex + "F0");
      grad.addColorStop(0.2, colorHex + "D8");
      grad.addColorStop(0.32, colorHex + "B4");
      grad.addColorStop(0.45, colorHex + "8A");
      grad.addColorStop(0.58, colorHex + "62");
      grad.addColorStop(0.7, colorHex + "40");
      grad.addColorStop(0.8, colorHex + "26");
      grad.addColorStop(0.9, colorHex + "12");
      grad.addColorStop(0.96, colorHex + "05");
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
      node.__glow.material.opacity = node.__idleOpacity != null ? node.__idleOpacity : 0.32;
    }}

    function setHighlightedNode(node) {{
      if (!node || !node.__glow) return;

      const r = Math.min(node.__idleSize, 22);
      node.__glow.scale.set(r, r, 1);
      const base = node.__idleOpacity != null ? node.__idleOpacity : 0.32;
      node.__glow.material.opacity = Math.min(1, base + 0.25);
    }}

    function renderList(items) {{
      if (!items || !items.length) return "<p>—</p>";
      return `<p>${{items.map(escapeHtml).join(", ")}}</p>`;
    }}

    function renderChips(items) {{
      if (!items || !items.length) return "<p>—</p>";
      const chips = items
        .map(item => `<span class="tag-chip">${{escapeHtml(item)}}</span>`)
        .join("");
      return `<div class="tag-chips">${{chips}}</div>`;
    }}

    function renderCoordMeters(node) {{
      const axes = [
        ["Relativity", node.xValue],
        ["Relatability", node.yValue],
        ["Depth", node.zValue]
      ];

      const rows = axes.map(([label, value]) => {{
        const v = Math.max(0, Math.min(AXIS_MAX, Number(value) || 0));
        const pct = (v / AXIS_MAX) * 100;
        return `
          <div class="coord-meter">
            <div class="coord-meter-label"><span>${{label}}</span><span>${{v}}/${{AXIS_MAX}}</span></div>
            <div class="coord-meter-track"><div class="coord-meter-fill" style="width:${{pct}}%"></div></div>
          </div>
        `;
      }}).join("");

      return `<div class="coord-meters">${{rows}}</div>`;
    }}

    function renderConnections(items) {{
      if (!items || !items.length) return "<p>—</p>";
      const chips = items.map(item => {{
        const label = escapeHtml(item.label || "");
        return item.id != null
          ? `<a class="tag-chip" href="#" data-connection-id="${{escapeHtml(String(item.id))}}">${{label}}</a>`
          : `<span class="tag-chip">${{label}}</span>`;
      }});
      return `<div class="tag-chips">${{chips.join("")}}</div>`;
    }}

    function openDrawer(node) {{
      if (selectedNode && selectedNode !== node) {{
        resetNodeVisual(selectedNode);
      }}

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
            ${{renderChips(node.subparts.split("/").map(s => s.trim()).filter(Boolean))}}
          </section>
        `
        : "";

      drawerBody.innerHTML = `
        ${{cover}}

        <section class="drawer-section">
          <h3>Description</h3>
          <p>${{escapeHtml(node.description || "No description yet.")}}</p>
        </section>

        <section class="drawer-section">
          <h3>Coordinates</h3>
          ${{renderCoordMeters(node)}}
        </section>

        ${{subpartsHtml}}

        <section class="drawer-section">
          <h3>Characters</h3>
          ${{renderChips(node.characters)}}
        </section>

        <section class="drawer-section">
          <h3>Connections</h3>
          ${{renderConnections(node.connectionLinks || [])}}
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
      nodeById = new Map(DATA.nodes.map(node => [String(node.id), node]));

      DATA.nodes.forEach(node => {{
        // --- Simple 3D scatter layout, centered on 0,0,0. ---
        // Cluster no longer affects position (it only colors the node):
        //   X <- (X) Relativity
        //   Y <- (Y) Relatability
        //   Z <- (Z) Depth magnitude, SIGNED by publish status (has a Content
        //        URL -> +Z, no Content URL -> -Z) so the two populations always
        //        land on opposite sides of the z=0 publish-divide plane.
        const seed = hash32(String(node.id) + "|" + String(node.cluster));

        // [TRAILER] nodes (YouTube trailers) aren't story content scored on
        // Relativity/Relatability/Depth -- they float freely through the
        // whole scene volume instead of sitting on those axes. Seeded so
        // they're stable across reloads, but otherwise untethered from the
        // coordinate system everything else is pinned to.
        if (node.isTrailer) {{
          node.x = (rand(seed + 10) - 0.5) * 2 * AXIS_SCALE;
          node.y = (rand(seed + 11) - 0.5) * 2 * AXIS_SCALE;
          node.z = (rand(seed + 12) - 0.5) * 2 * (DEPTH_GAP + DEPTH_SPAN);
          node.fx = node.x;
          node.fy = node.y;
          node.fz = node.z;
          node.val = node.size;
          return;
        }}

        // Normalize each metric to 0..1, then add a small seeded jitter so nodes
        // that share identical scores don't land on the exact same point.
        const relN   = Math.max(0, Math.min(1, node.xValue / AXIS_MAX));
        const relatN = Math.max(0, Math.min(1, node.yValue / AXIS_MAX));
        const depthN = Math.max(0, Math.min(1, node.zValue / AXIS_MAX));

        const published = Boolean(node.contentUrl);
        const zMag = DEPTH_GAP + DEPTH_SPAN * depthN * (1 + (rand(seed + 2) - 0.5) * JITTER);

        // Final absolute (Cartesian) jitter: a small per-node random nudge on each
        // axis so any dots that landed on identical coords still separate visibly.
        // Seeded off the node id, so it's stable across reloads (not Math.random).
        const jx = (rand(seed + 3) - 0.5) * 2 * POINT_JITTER;
        const jy = (rand(seed + 4) - 0.5) * 2 * POINT_JITTER;
        const jz = (rand(seed + 5) - 0.5) * 2 * POINT_JITTER;

        node.x = (relN - 0.5) * 2 * AXIS_SCALE * (1 + (rand(seed) - 0.5) * JITTER) + jx;
        node.y = (relatN - 0.5) * 2 * AXIS_SCALE * (1 + (rand(seed + 1) - 0.5) * JITTER) + jy;
        node.z = (published ? 1 : -1) * zMag + jz;

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

      // Build each node's connection list from the (already de-duped, undirected)
      // links so the drawer shows a connection on BOTH endpoints, not just the
      // node whose CSV cell happened to name the other. Each entry carries the
      // partner's id so clicking it opens that node's card in the drawer.
      DATA.nodes.forEach(node => {{ node.connectionLinks = []; }});
      DATA.links.forEach(link => {{
        const a = link.source;
        const b = link.target;
        if (typeof a !== "object" || typeof b !== "object") return;
        a.connectionLinks.push({{ label: b.label, url: b.contentUrl, id: b.id }});
        b.connectionLinks.push({{ label: a.label, url: a.contentUrl, id: a.id }});
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

      drawerBody.addEventListener("click", event => {{
        const chip = event.target.closest(".tag-chip[data-connection-id]");
        if (!chip) return;
        event.preventDefault();
        const target = nodeById.get(chip.dataset.connectionId);
        if (target) openDrawer(target);
      }});

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
          // Push saturation up so hue reads clearly regardless of lighting --
          // guarantees vividness at the data level instead of hoping the
          // light rig doesn't wash it out.
          {{
            const hsl = {{ h: 0, s: 0, l: 0 }};
            color.getHSL(hsl);
            color.setHSL(hsl.h, Math.min(1, hsl.s * 1.35), hsl.l);
          }}

          // EXPERIMENTAL: [MANGA] nodes get a faceted, low-poly core instead of
          // a smooth sphere -- a paneled silhouette instead of an orbital
          // accessory, so it doesn't compete with the isIntro ring treatment.
          // [META] nodes get a cube -- a distinct, unmissable silhouette for
          // "you're looking at authorial commentary, not a story," even
          // though the node itself now lives in its story's own cluster.
          // [TRAILER] nodes get a low-poly "rock" core (the comet head) --
          // the tail sprites added below are what actually sell the comet
          // read, this is just something for them to trail off of.
          const core = new THREE.Mesh(
            node.isManga ? new THREE.TetrahedronGeometry(5.5, 0) :
            node.isMeta ? new THREE.BoxGeometry(8, 8, 8) :
            node.isTrailer ? new THREE.IcosahedronGeometry(11, 0) :
            new THREE.SphereGeometry(5, 24, 24),
            new THREE.MeshStandardMaterial({{
              color,
              metalness: 0.03,
              roughness: 0.5,
              flatShading: node.isManga || node.isTrailer
            }})
          );

          const sizeVal = Number(node.size) || 1;
          // Experimental: pure proportional linear scale (no baseline offset),
          // so scale is directly proportional to Size instead of Size + a floor.
          // [TRAILER] nodes get a flat multiplier on top -- they need to read
          // as "notice me" even at low Size values, since there's no axis
          // score driving their prominence the way there is for story nodes.
          const scale = sizeVal * 0.32 * (node.isTrailer ? 1.8 : 1);
          core.scale.set(scale, scale, scale);

          if (node.isManga) {{
            // Random seeded orientation so the tetrahedrons don't all point
            // the same way -- every other node is rotationally symmetric
            // enough not to need this, but a flat-shaded pyramid very visibly
            // isn't.
            const rotSeed = hash32(String(node.id) + "|mangaRot");
            core.rotation.x = rand(rotSeed) * Math.PI * 2;
            core.rotation.y = rand(rotSeed + 1) * Math.PI * 2;
            core.rotation.z = rand(rotSeed + 2) * Math.PI * 2;
          }}

          if (node.isMeta) {{
            // Same idea as the manga rotation jitter -- a grid of perfectly
            // axis-aligned cubes reads as a bug, not a design choice.
            const rotSeed = hash32(String(node.id) + "|metaRot");
            core.rotation.x = rand(rotSeed) * Math.PI * 2;
            core.rotation.y = rand(rotSeed + 1) * Math.PI * 2;
            core.rotation.z = rand(rotSeed + 2) * Math.PI * 2;
          }}

          if (node.isTrailer) {{
            const rotSeed = hash32(String(node.id) + "|trailerRot");
            core.rotation.x = rand(rotSeed) * Math.PI * 2;
            core.rotation.y = rand(rotSeed + 1) * Math.PI * 2;
            core.rotation.z = rand(rotSeed + 2) * Math.PI * 2;

            // Comet tail: a staggered chain of shrinking, fading additive
            // glow puffs trailing off in one seeded-random direction. Each
            // puff is a camera-facing billboard, but the fixed offsets
            // between them still read as a directional streak from any
            // viewing angle -- cheaper and simpler than a real particle
            // system, and consistent with how every other glow in this file
            // is a hand-placed sprite rather than a postprocessing effect.
            const tailSeed = hash32(String(node.id) + "|trailerTail");
            const tailDir = new THREE.Vector3(
              rand(tailSeed) - 0.5,
              rand(tailSeed + 1) - 0.5,
              rand(tailSeed + 2) - 0.5
            ).normalize();

            const TAIL_STEPS = 7;
            for (let i = 1; i <= TAIL_STEPS; i++) {{
              const t = i / TAIL_STEPS;
              const puff = makeSoftGlowSprite(colorHex);
              puff.raycast = () => {{}};
              puff.material.depthTest = false;
              puff.material.blending = THREE.AdditiveBlending;
              puff.renderOrder = 8;
              const puffSize = (1 - t * 0.8) * 34;
              puff.scale.set(puffSize, puffSize, 1);
              puff.material.opacity = (1 - t) * 0.55;
              puff.position.copy(tailDir).multiplyScalar(-t * 46);
              core.add(puff);
            }}
          }}

          if (node.isIntro) {{
            const ringGlowColor = new THREE.Color(colorHex).lerp(new THREE.Color(0xffffff), 0.35);

            const ring = new THREE.Mesh(
              new THREE.RingGeometry(44, 50, 48),
              new THREE.MeshBasicMaterial({{
                color: ringGlowColor,
                side: THREE.DoubleSide,
                transparent: true,
                opacity: 0.26,
                depthWrite: false,
                blending: THREE.AdditiveBlending
              }})
            );

            // Wider, fainter halo layered behind the crisp ring to fake a glow/bloom
            // (there's no postprocessing pipeline here, so this is done by hand).
            const ringHalo = new THREE.Mesh(
              new THREE.RingGeometry(39, 55, 48),
              new THREE.MeshBasicMaterial({{
                color: ringGlowColor,
                side: THREE.DoubleSide,
                transparent: true,
                opacity: 0.07,
                depthWrite: false,
                blending: THREE.AdditiveBlending
              }})
            );

            const ringSeed = hash32(String(node.id) + "|ring");
            const tiltJitter = (rand(ringSeed) - 0.5) * (Math.PI / 2.5);
            const spin = rand(ringSeed + 1) * Math.PI * 2;
            const roll = (rand(ringSeed + 2) - 0.5) * (Math.PI / 3);
            ring.rotation.x = ringHalo.rotation.x = Math.PI / 2.6 + tiltJitter;
            ring.rotation.y = ringHalo.rotation.y = spin;
            ring.rotation.z = ringHalo.rotation.z = roll;
            core.add(ringHalo);
            core.add(ring);
          }}

          const glow = makeSoftGlowSprite(colorHex);
          glow.raycast = () => {{}};
          glow.material.depthTest = false;
          glow.renderOrder = 10;

          const idleSize = Math.max(22, 5 * scale * 5.4 * 1.3) * (node.isTrailer ? 1.5 : node.isIntro ? 1.0 : 1);
          const idleOpacity = node.isTrailer ? 0.5 : node.isIntro ? 0.19 : 0.38;
          glow.scale.set(idleSize * 0.98, idleSize * 0.98, 1);
          glow.material.opacity = idleOpacity;
          // Normal alpha blending just overlays a translucent patch, which reads
          // as small/dim on a dark background. Additive blending actually adds
          // light, which is what makes something look like it's glowing. The
          // soft multi-stop gradient (vs. the old 3-stop one) keeps it from
          // banding now that every node uses additive blending.
          glow.material.blending = THREE.AdditiveBlending;
          core.add(glow);

          if (node.isIntro) {{
            // A second, much wider and fainter additive sprite so the light
            // diffuses outward instead of staying a small hot patch.
            const megaGlow = makeSoftGlowSprite(colorHex);
            megaGlow.raycast = () => {{}};
            megaGlow.material.depthTest = false;
            megaGlow.material.blending = THREE.AdditiveBlending;
            megaGlow.material.opacity = 0.07;
            megaGlow.renderOrder = 9;
            const megaSize = idleSize * 1.15;
            megaGlow.scale.set(megaSize, megaSize, 1);
            core.add(megaGlow);
          }}

          node.__core = core;
          node.__glow = glow;
          node.__idleSize = idleSize;
          node.__idleOpacity = idleOpacity;

          return core;
        }})
        .linkColor(() => "#B8BFCC")
        .linkWidth(0)
        .linkOpacity(0);

      const renderer = new THREE.WebGLRenderer({{
        antialias: true,
        alpha: true
      }});

      renderer.setPixelRatio(window.devicePixelRatio || 1);
      renderer.setSize(window.innerWidth, window.innerHeight);
      renderer.setClearColor(0x000000, 0);
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 0.85;

      Graph.renderer(renderer);
      Graph.width(window.innerWidth).height(window.innerHeight);
      Graph.backgroundColor("rgba(0,0,0,0)");

      const scene = Graph.scene();
      scene.background = null;

      // Tinted violet instead of flat white -- white ambient uniformly washes
      // every surface toward grey/white regardless of its own hue; a tinted
      // fill light avoids that while still lighting the shadowed side.
      scene.add(new THREE.AmbientLight(0x4a3a66, 0.24));

      const dir = new THREE.DirectionalLight(0xffffff, 0.42);
      dir.position.set(60, 80, 40);
      scene.add(dir);

      const controls = Graph.controls();
      controls.enableRotate = true;
      controls.enablePan = true;
      controls.minDistance = 20;
      controls.maxDistance = 4000;

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

      // --- Globe reference frame (hidden by default; toggled via the "Show globe" switch) ---
      // Centered on 0,0,0: three axes through the origin, a faint wireframe globe at
      // max Depth, equator + meridian rings, and a bright marker at the exact center.
      const axesGroup = new THREE.Group();
      axesGroup.visible = false;

      function makeAxisLabel(text, colorHex, opts) {{
        opts = opts || {{}};
        const fontPx = opts.fontPx || 32;
        const opacity = opts.opacity != null ? opts.opacity : 1;
        const font = `600 ${{fontPx}}px Michroma, sans-serif`;

        // Measure first so the canvas is sized to fit the actual text --
        // a fixed-width canvas clips longer labels (e.g. "Relativity (inv r)")
        // equally off both edges since the text is centered.
        const measureCtx = document.createElement("canvas").getContext("2d");
        measureCtx.font = font;
        const textWidth = measureCtx.measureText(text).width;

        const paddingX = 24;
        const canvas = document.createElement("canvas");
        canvas.width = Math.ceil(textWidth) + paddingX * 2;
        canvas.height = Math.ceil(fontPx * 2);

        const ctx = canvas.getContext("2d");
        ctx.font = font;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = colorHex;
        ctx.globalAlpha = opacity;
        ctx.fillText(text, canvas.width / 2, canvas.height / 2);

        const tex = new THREE.CanvasTexture(canvas);

        const sprite = new THREE.Sprite(
          new THREE.SpriteMaterial({{
            map: tex,
            transparent: true,
            depthWrite: false,
            depthTest: false
          }})
        );

        // Keep label height fixed, scale width to match the canvas's aspect
        // ratio so text isn't stretched or squashed.
        const spriteHeight = opts.spriteHeight || 37;
        const spriteWidth = spriteHeight * (canvas.width / canvas.height);
        sprite.scale.set(spriteWidth, spriteHeight, 1);
        sprite.renderOrder = 20;
        return sprite;
      }}

      // Descriptive captions explaining what each end of an axis actually
      // means, in plain language -- not just the metric name. Placed further
      // out than the tip itself (along the same axis direction) so they never
      // overlap the bold category-name label sitting right at the tip, and
      // small/dim enough to read as secondary context rather than a title.
      function addAxisCaption(point, dir, colorHex, text) {{
        const GAP = 46; // distance beyond `point`, along `dir`, before the caption starts
        const label = makeAxisLabel(text, colorHex, {{ fontPx: 20, opacity: 0.65, spriteHeight: 26 }});
        label.position.set(
          point.x + dir.x * GAP,
          point.y + dir.y * GAP,
          point.z + dir.z * GAP
        );
        axesGroup.add(label);
      }}

      function addAxis(from, to, colorHex, labelText, lowCaption, highCaption) {{
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

        // Unit vector pointing from the low tip toward the high tip, so
        // captions push straight outward past each end -- never sideways
        // into the other two (orthogonal) axes' territory.
        const dx = to.x - from.x, dy = to.y - from.y, dz = to.z - from.z;
        const len = Math.hypot(dx, dy, dz) || 1;
        const dir = {{ x: dx / len, y: dy / len, z: dz / len }};
        const negDir = {{ x: -dir.x, y: -dir.y, z: -dir.z }};

        if (lowCaption) addAxisCaption(from, negDir, colorHex, lowCaption);
        if (highCaption) addAxisCaption(to, dir, colorHex, highCaption);
      }}

      // Three axes through the origin so the center (0,0,0) is unmistakable.
      // Each end gets a short plain-language caption (low value -> high value)
      // explaining what that side of the scale actually represents.
      const FRAME_XY = AXIS_SCALE + 30;
      const FRAME_Z = DEPTH_GAP + DEPTH_SPAN + 30;
      addAxis({{ x: -FRAME_XY, y: 0, z: 0 }}, {{ x: FRAME_XY, y: 0, z: 0 }}, "#4D96FF", "Relativity",
        "nothing unusual is happening", "reality is breaking");
      addAxis({{ x: 0, y: -FRAME_XY, z: 0 }}, {{ x: 0, y: FRAME_XY, z: 0 }}, "#6BCB77", "Relatability",
        "barely human", "painfully relatable");

      // Depth is a special case: its sign encodes publish status (+Z published,
      // -Z unpublished, see the divide plane below), not "low vs. high depth."
      // Depth itself is the *magnitude* -- distance from the z=0 plane in
      // either direction. So both tips are the "high depth" end, and "low
      // depth" sits near the origin on both sides, not at either tip.
      addAxis({{ x: 0, y: 0, z: -FRAME_Z }}, {{ x: 0, y: 0, z: FRAME_Z }}, "#FF6B6B", "Depth",
        null, "not bedtime reading");
      addAxisCaption({{ x: 0, y: 0, z: -FRAME_Z }}, {{ x: 0, y: 0, z: -1 }}, "#FF6B6B", "not bedtime reading & unpublished");
      addAxisCaption({{ x: 60, y: 0, z: DEPTH_GAP }}, {{ x: 1, y: 0, z: 0 }}, "#FF6B6B", "light and breezy");
      addAxisCaption({{ x: 60, y: 0, z: -DEPTH_GAP }}, {{ x: 1, y: 0, z: 0 }}, "#FF6B6B", "light and breezy & unpublished");

      // Bright marker at the exact center, 0,0,0.
      const originMarker = new THREE.Mesh(
        new THREE.SphereGeometry(6, 16, 16),
        new THREE.MeshBasicMaterial({{ color: 0xffffff }})
      );
      originMarker.raycast = () => {{}};
      axesGroup.add(originMarker);

      // Glowing wireframe box marking the outer edge of the coordinate space --
      // the max reach of every axis (FRAME_XY on X/Y, FRAME_Z on Z) stitched
      // into one bounding frame. A crisp inner line plus a wider, fainter
      // outer one (same trick as the INTRO rings) fakes a glow without a real
      // postprocessing pipeline.
      function makeBoundingBox(inflate, opacity) {{
        const geom = new THREE.BoxGeometry(
          FRAME_XY * 2 + inflate,
          FRAME_XY * 2 + inflate,
          FRAME_Z * 2 + inflate
        );
        const box = new THREE.LineSegments(
          new THREE.EdgesGeometry(geom),
          new THREE.LineBasicMaterial({{
            color: 0xffffff,
            transparent: true,
            opacity,
            depthWrite: false,
            blending: THREE.AdditiveBlending
          }})
        );
        box.raycast = () => {{}};
        return box;
      }}
      axesGroup.add(makeBoundingBox(0, 0.5));
      axesGroup.add(makeBoundingBox(14, 0.18));

      scene.add(axesGroup);

      // Publish-divide plane at z=0: published nodes (+Z) sit in front of it,
      // unpublished nodes (-Z) sit behind it. Gated behind the axes toggle,
      // same as the axes/frame and connection lines.
      const DIVIDE_SIZE = (AXIS_SCALE + 60) * 2;
      const dividePlane = new THREE.Mesh(
        new THREE.PlaneGeometry(DIVIDE_SIZE, DIVIDE_SIZE),
        new THREE.MeshBasicMaterial({{
          color: 0xffffff,
          transparent: true,
          opacity: 0.05,
          side: THREE.DoubleSide,
          depthWrite: false
        }})
      );
      dividePlane.raycast = () => {{}};
      axesGroup.add(dividePlane);

      const divideEdge = new THREE.LineLoop(
        new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(-DIVIDE_SIZE / 2, -DIVIDE_SIZE / 2, 0),
          new THREE.Vector3(DIVIDE_SIZE / 2, -DIVIDE_SIZE / 2, 0),
          new THREE.Vector3(DIVIDE_SIZE / 2, DIVIDE_SIZE / 2, 0),
          new THREE.Vector3(-DIVIDE_SIZE / 2, DIVIDE_SIZE / 2, 0)
        ]),
        new THREE.LineBasicMaterial({{ color: 0xffffff, transparent: true, opacity: 0.25 }})
      );
      divideEdge.raycast = () => {{}};
      axesGroup.add(divideEdge);

      // Pushed well past the Relatability axis's high-end caption ("painfully
      // relatable", which sits at y = FRAME_XY + 46 = 556) -- both labels are
      // pinned to x=0, z=0, so they need real vertical separation or they sit
      // right on top of each other.
      const divideLabel = makeAxisLabel("The Draft Horizon", "#FFFFFF");
      divideLabel.position.set(0, DIVIDE_SIZE / 2 + 110, 0);
      axesGroup.add(divideLabel);

      const axesToggle = document.getElementById("axesToggle");
      axesToggle.checked = false;
      axesGroup.visible = false;
      axesToggle.addEventListener("change", () => {{
        axesGroup.visible = axesToggle.checked;
      }});

      const linksToggle = document.getElementById("linksToggle");
      linksToggle.checked = false;
      Graph.linkOpacity(0);
      linksToggle.addEventListener("change", () => {{
        Graph.linkOpacity(linksToggle.checked ? 0.8 : 0);
      }});

      // "START HERE" callout over the entry-point INTRO node, gated behind the
      // same "Show axes" toggle as the rest of the reference frame -- it's a
      // wayfinding aid for people poking at the raw graph, not part of the
      // normal browsing experience.
      const startHereNode = nodeById.get("700");

      if (startHereNode) {{
        const startHereLabel = makeAxisLabel("START HERE", "#FFFFFF", {{
          fontPx: 52,
          spriteHeight: 75
        }});
        startHereLabel.position.set(
          startHereNode.x,
          startHereNode.y + 72,
          startHereNode.z
        );
        axesGroup.add(startHereLabel);
      }}

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
        if (node.isTrailer && node.contentUrl) {{
          window.open(node.contentUrl, "_blank", "noopener");
          return;
        }}
        openDrawer(node);
      }});

      renderer.setAnimationLoop(() => {{
        const t = performance.now() * 0.012;
        const wave = 0.5 + 0.5 * Math.sin(t);

        if (hoveredNode && hoveredNode.__glow && hoveredNode !== selectedNode) {{
          const base = hoveredNode.__idleOpacity != null ? hoveredNode.__idleOpacity : 0.32;
          hoveredNode.__glow.material.opacity = Math.min(1, base + 0.15 + 0.15 * wave);
        }}

        if (selectedNode && selectedNode.__glow) {{
          const base = selectedNode.__idleOpacity != null ? selectedNode.__idleOpacity : 0.32;
          selectedNode.__glow.material.opacity = Math.min(1, base + 0.2);
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