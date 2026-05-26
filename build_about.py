#!/usr/bin/env python3
"""
build_about.py

Generate the Poppyverse About page.

Output:
- about.html
"""
from __future__ import annotations

import argparse
from pathlib import Path

OUTPUT_HTML = "about.html"
POPPY_RED = "#FF1447"
BACKGROUND_IMAGE = "https://images.unsplash.com/photo-1569470451072-68314f596aec?q=80&w=1631&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D"
TUMBLR_ARCHIVE_URL = "https://inpoppyfields.tumblr.com/"
HOME_HREF = "index.html"
ABOUT_HREF = "about.html"
TWO_D_MAP_HREF = "2d_map.html"
THREE_D_MAP_HREF = "3d_map.html"


def common_nav_css() -> str:
    return """
    .poppy-nav {
      position: fixed;
      top: 14px;
      left: 50%;
      transform: translateX(-50%);
      z-index: 100;
      display: flex;
      gap: 8px;
      align-items: center;
      padding: 7px;
      border: 1px solid rgba(255, 255, 255, 0.18);
      border-radius: 999px;
      background: rgba(8, 8, 14, 0.66);
      box-shadow: 0 16px 42px rgba(0,0,0,.32), 0 0 22px rgba(255,20,71,.10);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
    }

    .poppy-nav a {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 34px;
      padding: 0 13px;
      border-radius: 999px;
      color: rgba(255,255,255,.82);
      text-decoration: none;
      font-size: 12px;
      font-weight: 850;
      letter-spacing: .35px;
      border: 1px solid transparent;
      transition: background .16s ease, border-color .16s ease, color .16s ease, box-shadow .16s ease;
      white-space: nowrap;
    }

    .poppy-nav a:hover {
      color: #fff;
      background: rgba(255,255,255,.08);
      border-color: rgba(255,255,255,.18);
    }

    .poppy-nav a.active {
      color: #fff;
      background: var(--poppy-red, #ff1447);
      border-color: color-mix(in srgb, var(--poppy-red, #ff1447) 72%, white);
      box-shadow: 0 0 18px color-mix(in srgb, var(--poppy-red, #ff1447) 44%, transparent);
    }

    @media (max-width: 680px) {
      .poppy-nav {
        top: 10px;
        width: calc(100vw - 20px);
        justify-content: flex-start;
        overflow-x: auto;
        border-radius: 18px;
      }

      .poppy-nav a {
        padding: 0 10px;
        font-size: 11px;
      }
    }
    """


def common_nav_html(active: str = "about") -> str:
    home_class = ' class="active" aria-current="page"' if active == "home" else ""
    about_class = ' class="active" aria-current="page"' if active == "about" else ""
    two_d_class = ' class="active" aria-current="page"' if active == "2d" else ""
    three_d_class = ' class="active" aria-current="page"' if active == "3d" else ""
    return (
        '<nav class="poppy-nav" aria-label="Poppyverse map navigation">\n'
        f'    <a href="{HOME_HREF}"{home_class}>Home</a>\n'
        f'    <a href="{ABOUT_HREF}"{about_class}>About</a>\n'
        f'    <a href="{TWO_D_MAP_HREF}"{two_d_class}>2D Map</a>\n'
        f'    <a href="{THREE_D_MAP_HREF}"{three_d_class}>3D Map</a>\n'
        f'    <a href="{TUMBLR_ARCHIVE_URL}" target="_blank" rel="noopener">Tumblr Archive</a>\n'
        '  </nav>'
    )


ABOUT_HTML = """<h2 data-start="184" data-end="200"><strong>Who are you?</strong></h2>
<p data-start="202" data-end="465">H.A.H is the pseudonym of this blog&rsquo;s author.<br data-start="247" data-end="250" /> By daylight: a Silicon Valley software engineer.<br data-start="298" data-end="301" /> By starlight: the kind of person who dreams of programming 30-foot mechs optimized for emotional support, deadpan sarcasm, and the occasional high-yield detonation.</p>
<p data-start="467" data-end="585">And yes, the name sounds like a rogue comedy AI having an identity crisis.<br data-start="390" data-end="393" /> This is not a coincidence.</p>
<h2 data-start="98" data-end="180"><strong data-start="98" data-end="121">Is this GenAI?</strong></h2>
<p data-start="98" data-end="180">&mdash;Yead. Obviously. You probably guessed from the em dashes and the unearned confidence.</p>
<p>But let&rsquo;s be clear.</p>
<p>The AI is doing the stitching. The human picked the thread.</p>
<p>It&rsquo;s the human who laid the dots down&mdash;scattered, sharp, deliberate.&nbsp;The AI just plays connect-the-trauma.</p>
<p>It doesn&rsquo;t dream. It doesn&rsquo;t ache.&nbsp;It doesn&rsquo;t lie awake at 2:13 AM, wondering if the metaphors are too obvious or not obvious enough.</p>
<p>It&rsquo;s a machine with excellent aim.&nbsp;But it only ever fires where it&rsquo;s told.</p>
<p>So if something hits you in the chest&mdash;<br />if it feels too precise, too quiet, too <em>true</em>&mdash;<br />don&rsquo;t ask what the model was trained on.</p>
<p>Ask who told it what to look for.</p>
<p>And if the answer looks like <em>you</em>&mdash;<br />well&hellip;&nbsp;Welcome aboard.</p>
<p>And don&rsquo;t worry. This isn&rsquo;t a test. You&rsquo;re allowed to enjoy the ride.</p>
<h2>What the hell is <em>lucid generation?</em></h2>
<p>Yep, yep, we know. It sounds like some LinkedIn-bloated buzzword for a VC-backed wellness startup that sells dream-enhancing AI toothbrushes.</p>
<p>But around here, it just means this:</p>
<p>The machine dreams.<br /> The human doesn&rsquo;t sleep. This isn&rsquo;t autopilot.<br /> It&rsquo;s a guided hallucination&mdash;with fingerprints.<br /> And someone&rsquo;s still awake in the middle of it.</p>""".strip()


def build_html() -> str:
    nav_css = common_nav_css()
    nav_html = common_nav_html("about")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>About | Into the Poppyverse</title>
  <link rel="icon" href='data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><text y="50%" x="50%" dominant-baseline="middle" text-anchor="middle" font-size="52">🌷</text></svg>'>
  <style>
    :root {{ --poppy-red: {POPPY_RED}; }}
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0;
      min-height: 100%;
      background: #05050a;
      color: #fff;
      font-family: "Proxima Nova", Proxima, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    body {{
      min-height: 100vh;
      overflow-x: hidden;
      background-image:
        linear-gradient(120deg, rgba(0,0,0,.86), rgba(0,0,0,.48) 45%, rgba(0,0,0,.88)),
        radial-gradient(circle at 50% 30%, rgba(255,20,71,.18), transparent 38%),
        url('{BACKGROUND_IMAGE}');
      background-size: cover;
      background-position: center;
      background-attachment: fixed;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background: linear-gradient(to bottom, rgba(0,0,0,.10), rgba(0,0,0,.78));
      z-index: 0;
    }}
{nav_css}
    main {{
      position: relative;
      z-index: 1;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 106px 22px 56px;
    }}
    .about-card {{
      width: min(900px, 100%);
      padding: clamp(24px, 4vw, 44px);
      border: 1px solid rgba(255,255,255,.20);
      border-radius: 30px;
      background: rgba(6, 6, 12, .72);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      box-shadow: 0 30px 90px rgba(0,0,0,.56), 0 0 34px rgba(255,20,71,.12);
    }}
    .eyebrow {{
      margin: 0 0 10px;
      color: var(--poppy-red);
      font-size: 12px;
      font-weight: 950;
      letter-spacing: .22em;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 0 0 22px;
      color: var(--poppy-red);
      font-size: clamp(42px, 7vw, 86px);
      line-height: .9;
      letter-spacing: -.055em;
      text-transform: uppercase;
      text-shadow: 0 0 20px rgba(255,20,71,.55), 0 12px 42px rgba(0,0,0,.72);
    }}
    .about-content h2 {{
      margin: 30px 0 10px;
      color: #fff;
      font-size: clamp(22px, 2.5vw, 32px);
      line-height: 1.12;
    }}
    .about-content h2:first-child {{ margin-top: 0; }}
    .about-content p {{
      margin: 12px 0;
      color: rgba(255,255,255,.84);
      font-size: 16px;
      line-height: 1.68;
    }}
    .about-content em {{ color: rgba(255,255,255,.95); }}
    .about-content strong {{ color: #fff; }}
    @media (max-width: 680px) {{
      main {{ padding: 96px 14px 36px; }}
      .about-card {{ border-radius: 22px; }}
    }}
  </style>
</head>
<body>
  {nav_html}
  <main>
    <article class="about-card">
      <p class="eyebrow">Author / process / cursed methodology</p>
      <h1>About</h1>
      <div class="about-content">
        {ABOUT_HTML}
      </div>
    </article>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Poppyverse about page.")
    parser.add_argument("--output", "--out", default=OUTPUT_HTML, help=f"Output HTML path. Default: {OUTPUT_HTML}")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    output = Path(args.output)
    if not output.is_absolute():
        output = script_dir / output
    output.write_text(build_html(), encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
