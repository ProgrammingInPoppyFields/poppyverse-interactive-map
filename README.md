<p align="center">
  <img src="/screenshots/header.png" alt="A field of glowing multiverse nodes and nebulae drifting in space" width="100%" />
</p>

<table align="center" width="100%">
  <tr valign="top">
    <td align="center" width="50%">
      <img src="/screenshots/3d-map-plain.png" alt="The 3D map showing glowing story clusters" width="100%" />
      <br />
      <sub><strong>3D map</strong><br />Story nodes floating in space, colored by cluster.</sub>
    </td>
    <td align="center" width="50%">
      <img src="/screenshots/3d-map-globe.png" alt="The 3D map with the Relativity / Relatability / Depth axes and connection lines revealed" width="100%" />
      <br />
      <sub><strong>3D map, "Show axes" enabled</strong><br />The same nodes with the axes, origin marker, and connection-link lines made visible.</sub>
    </td>
  </tr>
</table>

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
- **3D Map** — an interactive force-directed graph for seeing connections and narrative gravity

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

`3d_map.html` plots each node as a simple 3D scatter point centered at `(0, 0, 0)`. Three `0`–`10` scores in `SRC_toc.csv` drive the X and Y axes directly, while the Z axis is split by publish status:

| CSV column | Controls | Behavior |
|---|---|---|
| `(X) Relativity` | X position | Scaled directly; `0` and `10` sit at opposite edges of the X spread. |
| `(Y) Relatability` | Y position | Scaled directly; `0` and `10` sit at opposite edges of the Y spread. |
| `(Z) Depth` | Z magnitude only | Controls *distance* from the z=0 divide plane, not direction — see below. |
| `Content URL` (presence) | Z sign | Has a URL -> **+Z** (in front of the divide). No URL -> **-Z** (behind it). |

What each score is actually rating, story-wise:

* **RELATIVITY:** How far the story has wandered from ordinary reality into alternate universes, interdimensional events, cosmic entities, or related complications.
* **RELATABILITY:** How closely the story resembles recognizable human life, including familiar relationships, everyday problems, and the general inconvenience of being a person.
* **DEPTH:** How emotionally dark, psychologically complex, mature, or otherwise unsuitable for casual bedtime reading the story becomes.

A translucent plane sits at `z = 0` marking the divide: published stories (with a Content URL) float in front of it, everything still unpublished floats behind it.

Cluster no longer affects position, only color. A small seeded jitter keeps nodes with identical scores from stacking exactly on top of each other, but is deterministic per node id, so rebuilds don't shuffle anyone around.

Axes, the z=0 divide plane, and connection lines are all hidden by default — toggle "Show axes" (bottom-left) to see the three labeled axis lines, the origin marker, the divide plane, and the faint connection-link lines connecting nodes.

---

## what is a connection

The faint lines connecting nodes on the map, and the "Connections" list on each detail card, aren't a technical link — they're a story relationship, defined in the `Connections` column of `SRC_toc.csv`:

> **CONNECTION:** A connection defines a relationship between 2 stories where characters, timelines, or alternate versions of the same people from separate universes come into direct contact and begin affecting one another. Less "special crossover episode," more "the walls between realities have failed inspection."

Both concepts above show up together on a node's detail card — click any node on `3d_map.html` or `2d_map.html` to open it:

<p align="center">
  <img src="/screenshots/detail-card-view.png" alt="A story's detail card, showing its description, Relativity/Relatability/Depth coordinate meters, sub-parts, characters, connections, and read-more link" width="420" />
  <br />
  <sub>A detail card — Coordinates meters and Connections chips are populated straight from <code>SRC_toc.csv</code>.</sub>
</p>

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

## graph experiments

The 3D map's layout has been rebuilt more than once. These are snapshots from different experiments along the way — not necessarily what the live map looks like right now:

<table align="center" width="100%">
  <tr valign="top">
    <td align="center" width="50%">
      <img src="/screenshots/3d-map-plain.png" alt="An early 3D map layout experiment" width="100%" />
      <br />
      <sub>Layout experiment</sub>
    </td>
    <td align="center" width="50%">
      <img src="/screenshots/3d-map-globe.png" alt="A spherical globe layout experiment with axes revealed" width="100%" />
      <br />
      <sub>Spherical globe layout experiment, axes revealed</sub>
    </td>
  </tr>
  <tr valign="top">
    <td align="center" width="50%">
      <img src="/screenshots/3d-map-cube.png" alt="A cube-based layout experiment" width="100%" />
      <br />
      <sub>Cube layout experiment</sub>
    </td>
    <td align="center" width="50%">
      <img src="/screenshots/3d-map-cube-ON.png" alt="The cube-based layout experiment with axes revealed" width="100%" />
      <br />
      <sub>Cube layout experiment, axes revealed</sub>
    </td>
  </tr>
  <tr valign="top">
    <td align="center" width="50%">
      <img src="/screenshots/3d-map-div.png" alt="A scatter layout experiment split by the publish-divide plane" width="100%" />
      <br />
      <sub>Scatter/divide layout experiment</sub>
    </td>
    <td align="center" width="50%">
      <img src="/screenshots/3d-map-div-ON.png" alt="The scatter/divide layout experiment with axes, captions, and the Draft Horizon plane revealed" width="100%" />
      <br />
      <sub>Scatter/divide layout experiment, axes revealed</sub>
    </td>
  </tr>
</table>

---

## notes

3D space is a suggestion.  
Canon is unstable.  
Coherence is temporary.  
The build script is load-bearing emotional infrastructure.
