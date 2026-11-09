#!/usr/bin/env python3
"""Build the experimental Poppyverse 3D cluster-ring map directly from Notion.

Sources of truth:
  - The Full Catalogue
  - The Cluster Catalogue

Where NOTION_TOKEN comes from:
  1. In Notion, open Settings -> Connections and turn on Developer Mode.
  2. Open Personal access tokens, create a new internal connection, and copy
     its internal API/installation access token.
  3. Open The Full Catalogue and The Cluster Catalogue in Notion and add that
     connection to each database from its ... -> Connections menu. Read-only
     content access is sufficient for this generator.

Safe zsh/macOS setup (the token stays out of ordinary shell history):
  read -rs "NOTION_TOKEN?Paste Notion token: "
  echo
  export NOTION_TOKEN
  python3 -u scripts/build_3d_map_2.py
  unset NOTION_TOKEN

`read -rs` stores the pasted text in the shell variable without displaying it.
`export` makes that variable available to this Python process. The script reads
the token from the environment, uses it only in the private Authorization
header sent to api.notion.com, never prints it, and never embeds it in the HTML.

The data-source IDs are addresses, not secrets, and default to the current
Poppyverse sources. They can be overridden with environment variables or
command-line arguments.

For repeatable layouts, "random" positions are seeded. Pass --seed to generate
a different universe intentionally. Raw Notion rows are never written to disk;
only the compiled HTML is produced.
"""

from __future__ import annotations

import argparse
import colorsys
import hashlib
import json
import math
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

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
    parse_json_array,
    parse_tokens,
    relation_ids,
)


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_OUTPUT = REPO_ROOT / "3d_map_2.html"
POPPY_PINK = "#FF1447"
DEFAULT_NODE_BYTES = 100_000
NODE_SIZE_REFERENCE_BYTES = 16_000
NODE_RADIUS_MULTIPLIER = 1.5


def public_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "untitled"


def stable_seed(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def clean_color(value: object) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
        return text.upper()
    if re.fullmatch(r"[0-9a-fA-F]{6}", text):
        return f"#{text.upper()}"
    return POPPY_PINK


def vary_story_color(base_color: str, seed: int) -> str:
    """Give siblings a restrained, deterministic hue/lightness variation."""
    match = re.fullmatch(r"#([0-9A-Fa-f]{6})", clean_color(base_color))
    if not match:
        return clean_color(base_color)
    raw = match.group(1)
    r, g, b = (int(raw[index:index + 2], 16) / 255 for index in (0, 2, 4))
    hue, lightness, saturation = colorsys.rgb_to_hls(r, g, b)
    rng = random.Random(seed)
    hue = (hue + rng.uniform(-0.035, 0.035)) % 1.0
    saturation = clamp(saturation + rng.uniform(-0.035, 0.055), 0.52, 1.0)
    lightness = clamp(lightness + rng.uniform(-0.035, 0.045), 0.34, 0.72)
    vr, vg, vb = colorsys.hls_to_rgb(hue, lightness, saturation)
    return f"#{round(vr * 255):02X}{round(vg * 255):02X}{round(vb * 255):02X}"


@dataclass
class Basis:
    u: tuple[float, float, float]
    v: tuple[float, float, float]
    n: tuple[float, float, float]


def vector_add(a: Iterable[float], b: Iterable[float]) -> tuple[float, float, float]:
    av, bv = tuple(a), tuple(b)
    return av[0] + bv[0], av[1] + bv[1], av[2] + bv[2]


def vector_sub(a: Iterable[float], b: Iterable[float]) -> tuple[float, float, float]:
    av, bv = tuple(a), tuple(b)
    return av[0] - bv[0], av[1] - bv[1], av[2] - bv[2]


def vector_scale(a: Iterable[float], scale: float) -> tuple[float, float, float]:
    av = tuple(a)
    return av[0] * scale, av[1] * scale, av[2] * scale


def dot(a: Iterable[float], b: Iterable[float]) -> float:
    av, bv = tuple(a), tuple(b)
    return av[0] * bv[0] + av[1] * bv[1] + av[2] * bv[2]


def length(a: Iterable[float]) -> float:
    return math.sqrt(dot(a, a))


def normalize(a: Iterable[float]) -> tuple[float, float, float]:
    av = tuple(a)
    magnitude = length(av)
    if magnitude < 1e-9:
        return 1.0, 0.0, 0.0
    return av[0] / magnitude, av[1] / magnitude, av[2] / magnitude


def cross(a: Iterable[float], b: Iterable[float]) -> tuple[float, float, float]:
    av, bv = tuple(a), tuple(b)
    return (
        av[1] * bv[2] - av[2] * bv[1],
        av[2] * bv[0] - av[0] * bv[2],
        av[0] * bv[1] - av[1] * bv[0],
    )


def random_basis(rng: random.Random) -> Basis:
    z = rng.uniform(-0.82, 0.82)
    theta = rng.uniform(0, math.tau)
    radial = math.sqrt(max(0.0, 1 - z * z))
    normal = normalize((radial * math.cos(theta), radial * math.sin(theta), z))
    reference = (0.0, 0.0, 1.0) if abs(normal[2]) < 0.9 else (0.0, 1.0, 0.0)
    base_u = normalize(cross(reference, normal))
    base_v = normalize(cross(normal, base_u))
    roll = rng.uniform(0, math.tau)
    u = vector_add(vector_scale(base_u, math.cos(roll)), vector_scale(base_v, math.sin(roll)))
    v = vector_add(vector_scale(base_v, math.cos(roll)), vector_scale(base_u, -math.sin(roll)))
    return Basis(normalize(u), normalize(v), normal)


def local_to_world(
    center: tuple[float, float, float], basis: Basis, local: tuple[float, float, float]
) -> tuple[float, float, float]:
    result = center
    result = vector_add(result, vector_scale(basis.u, local[0]))
    result = vector_add(result, vector_scale(basis.v, local[1]))
    result = vector_add(result, vector_scale(basis.n, local[2]))
    return result


def nearest_ring_point(cluster: dict[str, Any], other: Iterable[float]) -> tuple[float, float, float]:
    center = tuple(cluster[axis] for axis in ("x", "y", "z"))
    u = tuple(cluster["basisU"])
    v = tuple(cluster["basisV"])
    direction = vector_sub(other, center)
    planar = vector_add(vector_scale(u, dot(direction, u)), vector_scale(v, dot(direction, v)))
    if length(planar) < 1e-6:
        planar = u
    return vector_add(center, vector_scale(normalize(planar), cluster["radius"]))


def compact_point(point: Iterable[float]) -> list[float]:
    return [round(value, 3) for value in point]


def resolve_target(token: str, lookups: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    raw = token.strip()
    if not raw:
        return None
    candidates = [raw, clean_id(raw), raw.casefold()]
    for candidate in candidates:
        if candidate and candidate in lookups:
            return lookups[candidate]
    numeric = re.sub(r"\.0$", "", raw)
    return lookups.get(numeric)


def build_map_data(
    full_rows: list[dict[str, Any]], cluster_rows: list[dict[str, Any]], seed: int
) -> dict[str, Any]:
    clusters: list[dict[str, Any]] = []
    cluster_by_page: dict[str, dict[str, Any]] = {}
    cluster_by_name: dict[str, dict[str, Any]] = {}

    for row in cluster_rows:
        page_id = clean_id(str(first(row, "__page_id", default=first(row, "__url"))))
        name = clean_display_text(first(row, "Name", default=""))
        if not page_id or not name:
            continue
        cluster = {
            "id": f"cluster:{public_slug(name)}",
            "pageId": page_id,
            "kind": "cluster",
            "name": name,
            "label": name,
            "description": clean_display_text(first(row, "Description", default=""), preserve_paragraphs=True),
            "color": clean_color(first(row, "Hex Code Color", "Color", default="")),
            "coverUrl": str(first(row, "Cover URL", default="")).strip(),
            "raw": row,
            "children": [],
            "totalBytes": 0,
        }
        clusters.append(cluster)
        cluster_by_page[page_id] = cluster
        cluster_by_name[name.casefold()] = cluster

    stories: list[dict[str, Any]] = []
    story_by_page: dict[str, dict[str, Any]] = {}
    story_by_catalog_id: dict[str, dict[str, Any]] = {}
    story_by_name: dict[str, dict[str, Any]] = {}

    for row_index, row in enumerate(full_rows, start=1):
        page_id = clean_id(str(first(row, "__page_id", default=first(row, "__url"))))
        if not page_id:
            continue
        name = clean_display_text(first(row, "Name", default="")) or f"Untitled {row_index}"
        catalog_value = first(row, "userDefined:ID", "ID", default=row_index)
        catalog_id = re.sub(r"\.0$", "", str(catalog_value or row_index).strip())
        normalized_title = name.casefold()
        if catalog_id in EXCLUDED_CATALOG_IDS or normalized_title in EXCLUDED_TITLES:
            continue
        type_name = str(first(row, "Type", default="story")).strip().casefold()
        status = str(first(row, "Status", default="")).strip()
        content_url = str(first(row, "userDefined:URL", "URL", default="")).strip()
        is_trailer = type_name == "youtube" or "youtube.com" in content_url or "youtu.be" in content_url
        is_intro = "intro" in name.casefold()
        is_ebook = type_name == "e-book"
        cluster_ids = relation_ids(first(row, "Cluster", default=[]))
        cluster = cluster_by_page.get(cluster_ids[0]) if cluster_ids else None
        if cluster is None:
            legacy = str(first(row, "Cluster (legacy)", default="")).strip().casefold()
            cluster = cluster_by_name.get(legacy)
        total_bytes = max(0.0, number(first(row, "Total bytes", default=0)))
        effective_bytes = total_bytes if total_bytes > 0 else DEFAULT_NODE_BYTES
        # Radius follows the cube root so rendered sphere volume is proportional
        # to manuscript bytes. A restrained clamp prevents one outlier from
        # swallowing its entire cluster, then the requested global 150% scale
        # makes every node easier to read.
        byte_radius = 8.0 * (effective_bytes / NODE_SIZE_REFERENCE_BYTES) ** (1 / 3)
        visual_radius = clamp(byte_radius, 5.5, 24.0) * NODE_RADIUS_MULTIPLIER
        base_color = cluster["color"] if cluster else "#8793A8"
        story_color = vary_story_color(base_color, stable_seed(seed, catalog_id, "story-color"))
        story = {
            "id": f"story:{catalog_id}",
            "pageId": page_id,
            "catalogId": catalog_id,
            "kind": "story",
            "name": name,
            "label": name,
            "description": clean_display_text(first(row, "Description", default=""), preserve_paragraphs=True),
            "subparts": str(first(row, "Sub-parts", default="")).strip(),
            "characters": first(row, "Characters", default=[]),
            "contentWarnings": parse_tokens(first(row, "Content warnings", default=[])),
            "contentUrl": content_url,
            "status": status,
            "published": status.casefold() == "published" or bool(content_url),
            "type": type_name,
            "isTrailer": is_trailer,
            "isIntro": is_intro,
            "isEbook": is_ebook,
            "bytes": int(total_bytes),
            "usesDefaultSize": total_bytes <= 0,
            "visualRadius": round(visual_radius, 3),
            "clusterId": cluster["id"] if cluster and not is_trailer else "",
            "clusterName": cluster["name"] if cluster else "",
            # Trailers float outside their ring, but keep their catalogue
            # cluster color so their asteroid glow still belongs to the map.
            "baseColor": base_color,
            "color": story_color,
            "nodeConnections": first(row, "Node connections", default=""),
            "clusterConnections": first(row, "Cluster connections", default=""),
            "raw": row,
        }
        stories.append(story)
        story_by_page[page_id] = story
        story_by_catalog_id[catalog_id] = story
        story_by_name[name.casefold()] = story
        if cluster and not is_trailer:
            cluster["children"].append(story)
            cluster["totalBytes"] += int(total_bytes)

    max_bytes = max((cluster["totalBytes"] for cluster in clusters), default=1) or 1
    for cluster in clusters:
        byte_scale = math.sqrt(cluster["totalBytes"] / max_bytes)
        byte_radius = 145 + 285 * byte_scale
        capacity_radius = 105 + 20 * math.sqrt(max(1, len(cluster["children"])))
        cluster["radius"] = round(max(byte_radius, capacity_radius), 3)
        rng = random.Random(stable_seed(seed, cluster["id"], "basis"))
        basis = random_basis(rng)
        cluster["basisU"] = compact_point(basis.u)
        cluster["basisV"] = compact_point(basis.v)
        cluster["basisN"] = compact_point(basis.n)
        cluster["storyCount"] = len(cluster["children"])

    positioned: list[dict[str, Any]] = []
    placement_rng = random.Random(stable_seed(seed, "cluster-centers"))
    base_span = max(1150.0, math.sqrt(sum((c["radius"] + 95) ** 2 for c in clusters)) * 0.95)
    for cluster in sorted(clusters, key=lambda item: (-item["radius"], item["id"])):
        chosen: tuple[float, float, float] | None = None
        for attempt in range(12000):
            growth = 1.0 + attempt / 12000 * 0.75
            span = base_span * growth
            candidate = (
                placement_rng.uniform(-span, span),
                placement_rng.uniform(-span * 0.62, span * 0.62),
                placement_rng.uniform(-span * 0.72, span * 0.72),
            )
            if all(
                length(vector_sub(candidate, (other["x"], other["y"], other["z"])))
                > (cluster["radius"] + other["radius"]) * 0.82 + 65
                for other in positioned
            ):
                chosen = candidate
                break
        if chosen is None:
            angle = len(positioned) * 2.399963
            chosen = (
                math.cos(angle) * base_span * 1.45,
                math.sin(angle) * base_span * 0.85,
                (len(positioned) % 5 - 2) * 320,
            )
        cluster["x"], cluster["y"], cluster["z"] = compact_point(chosen)
        positioned.append(cluster)

    for cluster in clusters:
        basis = Basis(tuple(cluster["basisU"]), tuple(cluster["basisV"]), tuple(cluster["basisN"]))
        center = (cluster["x"], cluster["y"], cluster["z"])
        radius = cluster["radius"]
        for story in cluster["children"]:
            rng = random.Random(stable_seed(seed, story["id"], "story-position"))
            theta = rng.uniform(0, math.tau)
            z_direction = rng.uniform(-1.0, 1.0)
            xy_direction = math.sqrt(max(0.0, 1.0 - z_direction * z_direction))
            if rng.random() < 0.82:
                radial = rng.random() ** (1 / 3) * radius * 0.77
            else:
                radial = radius * rng.uniform(1.04, 1.34)
            local = (
                math.cos(theta) * xy_direction * radial,
                math.sin(theta) * xy_direction * radial,
                z_direction * radial,
            )
            world = local_to_world(center, basis, local)
            story["x"], story["y"], story["z"] = compact_point(world)

    world_extent = base_span * 1.15
    occupied_clusters = clusters
    for story in stories:
        if story.get("clusterId") and not story["isTrailer"]:
            continue
        rng = random.Random(stable_seed(seed, story["id"], "free-floating"))
        chosen = None
        for _ in range(3000):
            candidate = (
                rng.uniform(-world_extent, world_extent),
                rng.uniform(-world_extent * 0.68, world_extent * 0.68),
                rng.uniform(-world_extent * 0.78, world_extent * 0.78),
            )
            if all(
                length(vector_sub(candidate, (cluster["x"], cluster["y"], cluster["z"])))
                > cluster["radius"] * 1.24
                for cluster in occupied_clusters
            ):
                chosen = candidate
                break
        chosen = chosen or (rng.uniform(-world_extent, world_extent), 0.0, 0.0)
        story["x"], story["y"], story["z"] = compact_point(chosen)

    story_lookup: dict[str, dict[str, Any]] = {}
    for story in stories:
        story_lookup[story["pageId"]] = story
        story_lookup[story["catalogId"]] = story
        story_lookup[story["name"].casefold()] = story
        story_lookup[story["id"]] = story
    cluster_lookup: dict[str, dict[str, Any]] = {}
    for cluster in clusters:
        cluster_lookup[cluster["pageId"]] = cluster
        cluster_lookup[cluster["name"].casefold()] = cluster
        cluster_lookup[cluster["id"]] = cluster

    links: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    unresolved: list[str] = []

    def add_link(source: dict[str, Any], target: dict[str, Any], kind: str) -> None:
        if source["id"] == target["id"]:
            return
        key = (kind, *sorted((source["id"], target["id"])))
        if key in seen:
            return
        seen.add(key)
        source_center = (source["x"], source["y"], source["z"])
        target_center = (target["x"], target["y"], target["z"])
        start = nearest_ring_point(source, target_center) if source["kind"] == "cluster" else source_center
        end = nearest_ring_point(target, source_center) if target["kind"] == "cluster" else target_center
        links.append({
            "source": source["id"],
            "target": target["id"],
            "kind": kind,
            "start": compact_point(start),
            "end": compact_point(end),
        })

    for story in stories:
        for token in parse_tokens(story["nodeConnections"]):
            target = resolve_target(token, story_lookup)
            if target:
                add_link(story, target, "story-story")
            else:
                unresolved.append(f"{story['name']} -> story {token!r}")
        for token in parse_tokens(story["clusterConnections"]):
            target = resolve_target(token, cluster_lookup)
            if target:
                add_link(story, target, "story-cluster")
            else:
                unresolved.append(f"{story['name']} -> cluster {token!r}")

    for cluster in clusters:
        raw = cluster["raw"]
        for token in parse_tokens(first(raw, "Cluster connections", default="")):
            target = resolve_target(token, cluster_lookup)
            if target:
                add_link(cluster, target, "cluster-cluster")
            else:
                unresolved.append(f"{cluster['name']} -> cluster {token!r}")
        for token in parse_tokens(first(raw, "Node connections", default="")):
            target = resolve_target(token, story_lookup)
            if target:
                add_link(cluster, target, "cluster-story")
            else:
                unresolved.append(f"{cluster['name']} -> story {token!r}")

    public_clusters = []
    for cluster in clusters:
        clean = {
            key: value
            for key, value in cluster.items()
            if key not in {"raw", "children", "pageId"}
        }
        public_clusters.append(clean)
    public_stories = []
    for story in stories:
        clean = {
            key: value
            for key, value in story.items()
            if key not in {"raw", "subparts", "nodeConnections", "clusterConnections", "pageId"}
        }
        public_stories.append(clean)

    all_nodes = public_clusters + public_stories
    xs = [node["x"] for node in all_nodes]
    ys = [node["y"] for node in all_nodes]
    zs = [node["z"] for node in all_nodes]
    bounds = {
        "minX": min(xs, default=-1000), "maxX": max(xs, default=1000),
        "minY": min(ys, default=-1000), "maxY": max(ys, default=1000),
        "minZ": min(zs, default=-1000), "maxZ": max(zs, default=1000),
    }
    return {
        "seed": seed,
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "clusters": public_clusters,
        "stories": public_stories,
        "nodes": all_nodes,
        "links": links,
        "bounds": bounds,
        "unresolvedConnections": unresolved,
    }


HTML_TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>POPPYVERSE 3D MAP 2.0</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Michroma&family=Space+Grotesk:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root { --pink:#ff1447; --panel:rgba(7,9,19,.78); --line:rgba(195,218,255,.35); }
    * { box-sizing:border-box; }
    html,body { width:100%; height:100%; margin:0; overflow:hidden; background:#02030a; color:#eef4ff; }
    body { font-family:"Space Grotesk",system-ui,sans-serif; }
    #graph { position:fixed; inset:0; background:
      radial-gradient(circle at 52% 42%,rgba(25,49,92,.16),transparent 38%),
      radial-gradient(circle at 20% 80%,rgba(92,20,80,.12),transparent 32%),#02030a; }
    poppy-nav { z-index:10; }
    .map-tools { position:fixed; z-index:11; bottom:18px; left:18px; display:flex; flex-wrap:wrap; gap:10px; }
    .tool-button { height:42px; display:inline-flex; align-items:center; gap:10px; padding:0 16px; border:1px solid rgba(255,255,255,.18);
      border-radius:999px; background:rgba(3,5,12,.72); color:#e8effb; backdrop-filter:blur(16px); cursor:pointer;
      font-family:Michroma,sans-serif; font-size:10px; letter-spacing:.09em; text-transform:uppercase;
      box-shadow:0 10px 35px rgba(0,0,0,.3); transition:border-color .18s ease,background .18s ease,box-shadow .18s ease; }
    .tool-button:hover,.tool-button.is-on { border-color:rgba(255,255,255,.42); background:rgba(9,12,23,.88); }
    .tool-button.is-on { box-shadow:0 0 22px color-mix(in srgb,var(--pink) 24%,transparent); }
    .toggle-track { position:relative; width:31px; height:17px; border-radius:999px; background:rgba(255,255,255,.18); transition:background .18s ease; }
    .toggle-track::after { content:""; position:absolute; width:13px; height:13px; top:2px; left:2px; border-radius:50%; background:#fff;
      box-shadow:0 0 10px rgba(255,255,255,.55); transition:transform .18s ease; }
    .tool-button.is-on .toggle-track { background:var(--pink); }
    .tool-button.is-on .toggle-track::after { transform:translateX(14px); }
    .tool-button .caret { display:inline-block; transition:transform .18s ease; }
    .tool-button[aria-expanded="true"] .caret { transform:rotate(180deg); }
    .legend { position:fixed; z-index:10; left:18px; bottom:72px; width:270px; max-height:calc(100vh - 160px);
      overflow:auto; padding:14px; border:1px solid rgba(174,205,255,.17); border-radius:16px;
      background:rgba(5,7,16,.88); backdrop-filter:blur(22px); opacity:0; pointer-events:none; transform:translateY(8px) scale(.98);
      transform-origin:bottom left; transition:opacity .18s ease,transform .18s ease; }
    .legend.open { opacity:1; pointer-events:auto; transform:translateY(0) scale(1); }
    .legend-title { font-family:Michroma,sans-serif; font-size:11px; letter-spacing:.1em; margin:0 0 10px; }
    .legend-section { margin:12px 3px 5px; color:#718099; font-size:9px; letter-spacing:.13em; text-transform:uppercase; }
    .legend-row { display:grid; grid-template-columns:13px 1fr auto; gap:9px; align-items:center; padding:6px 3px; }
    .swatch { width:10px; height:10px; border-radius:50%; box-shadow:0 0 12px currentColor; }
    .shape-icon { width:14px; color:#dce8fa; font-size:14px; text-align:center; text-shadow:0 0 10px #7eb7ff; }
    .legend-name { font-size:11px; color:#dce8fa; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .legend-count { color:#718099; font-size:10px; }
    .drawer-backdrop { position:fixed; inset:0; z-index:12; background:rgba(0,0,0,.46); opacity:0; pointer-events:none; transition:opacity .2s ease; }
    .drawer-backdrop.open { opacity:1; pointer-events:auto; }
    .drawer { position:fixed; z-index:13; top:0; right:0; width:min(560px,96vw); height:100%;
      transform:translateX(105%); transition:transform .24s ease; overflow:auto; background:#080910;
      border-left:1px solid rgba(255,255,255,.16); box-shadow:-24px 0 70px rgba(0,0,0,.62); }
    .drawer.open { transform:translateX(0); }
    poppy-card { --poppy-card-top:96px; min-height:100%; }
    @media(max-width:760px) { .map-tools{left:10px;right:10px;bottom:10px}.tool-button{padding:0 12px}.legend{left:10px;right:10px;bottom:120px;width:auto;max-height:calc(100vh - 208px)} }
  </style>
</head>
<body>
  <div id="graph"></div>
  <script src="components/poppy-nav.js"></script>
  <script src="components/poppy-card.js"></script>
  <poppy-nav></poppy-nav>
  <div class="map-tools">
    <button id="linksToggle" class="tool-button is-on" type="button" aria-pressed="true"><span class="toggle-track"></span><span>Connections</span></button>
    <button id="ringsToggle" class="tool-button is-on" type="button" aria-pressed="true"><span class="toggle-track"></span><span>Cluster rings</span></button>
    <button id="legendToggle" class="tool-button" type="button" aria-expanded="false"><span>Legend</span><span class="caret" aria-hidden="true">▴</span></button>
  </div>
  <aside id="legend" class="legend" aria-hidden="true"><h2 class="legend-title">MAP LEGEND</h2><div id="legendRows"></div></aside>
  <div id="drawerBackdrop" class="drawer-backdrop"></div>
  <aside id="drawer" class="drawer" aria-hidden="true"><poppy-card id="card"></poppy-card></aside>
  <script id="poppy-data" type="application/json">__DATA__</script>
  <script src="https://unpkg.com/three@0.148.0/build/three.min.js"></script>
  <script src="https://unpkg.com/3d-force-graph@1.72.0/dist/3d-force-graph.min.js"></script>
  <script>
  (() => {
    "use strict";
    const DATA = JSON.parse(document.getElementById("poppy-data").textContent);
    const graphEl = document.getElementById("graph");
    const drawer = document.getElementById("drawer");
    const card = document.getElementById("card");
    const drawerBackdrop = document.getElementById("drawerBackdrop");
    const legendPanel = document.getElementById("legend");
    const nodeById = new Map(DATA.nodes.map(node => [String(node.id), node]));
    const glowTextures = new Map();
    const ringObjects = new Map();
    const storyObjects = new Map();

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    }
    function formatBytes(value) {
      let n = Number(value) || 0;
      if (n < 1024) return `${Math.round(n)} B`;
      const units = ["KB","MB","GB"]; let i = -1;
      do { n /= 1024; i++; } while (n >= 1024 && i < units.length - 1);
      return `${n.toFixed(n >= 100 ? 0 : n >= 10 ? 1 : 2)} ${units[i]}`;
    }
    function glowTexture(color) {
      if (glowTextures.has(color)) return glowTextures.get(color);
      const canvas = document.createElement("canvas"); canvas.width = canvas.height = 128;
      const ctx = canvas.getContext("2d"); const g = ctx.createRadialGradient(64,64,0,64,64,64);
      g.addColorStop(0,color + "FF");
      g.addColorStop(.1,color + "F0");
      g.addColorStop(.2,color + "D8");
      g.addColorStop(.32,color + "B4");
      g.addColorStop(.45,color + "8A");
      g.addColorStop(.58,color + "62");
      g.addColorStop(.7,color + "40");
      g.addColorStop(.8,color + "26");
      g.addColorStop(.9,color + "12");
      g.addColorStop(.96,color + "05");
      g.addColorStop(1,color + "00");
      ctx.fillStyle = g; ctx.fillRect(0,0,128,128);
      const texture = new THREE.CanvasTexture(canvas); glowTextures.set(color,texture); return texture;
    }
    function createGlowSprite(color, opacity=.55) {
      const sprite = new THREE.Sprite(new THREE.SpriteMaterial({map:glowTexture(color),transparent:true,opacity,depthTest:false,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false}));
      sprite.raycast=()=>{}; sprite.renderOrder=8; return sprite;
    }
    function addGlow(group, color, size, opacity=.55) {
      const sprite=createGlowSprite(color,opacity); sprite.scale.set(size,size,1); group.add(sprite); return sprite;
    }
    function hash32(text) {
      let hash=2166136261;
      for (const c of String(text)) hash=Math.imul(hash^c.charCodeAt(0),16777619);
      return hash>>>0;
    }
    function seededUnit(seed) {
      let x=seed>>>0; x^=x<<13; x^=x>>>17; x^=x<<5; return (x>>>0)/4294967296;
    }
    function orientFromBasis(group, node) {
      const u = new THREE.Vector3(...node.basisU), v = new THREE.Vector3(...node.basisV), n = new THREE.Vector3(...node.basisN);
      const matrix = new THREE.Matrix4().makeBasis(u,v,n); group.setRotationFromMatrix(matrix);
    }
    function makeClusterRing(node) {
      const group = new THREE.Group(); const color = new THREE.Color(node.color);
      const tube = Math.max(.9, Math.min(2.2, node.radius * .0045));
      const ring = new THREE.Mesh(new THREE.TorusGeometry(node.radius,tube,16,160),new THREE.MeshBasicMaterial({color,toneMapped:false}));
      const halo = new THREE.Mesh(new THREE.TorusGeometry(node.radius,tube*2,12,160),new THREE.MeshBasicMaterial({color,transparent:true,opacity:.18,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false}));
      const outerGlow = new THREE.Mesh(new THREE.TorusGeometry(node.radius,tube*3.2,10,160),new THREE.MeshBasicMaterial({color,transparent:true,opacity:.06,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false}));
      const veil = new THREE.Mesh(new THREE.CircleGeometry(node.radius*.985,128),new THREE.MeshBasicMaterial({color,transparent:true,opacity:.026,side:THREE.DoubleSide,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false}));
      halo.raycast=()=>{}; outerGlow.raycast=()=>{}; veil.raycast=()=>{};
      ring.userData.clusterRing = true; halo.userData.clusterRing = true; outerGlow.userData.clusterRing = true; veil.userData.clusterRing = true;
      group.add(ring,halo,outerGlow,veil); orientFromBasis(group,node); ringObjects.set(String(node.id),group); return group;
    }
    function makePlanetRing(group, color, radius, seedText) {
      const ring = new THREE.Mesh(new THREE.RingGeometry(radius*1.95,radius*2.28,56),new THREE.MeshBasicMaterial({color:new THREE.Color(color).lerp(new THREE.Color(0xffffff),.28),transparent:true,opacity:.78,side:THREE.DoubleSide,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false}));
      let hash = hash32(seedText);
      ring.rotation.set(((hash>>>0)%1000)/1000*Math.PI,(((hash>>>10)%1000)/1000)*Math.PI,(((hash>>>20)%1000)/1000)*Math.PI);
      group.add(ring);
    }
    function triangularPyramidGeometry(radius) {
      const apexY=radius*1.15, baseY=-radius*.62, baseR=radius*.92;
      const positions=[0,apexY,0];
      for(let i=0;i<3;i++) {
        const a=-Math.PI/2+i*Math.PI*2/3;
        positions.push(Math.cos(a)*baseR,baseY,Math.sin(a)*baseR);
      }
      const geometry=new THREE.BufferGeometry();
      geometry.setAttribute("position",new THREE.Float32BufferAttribute(positions,3));
      geometry.setIndex([1,3,2, 0,1,2, 0,2,3, 0,3,1]);
      geometry.computeVertexNormals(); return geometry;
    }
    function makeStoryNode(node) {
      const group = new THREE.Group(); const color = new THREE.Color(node.color || "#8793A8");
      const radius = Number(node.visualRadius) || 12;
      let geometry;
      if (node.isTrailer) geometry = new THREE.SphereGeometry(radius*1.45,24,18);
      else if (node.isEbook) geometry = new THREE.BoxGeometry(radius*2,radius*2,radius*2);
      else if (node.isIntro) geometry = triangularPyramidGeometry(radius*1.7);
      else geometry = new THREE.SphereGeometry(radius,24,20);
      const material = new THREE.MeshBasicMaterial({color,toneMapped:false});
      const core = new THREE.Mesh(geometry,material); group.add(core);
      const objectSeed=hash32(node.id+"|shape");
      if (node.isTrailer) {
        const tailSeed=hash32(node.id+"|trailerTail");
        const tailDir=new THREE.Vector3(seededUnit(tailSeed)-.5,seededUnit(tailSeed+1)-.5,seededUnit(tailSeed+2)-.5).normalize();
        const tailBack=tailDir.clone().multiplyScalar(-1), tailLength=radius*9.5;
        const tailQuaternion=new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,1,0),tailBack);
        const outerFlame=new THREE.Mesh(new THREE.ConeGeometry(radius*2.5,tailLength,24,1,true),new THREE.MeshBasicMaterial({color,transparent:true,opacity:.42,side:THREE.DoubleSide,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false}));
        outerFlame.position.copy(tailBack).multiplyScalar(tailLength*.5); outerFlame.quaternion.copy(tailQuaternion); outerFlame.raycast=()=>{}; group.add(outerFlame);
        const hotColor=new THREE.Color(color).lerp(new THREE.Color(0xffffff),.42);
        const innerFlame=new THREE.Mesh(new THREE.ConeGeometry(radius*1.05,tailLength*.78,20,1,true),new THREE.MeshBasicMaterial({color:hotColor,transparent:true,opacity:.66,side:THREE.DoubleSide,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false}));
        innerFlame.position.copy(tailBack).multiplyScalar(tailLength*.39); innerFlame.quaternion.copy(tailQuaternion); innerFlame.raycast=()=>{}; group.add(innerFlame);
        const hotHex="#"+hotColor.getHexString();
        for(let i=1;i<=12;i++) {
          const t=i/12, puff=createGlowSprite(node.color,(1-t*.7)*.9);
          const puffSize=(1-t*.78)*radius*5;
          puff.scale.set(puffSize,puffSize,1);
          puff.position.copy(tailBack).multiplyScalar(t*tailLength);
          group.add(puff);
          if(i<9) {
            const hot=createGlowSprite(hotHex,(1-t)*.72);
            const hotSize=(1-t*.82)*radius*2.6;
            hot.scale.set(hotSize,hotSize,1); hot.position.copy(puff.position); group.add(hot);
          }
        }
      } else if (node.isIntro || node.isEbook) {
        core.rotation.set(seededUnit(objectSeed)*Math.PI*2,seededUnit(objectSeed+1)*Math.PI*2,seededUnit(objectSeed+2)*Math.PI*2);
      }
      if (!node.isTrailer) {
        const highlight=new THREE.Mesh(new THREE.SphereGeometry(radius*.18,12,10),new THREE.MeshBasicMaterial({color:0xffffff,transparent:true,opacity:.72,depthWrite:false,toneMapped:false}));
        highlight.position.set(-radius*.34,radius*.36,radius*.72); highlight.raycast=()=>{}; group.add(highlight);
      }
      if (node.published) makePlanetRing(group,node.color,radius,node.id);
      addGlow(group,node.color,node.isTrailer?radius*11:radius*12,node.isTrailer?.58:.48);
      addGlow(group,node.color,node.isTrailer?radius*18:radius*20,node.isTrailer?.18:.16);
      addGlow(group,node.color,node.isTrailer?radius*27:radius*31,node.isTrailer?.06:.05);
      storyObjects.set(String(node.id),group); return group;
    }

    DATA.nodes.forEach(node => { node.fx=node.x; node.fy=node.y; node.fz=node.z; node.val=1; });
    const graphData = {nodes:DATA.nodes,links:[]};
    const Graph = ForceGraph3D()(graphEl)
      .graphData(graphData).showNavInfo(false).enableNodeDrag(false).cooldownTicks(0)
      .d3Force("link",null).d3Force("charge",null)
      .nodeLabel(node => `<div style="padding:7px 9px;background:rgba(3,5,12,.9);border:1px solid ${escapeHtml(node.color)}55;border-radius:8px"><b>${escapeHtml(node.label)}</b><br><small>${node.kind === "cluster" ? `${node.storyCount} stories · ${formatBytes(node.totalBytes)}` : escapeHtml(node.clusterName || (node.isTrailer ? "Free-floating trailer" : "Unclustered"))}</small></div>`)
      .nodeThreeObject(node => node.kind === "cluster" ? makeClusterRing(node) : makeStoryNode(node))
      .onNodeClick(node => openDrawer(node));

    Graph.backgroundColor("rgba(0,0,0,0)");
    const renderer=Graph.renderer();
    renderer.toneMapping=THREE.NoToneMapping;
    if ("outputColorSpace" in renderer && THREE.SRGBColorSpace) renderer.outputColorSpace=THREE.SRGBColorSpace;
    const scene = Graph.scene();
    scene.add(new THREE.AmbientLight(0x33466f,.18));
    const key = new THREE.DirectionalLight(0xbcd8ff,.72); key.position.set(900,1300,1100); scene.add(key);
    const fill = new THREE.DirectionalLight(0x764fba,.2); fill.position.set(-900,-500,-700); scene.add(fill);

    const connections = new THREE.Group(); connections.name="poppy-connections"; scene.add(connections);
    function makeBeam(link) {
      const points=[new THREE.Vector3(...link.start),new THREE.Vector3(...link.end)];
      const group=new THREE.Group();
      const geometry=new THREE.BufferGeometry().setFromPoints(points);
      const opacity=link.kind === "cluster-cluster" ? .92 : link.kind.includes("cluster") ? .78 : .56;
      const main=new THREE.Line(geometry,new THREE.LineBasicMaterial({color:0xeaf4ff,transparent:true,opacity,depthWrite:false}));
      const glow=new THREE.Line(geometry.clone(),new THREE.LineBasicMaterial({color:0x7eb7ff,transparent:true,opacity:opacity*.32,depthWrite:false,blending:THREE.AdditiveBlending}));
      glow.scale.setScalar(1.0001); group.add(glow,main); group.userData.kind=link.kind; return group;
    }
    DATA.links.forEach(link => connections.add(makeBeam(link)));

    const b=DATA.bounds; const cx=(b.minX+b.maxX)/2, cy=(b.minY+b.maxY)/2, cz=(b.minZ+b.maxZ)/2;
    const span=Math.max(b.maxX-b.minX,b.maxY-b.minY,b.maxZ-b.minZ,700);
    Graph.cameraPosition({x:cx+span*.40,y:cy+span*.20,z:cz+span*.70},{x:cx,y:cy,z:cz},0);
    Graph.controls().target.set(cx,cy,cz); Graph.controls().minDistance=80; Graph.controls().maxDistance=span*5;

    function asList(value) {
      if(Array.isArray(value)) return value.map(String).map(item=>item.trim()).filter(Boolean);
      return String(value||"").split(/[;,]/).map(item=>item.trim()).filter(Boolean);
    }
    function connectionNodes(node) {
      const found=new Map();
      DATA.links.forEach(link=>{
        let otherId="";
        if(String(link.source)===String(node.id)) otherId=String(link.target);
        else if(String(link.target)===String(node.id)) otherId=String(link.source);
        if(otherId && nodeById.has(otherId)) found.set(otherId,nodeById.get(otherId));
      });
      return [...found.values()];
    }
    function closeDrawer() {
      drawer.classList.remove("open"); drawerBackdrop.classList.remove("open"); drawer.setAttribute("aria-hidden","true");
    }
    function openDrawer(node) {
      const related=connectionNodes(node);
      const connections={title:"Connections",chips:related.map(n=>({id:String(n.id),label:n.label||n.name})),empty:"—"};
      if (node.kind === "cluster") {
        card.data={
          title:node.name, badge:"Cluster ring", color:node.color||"#ff1447",
          sections:[
            {title:"Description",text:node.description,empty:"No cluster description yet."},
            {title:"Details",stats:[{label:"Stories",value:String(node.storyCount)},{label:"Story bytes",value:formatBytes(node.totalBytes)},{label:"Connections",value:String(related.length)}]},
            connections,
          ],
        };
      } else {
        const shape=node.isTrailer?"Trailer":node.isEbook?"E-book":node.isIntro?"Intro":"Story";
        card.data={
          title:node.name, badge:node.clusterName||shape, color:node.color||"#ff1447",
          sections:[
            {title:"Description",text:node.description,empty:"No description yet."},
            {title:"Details",stats:[{label:"Type",value:shape},{label:"Manuscript",value:node.usesDefaultSize?"Default size":formatBytes(node.bytes)},{label:"Status",value:node.status||"—"}]},
            {title:"Characters",chips:asList(node.characters),empty:"—"},
            {title:"Content warnings",chips:asList(node.contentWarnings),empty:"None listed"},
            connections,
            {title:"Content",link:node.contentUrl?{href:node.contentUrl,label:"Open"}:null,empty:"Content not ready."},
          ],
        };
      }
      drawer.classList.add("open"); drawerBackdrop.classList.add("open"); drawer.setAttribute("aria-hidden","false");
    }
    card.addEventListener("close",closeDrawer);
    card.addEventListener("chip-select",event=>{
      const target=nodeById.get(event.detail.id);
      if(target) openDrawer(target);
    });
    drawerBackdrop.addEventListener("click",closeDrawer);
    function toggleButton(button,enabled) {
      button.classList.toggle("is-on",enabled); button.setAttribute("aria-pressed",String(enabled));
    }
    const linksToggle=document.getElementById("linksToggle");
    const ringsToggle=document.getElementById("ringsToggle");
    linksToggle.addEventListener("click",()=>{const enabled=linksToggle.getAttribute("aria-pressed")!=="true"; connections.visible=enabled; toggleButton(linksToggle,enabled);});
    ringsToggle.addEventListener("click",()=>{const enabled=ringsToggle.getAttribute("aria-pressed")!=="true"; ringObjects.forEach(object=>object.visible=enabled); toggleButton(ringsToggle,enabled);});
    const legendToggle=document.getElementById("legendToggle");
    legendToggle.addEventListener("click",()=>{const open=!legendPanel.classList.contains("open"); legendPanel.classList.toggle("open",open); legendPanel.setAttribute("aria-hidden",String(!open)); legendToggle.setAttribute("aria-expanded",String(open)); legendToggle.classList.toggle("is-on",open);});

    const legend=document.getElementById("legendRows");
    const shapes=[
      ["◯","Cluster rings"],
      ["●","Sphere nodes"],
      ["■","Cubes — e-books"],
      ["▲","Triangular pyramids — intros"],
      ["☄","Comet spheres — trailers"]
    ];
    shapes.forEach(([icon,label])=>{
      const row=document.createElement("div"); row.className="legend-row";
      row.innerHTML=`<span class="shape-icon">${icon}</span><span class="legend-name">${escapeHtml(label)}</span><span></span>`;
      legend.appendChild(row);
    });
    const section=document.createElement("div"); section.className="legend-section"; section.textContent="Cluster colors"; legend.appendChild(section);
    DATA.clusters.forEach(cluster=>{
      const row=document.createElement("div"); row.className="legend-row";
      row.innerHTML=`<span class="swatch" style="background:${escapeHtml(cluster.color)};color:${escapeHtml(cluster.color)}"></span><span class="legend-name">${escapeHtml(cluster.name)}</span><span class="legend-count">${cluster.storyCount}</span>`;
      row.addEventListener("click",()=>openDrawer(cluster)); legend.appendChild(row);
    });
    window.addEventListener("resize",()=>{Graph.width(window.innerWidth).height(window.innerHeight);});
  })();
  </script>
</body>
</html>
'''


def build_html(data: dict[str, Any]) -> str:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    raw = raw.replace("</", "<\\/")
    return (
        HTML_TEMPLATE.replace("__DATA__", raw)
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build 3d_map_2.html directly from the Poppyverse Notion catalogues.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Generated HTML path")
    parser.add_argument("--full-data-source", default=os.environ.get("NOTION_FULL_CATALOG_DATA_SOURCE_ID", DEFAULT_FULL_DATA_SOURCE))
    parser.add_argument("--cluster-data-source", default=os.environ.get("NOTION_CLUSTER_CATALOG_DATA_SOURCE_ID", DEFAULT_CLUSTER_DATA_SOURCE))
    parser.add_argument("--seed", type=int, default=20261108, help="Stable layout seed")
    parser.add_argument("--snapshot", help="Read catalogue rows as JSON from this file ('-' for stdin) instead of calling Notion; build_all.py uses this.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.snapshot:
        full_rows, cluster_rows = load_snapshot(args.snapshot)
    else:
        try:
            full_rows, cluster_rows = fetch_catalogues(args.full_data_source, args.cluster_data_source)
        except NotionError as exc:
            raise SystemExit(f"Notion fetch failed: {exc}") from None

    if not full_rows:
        raise SystemExit("The Full Catalogue query returned no rows; refusing to overwrite the map.")
    if not cluster_rows:
        raise SystemExit("The Cluster Catalogue query returned no rows; refusing to overwrite the map.")

    data = build_map_data(full_rows, cluster_rows, args.seed)
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_html(data), encoding="utf-8")
    print(f"Built {output}")
    print(f"Clusters: {len(data['clusters'])}")
    print(f"Stories: {len(data['stories'])}")
    print(f"Links: {len(data['links'])}")
    print(f"Layout seed: {data['seed']}")
    if data["unresolvedConnections"]:
        print(f"Warning: {len(data['unresolvedConnections'])} unresolved connection(s):", file=sys.stderr)
        for item in data["unresolvedConnections"][:25]:
            print(f"  - {item}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
