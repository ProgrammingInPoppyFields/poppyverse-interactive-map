#!/usr/bin/env python3
"""
build_all.py

One-command build script for the Poppyverse static site.

Assumes these source-of-truth files are updated and ready:
- SRC_clusters.csv
- SRC_toc.csv

Runs the page generators and writes:
- index.html
- about.html
- 2d_map.html
- 3d_map.html

Usage:
  python build_all.py
  python build_all.py --src-dir . --out-dir .
  python build_all.py --skip-3d
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_CLUSTERS = "SRC_clusters.csv"
DEFAULT_TOC = "SRC_toc.csv"


@dataclass(frozen=True)
class BuildStep:
    name: str
    script: str
    output: str
    needs_sources: bool = False
    extra_args: tuple[str, ...] = ()


def resolve(base: Path, maybe_relative: str | Path) -> Path:
    path = Path(maybe_relative)
    return path if path.is_absolute() else base / path


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"Expected {label} to be a file, but got: {path}")


def run_step(
    step: BuildStep,
    *,
    python_exe: str,
    script_dir: Path,
    out_dir: Path,
    clusters_path: Path,
    toc_path: Path,
) -> None:
    script_path = resolve(script_dir, step.script)
    output_path = resolve(out_dir, step.output)

    require_file(script_path, f"generator script for {step.name}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [python_exe, str(script_path)]

    if step.needs_sources:
        cmd.extend([
            "--clusters", str(clusters_path),
            "--toc", str(toc_path),
        ])

    # The generators currently accept either --out or --output depending on page.
    # Step-specific args keep this orchestrator boring and predictable.
    cmd.extend(step.extra_args)
    cmd.append(str(output_path))

    print(f"\n=== Building {step.name} ===")
    print(" ".join(cmd))

    completed = subprocess.run(cmd, cwd=script_dir, text=True)
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, cmd)

    require_file(output_path, f"output for {step.name}")
    print(f"✓ {step.name}: {output_path.name}")


def build_steps(args: argparse.Namespace) -> list[BuildStep]:
    steps = [
        BuildStep(
            name="Home splash page",
            script="build_home.py",
            output="index.html",
            needs_sources=False,
            extra_args=("--output",),
        ),
        BuildStep(
            name="About page",
            script="build_about.py",
            output="about.html",
            needs_sources=False,
            extra_args=("--output",),
        ),
    ]

    if not args.skip_2d:
        steps.append(
            BuildStep(
                name="2D map",
                script="build_2d_map.py",
                output="2d_map.html",
                needs_sources=True,
                extra_args=("--out",),
            )
        )

    if not args.skip_3d:
        steps.append(
            BuildStep(
                name="3D map",
                script="build_3d_map_with_nav.py",
                output="3d_map.html",
                needs_sources=True,
                extra_args=("--output",),
            )
        )

    return steps


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build all Poppyverse static HTML pages from the current source CSVs."
    )
    parser.add_argument(
        "--src-dir",
        default=".",
        help="Directory containing SRC_clusters.csv, SRC_toc.csv, and the generator scripts. Default: current script directory / working repo root.",
    )
    parser.add_argument(
        "--out-dir",
        default=".",
        help="Directory where generated HTML files should be written. Default: same directory.",
    )
    parser.add_argument(
        "--clusters",
        default=DEFAULT_CLUSTERS,
        help=f"Cluster CSV filename/path. Default: {DEFAULT_CLUSTERS}",
    )
    parser.add_argument(
        "--toc",
        default=DEFAULT_TOC,
        help=f"TOC CSV filename/path. Default: {DEFAULT_TOC}",
    )
    parser.add_argument("--skip-2d", action="store_true", help="Do not rebuild 2d_map.html.")
    parser.add_argument("--skip-3d", action="store_true", help="Do not rebuild 3d_map.html.")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)

    # Anchor relative paths to the folder containing this script, which is the
    # least surprising behavior when run from random terminals / VS Code panes.
    script_dir = Path(__file__).resolve().parent
    src_dir = resolve(script_dir, args.src_dir).resolve()
    out_dir = resolve(script_dir, args.out_dir).resolve()

    clusters_path = resolve(src_dir, args.clusters).resolve()
    toc_path = resolve(src_dir, args.toc).resolve()

    print("Poppyverse build starting.")
    print(f"Source dir: {src_dir}")
    print(f"Output dir: {out_dir}")

    require_file(clusters_path, "cluster source CSV")
    require_file(toc_path, "TOC source CSV")

    steps = build_steps(args)
    for step in steps:
        run_step(
            step,
            python_exe=sys.executable,
            script_dir=src_dir,
            out_dir=out_dir,
            clusters_path=clusters_path,
            toc_path=toc_path,
        )

    print("\nAll done. The Poppyverse has been rebuilt, which is concerning but convenient.")
    for step in steps:
        print(f"- {resolve(out_dir, step.output)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nBuild failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
