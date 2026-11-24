/* Beauty hero behaviour: vanilla port of the "Elias" React hero.
 * Splash -> staged reveals -> cursor depth, ink spotlight, custom cursor,
 * the self-writing note and the 3D product box carousel. */
(() => {
  const root = document.querySelector('[data-bh]');
  if (!root) return;

  const MOTION = {
    delays: { first: 0.1, last: 0.25 },
    depth: { portrait: 14, first: 6, last: 9 },
    letter: { perCharacter: 0.06, pauseAfterPunctuation: 0.36, beforeSeal: 1.4, press: 0.8, sealHold: 4.8 },
    bookTilt: 14, bookOpen: 34, bookCycle: 3.2,
    spotlight: { radius: 145, readyAfter: 2.1 },
  };
  const SPLASH = { openAt: 1.4, openDuration: 850, fontTimeout: 1200 };
  const media = (q) => window.matchMedia(q);
  const reduce = media('(prefers-reduced-motion: reduce)').matches;
  const finePointer = media('(hover: hover) and (pointer: fine)').matches;
  const composition = media('(min-width: 64rem) and (min-aspect-ratio: 5/4)');
  const fa = (n) => String(n).padStart(2, '0').replace(/\d/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[d]);

  /* A critically damped-ish spring driven by rAF, standing in for motion's useSpring */
  const spring = ({ stiffness, damping, mass }, onUpdate, initial = 0) => {
    let value = initial, velocity = 0, target = initial, frame = 0;
    const step = () => {
      const force = -stiffness * (value - target) - damping * velocity;
      velocity += (force / mass) / 60;
      value += velocity / 60;
      onUpdate(value);
      if (Math.abs(velocity) > 0.001 || Math.abs(value - target) > 0.001) frame = requestAnimationFrame(step);
      else { value = target; onUpdate(value); frame = 0; }
    };
    return {
      set(v) { target = v; if (!frame) frame = requestAnimationFrame(step); },
      jump(v) { cancelAnimationFrame(frame); frame = 0; value = target = v; velocity = 0; onUpdate(v); },
      get: () => value,
    };
  };

  /* ---------- Name: each word rises inside its own mask (Persian letters join, so the word is the unit) ---------- */
  root.querySelectorAll('[data-bh-word]').forEach((word) => {
    const inner = document.createElement('span');
    inner.textContent = word.textContent;
    inner.style.setProperty('--from', word.dataset.bhWord === 'below' ? '105%' : '-105%');
    inner.style.setProperty('--d', `${word.dataset.bhWord === 'below' ? MOTION.delays.first : MOTION.delays.last}s`);
    word.replaceChildren(inner);
  });

  /* ---------- Start: plays the entrance; everything else keys off it ---------- */
  let started = false;
  const startCallbacks = [];
  const onStart = (fn) => (started ? fn() : startCallbacks.push(fn));
  const start = () => {
    if (started) return;
    started = true;
    root.classList.add('is-started');
    startCallbacks.splice(0).forEach((fn) => fn());
  };

  /* ---------- Splash ---------- */
  const splash = root.querySelector('[data-bh-splash]');
  if (splash && !reduce && !sessionStorage.getItem('bh-splash-seen')) {
    // Fixed inside a size container is trapped by containment; the splash must cover the whole viewport
    document.body.append(splash);
    splash.hidden = false;
    const html = document.documentElement;
    const previousOverflow = html.style.overflow;
    html.style.overflow = 'hidden';
    let opened = false;
    const open = () => {
      if (opened) return;
      opened = true;
      sessionStorage.setItem('bh-splash-seen', '1');
      start();
      const radius = Math.hypot(window.innerWidth, window.innerHeight) / 2 + 24;
      const t0 = performance.now();
      const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
      const grow = (now) => {
        const p = Math.min(1, (now - t0) / SPLASH.openDuration);
        splash.style.setProperty('--hole', `${ease(p) * radius}px`);
        if (p < 1) requestAnimationFrame(grow);
        else { splash.remove(); html.style.overflow = previousOverflow; }
      };
      requestAnimationFrame(grow);
      window.removeEventListener('keydown', open);
    };
    window.addEventListener('keydown', open);
    splash.addEventListener('pointerdown', open);
    const timeout = new Promise((resolve) => setTimeout(resolve, SPLASH.fontTimeout));
    Promise.race([document.fonts?.ready ?? Promise.resolve(), timeout]).then(() => {
      splash.classList.add('is-tracing');
      setTimeout(open, SPLASH.openAt * 1000);
    });
  } else {
    splash?.remove();
    requestAnimationFrame(start);
  }

  /* ---------- On screen: the self-running loops hold off screen or in a hidden tab ---------- */
  let onScreen = true;
  const screenListeners = [];
  const updateScreen = (visible) => {
    const next = visible && !document.hidden;
    if (next === onScreen) return;
    onScreen = next;
    screenListeners.forEach((fn) => fn(onScreen));
  };
  let intersecting = true;
  new IntersectionObserver(([entry]) => { intersecting = entry.isIntersecting; updateScreen(intersecting); }).observe(root);
  document.addEventListener('visibilitychange', () => updateScreen(intersecting));

  /* A pausable timer: keeps how long it had waited when held, and resumes with the rest */
  const pausableTimer = (fn, ms) => {
    let remaining = ms, begun = 0, id = 0, done = false;
    const run = () => { if (done || !onScreen) return; begun = performance.now(); id = setTimeout(() => { done = true; fn(); }, remaining); };
    const hold = () => { if (!id) return; clearTimeout(id); id = 0; remaining -= performance.now() - begun; };
    const listener = (visible) => (visible ? run() : hold());
    screenListeners.push(listener);
    run();
    return () => { done = true; hold(); screenListeners.splice(screenListeners.indexOf(listener), 1); };
  };

  /* ---------- Depth, ink spotlight and the custom cursor (mouse only, never under reduced motion) ---------- */
  const canvas = root.querySelector('[data-bh-canvas]');
  const depthActive = finePointer && !reduce;
  if (depthActive && canvas) {
    const DEPTH = { stiffness: 50, damping: 18, mass: 0.9 };
    const SPOT = { stiffness: 380, damping: 36, mass: 0.6 };
    const layers = {
      first: [...root.querySelectorAll('[data-bh-depth="first"]')],
      last: [...root.querySelectorAll('[data-bh-depth="last"]')],
      portrait: [...root.querySelectorAll('[data-bh-depth="portrait"]')],
    };
    let dx = 0, dy = 0;
    const paint = () => {
      layers.first.forEach((el) => { el.style.translate = `${dx * -MOTION.depth.first}px ${dy * -MOTION.depth.first * 0.4}px`; });
      layers.last.forEach((el) => { el.style.translate = `${dx * -MOTION.depth.last}px ${dy * -MOTION.depth.last * 0.3}px`; });
      // Sideways only, so the portrait's cut-off bottom edge never lifts off the hero's bottom edge
      layers.portrait.forEach((el) => { el.style.translate = `${dx * MOTION.depth.portrait}px 0`; });
    };
    const depthX = spring(DEPTH, (v) => { dx = v; paint(); });
    const depthY = spring(DEPTH, (v) => { dy = v; paint(); });

    const spotX = spring(SPOT, (v) => canvas.style.setProperty('--spot-x', `${v}px`));
    const spotY = spring(SPOT, (v) => canvas.style.setProperty('--spot-y', `${v}px`));
    let spotRadius = 0, spotAnim = 0, spotOpen = false, spotReady = false;
    const animateRadius = (to, duration) => {
      cancelAnimationFrame(spotAnim);
      const from = spotRadius, t0 = performance.now();
      const tick = (now) => {
        const p = Math.min(1, (now - t0) / duration);
        spotRadius = from + (to - from) * (1 - Math.pow(1 - p, 4));
        canvas.style.setProperty('--spot-r', `${spotRadius}px`);
        if (p < 1) spotAnim = requestAnimationFrame(tick);
      };
      spotAnim = requestAnimationFrame(tick);
    };
    onStart(() => setTimeout(() => { spotReady = true; }, MOTION.spotlight.readyAfter * 1000));

    root.addEventListener('pointermove', (event) => {
      depthX.set((event.clientX / window.innerWidth) * 2 - 1);
      depthY.set((event.clientY / window.innerHeight) * 2 - 1);
      if (!spotReady || !composition.matches) return;
      root.classList.add('spot-on');
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left, y = event.clientY - rect.top;
      if (!spotOpen) {
        spotOpen = true;
        // Fully closed, it is placed under the cursor first so it opens there instead of gliding over
        if (spotRadius < 1) { spotX.jump(x); spotY.jump(y); }
        animateRadius(MOTION.spotlight.radius, 600);
      }
      spotX.set(x); spotY.set(y);
    }, { passive: true });
    root.addEventListener('pointerleave', () => {
      depthX.set(0); depthY.set(0);
      spotOpen = false;
      animateRadius(0, 450);
    });

    // The cursor: a dot that follows exactly, and a trailing ring/disc on a spring
    const cursor = root.querySelector('[data-bh-cursor]');
    const pos = cursor.querySelector('.bh-cursor-pos');
    const trail = cursor.querySelector('.bh-cursor-trail');
    const TRAIL = { stiffness: 420, damping: 34, mass: 0.5 };
    let tx = -100, ty = -100;
    const trailX = spring(TRAIL, (v) => { tx = v; trail.style.transform = `translate(${tx}px, ${ty}px)`; }, -100);
    const trailY = spring(TRAIL, (v) => { ty = v; trail.style.transform = `translate(${tx}px, ${ty}px)`; }, -100);
    root.classList.add('has-cursor');
    let mode = 'dot';
    root.addEventListener('pointermove', (event) => {
      const rect = root.getBoundingClientRect();
      const x = event.clientX - rect.left, y = event.clientY - rect.top;
      pos.style.transform = `translate(${x}px, ${y}px)`;
      trailX.set(x); trailY.set(y);
      cursor.style.setProperty('--visible', '1');
      const target = event.target instanceof Element ? event.target : null;
      const next = target?.closest('.bh-book-frame') ? 'read' : target?.closest('a, button') ? 'link' : 'dot';
      if (next !== mode) { mode = next; cursor.dataset.mode = mode; }
    }, { passive: true });
    root.addEventListener('pointerleave', () => cursor.style.setProperty('--visible', '0'));
  }

  /* ---------- The note to tomorrow: types, presses the stamp, seals, then the next note ---------- */
  const letter = root.querySelector('[data-bh-letter]');
  const messages = [...root.querySelectorAll('[data-bh-message]')].map((t) => t.innerHTML.trim()).filter(Boolean);
  if (letter && messages.length) {
    const sheet = letter.querySelector('[data-bh-sheet]');
    const envelope = letter.querySelector('[data-bh-envelope]');
    const typed = letter.querySelector('[data-bh-typed]');
    const caret = letter.querySelector('[data-bh-caret]');
    const stamp = letter.querySelector('[data-bh-stamp]');
    const counter = letter.querySelector('[data-bh-letter-count]');
    const tomorrow = new Date(Date.now() + 864e5).toLocaleDateString('fa-IR', { month: 'long', day: 'numeric' });
    letter.querySelectorAll('[data-bh-tomorrow]').forEach((el) => { el.textContent = tomorrow; });
    const L = MOTION.letter;
    let index = 0, chars = 0, cancel = null;
    const showSheet = () => {
      counter.textContent = `${fa(index + 1)} / ${fa(messages.length)}`;
      typed.textContent = reduce ? messages[index] : '';
      stamp.classList.toggle('is-ready', reduce);
      stamp.classList.remove('is-pressed');
      caret.hidden = reduce;
    };
    const wait = (seconds, fn) => { cancel = pausableTimer(fn, seconds * 1000); };
    const typeNext = () => {
      const message = messages[index];
      if (chars < message.length) {
        const previous = message[chars - 1] ?? '';
        wait(L.perCharacter + (/[،,.؛]/.test(previous) ? L.pauseAfterPunctuation : 0), () => {
          chars += 1;
          typed.textContent = message.slice(0, chars);
          if (chars === message.length) stamp.classList.add('is-ready');
          typeNext();
        });
        return;
      }
      caret.hidden = true;
      wait(L.beforeSeal, () => {
        stamp.classList.add('is-pressed');
        wait(L.press, seal);
      });
    };
    const seal = () => {
      sheet.classList.add('is-leaving');
      setTimeout(() => {
        sheet.hidden = true;
        sheet.classList.remove('is-leaving');
        envelope.hidden = false;
        requestAnimationFrame(() => envelope.classList.add('is-sealing'));
        wait(L.sealHold, () => {
          envelope.classList.add('is-leaving');
          setTimeout(() => {
            envelope.hidden = true;
            envelope.classList.remove('is-sealing', 'is-leaving');
            index = (index + 1) % messages.length;
            chars = 0;
            showSheet();
            sheet.classList.add('is-arriving');
            sheet.hidden = false;
            requestAnimationFrame(() => requestAnimationFrame(() => sheet.classList.remove('is-arriving')));
            caret.hidden = false;
            typeNext();
          }, 900);
        });
      }, 600);
    };
    showSheet();
    // Under reduced motion the first note simply rests, written
    if (!reduce) onStart(() => setTimeout(typeNext, 1200));
  }

  /* ---------- The 3D product box: turns toward the cursor, lid lifts on hover, opens on click, cycles ---------- */
  const book = root.querySelector('[data-bh-book]');
  if (book) {
    const button = book.querySelector('[data-bh-book-button]');
    const slots = [...book.querySelectorAll('[data-bh-slot]')];
    const shadow = book.querySelector('[data-bh-book-shadow]');
    const label = book.querySelector('[data-bh-book-label]');
    const topics = book.querySelector('[data-bh-book-topics]');
    const link = book.querySelector('[data-bh-book-link]');
    const name = book.querySelector('[data-bh-book-name]');
    const live = book.querySelector('[data-bh-book-live]');
    const REST = { rotateY: 24, rotateX: 6 }; // mirrored for RTL: the spine sits on the right
    const TURN = { stiffness: 160, damping: 20, mass: 0.7 };
    const OPEN = { stiffness: 90, damping: 17, mass: 0.9 };
    let index = 0, open = false, hovered = false, cancel = null;
    let px = 0, py = 0, peek = 0, openness = 0;
    const current = () => slots[index].querySelector('.bh-book-3d');
    const paint = () => {
      const el = current();
      const o = openness;
      el.style.setProperty('--ry', `${(REST.rotateY - px * MOTION.bookTilt) * (1 - o) - px * 3 * o}deg`);
      el.style.setProperty('--rx', `${(REST.rotateX - py * MOTION.bookTilt * 0.5) * (1 - o) - py * 2 * o}deg`);
      el.style.setProperty('--shift', `${o * -50}%`);
      el.style.setProperty('--scale', String(1 + o * 0.2));
      el.style.setProperty('--cover', `${Math.max(peek * MOTION.bookOpen, o * 178)}deg`);
      shadow.style.transform = `scaleX(${1 + o * 1.1})`;
    };
    const sx = spring(TURN, (v) => { px = v; paint(); });
    const sy = spring(TURN, (v) => { py = v; paint(); });
    const sp = spring(TURN, (v) => { peek = v; paint(); });
    const so = spring(OPEN, (v) => { openness = v; paint(); });
    const turnActive = finePointer && !reduce;

    const describe = () => {
      const slot = slots[index];
      label.textContent = slot.dataset.label;
      topics.textContent = slot.dataset.topics;
      link.href = slot.dataset.href;
      link.setAttribute('aria-label', `مشاهده ${slot.dataset.title}`);
      name.textContent = `${open ? 'بستن و نمایش محصول بعدی:' : 'باز کردن جعبه'} ${slot.dataset.title}`;
      button.setAttribute('aria-expanded', String(open));
    };
    const go = (next) => {
      if (slots.length < 2) return;
      const leaving = slots[index];
      index = (next + slots.length) % slots.length;
      const arriving = slots[index];
      // Place the arriving box on the far side without animating, then slide both
      arriving.classList.add('no-transition');
      arriving.classList.remove('is-leaving', 'is-active');
      arriving.style.transform = 'translateX(-100%)';
      arriving.style.visibility = 'visible';
      void arriving.offsetWidth;
      arriving.classList.remove('no-transition');
      arriving.style.transform = '';
      arriving.style.visibility = '';
      arriving.classList.add('is-active');
      leaving.classList.remove('is-active');
      leaving.classList.add('is-leaving');
      setTimeout(() => leaving.classList.remove('is-leaving'), 950);
      const old = leaving.querySelector('.bh-book-3d');
      ['--ry', '--rx', '--shift', '--scale', '--cover'].forEach((prop) => old.style.removeProperty(prop));
      sx.jump(0); sy.jump(0); sp.jump(0); so.jump(0);
      describe();
      schedule();
    };
    // Cycles by itself every few seconds, unless hovered or open; holds off screen
    const schedule = () => {
      cancel?.();
      cancel = null;
      if (reduce || hovered || open || !started) return;
      cancel = pausableTimer(() => go(index + 1), MOTION.bookCycle * 1000);
    };
    const setOpen = (value) => {
      open = value;
      if (reduce) so.jump(value ? 1 : 0); else so.set(value ? 1 : 0);
      describe();
      live.textContent = value ? `${slots[index].dataset.title}. ${slots[index].querySelector('.bh-book-page').textContent.trim().replace(/\s+/g, ' ')}` : '';
    };
    button.addEventListener('click', () => {
      sp.set(0);
      if (!open) { setOpen(true); schedule(); return; }
      setOpen(false);
      setTimeout(() => go(index + 1), reduce ? 0 : 650);
    });
    window.addEventListener('keydown', (event) => { if (event.key === 'Escape' && open) { setOpen(false); schedule(); } });
    button.addEventListener('pointerenter', () => { hovered = true; schedule(); if (turnActive && !open) sp.set(1); });
    button.addEventListener('pointermove', (event) => {
      if (!turnActive) return;
      const rect = button.getBoundingClientRect();
      sx.set(((event.clientX - rect.left) / rect.width) * 2 - 1);
      sy.set(((event.clientY - rect.top) / rect.height) * 2 - 1);
    });
    button.addEventListener('pointerleave', () => { hovered = false; sx.set(0); sy.set(0); sp.set(0); schedule(); });
    describe();
    paint();
    onStart(() => setTimeout(schedule, 1200));
  }
})();