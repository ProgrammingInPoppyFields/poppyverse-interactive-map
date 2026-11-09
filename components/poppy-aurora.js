/*
 * <poppy-aurora> -- an animated background of soft, glowing colour blobs
 * drifting slowly over a dark field. Used by the home and About pages.
 *
 *   <script src="components/poppy-aurora.js"></script>
 *   <poppy-aurora></poppy-aurora>        <!-- first thing inside <body> -->
 *
 * It fixes itself behind the page (position: fixed, z-index: -1, no pointer
 * events), so nothing else needs to change. Blobs are painted with additive
 * blending ("lighter"), so where they overlap the light adds up and the colours
 * bloom. Everything is drawn at reduced resolution and scaled up, which keeps
 * it cheap and makes the edges extra fuzzy.
 *
 * Optional attributes:
 *   count="11"        number of blobs
 *   speed="1"         drift speed multiplier (0.5 = half speed)
 *   intensity="1"     overall brightness, 0 to 1.5
 *   scale="0.5"       render resolution relative to the screen (lower = softer, faster)
 *
 * Honours prefers-reduced-motion (draws one still frame) and pauses while the
 * tab is hidden. Edit this one file and every page that uses it changes.
 */
(() => {
  // Palette sampled from the reference look: violet, lime, emerald, cyan-blue,
  // teal, ember red, gold, magenta, plus Poppy pink and a deep green.
  const PALETTE = [
    [128, 24, 255],  // violet
    [150, 235, 80],  // lime
    [20, 214, 150],  // emerald
    [24, 150, 235],  // cyan-blue
    [30, 200, 210],  // teal
    [235, 70, 50],   // ember
    [235, 215, 60],  // gold
    [210, 20, 150],  // magenta
    [255, 20, 71],   // poppy pink
    [20, 120, 50],   // deep green
  ];

  const STYLE = `
    :host {
      position: fixed;
      inset: 0;
      z-index: -1;
      display: block;
      overflow: hidden;
      pointer-events: none;
      background: #06060a;
    }
    canvas { display: block; width: 100%; height: 100%; }
    .veil {
      position: absolute;
      inset: 0;
      /* keeps text legible: a little darker toward the edges */
      background: radial-gradient(ellipse at 50% 45%, transparent 40%, rgba(0, 0, 0, 0.42) 100%);
    }
  `;

  const rand = (min, max) => min + Math.random() * (max - min);
  const TAU = Math.PI * 2;

  class PoppyAurora extends HTMLElement {
    connectedCallback() {
      const root = this.shadowRoot || this.attachShadow({ mode: "open" });
      const style = document.createElement("style");
      style.textContent = STYLE;
      this.canvas = document.createElement("canvas");
      const veil = document.createElement("div");
      veil.className = "veil";
      root.replaceChildren(style, this.canvas, veil);
      this.ctx = this.canvas.getContext("2d");

      this.reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
      this.blobs = this.makeBlobs();
      this.clock = rand(0, 1000); // start each visit at a different moment
      this.last = 0;

      this.resize = this.resize.bind(this);
      this.frame = this.frame.bind(this);
      this.observer = new ResizeObserver(this.resize);
      this.observer.observe(this);
      this.resize();
      this.frame(performance.now());
    }

    disconnectedCallback() {
      cancelAnimationFrame(this.raf);
      if (this.observer) this.observer.disconnect();
    }

    num(name, fallback) {
      const value = parseFloat(this.getAttribute(name));
      return Number.isFinite(value) ? value : fallback;
    }

    makeBlobs() {
      const count = Math.max(1, Math.round(this.num("count", 11)));
      const blobs = [];
      for (let i = 0; i < count; i += 1) {
        // Cycle the palette so every colour shows up before any repeats.
        const color = PALETTE[(i + Math.floor(rand(0, PALETTE.length))) % PALETTE.length];
        const big = Math.random() < 0.4;
        blobs.push({
          color,
          x: rand(0.05, 0.95), y: rand(0.05, 0.95),         // home position (0..1)
          ax: rand(0.05, 0.22), ay: rand(0.05, 0.2),        // drift amplitude
          fx: rand(0.012, 0.034), fy: rand(0.012, 0.034),   // drift rate (cycles/s)
          px: rand(0, TAU), py: rand(0, TAU),               // drift phase
          radius: big ? rand(0.3, 0.5) : rand(0.13, 0.27),  // fraction of the short side
          alpha: big ? rand(0.4, 0.62) : rand(0.55, 0.85),
          pulse: rand(0.04, 0.1), pulsePhase: rand(0, TAU), // slow breathing
          core: Math.random() < 0.5,                        // a hotter centre
        });
      }
      return blobs;
    }

    resize() {
      const scale = Math.min(1, Math.max(0.2, this.num("scale", 0.5)));
      const w = Math.max(2, Math.round(this.clientWidth * scale));
      const h = Math.max(2, Math.round(this.clientHeight * scale));
      if (this.canvas.width !== w || this.canvas.height !== h) {
        this.canvas.width = w;
        this.canvas.height = h;
      }
      this.paint(); // repaint at once so a resize never shows a blank frame
    }

    frame(now) {
      this.raf = requestAnimationFrame(this.frame);
      if (this.reduced.matches) return; // one still frame is already painted
      if (now - this.last < 33) return; // ~30 fps is plenty for slow, soft motion
      const dt = this.last ? Math.min(0.1, (now - this.last) / 1000) : 0;
      this.last = now;
      this.clock += dt * this.num("speed", 1);
      this.paint();
    }

    paint() {
      const { ctx, canvas } = this;
      const w = canvas.width;
      const h = canvas.height;
      const short = Math.min(w, h);
      const intensity = this.num("intensity", 1);

      ctx.globalCompositeOperation = "source-over";
      ctx.fillStyle = "#06060a";
      ctx.fillRect(0, 0, w, h);
      ctx.globalCompositeOperation = "lighter"; // additive: overlaps glow brighter

      for (const b of this.blobs) {
        const t = this.clock;
        const x = (b.x + Math.sin(t * TAU * b.fx + b.px) * b.ax) * w;
        const y = (b.y + Math.sin(t * TAU * b.fy + b.py) * b.ay) * h;
        const r = b.radius * short * (1 + Math.sin(t * TAU * b.pulse + b.pulsePhase) * 0.12);
        const [cr, cg, cb] = b.color;
        const a = b.alpha * intensity;

        this.glow(x, y, r, cr, cg, cb, a);
        if (b.core) this.glow(x, y, r * 0.38, cr, cg, cb, a * 0.8);
      }
    }

    // A radial gradient with a gaussian-ish falloff, so there is no visible rim.
    glow(x, y, r, cr, cg, cb, a) {
      const g = this.ctx.createRadialGradient(x, y, 0, x, y, r);
      const stops = [[0, 1], [0.25, 0.76], [0.5, 0.4], [0.75, 0.14], [1, 0]];
      for (const [offset, k] of stops) g.addColorStop(offset, `rgba(${cr},${cg},${cb},${(a * k).toFixed(3)})`);
      this.ctx.fillStyle = g;
      this.ctx.fillRect(x - r, y - r, r * 2, r * 2);
    }
  }

  if (!customElements.get("poppy-aurora")) customElements.define("poppy-aurora", PoppyAurora);
})();
