/*
 * <poppy-card> -- the Poppyverse detail card, used by the 3D map's side drawer
 * and by the 2D map's mobile story cards.
 *
 * Include the script, add the tag, then hand it data from JavaScript:
 *
 *   <script src="components/poppy-card.js"></script>
 *   <poppy-card id="card"></poppy-card>
 *
 *   card.data = {
 *     title:  "Story name",
 *     badge:  "cluster name",          // optional pill under the title
 *     color:  "#ff1447",               // accent color; falls back to the page's --active-color
 *     closable: true,                  // show the x button (default true, never in compact)
 *     sections: [
 *       { title: "Description", text: "..." , empty: "No description yet." },
 *       { title: "Details", stats: [{ label: "Type", value: "Story" }] },
 *       { title: "Characters", chips: ["PILOT", "DONOR"], empty: "—" },
 *       { title: "Connections", chips: [{ id: "story:12", label: "Other story" }] },
 *       { title: "Content", link: { href: "https://...", label: "Open" }, empty: "Content not ready." },
 *     ],
 *   };
 *
 * A chip given as a string is plain text; a chip given as { id, label } is a
 * button. Events (both bubble and cross the shadow boundary):
 *   "close"        the x button was pressed
 *   "chip-select"  a button chip was pressed; event.detail.id is its id
 *
 * Attribute variant="compact" renders a smaller, bordered card for lists. For
 * the full card, set --poppy-card-top (default 24px) on the element to push the
 * header down, e.g. to clear a fixed menu bar.
 *
 * Styling lives in a shadow root so page CSS cannot break it. Edit this one
 * file and both maps change together.
 */
(() => {
  const STYLE = `
    :host {
      display: block;
      color: #fff;
      font-family: "Space Grotesk", system-ui, sans-serif;
    }
    * { box-sizing: border-box; }

    .header {
      position: relative;
      min-height: 190px;
      padding: var(--poppy-card-top, 24px) 24px 22px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.14);
      background:
        radial-gradient(circle at top left, color-mix(in srgb, var(--active-color, #ff1447) 34%, transparent), transparent 42%),
        linear-gradient(135deg, color-mix(in srgb, var(--active-color, #ff1447) 24%, #080910 76%), #080910 70%);
    }
    .close {
      position: absolute;
      top: calc(var(--poppy-card-top, 24px) - 26px);
      right: 18px;
      width: 38px;
      height: 38px;
      border: 1px solid rgba(255, 255, 255, 0.24);
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.07);
      color: #fff;
      font-size: 20px;
      font-weight: 900;
      cursor: pointer;
    }
    .title {
      max-width: calc(100% - 52px);
      margin: 0;
      color: var(--active-color, #ff1447);
      font-family: Michroma, sans-serif;
      font-size: clamp(22px, 3vw, 32px);
      line-height: 1.18;
      letter-spacing: 0.07em;
      text-transform: uppercase;
      text-shadow: 0 0 22px color-mix(in srgb, var(--active-color, #ff1447) 38%, transparent);
    }
    .badge {
      display: inline-flex;
      margin-top: 14px;
      padding: 5px 9px;
      border-radius: 999px;
      background: color-mix(in srgb, var(--active-color, #ff1447) 50%, #000);
      color: #fff;
      font-size: 10px;
      font-weight: 900;
      letter-spacing: 0.09em;
      line-height: 1;
      text-transform: uppercase;
    }

    .body { padding: 22px 24px 44px; }
    .section { margin: 0 0 20px; padding-bottom: 20px; border-bottom: 1px solid rgba(255, 255, 255, 0.12); }
    .section:last-child { border-bottom: 0; }
    .section h3 {
      margin: 0 0 10px;
      color: #fff;
      font-family: Michroma, sans-serif;
      font-size: 12px;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }
    .section p {
      margin: 0;
      color: rgba(255, 255, 255, 0.8);
      font-size: 14px;
      line-height: 1.68;
      white-space: pre-line;
    }

    .stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
    .stat {
      padding: 10px;
      border: 1px solid color-mix(in srgb, var(--active-color, #ff1447) 42%, transparent);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.045);
      text-align: center;
    }
    .stat span {
      display: block;
      color: var(--active-color, #ff1447);
      font-size: 9px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .stat b { display: block; margin-top: 4px; color: #fff; font-size: 14px; font-variant-numeric: tabular-nums; }

    .chips { display: flex; flex-wrap: wrap; gap: 6px; }
    .chip {
      display: inline-block;
      padding: 5px 9px;
      border: 1px solid color-mix(in srgb, var(--active-color, #ff1447) 45%, transparent);
      border-radius: 6px;
      background: color-mix(in srgb, var(--active-color, #ff1447) 17%, transparent);
      color: #fff;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.07em;
      line-height: 1.3;
      text-transform: uppercase;
      text-decoration: none;
    }
    button.chip { cursor: pointer; font-family: inherit; }
    button.chip:hover { background: color-mix(in srgb, var(--active-color, #ff1447) 34%, transparent); }

    .read {
      display: inline-flex;
      min-height: 40px;
      align-items: center;
      padding: 10px 15px;
      border-radius: 5px;
      background: color-mix(in srgb, var(--active-color, #ff1447) 55%, #000);
      color: #fff;
      text-decoration: none;
      font-size: 11px;
      font-weight: 900;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }

    /* Compact variant: a small bordered card for lists. */
    :host([variant="compact"]) {
      border: 1px solid rgba(255, 255, 255, 0.14);
      border-radius: 16px;
      background: #10131c;
      overflow: hidden;
    }
    :host([variant="compact"]) .header {
      min-height: 0;
      padding: 18px 18px 0;
      border-bottom: 0;
      background: none;
    }
    :host([variant="compact"]) .title {
      max-width: none;
      color: #fff;
      font-family: inherit;
      font-size: 18px;
      font-weight: 700;
      letter-spacing: 0;
      text-transform: none;
      text-shadow: none;
    }
    :host([variant="compact"]) .badge { margin-top: 8px; }
    :host([variant="compact"]) .body { padding: 6px 18px 18px; }
    :host([variant="compact"]) .section { margin: 13px 0 0; padding-bottom: 0; border-bottom: 0; }
    :host([variant="compact"]) .section h3 {
      margin-bottom: 6px;
      color: #838c9d;
      font-family: inherit;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.12em;
    }
    :host([variant="compact"]) .section p { font-size: 14px; line-height: 1.55; color: #c6cbd5; }

    @media (max-width: 760px) {
      .stats { grid-template-columns: 1fr 1fr; }
    }
  `;

  const SAFE_URL = /^https?:\/\//i;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  class PoppyCard extends HTMLElement {
    get data() { return this._data; }
    set data(value) {
      this._data = value;
      if (this.isConnected) this.render();
    }

    connectedCallback() { this.render(); }

    render() {
      const root = this.shadowRoot || this.attachShadow({ mode: "open" });
      const style = el("style");
      style.textContent = STYLE;
      const data = this._data;
      if (!data) { root.replaceChildren(style); return; }

      if (data.color) this.style.setProperty("--active-color", data.color);
      const compact = this.getAttribute("variant") === "compact";

      const header = el("header", "header");
      if (data.closable !== false && !compact) {
        const close = el("button", "close", "×");
        close.type = "button";
        close.setAttribute("aria-label", "Close");
        close.addEventListener("click", () =>
          this.dispatchEvent(new CustomEvent("close", { bubbles: true, composed: true })));
        header.appendChild(close);
      }
      header.appendChild(el(compact ? "h3" : "h2", "title", data.title || ""));
      if (data.badge) header.appendChild(el("div", "badge", data.badge));

      const body = el("div", "body");
      for (const section of data.sections || []) body.appendChild(this.renderSection(section));

      root.replaceChildren(style, header, body);
    }

    renderSection(section) {
      const wrap = el("section", "section");
      if (section.title) wrap.appendChild(el("h3", "", section.title));
      let filled = false;

      if (section.text) {
        wrap.appendChild(el("p", "", section.text));
        filled = true;
      }
      if (section.stats && section.stats.length) {
        const grid = el("div", "stats");
        for (const stat of section.stats) {
          const cell = el("div", "stat");
          cell.append(el("span", "", stat.label), el("b", "", stat.value));
          grid.appendChild(cell);
        }
        wrap.appendChild(grid);
        filled = true;
      }
      if (section.chips && section.chips.length) {
        const row = el("div", "chips");
        for (const chip of section.chips) {
          if (chip && typeof chip === "object") {
            const button = el("button", "chip", chip.label || chip.id);
            button.type = "button";
            button.addEventListener("click", () =>
              this.dispatchEvent(new CustomEvent("chip-select", {
                detail: { id: chip.id }, bubbles: true, composed: true,
              })));
            row.appendChild(button);
          } else {
            row.appendChild(el("span", "chip", String(chip)));
          }
        }
        wrap.appendChild(row);
        filled = true;
      }
      if (section.link && SAFE_URL.test(section.link.href || "")) {
        const link = el("a", "read", section.link.label || "Open");
        link.href = section.link.href;
        link.target = "_blank";
        link.rel = "noopener";
        wrap.appendChild(link);
        filled = true;
      }
      if (!filled) wrap.appendChild(el("p", "", section.empty ?? "—"));
      return wrap;
    }
  }

  if (!customElements.get("poppy-card")) customElements.define("poppy-card", PoppyCard);
})();
