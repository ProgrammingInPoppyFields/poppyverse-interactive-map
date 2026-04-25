# poppyverse-3d

**Forked from:** [vasturiano/3d-force-graph](https://github.com/vasturiano/3d-force-graph)

![poppyverse preview](/screenshots/1.png)

building a 3D representation of a multiverse that doesn't fit in 3D — trying anyway

---

## what is this

A questionable attempt to turn the Poppyverse into something spatially navigable.

It mostly works.  
Sometimes.

---

## how this works

Everything starts from:

- `the_poppy_board.csv` — the main source of truth (entities, relationships, chaos)

From there, the project splits into two paths:

---

### 1) 3D path (chaos mode)

```
the_poppy_board.csv + cluster_table.csv
                │
                ▼
           index.html
                │
                ▼
           3D website
```

`index.html` consumes:
- `the_poppy_board.csv`
- `cluster_table.csv`

Produces an interactive 3D graph. This is the cinematic version. This is also the version most likely to break your brain.

---

### 2) 2D path (sanity mode)

```
the_poppy_board.csv
        │
        ▼
   build_toc.py
        │
        ▼
     toc.html
```

`build_toc.py` consumes:
- `the_poppy_board.csv`

Produces `toc.html` — a more readable table of contents. This is the "I just want to read things like a normal person" version.

---

## files

| File | What it is |
|---|---|
| `the_poppy_board.csv` | Main lore / data graph (source of truth) |
| `cluster_table.csv` | Cluster/grouping metadata (used by 3D view) |
| `index.html` | Renders the 3D graph |
| `build_toc.py` | Generates the 2D table of contents |
| `toc.html` | Readable output of the 2D view |
| `/screenshots/` | Preview images |

---

## running

**3D version:**
```
cd path/to/repo
python3 -m http.server 8080
```
Then open `http://localhost:8080/index.html` in a browser.

**2D version:**
```
python build_toc.py
# then open toc.html
```

---

## notes

3D space is a suggestion.  
Canon is unstable.  
Coherence is temporary.