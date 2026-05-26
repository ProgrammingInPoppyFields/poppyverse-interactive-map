# poppyverse-3d

**Forked from:** [vasturiano/3d-force-graph](https://github.com/vasturiano/3d-force-graph)

![poppyverse preview](/screenshots/1.png)

A small static site for navigating the Poppyverse: part story map, part multiverse directory, part emotionally unstable control panel.

---

## what is this

This repo generates a tiny GitHub Pages site from two CSV source-of-truth files.

The site currently includes:

- `index.html` — splash / home page
- `about.html` — author / GenAI / lucid generation page
- `2d_map.html` — calmer cluster-first story map
- `3d_map.html` — dramatic 3D graph map, because apparently sanity was optional

All pages share the same top navigation bar:

- Home
- About
- 2D Map
- 3D Map
- Tumblr Archive

---

## source of truth files

Before rebuilding, make sure these are updated and ready to go:

| File | What it controls |
|---|---|
| `SRC_clusters.csv` | Cluster names, descriptions, colors, and optional cluster cover images |
| `SRC_toc.csv` | Main table of contents / story entries / relationships / metadata |

These two files are the real source of truth. The HTML files are generated outputs.

---

## how to rebuild the site

From the repo root, run:

```bash
python build_all.py
```

That should be it. Good to go.

`build_all.py` regenerates:

```text
index.html
about.html
2d_map.html
3d_map.html
```

So the normal update flow is:

1. Update `SRC_clusters.csv`.
2. Update `SRC_toc.csv`.
3. Run `python build_all.py`.
4. Commit the updated CSVs, generator scripts, and generated HTML files.
5. Let GitHub Pages do its thing.

---

## generated pages

| File | What it is |
|---|---|
| `index.html` | Splash page / site entrance |
| `about.html` | About page explaining H.A.H, GenAI usage, and lucid generation |
| `2d_map.html` | Cluster-card dashboard; click a cluster to open its table of contents |
| `3d_map.html` | Interactive 3D graph using Three.js / 3d-force-graph |

---

## build scripts

| File | What it does |
|---|---|
| `build_all.py` | Runs the full site build |
| `build_home.py` | Generates `index.html` |
| `build_about.py` | Generates `about.html` |
| `build_2d_map.py` | Generates `2d_map.html` from `SRC_clusters.csv` + `SRC_toc.csv` |
| `build_3d_map_with_nav.py` | Generates `3d_map.html` from `SRC_clusters.csv` + `SRC_toc.csv` |

You usually only need to run `build_all.py`.

---

## optional build shortcuts

If you only want part of the site rebuilt:

```bash
python build_all.py --skip-3d
python build_all.py --skip-2d
python build_all.py --skip-home
python build_all.py --skip-about
```

Useful when the cursed glowing space cube does not need to be awakened.

---

## local preview

After building, you can preview the site locally:

```bash
python3 -m http.server 8080
```

Then open:

```text
http://localhost:8080/index.html
```

---

## deployment notes

For GitHub Pages, `index.html` is the homepage.

The map pages live next to it:

```text
/index.html
/about.html
/2d_map.html
/3d_map.html
```

Do not hand-edit the generated HTML unless you enjoy losing changes the next time `build_all.py` runs. Update the source CSVs or generator scripts instead.

---

## notes

3D space is a suggestion.  
Canon is unstable.  
Coherence is temporary.  
The build script is load-bearing emotional infrastructure.
