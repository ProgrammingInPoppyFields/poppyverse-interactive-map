#!/usr/bin/env python3
"""
Build the Poppyverse home/splash page.

Output:
- index.html

This is the GitHub Pages landing page.
The actual maps live at:
- 2d_map.html
- 3d_map.html
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT_HTML = ROOT / "index.html"

POPPY_PINK = "#FF1447"
TUMBLR_ARCHIVE_URL = "https://inpoppyfields.tumblr.com/"
BACKGROUND_IMAGE_URL = (
    "https://images.unsplash.com/photo-1569470451072-68314f596aec"
    "?q=80&w=1631&auto=format&fit=crop&ixlib=rb-4.1.0"
    "&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D"
)


INTRO_HTML = """
<h1>Welcome to the Poppyverse</h1>
<p>A collection of stories set across a quantum multiverse framework, characterized primarily by narrative inconsistency, emotional damage, and a complete disregard for traditional storytelling structure.</p>
<p><strong>Disclaimer:</strong> Table of Content titles won&rsquo;t always match post titles. This is a work in progress. Confusion is part of the experience.</p>
<hr />
<h1>Suggested Reading Logic</h1>
<p><em>A non-binding attempt at structural clarity</em></p>
<h2>p# &rarr; Progressive Thread</h2>
<p>Indicates chronological sequence. Used when a story pretends to follow linear causality. Read in order. Pretend it matters.</p>
<ul>
<li><strong>p1</strong> &rarr; the mech sneezes</li>
<li><strong>p2</strong> &rarr; the mech then dies heroically in a sandwich fire</li>
</ul>
<h2>v# &rarr; Narrative Variant</h2>
<p>Alternate versions of the same key event. May differ by perspective, tone, emotional damage, or ethical collapse. Choose your fighter.</p>
<ul>
<li><strong>v1</strong> &rarr; everyone survives but hates each other</li>
<li><strong>v2</strong> &rarr; everyone dies but hugs first</li>
</ul>
<h2>(no prefix) &rarr; Wildcard Unit</h2>
<p>Independent entry. Possibly self-contained. Possibly entangled with eight other entries via an anomalous IKEA desk and one very specific trauma response.</p>
<ul>
<li>postmortem dog walk</li>
<li>emotional tax fraud</li>
</ul>
<p>All timelines are canon.<br /> Even the ones that mutually invalidate each other.<br /> Especially those.</p>
<hr />
<h1>Extra: Story Music (Optional, but Highly Recommended)</h1>
<p>Some stories include a YouTube track. Totally optional. But if you want a vibe assist:</p>
<ul>
<li>Click the link.</li>
<li>Let the music play for a few seconds.</li>
<li>Read on with the soundtrack running.</li>
</ul>
<p>We&rsquo;re not saying it&rsquo;ll change your life. But it might hit harder with a haunting piano or a slow-burn synth humming in your ears. Consider it mood lighting for your soul.</p>
<hr />
<h1>Final Notes</h1>
<p>Confused? Good. You&rsquo;re supposed to be. That&rsquo;s how you know it&rsquo;s working.</p>
<p>Please enjoy your descent. And remember: it&rsquo;s not a contradiction, it&rsquo;s a multiverse.</p>
""".strip()


def favicon_html() -> str:
    return """
<link rel="icon" href='data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><text y="50%" x="50%" dominant-baseline="middle" text-anchor="middle" font-size="52">🌷</text></svg>'>
""".strip()


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
            f'<a class="top-nav-link{active_class}" href="{href}"{external_attrs}>{label}</a>'
        )

    return f"""
<nav class="top-nav" aria-label="Main navigation">
  <div class="top-nav-inner">
    {"".join(links)}
  </div>
</nav>
""".strip()


def build_html() -> str:
    nav = make_nav("home")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Welcome to the Poppyverse</title>
  {favicon_html()}

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Michroma&display=swap" rel="stylesheet">

  <style>
    :root {{
      --poppy-pink: {POPPY_PINK};
      --text: rgba(255, 255, 255, 0.94);
      --muted: rgba(255, 255, 255, 0.72);
      --line: rgba(255, 255, 255, 0.16);
      --nav-height: 58px;
    }}

    * {{
      box-sizing: border-box;
    }}

    html,
    body {{
      margin: 0;
      min-height: 100%;
      color: var(--text);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #06060a;
    }}

    body {{
      min-height: 100vh;
      overflow-x: hidden;
    }}

    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      z-index: -3;
      background-image: url("{BACKGROUND_IMAGE_URL}");
      background-size: cover;
      background-position: center;
      filter: saturate(1.06) contrast(1.08) brightness(0.72);
      transform: scale(1.02);
    }}

    body::after {{
      content: "";
      position: fixed;
      inset: 0;
      z-index: -2;
      background:
        radial-gradient(circle at 50% 24%, rgba(255, 20, 71, 0.22), transparent 34%),
        radial-gradient(circle at 20% 80%, rgba(120, 60, 255, 0.16), transparent 32%),
        linear-gradient(to bottom, rgba(0, 0, 0, 0.42), rgba(0, 0, 0, 0.84));
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

    .page {{
      min-height: 100vh;
      padding: calc(var(--nav-height) + 72px) 24px 64px;
      display: grid;
      place-items: center;
    }}

    .hero {{
      width: min(1080px, 100%);
      text-align: center;
    }}

    .title {{
      margin: 0;
      color: var(--poppy-pink);
      font-family: "Michroma", sans-serif;
      font-size: clamp(38px, 8vw, 92px);
      line-height: 1.05;
      letter-spacing: 0.055em;
      text-transform: uppercase;
      text-shadow:
        0 0 12px rgba(255, 20, 71, 0.68),
        0 0 36px rgba(255, 20, 71, 0.38),
        0 0 70px rgba(0, 0, 0, 0.92);
    }}

    .subtitle {{
      max-width: 760px;
      margin: 22px auto 0;
      color: var(--muted);
      font-size: clamp(15px, 1.7vw, 19px);
      line-height: 1.65;
      text-shadow: 0 0 18px rgba(0, 0, 0, 0.82);
    }}

    .actions {{
      margin-top: 34px;
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }}

    .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 44px;
      padding: 12px 18px;
      border: 1px solid rgba(255, 255, 255, 0.22);
      border-radius: 999px;
      background: rgba(0, 0, 0, 0.48);
      color: #fff;
      text-decoration: none;
      font-size: 12px;
      font-weight: 900;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      backdrop-filter: blur(10px);
      box-shadow: 0 0 24px rgba(0, 0, 0, 0.36);
      cursor: pointer;
      transition:
        transform 160ms ease,
        background 160ms ease,
        border-color 160ms ease,
        box-shadow 160ms ease;
    }}

    .button:hover {{
      transform: translateY(-2px);
      border-color: rgba(255, 255, 255, 0.42);
      background: var(--poppy-pink);
      box-shadow: 0 0 26px rgba(255, 20, 71, 0.48);
    }}

    .intro-shell {{
      width: min(920px, 100%);
      margin: 28px auto 0;
      display: none;
      text-align: left;
    }}

    .intro-shell.open {{
      display: block;
      animation: introDrop 220ms ease both;
    }}

    .intro-card {{
      padding: 28px;
      border: 1px solid rgba(255, 255, 255, 0.18);
      border-radius: 24px;
      background: rgba(7, 7, 13, 0.78);
      backdrop-filter: blur(14px);
      box-shadow:
        0 24px 80px rgba(0, 0, 0, 0.52),
        0 0 28px rgba(255, 20, 71, 0.16);
    }}

    .intro-card h1,
    .intro-card h2 {{
      font-family: "Michroma", sans-serif;
      line-height: 1.2;
      text-transform: uppercase;
    }}

    .intro-card h1 {{
      margin: 0 0 14px;
      color: var(--poppy-pink);
      font-size: 24px;
      letter-spacing: 0.08em;
    }}

    .intro-card h2 {{
      margin: 26px 0 10px;
      color: #fff;
      font-size: 16px;
      letter-spacing: 0.06em;
    }}

    .intro-card p,
    .intro-card li {{
      color: rgba(255, 255, 255, 0.83);
      font-size: 15px;
      line-height: 1.7;
    }}

    .intro-card p {{
      margin: 0 0 14px;
    }}

    .intro-card ul {{
      margin: 8px 0 18px 22px;
      padding: 0;
    }}

    .intro-card hr {{
      margin: 28px 0;
      border: 0;
      border-top: 1px solid rgba(255, 255, 255, 0.16);
    }}

    @keyframes introDrop {{
      from {{
        opacity: 0;
        transform: translateY(-8px);
      }}
      to {{
        opacity: 1;
        transform: translateY(0);
      }}
    }}

    @media (max-width: 760px) {{
      .page {{
        padding-left: 16px;
        padding-right: 16px;
      }}

      .top-nav {{
        padding-left: 8px;
        padding-right: 8px;
      }}

      .top-nav-inner {{
        justify-content: flex-start;
      }}

      .intro-card {{
        padding: 22px;
      }}
    }}
  </style>
</head>

<body>
  {nav}

  <main class="page">
    <section class="hero">
      <h1 class="title">WELCOME TO THE POPPYVERSE</h1>

      <p class="subtitle">
        A quantum story archive for narrative inconsistency, emotional damage,
        and suspiciously well-organized chaos.
      </p>

      <div class="actions">
        <button id="introToggle" class="button" type="button" aria-expanded="false" aria-controls="introPanel">
          Intro
        </button>
        <a class="button" href="2d_map.html">Enter 2D Map</a>
        <a class="button" href="3d_map.html">Enter 3D Map</a>
      </div>

      <div id="introPanel" class="intro-shell">
        <article class="intro-card">
          {INTRO_HTML}
        </article>
      </div>
    </section>
  </main>

  <script>
    "use strict";

    const introToggle = document.getElementById("introToggle");
    const introPanel = document.getElementById("introPanel");

    introToggle.addEventListener("click", () => {{
      const isOpen = introPanel.classList.toggle("open");
      introToggle.setAttribute("aria-expanded", String(isOpen));
      introToggle.textContent = isOpen ? "Hide Intro" : "Intro";
    }});
  </script>
</body>
</html>
"""


def main() -> None:
    OUTPUT_HTML.write_text(build_html(), encoding="utf-8")
    print(f"Built {OUTPUT_HTML.name}")


if __name__ == "__main__":
    main()