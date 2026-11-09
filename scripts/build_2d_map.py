#!/usr/bin/env python3
"""Build the sane, searchable Poppyverse 2D catalogue directly from Notion.

Run from the repository root:

  read -rs "NOTION_TOKEN?Paste Notion token: "; echo; export NOTION_TOKEN
  python3 -u scripts/build_2d_map.py
  unset NOTION_TOKEN

Only normalized public catalogue fields are embedded in 2d_map.html. The token
and the raw Notion responses never leave memory.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from poppyverse_notion import (
    DEFAULT_CLUSTER_DATA_SOURCE,
    DEFAULT_FULL_DATA_SOURCE,
    EXCLUDED_CATALOG_IDS,
    EXCLUDED_TITLES,
    NotionError,
    clean_display_text,
    clean_id,
    fetch_catalogues,
    first,
    load_snapshot,
    number,
    parse_tokens,
    relation_ids,
)


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_OUTPUT = REPO_ROOT / "2d_map.html"
POPPY_PINK = "#FF1447"


def clean_color(value: object) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"#?[0-9a-fA-F]{6}", text):
        return f"#{text.lstrip('#').upper()}"
    return POPPY_PINK


def clean_url(value: object) -> str:
    if isinstance(value, list):
        value = value[0] if value else ""
    text = str(value or "").strip()
    if not text.lower().startswith(("https://", "http://")):
        return ""
    try:
        parts = urlsplit(text)
        path = quote(parts.path, safe="/:%")
        query = quote(parts.query, safe="=&?/%:+,#[]@!$'()*;")
        return urlunsplit((parts.scheme, parts.netloc, path, query, ""))
    except ValueError:
        return ""


def catalog_id(row: dict[str, Any], fallback: int) -> str:
    value = first(row, "userDefined:ID", "ID", default=fallback)
    return re.sub(r"\.0$", "", str(value or fallback).strip())


def explicit_order(row: dict[str, Any], fallback: int) -> tuple[int, float, int]:
    raw = first(row, "Order", "Sort order", "Position", default=None)
    if raw in (None, ""):
        return (1, 0.0, fallback)
    return (0, number(raw), fallback)


def build_map_data(
    full_rows: list[dict[str, Any]], cluster_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    clusters: list[dict[str, Any]] = []
    cluster_by_page: dict[str, dict[str, Any]] = {}
    cluster_by_name: dict[str, dict[str, Any]] = {}

    for source_index, row in enumerate(cluster_rows):
        page_id = clean_id(first(row, "__page_id", default=first(row, "__url")))
        name = clean_display_text(first(row, "Name", "Cluster", default=""))
        if not page_id or not name:
            continue
        cluster = {
            "id": page_id,
            "name": name,
            "description": clean_display_text(first(row, "Description", default=""), preserve_paragraphs=True),
            "color": clean_color(first(row, "Hex Code Color", "Hex Color", "Color", default="")),
            "coverUrl": clean_url(first(row, "Cover URL", "Cover", "Image URL", default="")),
            "stories": [],
            "_sourceIndex": source_index,
            "_sort": explicit_order(row, source_index),
        }
        clusters.append(cluster)
        cluster_by_page[page_id] = cluster
        cluster_by_name[name.casefold()] = cluster

    def cluster_sort_key(cluster: dict[str, Any]) -> tuple[int, float, int]:
        sort_kind, sort_value, source_index = cluster["_sort"]
        if sort_kind == 0:
            return (0, sort_value, source_index)
        welcome_first = 0 if cluster["name"].casefold() == "welcome to the poppyverse" else 1
        return (1, welcome_first, source_index)

    clusters.sort(key=cluster_sort_key)

    unclustered: list[dict[str, Any]] = []
    for source_index, row in enumerate(full_rows, start=1):
        page_id = clean_id(first(row, "__page_id", default=first(row, "__url")))
        name = clean_display_text(first(row, "Name", default=""))
        item_id = catalog_id(row, source_index)
        if not page_id or not name:
            continue
        if item_id in EXCLUDED_CATALOG_IDS or name.casefold() in EXCLUDED_TITLES:
            continue

        status = clean_display_text(first(row, "Status", default=""))
        content_url = clean_url(first(row, "userDefined:URL", "URL", "Content URL", default=""))
        story = {
            "id": item_id,
            "name": name,
            "description": clean_display_text(first(row, "Description", default=""), preserve_paragraphs=True),
            "bytes": int(max(0.0, number(first(row, "Total bytes", default=0)))),
            "characters": parse_tokens(first(row, "Characters", default=[])),
            "contentWarnings": parse_tokens(first(row, "Content warnings", default=[])),
            "crossovers": parse_tokens(first(row, "Canon crossovers", "Crossover", default=[])),
            "contentUrl": content_url,
            "status": status,
            "published": status.casefold() == "published" or bool(content_url),
            "type": clean_display_text(first(row, "Type", default="")),
            "_sourceIndex": source_index,
        }

        related = relation_ids(first(row, "Cluster", default=[]))
        cluster = cluster_by_page.get(related[0]) if related else None
        if cluster is None:
            legacy_name = clean_display_text(first(row, "Cluster (legacy)", "Cluster name", default=""))
            cluster = cluster_by_name.get(legacy_name.casefold())
        if cluster is None:
            unclustered.append(story)
        else:
            cluster["stories"].append(story)

    if unclustered:
        clusters.append({
            "id": "unclustered",
            "name": "Unclustered",
            "description": "Catalogue entries currently between universes.",
            "color": "#6E7A91",
            "coverUrl": "",
            "stories": unclustered,
            "_sourceIndex": len(clusters),
            "_sort": (1, 0, len(clusters)),
        })

    story_count = 0
    published_count = 0
    for cluster in clusters:
        cluster["stories"].sort(key=lambda story: (story["name"].casefold(), story["_sourceIndex"]))
        for story in cluster["stories"]:
            story.pop("_sourceIndex", None)
        cluster["storyCount"] = len(cluster["stories"])
        cluster["publishedCount"] = sum(1 for story in cluster["stories"] if story["published"])
        story_count += cluster["storyCount"]
        published_count += cluster["publishedCount"]
        cluster.pop("_sourceIndex", None)
        cluster.pop("_sort", None)

    return {"clusters": clusters, "storyCount": story_count, "publishedCount": published_count}


def json_script(data: dict[str, Any]) -> str:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script id="poppy-data" type="application/json">{raw}</script>'


HTML_TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Poppyverse 2D Map</title>
  <link rel="icon" href='data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><text y="50%" x="50%" dominant-baseline="middle" text-anchor="middle" font-size="52">%F0%9F%8C%B7</text></svg>'>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Michroma&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root{--pink:#FF1447;--bg:#07080d;--panel:#0d0f17;--line:rgba(255,255,255,.14);--text:#f5f7fb;--muted:#aab1c0;--active:#FF1447}
    *{box-sizing:border-box}html,body{margin:0;min-height:100%;background:#07080d;color:var(--text);font-family:"Space Grotesk",system-ui,sans-serif}body{background:radial-gradient(circle at 18% 0%,rgba(255,20,71,.16),transparent 31%),radial-gradient(circle at 83% 12%,rgba(102,75,255,.13),transparent 32%),linear-gradient(145deg,#050507,#0a0c13 50%,#10111c)}button,input{font:inherit}a{color:inherit}
    main{min-height:100vh;padding:104px 24px 60px}.hero{max-width:920px;margin:0 auto 28px;text-align:center}.hero h1{margin:0;font-family:Michroma,sans-serif;font-size:clamp(30px,5vw,64px);letter-spacing:.05em;text-transform:uppercase;color:var(--pink);text-shadow:0 0 18px rgba(255,20,71,.65)}.hero p{max-width:680px;margin:16px auto 0;color:var(--muted);line-height:1.65}
    .controls{max-width:980px;margin:26px auto 28px;display:grid;grid-template-columns:minmax(220px,1fr) auto auto;gap:12px;align-items:center}.search-wrap{position:relative}.search-wrap svg{position:absolute;left:15px;top:50%;transform:translateY(-50%);width:18px;color:#8e96a8}.search{width:100%;height:48px;padding:0 44px;border:1px solid var(--line);border-radius:14px;background:rgba(4,5,10,.7);color:white;outline:none}.search:focus{border-color:var(--pink);box-shadow:0 0 0 3px rgba(255,20,71,.14)}.toggle{height:48px;padding:0 16px;display:flex;align-items:center;gap:10px;border:1px solid var(--line);border-radius:14px;background:rgba(4,5,10,.7);color:#dce1eb;cursor:pointer}.toggle-track{width:34px;height:19px;padding:2px;border-radius:999px;background:#424755;transition:.18s}.toggle-track:after{content:"";display:block;width:15px;height:15px;border-radius:50%;background:white;transition:.18s}.toggle[aria-pressed="true"] .toggle-track{background:var(--pink)}.toggle[aria-pressed="true"] .toggle-track:after{transform:translateX(15px)}.result-count{color:var(--muted);font-size:13px;white-space:nowrap}
    .cluster-grid{max-width:1320px;margin:auto;display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,300px));justify-content:center;gap:22px}.cluster-card{--cluster:#FF1447;position:relative;min-height:206px;padding:19px;display:flex;flex-direction:column;justify-content:flex-end;overflow:hidden;border:1px solid rgba(255,255,255,.2);border-radius:22px;background:#111;color:white;text-align:left;box-shadow:0 18px 45px rgba(0,0,0,.38),0 0 26px color-mix(in srgb,var(--cluster) 34%,transparent);cursor:pointer;isolation:isolate;transition:.18s}.cluster-card:hover{transform:translateY(-5px);border-color:rgba(255,255,255,.48);box-shadow:0 26px 65px rgba(0,0,0,.46),0 0 34px color-mix(in srgb,var(--cluster) 54%,transparent)}.cluster-card:focus-visible{outline:3px solid white;outline-offset:3px}.cluster-image,.cluster-tint,.cluster-shade{position:absolute;inset:0;z-index:-3;background-size:cover;background-position:center}.cluster-tint{z-index:-2;background:linear-gradient(135deg,color-mix(in srgb,var(--cluster) 88%,black 12%),color-mix(in srgb,var(--cluster) 48%,black 52%));opacity:.9}.has-cover .cluster-tint{mix-blend-mode:multiply}.cluster-shade{z-index:-1;background:radial-gradient(circle at 50% 8%,rgba(255,255,255,.2),transparent 37%),linear-gradient(transparent 10%,rgba(0,0,0,.82))}.cluster-card h2{margin:0;font:700 15px/1.3 Michroma,sans-serif;letter-spacing:.06em;text-transform:uppercase;text-shadow:0 2px 16px black}.cluster-card p{margin:9px 0 0;color:rgba(255,255,255,.78);font-size:12px;letter-spacing:.08em;text-transform:uppercase}.empty{display:none;padding:48px 20px;text-align:center;color:var(--muted)}
    .backdrop{position:fixed;z-index:1090;inset:0;background:rgba(0,0,0,.58);opacity:0;pointer-events:none;transition:.2s}.backdrop.open{opacity:1;pointer-events:auto}.drawer{position:fixed;z-index:1100;top:0;right:0;width:min(88vw,1180px);height:100vh;background:#090b12;border-left:1px solid var(--line);box-shadow:-26px 0 75px rgba(0,0,0,.66);transform:translateX(105%);transition:.23s;overflow-y:auto}.drawer.open{transform:none}.drawer-head{position:sticky;z-index:2;top:0;padding:78px 74px 24px 30px;border-bottom:1px solid var(--line);background:radial-gradient(circle at top left,color-mix(in srgb,var(--active) 35%,transparent),transparent 43%),rgba(9,11,18,.95);backdrop-filter:blur(15px)}.drawer-title{margin:0;font:700 clamp(22px,4vw,42px)/1.15 Michroma,sans-serif;letter-spacing:.05em;text-transform:uppercase;color:var(--active)}.drawer-description{max-width:780px;margin:13px 0 0;color:#c7ccd7;line-height:1.55;white-space:pre-line}.drawer-meta{margin-top:13px;color:#9da5b5;font-size:13px}.close{position:absolute;top:18px;right:22px;width:42px;height:42px;border:1px solid rgba(255,255,255,.25);border-radius:13px;background:rgba(0,0,0,.32);color:white;font-size:24px;cursor:pointer}.drawer-body{padding:24px 30px 50px}.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:16px}.story-table{width:100%;border-collapse:collapse;table-layout:fixed}.story-table th{padding:13px;text-align:left;color:#9ea6b6;background:#11141d;font-size:10px;letter-spacing:.12em;text-transform:uppercase}.story-table td{padding:15px 13px;vertical-align:top;border-top:1px solid var(--line);color:#dce0e8;font-size:13px;line-height:1.48}.story-table th:nth-child(1){width:18%}.story-table th:nth-child(2){width:9%}.story-table th:nth-child(3){width:28%}.story-table th:nth-child(4){width:17%}.story-table th:nth-child(5){width:17%}.story-table th:nth-child(6){width:11%}.story-name{font-weight:700;color:white}.badge-row{display:flex;flex-wrap:wrap;gap:5px;margin-top:7px}.badge{padding:3px 7px;border:1px solid color-mix(in srgb,var(--active) 62%,transparent);border-radius:999px;background:color-mix(in srgb,var(--active) 18%,transparent);font-size:9px;font-weight:700;letter-spacing:.05em;text-transform:uppercase}.muted{color:#7f8797}.open-link{display:inline-flex;padding:8px 10px;border-radius:9px;background:var(--active);color:white;text-decoration:none;font-size:10px;font-weight:800;letter-spacing:.09em}.mobile-stories{display:none}.mobile-stories poppy-card+poppy-card{margin-top:12px}.no-stories{padding:45px 20px;text-align:center;color:var(--muted)}
    @media(max-width:760px){main{padding:94px 15px 42px}.controls{grid-template-columns:1fr}.toggle{justify-content:center}.result-count{text-align:center}.cluster-grid{grid-template-columns:1fr}.cluster-card{width:100%;min-height:180px}.drawer{width:100vw}.drawer-head{padding:74px 64px 22px 20px}.drawer-body{padding:18px 15px 38px}.table-wrap{display:none}.mobile-stories{display:block}}
  </style>
</head>
<body>
  <script src="components/poppy-nav.js"></script>
  <script src="components/poppy-card.js"></script>
  <poppy-nav></poppy-nav>
  <main>
    <header class="hero"><h1>Poppyverse 2D Map</h1><p>The calmer catalogue view. Pick a universe, search the archive, and inspect its stories without being launched through three-dimensional spacetime.</p></header>
    <section class="controls" aria-label="Catalogue filters"><label class="search-wrap"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-4-4"></path></svg><input id="search" class="search" type="search" placeholder="Search stories, characters, clusters…" autocomplete="off"></label><button id="published-toggle" class="toggle" type="button" aria-pressed="false"><span class="toggle-track" aria-hidden="true"></span>Published only</button><div id="result-count" class="result-count"></div></section>
    <section id="cluster-grid" class="cluster-grid"></section><div id="empty" class="empty">No catalogue entries match that filter.</div>
  </main>
  <div id="backdrop" class="backdrop"></div>
  <aside id="drawer" class="drawer" aria-hidden="true" aria-label="Cluster stories"><header class="drawer-head"><button id="close" class="close" aria-label="Close">×</button><h2 id="drawer-title" class="drawer-title"></h2><p id="drawer-description" class="drawer-description"></p><div id="drawer-meta" class="drawer-meta"></div></header><div id="drawer-body" class="drawer-body"></div></aside>
  __DATA__
  <script>
  (()=>{
    const DATA=JSON.parse(document.getElementById("poppy-data").textContent);
    const grid=document.getElementById("cluster-grid"),search=document.getElementById("search"),toggle=document.getElementById("published-toggle"),count=document.getElementById("result-count"),empty=document.getElementById("empty"),drawer=document.getElementById("drawer"),backdrop=document.getElementById("backdrop"),drawerBody=document.getElementById("drawer-body");
    let publishedOnly=false,activeCluster=null;
    const esc=value=>String(value??"").replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
    const tokens=values=>values?.length?`<div class="badge-row">${values.map(value=>`<span class="badge">${esc(value)}</span>`).join("")}</div>`:`<span class="muted">—</span>`;
    const formatBytes=value=>{let n=Number(value)||0;if(n<=0)return "—";if(n<1024)return `${Math.round(n)} B`;const units=["KB","MB","GB"];let i=-1;do{n/=1024;i++;}while(n>=1024&&i<units.length-1);return `${n.toFixed(n>=100?0:n>=10?1:2)} ${units[i]}`;};
    const sizeCell=story=>story.bytes>0?`<span title="${story.bytes.toLocaleString("en-US")} bytes">${formatBytes(story.bytes)}</span>`:'<span class="muted">—</span>';
    const searchable=(cluster,story)=>[cluster.name,cluster.description,story.name,story.description,...story.characters,...story.contentWarnings,...story.crossovers].join(" ").toLowerCase();
    function filteredStories(cluster){const query=search.value.trim().toLowerCase();return cluster.stories.filter(story=>(!publishedOnly||story.published)&&(!query||searchable(cluster,story).includes(query)));}
    function render(){let visibleStories=0,visibleClusters=0;grid.innerHTML="";DATA.clusters.forEach(cluster=>{const stories=filteredStories(cluster);if(!stories.length)return;visibleClusters++;visibleStories+=stories.length;const card=document.createElement("button");card.type="button";card.className=`cluster-card${cluster.coverUrl?" has-cover":""}`;card.style.setProperty("--cluster",cluster.color);card.innerHTML=`${cluster.coverUrl?`<span class="cluster-image" style="background-image:url('${esc(cluster.coverUrl)}')"></span>`:""}<span class="cluster-tint"></span><span class="cluster-shade"></span><h2>${esc(cluster.name)}</h2><p>${stories.length} ${stories.length===1?"story":"stories"} · ${stories.filter(story=>story.published).length} public</p>`;card.addEventListener("click",()=>openCluster(cluster));grid.appendChild(card);});count.textContent=`${visibleStories} stories · ${visibleClusters} clusters`;empty.style.display=visibleClusters?"none":"block";if(activeCluster&&drawer.classList.contains("open"))openCluster(activeCluster,false);}
    function desktopTable(stories){return `<div class="table-wrap"><table class="story-table"><thead><tr><th>Name</th><th>Size</th><th>Description</th><th>Characters</th><th>Content warnings</th><th>Content</th></tr></thead><tbody>${stories.map(story=>`<tr><td><div class="story-name">${esc(story.name)}</div>${tokens(story.crossovers)}</td><td>${sizeCell(story)}</td><td>${esc(story.description)||'<span class="muted">—</span>'}</td><td>${tokens(story.characters)}</td><td>${tokens(story.contentWarnings)}</td><td>${story.contentUrl?`<a class="open-link" href="${esc(story.contentUrl)}" target="_blank" rel="noopener">OPEN</a>`:'<span class="muted">—</span>'}</td></tr>`).join("")}</tbody></table></div>`;}
    function mobileCards(){return '<div class="mobile-stories"></div>';}
    function storyCardData(story,color){return{title:story.name,color,sections:[story.crossovers.length?{chips:story.crossovers}:null,story.description?{text:story.description}:null,{title:"Size",text:formatBytes(story.bytes)},{title:"Characters",chips:story.characters,empty:"—"},{title:"Content warnings",chips:story.contentWarnings,empty:"—"},story.contentUrl?{link:{href:story.contentUrl,label:"Open"}}:null].filter(Boolean)};}
    function fillMobileCards(stories,color){const holder=drawerBody.querySelector(".mobile-stories");if(!holder)return;stories.forEach(story=>{const card=document.createElement("poppy-card");card.setAttribute("variant","compact");card.data=storyCardData(story,color);holder.appendChild(card);});}
    function openCluster(cluster,moveFocus=true){activeCluster=cluster;const stories=filteredStories(cluster);drawer.style.setProperty("--active",cluster.color);document.getElementById("drawer-title").textContent=cluster.name;document.getElementById("drawer-description").textContent=cluster.description;document.getElementById("drawer-meta").textContent=`${stories.length} visible · ${stories.filter(story=>story.published).length} public · ${cluster.storyCount} total`;drawerBody.innerHTML=stories.length?desktopTable(stories)+mobileCards():'<div class="no-stories">No stories in this cluster match the current filters.</div>';if(stories.length)fillMobileCards(stories,cluster.color);drawer.classList.add("open");backdrop.classList.add("open");drawer.setAttribute("aria-hidden","false");document.body.style.overflow="hidden";if(moveFocus)document.getElementById("close").focus();}
    function closeDrawer(){drawer.classList.remove("open");backdrop.classList.remove("open");drawer.setAttribute("aria-hidden","true");document.body.style.overflow="";activeCluster=null;}
    search.addEventListener("input",render);toggle.addEventListener("click",()=>{publishedOnly=!publishedOnly;toggle.setAttribute("aria-pressed",String(publishedOnly));render();});document.getElementById("close").addEventListener("click",closeDrawer);backdrop.addEventListener("click",closeDrawer);document.addEventListener("keydown",event=>{if(event.key==="Escape")closeDrawer();});render();
  })();
  </script>
</body>
</html>'''


def build_html(data: dict[str, Any]) -> str:
    return (
        HTML_TEMPLATE.replace("__DATA__", json_script(data))
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build 2d_map.html directly from the Poppyverse Notion catalogues.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Generated HTML path")
    parser.add_argument("--full-data-source", default=os.environ.get("NOTION_FULL_CATALOG_DATA_SOURCE_ID", DEFAULT_FULL_DATA_SOURCE))
    parser.add_argument("--cluster-data-source", default=os.environ.get("NOTION_CLUSTER_CATALOG_DATA_SOURCE_ID", DEFAULT_CLUSTER_DATA_SOURCE))
    parser.add_argument("--snapshot", help="Read catalogue rows as JSON from this file ('-' for stdin) instead of calling Notion; build_all.py uses this.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        full_rows, cluster_rows = load_snapshot(args.snapshot) if args.snapshot else fetch_catalogues(args.full_data_source, args.cluster_data_source)
    except NotionError as exc:
        raise SystemExit(f"Notion fetch failed: {exc}") from None
    data = build_map_data(full_rows, cluster_rows)
    if not data["clusters"] or not data["storyCount"]:
        raise SystemExit("No usable catalogue data was found; refusing to overwrite the map.")
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_html(data), encoding="utf-8")
    print(f"Built {output}")
    print(f"Clusters: {len(data['clusters'])}")
    print(f"Stories: {data['storyCount']}")
    print(f"Published/public: {data['publishedCount']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
