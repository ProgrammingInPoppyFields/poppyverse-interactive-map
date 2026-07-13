<p align="center">
  <img src="/screenshots/4.png" alt="The Poppyverse — glowing story clusters linked by collision lines" width="100%" />
</p>

<h1 align="center">The Poppyverse Interactive Map</h1>

<p align="center">
  <em>Part story map, part multiverse directory, part emotionally unstable control panel.</em>
</p>

<p align="center">
  <strong><a href="https://programminginpoppyfields.github.io/poppyverse-interactive-map/">Explore the live map</a></strong>
</p>

---

A data-driven interactive archive for navigating a large fictional multiverse through clustered dashboards, character directories, story metadata, and 2D and 3D relationship maps.

The public site exposes the maps, navigation system, character information, and story descriptions. Full story text is kept private behind password-protected access.

---

## what is this

The Poppyverse is too interconnected for a normal table of contents and too unstable for a normal map.

This project turns its stories, characters, timelines, and relationships into a browsable interface with two complementary views:

- **2D Map** — a calmer cluster-first dashboard for structured browsing
- **3D Map** — an interactive force-directed graph for seeing collisions, connections, and narrative gravity

The site is generated from structured CSV data rather than maintained as a pile of hand-edited HTML pages. Content, metadata, relationships, and presentation logic stay separate, which makes the archive easier to expand without manually rebuilding the universe every time canon shifts.

---

## technical highlights

- Data-driven content model built from shared CSV source files
- Python generators for repeatable static-site builds
- 2D cluster dashboard for structured navigation
- Interactive 3D relationship graph using Three.js and `3d-force-graph`
- Shared navigation and visual language across generated pages
- Public metadata layer with password-protected full story content
- Static GitHub Pages deployment with no application server required
- Selective build flags for regenerating only the pages that changed

---

## how it works

```text
CSV content + relationship data
            ↓
      Python build scripts
            ↓
generated HTML / CSS / JavaScript
            ↓
  2D dashboard + 3D graph map
            ↓
      GitHub Pages deployment
```

The source CSVs hold the actual archive data. Python scripts transform that data into the public site, including the homepage, informational pages, cluster dashboard, and 3D relationship graph.

The generated HTML files are outputs, not the source of truth.

---

## site structure

| Page | What it is |
|---|---|
| `index.html` | Splash page and site entrance |
| `about.html` | About H.A.H., GenAI usage, and lucid generation |
| `2d_map.html` | Cluster-card dashboard with story and character metadata |
| `3d_map.html` | Interactive 3D relationship graph using Three.js and `3d-force-graph` |

All pages share the same top navigation:

- Home
- About
- 2D Map
- 3D Map
- Tumblr Archive

---

## source of truth

| File | What it controls |
|---|---|
| `SRC_clusters.csv` | Cluster names, descriptions, colors, and optional cover images |
| `SRC_toc.csv` | Story entries, characters, relationships, descriptions, and archive metadata |

These files drive both map views and the surrounding archive interface.

To change the content or structure of the site, update the CSVs or generator scripts rather than editing the generated HTML directly.

---

## the 3D coordinate system

`3d_map.html` doesn't plot the story metadata as literal x/y/z coordinates. Every node lives on (or inside) a sphere centered at `(0, 0, 0)`, and three `0`–`10` scores in `SRC_toc.csv` get converted into spherical coordinates:

| CSV column | Controls | Behavior |
|---|---|---|
| `(X) Relativity` | radius (distance from center) | **Inverted.** `10` pulls a node in toward the core; `0` flings it out to the globe's surface. |
| `(Y) Relatability` | latitude (pole to pole) | `0` = north pole, `10` = south pole. |
| `(Z) Depth` | longitude (around the equator) | Wraps a full circle; `0` and `10` land on the same meridian. |

What each score is actually rating, story-wise:

* **RELATIVITY:** How far the story has wandered from ordinary reality into alternate universes, interdimensional events, cosmic entities, or related complications.
* **RELATABILITY:** How closely the story resembles recognizable human life, including familiar relationships, everyday problems, and the general inconvenience of being a person.
* **DEPTH:** How emotionally dark, psychologically complex, mature, or otherwise unsuitable for casual bedtime reading the story becomes.

So `Relativity 10, Relatability 0, Depth 0` sits at the north pole right next to the core. `Relativity 0, Relatability 5, Depth 5` sits way out on the equator, on the globe's surface.

Cluster no longer affects position, only color. A small seeded jitter keeps nodes with identical scores from stacking exactly on top of each other, but is deterministic per node id, so rebuilds don't shuffle anyone around.

Axes are hidden by default — toggle "Show globe" (bottom-left) to see the reference sphere, the three labeled axis lines, the equator/meridian rings, and the origin marker.

---

## build scripts

| File | What it does |
|---|---|
| `build_all.py` | Runs the complete site build |
| `build_home.py` | Generates `index.html` |
| `build_about.py` | Generates `about.html` |
| `build_2d_map.py` | Generates the 2D cluster dashboard from the source CSVs |
| `build_3d_map_with_nav.py` | Generates the 3D relationship graph and shared navigation |

You usually only need `build_all.py`.

---

## rebuilding the site

From the repository root:

```bash
python build_all.py
```

This regenerates:

```text
index.html
about.html
2d_map.html
3d_map.html
```

The normal update flow is:

1. Update `SRC_clusters.csv`.
2. Update `SRC_toc.csv`.
3. Run `python build_all.py`.
4. Review the generated pages locally.
5. Commit the source data, generator scripts, and generated outputs.
6. Let GitHub Pages do its thing.

---

## optional build shortcuts

Regenerate only the parts you need:

```bash
python build_all.py --skip-3d
python build_all.py --skip-2d
python build_all.py --skip-home
python build_all.py --skip-about
```

Useful when the cursed glowing space cube does not need to be awakened.

---

## local preview

After rebuilding:

```bash
python3 -m http.server 8080
```

Then open:

```text
http://localhost:8080/index.html
```

---

## public and private content

The public experience is designed to make the structure of the Poppyverse visible without publishing the full text of every story.

Publicly available:

- cluster dashboards
- character directories
- story titles and descriptions
- relationship maps
- navigation and archive metadata

Password-protected:

- full story text

This boundary keeps the interactive system open for exploration while preserving the underlying writing as a private archive.

---

## deployment notes

GitHub Pages serves `index.html` as the homepage.

The primary generated pages live beside it:

```text
/index.html
/about.html
/2d_map.html
/3d_map.html
```

Do not hand-edit the generated HTML unless you enjoy losing those changes the next time the build runs. Update the source CSVs or generator scripts instead.

---

## attribution

The 3D visualization builds on the open-source [`3d-force-graph`](https://github.com/vasturiano/3d-force-graph) project by [vasturiano](https://github.com/vasturiano).

The surrounding archive system, content model, Python build pipeline, 2D dashboard, navigation, styling, and Poppyverse-specific interaction design were developed for this project.

---

## notes

3D space is a suggestion.  
Canon is unstable.  
Coherence is temporary.  
The build script is load-bearing emotional infrastructure.
