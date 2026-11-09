/*
 * <poppy-nav> -- the one top navigation bar for every Poppyverse page.
 *
 * Usage (any page, any generator):
 *
 *   <script src="components/poppy-nav.js"></script>
 *   <poppy-nav></poppy-nav>
 *
 * The current page is detected from the URL, so no per-page setting is needed
 * (override with <poppy-nav active="2d"> if you ever have to). Edit NAV_ITEMS or
 * the styles below and every page that includes this file picks it up on its
 * next load, with no rebuild. That includes the frozen legacy 3d_map_1.html.
 *
 * Styling lives in a shadow root, so page CSS cannot break it. The pink accent
 * comes from the page's --poppy-pink (or --pink) variable if it defines one.
 * To stack the bar above/below other fixed UI, set z-index on the element from
 * the page's own CSS, e.g.  poppy-nav { z-index: 10; }
 */
(() => {
  // [label, href, key]. `href` doubles as the filename used to detect the current page.
  const NAV_ITEMS = [
    ["Home", "index.html", "home"],
    ["About", "about.html", "about"],
    ["2D Map", "2d_map.html", "2d"],
    ["3D Map 1.0", "3d_map_1.html", "3d1"],
    ["3D Map 2.0", "3d_map_2.html", "3d2"],
  ];

  const STYLE = `
    :host {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      z-index: 1000;
      display: block;
      padding: 10px 16px;
      pointer-events: none;
      font-family: "Space Grotesk", system-ui, sans-serif;
    }
    .inner {
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
      -webkit-backdrop-filter: blur(12px);
      box-shadow: 0 0 28px rgba(0, 0, 0, 0.42);
      pointer-events: auto;
      overflow-x: auto;
      box-sizing: border-box;
    }
    a {
      flex: 0 0 auto;
      padding: 8px 13px;
      border-radius: 999px;
      color: rgba(255, 255, 255, 0.82);
      text-decoration: none;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      transition: color 160ms ease, background 160ms ease, box-shadow 160ms ease;
    }
    a:hover,
    a.active {
      color: #fff;
      background: var(--poppy-pink, var(--pink, #ff1447));
      box-shadow: 0 0 18px rgba(255, 20, 71, 0.44);
    }
    @media (max-width: 760px) {
      :host { padding-left: 8px; padding-right: 8px; }
      .inner { justify-content: flex-start; max-width: calc(100vw - 16px); }
    }
  `;

  function currentKey() {
    const file = (location.pathname.split("/").pop() || "index.html").toLowerCase();
    const match = NAV_ITEMS.find(([, href]) => href === file);
    return match ? match[2] : "";
  }

  class PoppyNav extends HTMLElement {
    static get observedAttributes() { return ["active"]; }
    connectedCallback() { this.render(); }
    attributeChangedCallback() { if (this.isConnected) this.render(); }

    render() {
      const active = this.getAttribute("active") || currentKey();
      const root = this.shadowRoot || this.attachShadow({ mode: "open" });
      const style = document.createElement("style");
      style.textContent = STYLE;
      const nav = document.createElement("nav");
      nav.className = "inner";
      nav.setAttribute("aria-label", "Main navigation");
      for (const [label, href, key] of NAV_ITEMS) {
        const link = document.createElement("a");
        link.href = href;
        link.textContent = label;
        if (key === active) {
          link.className = "active";
          link.setAttribute("aria-current", "page");
        }
        nav.appendChild(link);
      }
      root.replaceChildren(style, nav);
    }
  }

  if (!customElements.get("poppy-nav")) customElements.define("poppy-nav", PoppyNav);
})();
