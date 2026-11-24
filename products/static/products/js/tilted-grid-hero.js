/* Tilted Grid Hero (vanilla port of the React TiltedGridHero).
 * One row of images streams round the inside of a cylinder: flat at the
 * centre, curling toward the viewer at the ends, fading at the edges.
 * Each tile is cut into SLICES vertical strips, each a facet of the
 * cylinder; the tile (preserve-3d) is the only thing animated, so strips
 * never drift apart. JS only sizes the loop and swaps a tile's image when
 * it wraps out of sight. */
(() => {
  const SLICES = 16;
  const CAMERA = 1.6;
  const MAX_WIDTH = 55;
  const round = (n) => +n.toFixed(4);
  const deg = (rad) => (rad * 180) / Math.PI;

  // Cylinder radius as a share of width that puts the frame edge `bend` rad round the arc.
  const arc = (bend) => (CAMERA - 1 + Math.cos(bend)) / (2 * CAMERA * Math.sin(bend));

  function measure(width, height, tile, aspect, gap, bend) {
    const h = Math.min((tile / 100) * height, ((MAX_WIDTH / 100) * width) / aspect);
    const radius = width * arc(bend);
    if (!(h > 0) || !(radius > 0)) return { columns: 2, sweep: 0, unit: 0, limit: 0 };
    const unit = deg(h / radius);
    const pitch = (aspect + gap / 100) * unit;
    const limit = deg(bend) + (aspect * unit) / 2;
    const columns = Math.min(60, Math.max(2, Math.ceil((2 * limit) / pitch)));
    const sweep = round((columns * pitch) / 2);
    return { columns, sweep, unit: round(unit), limit: round(Math.min(sweep, limit)) };
  }

  let counter = 0;
  function mount(root) {
    const num = (name, fallback) => {
      const v = parseFloat(root.dataset[name]);
      return Number.isFinite(v) ? v : fallback;
    };
    const speed = num('speed', 4);
    const tileHeight = num('tileHeight', 26);
    const aspect = num('aspect', 16 / 9);
    const gap = num('gap', 6);
    const axis = num('axis', 56);
    const fade = num('fade', 12);
    const bend = (Math.min(85, Math.max(5, num('curve', 80))) * Math.PI) / 180;
    const images = [...root.querySelectorAll('[data-tgh-image]')].map((t) => t.dataset.src).filter(Boolean);
    if (!images.length) return;
    images.forEach((src) => { new Image().src = src; });

    const id = `tgh${++counter}`;
    const orbit = `${id}-o`;
    const tileClass = `${id}-t`;
    const r = 100 * arc(bend);
    const radius = `${+r.toFixed(3)}cqw`;
    const u = (n) => `calc(${round(n)} * min(${tileHeight}cqh, ${round(MAX_WIDTH / aspect)}cqw))`;
    const turn = (d) => `translateZ(${radius}) rotateY(${round(d)}deg) translateZ(-${radius})`;
    const share = aspect / SLICES;

    root.style.containerType = 'size';
    const style = document.createElement('style');
    const band = document.createElement('div');
    band.className = 'tgh__band';
    band.setAttribute('aria-hidden', 'true');
    const mask = `linear-gradient(90deg,transparent,#000 ${fade}%,#000 ${100 - fade}%,transparent)`;
    Object.assign(band.style, {
      perspective: `${+(r * CAMERA).toFixed(3)}cqw`,
      perspectiveOrigin: `50% ${axis}%`,
      maskImage: mask,
      webkitMaskImage: mask,
    });
    root.prepend(style, band);

    let layout = null;
    const shownByTile = [];
    const render = (next) => {
      const { columns, sweep, unit, limit } = next;
      const duration = columns * speed;
      const hide = round(((sweep - limit) / (2 * sweep || 1)) * 100);
      style.textContent =
        `@keyframes ${orbit}{from{transform:${turn(-sweep)}}to{transform:${turn(sweep)}}` +
        `0%,${hide}%,${100 - hide}%,100%{visibility:hidden}` +
        `${hide + 0.001}%,${100 - hide - 0.001}%{visibility:visible}}` +
        `@media(prefers-reduced-motion:reduce){.${tileClass}{animation-play-state:paused}}`;
      band.replaceChildren();

      for (let t = 0; t < columns; t++) {
        // Tile `columns - 1` starts nearest the exit, tile 0 furthest back.
        const first = columns - 1 - t;
        const tile = document.createElement('div');
        tile.className = `tgh__tile ${tileClass}`;
        Object.assign(tile.style, {
          left: `calc(50% - ${u(aspect / 2)})`,
          top: `calc(${axis}% - ${u(0.5)})`,
          width: u(aspect),
          height: u(1),
          animation: `${orbit} ${duration}s linear ${-t * speed}s infinite`,
        });
        const pictures = [];
        for (let k = 0; k < SLICES; k++) {
          const slice = document.createElement('div');
          slice.className = 'tgh__slice';
          if (k === 0) slice.classList.add('tgh__slice--first');
          if (k === SLICES - 1) slice.classList.add('tgh__slice--last');
          Object.assign(slice.style, {
            left: u((aspect - share) / 2),
            // One pixel wider so neighbouring facets overlap without hairlines.
            width: k === SLICES - 1 ? u(share) : `calc(${u(share)} + 1px)`,
            height: u(1),
            transform: turn((aspect / 2 - (k + 0.5) * share) * unit),
          });
          const img = document.createElement('img');
          img.alt = '';
          img.draggable = false;
          img.decoding = 'async';
          Object.assign(img.style, { left: u(-k * share), width: u(aspect), height: u(1) });
          slice.append(img);
          pictures.push(img);
          tile.append(slice);
        }
        let shown = -1;
        const show = (index) => {
          if (index === shown) return;
          shown = index;
          shownByTile[t] = index;
          const src = images[index % images.length];
          pictures.forEach((img) => { img.src = src; });
        };
        show(shownByTile[t] ?? first);
        // The image only changes on wrap, which happens out of sight.
        tile.addEventListener('animationiteration', (event) => {
          show(Math.round(event.elapsedTime / duration) * columns + first);
        });
        band.append(tile);
      }
      band.classList.add('is-ready');
    };

    new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      const next = measure(width, height, tileHeight, aspect, gap, bend);
      if (layout && layout.columns === next.columns && layout.sweep === next.sweep && layout.unit === next.unit) return;
      layout = next;
      render(next);
    }).observe(root);
  }

  const start = () => {
    if (!('ResizeObserver' in window) || !CSS.supports('container-type', 'size')) return;
    document.querySelectorAll('[data-tgh]').forEach(mount);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
