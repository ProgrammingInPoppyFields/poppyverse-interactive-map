#!/usr/bin/env python3
"""
Build the Poppyverse About page.

Output:
- about.html

Shared toolbar:
- Home
- About
- 2D Map
- 3D Map
- Tumblr Archive
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT_HTML = ROOT / "about.html"

POPPY_PINK = "#FF1447"
TUMBLR_ARCHIVE_URL = "https://inpoppyfields.tumblr.com/"
BACKGROUND_IMAGE_URL = (
    "https://images.unsplash.com/photo-1569470451072-68314f596aec"
    "?q=80&w=1631&auto=format&fit=crop&ixlib=rb-4.1.0"
    "&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D"
)


ABOUT_HTML = """
<h2><strong>Who are you?</strong></h2>
<p>H.A.H is the pseudonym of this blog&rsquo;s author.<br /> By daylight: a Silicon Valley software engineer.<br /> By starlight: the kind of person who dreams of programming 30-foot mechs optimized for emotional support, deadpan sarcasm, and the occasional high-yield detonation.</p>
<p>And yes, the name sounds like a rogue comedy AI having an identity crisis.<br /> This is not a coincidence.</p>

<h2><strong>Is this GenAI?</strong></h2>
<p>&mdash;Yead. Obviously. You probably guessed from the em dashes and the unearned confidence.</p>
<p>But let&rsquo;s be clear.</p>
<p>The AI is doing the stitching. The human picked the thread.</p>
<p>It&rsquo;s the human who laid the dots down&mdash;scattered, sharp, deliberate. The AI just plays connect-the-trauma.</p>
<p>It doesn&rsquo;t dream. It doesn&rsquo;t ache. It doesn&rsquo;t lie awake at 2:13 AM, wondering if the metaphors are too obvious or not obvious enough.</p>
<p>It&rsquo;s a machine with excellent aim. But it only ever fires where it&rsquo;s told.</p>
<p>So if something hits you in the chest&mdash;<br />if it feels too precise, too quiet, too <em>true</em>&mdash;<br />don&rsquo;t ask what the model was trained on.</p>
<p>Ask who told it what to look for.</p>
<p>And if the answer looks like <em>you</em>&mdash;<br />well&hellip; Welcome aboard.</p>
<p>And don&rsquo;t worry. This isn&rsquo;t a test. You&rsquo;re allowed to enjoy the ride.</p>

<h2>What the hell is <em>lucid generation?</em></h2>
<p>Yep, yep, we know. It sounds like some LinkedIn-bloated buzzword for a VC-backed wellness startup that sells dream-enhancing AI toothbrushes.</p>
<p>But around here, it just means this:</p>
<p>The machine dreams.<br /> The human doesn&rsquo;t sleep. This isn&rsquo;t autopilot.<br /> It&rsquo;s a guided hallucination&mdash;with fingerprints.<br /> And someone&rsquo;s still awake in the middle of it.</p>
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
    nav = make_nav("about")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>About the Poppyverse</title>
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
      filter: saturate(1.06) contrast(1.08) brightness(0.64);
      transform: scale(1.02);
    }}

    body::after {{
      content: "";
      position: fixed;
      inset: 0;
      z-index: -2;
      pointer-events: none;
      background:
        radial-gradient(circle at 50% 16%, rgba(255, 20, 71, 0.20), transparent 34%),
        radial-gradient(circle at 20% 80%, rgba(120, 60, 255, 0.14), transparent 32%),
        linear-gradient(to bottom, rgba(0, 0, 0, 0.48), rgba(0, 0, 0, 0.88));
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
      padding: calc(var(--nav-height) + 72px) 24px 72px;
      display: grid;
      place-items: start center;
    }}

    .shell {{
      width: min(920px, 100%);
    }}

    .page-title {{
      margin: 0 0 24px;
      color: var(--poppy-pink);
      font-family: "Michroma", sans-serif;
      font-size: clamp(34px, 6vw, 72px);
      line-height: 1.05;
      letter-spacing: 0.055em;
      text-align: center;
      text-transform: uppercase;
      text-shadow:
        0 0 12px rgba(255, 20, 71, 0.68),
        0 0 36px rgba(255, 20, 71, 0.38),
        0 0 70px rgba(0, 0, 0, 0.92);
    }}

    .card {{
      padding: 32px;
      border: 1px solid rgba(255, 255, 255, 0.18);
      border-radius: 26px;
      background: rgba(7, 7, 13, 0.78);
      backdrop-filter: blur(14px);
      box-shadow:
        0 24px 80px rgba(0, 0, 0, 0.52),
        0 0 28px rgba(255, 20, 71, 0.16);
    }}

    .card h2 {{
      margin: 28px 0 12px;
      color: var(--poppy-pink);
      font-family: "Michroma", sans-serif;
      font-size: clamp(18px, 2.6vw, 25px);
      line-height: 1.25;
      letter-spacing: 0.055em;
      text-transform: uppercase;
    }}

    .card h2:first-child {{
      margin-top: 0;
    }}

    .card p {{
      margin: 0 0 15px;
      color: rgba(255, 255, 255, 0.84);
      font-size: 16px;
      line-height: 1.75;
    }}

    .card em {{
      color: rgba(255, 255, 255, 0.94);
    }}

    .card strong {{
      color: #fff;
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

      .card {{
        padding: 24px;
      }}
    }}
  </style>
</head>

<body>
  {nav}

  <main class="page">
    <section class="shell">
      <h1 class="page-title">ABOUT THE POPPYVERSE</h1>

      <article class="card">
        {ABOUT_HTML}
      </article>
    </section>
  </main>
</body>
</html>
"""


def main() -> None:
    OUTPUT_HTML.write_text(build_html(), encoding="utf-8")
    print(f"Built {OUTPUT_HTML.name}")


if __name__ == "__main__":
    main()