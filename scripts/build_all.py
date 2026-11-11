#!/usr/bin/env python3
"""Rebuild the public Poppyverse pages from the repository root.

Usage (from the repo root):

  python3 -u scripts/build_all.py              # rebuild every page
  python3 -u scripts/build_all.py 2d 3d        # only the 2D and 3D maps
  python3 -u scripts/build_all.py home about   # only the static pages

Pages: home, about, 2d, 3d (3d = 3d_map.html).

This script is the only place that talks to Notion. It fetches The Full
Catalogue and The Cluster Catalogue once, then hands the same rows to the 2D
and 3D generators over stdin (their `--snapshot -` mode). Nothing is written to
disk except the finished HTML pages. Set NOTION_TOKEN before running:

The individual generators can still be run on their own; without `--snapshot`
they fetch from Notion themselves.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from poppyverse_notion import (
    DEFAULT_CLUSTER_DATA_SOURCE,
    DEFAULT_FULL_DATA_SOURCE,
    NotionError,
    fetch_catalogues,
)


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent


PAGES = ("home", "about", "2d", "3d")


@dataclass(frozen=True)
class Step:
    name: str
    script: str
    output: str
    args: tuple[str, ...] = ()
    needs_notion: bool = False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Poppyverse static site from Notion.")
    parser.add_argument(
        "pages",
        nargs="*",
        type=str.lower,
        metavar="page",
        help="Pages to rebuild: " + ", ".join(PAGES) + ". Omit to rebuild all of them.",
    )
    parser.add_argument("--seed", type=int, default=20261108, help="Stable 3D layout seed.")
    parser.add_argument(
        "--full-data-source",
        default=os.environ.get("NOTION_FULL_CATALOG_DATA_SOURCE_ID", DEFAULT_FULL_DATA_SOURCE),
        help="Full Catalogue data-source ID (or NOTION_FULL_CATALOG_DATA_SOURCE_ID).",
    )
    parser.add_argument(
        "--cluster-data-source",
        default=os.environ.get("NOTION_CLUSTER_CATALOG_DATA_SOURCE_ID", DEFAULT_CLUSTER_DATA_SOURCE),
        help="Cluster Catalogue data-source ID (or NOTION_CLUSTER_CATALOG_DATA_SOURCE_ID).",
    )
    args = parser.parse_args(argv)
    # Validated by hand: argparse's `choices` rejects the empty default for nargs="*".
    unknown = [page for page in args.pages if page not in PAGES]
    if unknown:
        parser.error(f"unknown page(s): {', '.join(unknown)} (choose from {', '.join(PAGES)})")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    wanted = set(args.pages) or set(PAGES)
    steps: list[Step] = []
    if "home" in wanted:
        steps.append(Step("Home", "build_home.py", "index.html"))
    if "about" in wanted:
        steps.append(Step("About", "build_about.py", "about.html"))
    if "2d" in wanted:
        steps.append(Step("2D map", "build_2d_map.py", "2d_map.html",
                          ("--output", str(REPO_ROOT / "2d_map.html")), needs_notion=True))
    if "3d" in wanted:
        steps.append(Step("3D map", "build_3d_map.py", "3d_map.html",
                          ("--output", str(REPO_ROOT / "3d_map.html"), "--seed", str(args.seed)),
                          needs_notion=True))

    print(f"Building Poppyverse in {REPO_ROOT}", flush=True)

    # One Notion fetch, shared by every step that needs catalogue data.
    snapshot: bytes | None = None
    if any(step.needs_notion for step in steps):
        try:
            full_rows, cluster_rows = fetch_catalogues(args.full_data_source, args.cluster_data_source)
        except NotionError as exc:
            raise SystemExit(f"Notion fetch failed: {exc}") from None
        snapshot = json.dumps({"full": full_rows, "clusters": cluster_rows}).encode("utf-8")

    for step in steps:
        script = SCRIPT_DIR / step.script
        command = [sys.executable, "-u", str(script), *step.args]
        if step.needs_notion:
            command += ["--snapshot", "-"]
        print(f"\n=== {step.name} ===", flush=True)
        subprocess.run(
            command,
            cwd=REPO_ROOT,
            check=True,
            input=snapshot if step.needs_notion else None,
        )
        output = REPO_ROOT / step.output
        if not output.is_file():
            raise FileNotFoundError(f"{step.name} did not create {output}")
        print(f"✓ {output.name}", flush=True)

    print("\nAll selected pages rebuilt.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Build stopped because a generator exited with status {exc.returncode}.") from None
