(() => {
  const toFa = (value) => String(value).replace(/\d/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[d]);
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* Mobile menu, alerts, filters */
  const menuButton = document.querySelector('[data-menu-toggle]');
  const mobileMenu = document.getElementById('mobile-navigation');
  menuButton?.addEventListener('click', () => {
    const isOpen = menuButton.getAttribute('aria-expanded') === 'true';
    menuButton.setAttribute('aria-expanded', String(!isOpen));
    mobileMenu.hidden = isOpen;
  });
  document.querySelectorAll('[data-dismiss]').forEach((button) => {
    button.addEventListener('click', () => button.closest('.alert')?.remove());
  });
  const filterButton = document.querySelector('[data-filter-toggle]');
  const filterPanel = document.getElementById('catalog-filters');
  filterButton?.addEventListener('click', () => {
    const isOpen = filterButton.getAttribute('aria-expanded') === 'true';
    filterButton.setAttribute('aria-expanded', String(!isOpen));
    filterPanel?.classList.toggle('is-open', !isOpen);
    if (!isOpen) filterPanel?.querySelector('input, select')?.focus();
  });

  /* Header shadow on scroll */
  const header = document.querySelector('[data-site-header]');
  if (header) {
    const onScroll = () => header.classList.toggle('is-scrolled', window.scrollY > 12);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  /* Toast + cart badge */
  const toast = document.querySelector('[data-toast]');
  let toastTimer;
  const showToast = (message, isError = false) => {
    if (!toast) return;
    toast.querySelector('[data-toast-text]').textContent = message;
    toast.classList.toggle('toast--error', isError);
    toast.querySelector('.toast__link').hidden = isError;
    toast.hidden = false;
    requestAnimationFrame(() => toast.classList.add('is-visible'));
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 4200);
  };
  const setCartCount = (count) => {
    const badge = document.querySelector('[data-cart-count]');
    if (!badge || count === undefined) return;
    badge.textContent = toFa(count);
    badge.classList.remove('is-bouncing');
    void badge.offsetWidth;
    badge.classList.add('is-bouncing');
  };
  const cartBadge = document.querySelector('[data-cart-count]');
  if (cartBadge) cartBadge.textContent = toFa(cartBadge.textContent.trim());

  /* Add to cart without leaving the page; the form still works without JS. */
  const addToCart = async (form, button) => {
    const data = new FormData(form);
    const payload = { product_id: data.get('product_id'), quantity: data.get('quantity') || 1 };
    if (data.get('variant_id')) payload.variant_id = data.get('variant_id');
    const label = button?.textContent;
    button?.classList.add('is-loading');
    if (button) button.textContent = 'در حال افزودن…';
    try {
      const response = await fetch(form.action, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': data.get('csrfmiddlewaretoken'), Accept: 'application/json' },
        body: JSON.stringify(payload),
      });
      const result = await response.json().catch(() => ({}));
      if (response.ok && result.success) {
        setCartCount(result.cart_count);
        showToast(result.message || 'به سبد خرید اضافه شد.');
        if (button) button.textContent = 'اضافه شد';
        setTimeout(() => { if (button) button.textContent = label; }, 1800);
      } else {
        showToast(result.error || 'افزودن به سبد انجام نشد. دوباره تلاش کنید.', true);
        if (button) button.textContent = label;
      }
    } catch {
      form.submit();
    } finally {
      button?.classList.remove('is-loading');
    }
  };
  document.querySelectorAll('[data-quick-add], [data-purchase-form]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.fetch) return;
      event.preventDefault();
      addToCart(form, form.querySelector('[type="submit"]'));
    });
  });

  /* Quantity steppers */
  document.querySelectorAll('[data-quantity-control]').forEach((control) => {
    const input = control.querySelector('input');
    if (!input) return;
    control.querySelectorAll('[data-quantity-change]').forEach((button) => {
      button.addEventListener('click', () => {
        const min = Number(input.min || 1);
        const max = Number(input.max || 999);
        const next = Number(input.value || min) + Number(button.dataset.quantityChange);
        input.value = String(Math.min(max, Math.max(min, next)));
        input.dispatchEvent(new Event('change', { bubbles: true }));
      });
    });
  });

  /* Product gallery */
  document.querySelectorAll('[data-gallery-thumb]').forEach((button) => {
    button.addEventListener('click', () => {
      const mainImage = document.getElementById('product-main-image');
      if (!mainImage || !button.dataset.image) return;
      mainImage.src = button.dataset.image;
      mainImage.alt = button.dataset.alt || mainImage.alt;
      document.querySelectorAll('[data-gallery-thumb]').forEach((thumb) => thumb.setAttribute('aria-pressed', String(thumb === button)));
    });
  });

  /* Variant selection updates price, stock and image */
  const purchaseForm = document.querySelector('[data-purchase-form]');
  if (purchaseForm) {
    const quantity = purchaseForm.querySelector('[data-quantity]');
    const variants = [...purchaseForm.querySelectorAll('[data-variant]')];
    const prices = document.querySelectorAll('[data-product-price]');
    const oldPrice = document.querySelector('[data-product-old-price]');
    const stock = document.querySelector('[data-product-stock]');
    const mainImage = document.getElementById('product-main-image');
    const submit = purchaseForm.querySelector('[data-purchase-submit]');
    const update = () => {
      const selected = variants.find((input) => input.checked);
      if (!selected) return;
      const tracked = selected.dataset.trackInventory !== 'false';
      const available = Number(selected.dataset.stock || 0);
      const inStock = !tracked || available > 0;
      if (quantity) {
        quantity.max = tracked ? String(Math.max(available, 1)) : '';
        if (tracked && Number(quantity.value) > available) quantity.value = String(Math.max(available, 1));
      }
      prices.forEach((el) => { el.textContent = Math.round(Number(selected.dataset.price)).toLocaleString('fa-IR'); });
      if (oldPrice) {
        const compare = Number(selected.dataset.comparePrice || 0);
        oldPrice.hidden = !(compare > Number(selected.dataset.price));
        oldPrice.textContent = oldPrice.hidden ? '' : `${Math.round(compare).toLocaleString('fa-IR')} تومان`;
      }
      if (selected.dataset.image && mainImage) mainImage.src = selected.dataset.image;
      if (stock) {
        stock.textContent = inStock ? 'موجود و آماده ارسال' : 'این گزینه ناموجود است';
        stock.classList.toggle('stock-message--out', !inStock);
        stock.classList.remove('stock-message--low');
      }
      if (submit) {
        submit.disabled = !inStock;
        submit.textContent = inStock ? 'افزودن به سبد خرید' : 'ناموجود';
      }
    };
    variants.forEach((input) => input.addEventListener('change', update));
    update();

    /* Mobile buy bar mirrors the main button once it scrolls out of view */
    const buyBar = document.querySelector('[data-buy-bar]');
    if (buyBar && submit && 'IntersectionObserver' in window) {
      new IntersectionObserver(([entry]) => {
        const visible = !entry.isIntersecting && entry.boundingClientRect.top < 0;
        buyBar.classList.toggle('is-visible', visible);
        buyBar.setAttribute('aria-hidden', String(!visible));
        buyBar.querySelector('button').tabIndex = visible ? 0 : -1;
      }).observe(submit);
      buyBar.querySelector('[data-buy-bar-submit]')?.addEventListener('click', () => {
        if (submit.disabled) { submit.scrollIntoView({ behavior: 'smooth', block: 'center' }); return; }
        purchaseForm.requestSubmit(submit);
      });
    }
  }

  /* Campaign countdown */
  const countdown = document.querySelector('[data-countdown]');
  if (countdown?.dataset.countdown) {
    const target = new Date(countdown.dataset.countdown).getTime();
    const parts = { days: 864e5, hours: 36e5, minutes: 6e4 };
    const tick = () => {
      const diff = target - Date.now();
      if (diff <= 0) { countdown.textContent = 'این پیشنهاد به پایان رسیده است.'; return false; }
      countdown.querySelector('[data-cd-days]').textContent = toFa(Math.floor(diff / parts.days));
      countdown.querySelector('[data-cd-hours]').textContent = toFa(Math.floor((diff % parts.days) / parts.hours));
      countdown.querySelector('[data-cd-minutes]').textContent = toFa(Math.floor((diff % parts.hours) / parts.minutes));
      return true;
    };
    if (tick()) { const timer = setInterval(() => { if (!tick()) clearInterval(timer); }, 30000); }
  }

  /* Copy coupon code */
  document.querySelectorAll('[data-copy-coupon]').forEach((button) => {
    button.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(button.dataset.copyCoupon); } catch { return; }
      const text = button.querySelector('.copy-text');
      button.classList.add('is-copied');
      if (text) text.textContent = 'کپی شد';
      setTimeout(() => { button.classList.remove('is-copied'); if (text) text.textContent = 'کپی'; }, 2200);
    });
  });

  /* One quiet entrance per home section */
  const reveal = document.querySelectorAll('[data-reveal]');
  if (!reduceMotion && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-revealed');
      observer.unobserve(entry.target);
    }), { rootMargin: '0px 0px -60px 0px', threshold: 0.08 });
    reveal.forEach((el) => observer.observe(el));
  } else {
    reveal.forEach((el) => el.classList.add('is-revealed'));
  }

  /* The atelier is intentionally user-controlled, with a gentle auto-advance only on idle. */
  const atelier = document.querySelector('[data-atelier]');
  if (atelier) {
    const slides = [...atelier.querySelectorAll('[data-atelier-slide]')];
    const image = atelier.querySelector('[data-atelier-image]');
    const caption = atelier.querySelector('[data-atelier-caption]');
    const card = atelier.querySelector('.atelier__card--front');
    const current = atelier.querySelector('[data-atelier-current]');
    const total = atelier.querySelector('[data-atelier-total]');
    let index = 0;
    let timer;
    if (total) total.textContent = toFa(slides.length);
    const show = (next, fromAuto = false) => {
      index = (next + slides.length) % slides.length;
      const slide = slides[index];
      slides.forEach((item, i) => {
        const active = i === index;
        item.classList.toggle('is-active', active);
        item.setAttribute('aria-selected', String(active));
      });
      if (card && !reduceMotion) card.classList.add('is-changing');
      const replace = () => {
        image.src = slide.dataset.src;
        image.alt = slide.dataset.alt;
        caption.textContent = slide.dataset.caption;
        current.textContent = toFa(index + 1);
        card?.classList.remove('is-changing');
      };
      if (card && !reduceMotion) setTimeout(replace, 170); else replace();
      if (!fromAuto) restart();
    };
    const restart = () => {
      clearInterval(timer);
      if (!reduceMotion) timer = setInterval(() => show(index + 1, true), 6000);
    };
    slides.forEach((slide, i) => slide.addEventListener('click', () => show(i)));
    atelier.querySelector('[data-atelier-prev]')?.addEventListener('click', () => show(index - 1));
    atelier.querySelector('[data-atelier-next]')?.addEventListener('click', () => show(index + 1));
    atelier.querySelector('.atelier__stage')?.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowRight') { event.preventDefault(); show(index - 1); }
      if (event.key === 'ArrowLeft') { event.preventDefault(); show(index + 1); }
    });
    atelier.addEventListener('mouseenter', () => clearInterval(timer));
    atelier.addEventListener('mouseleave', restart);
    atelier.addEventListener('focusin', () => clearInterval(timer));
    atelier.addEventListener('focusout', (event) => { if (!atelier.contains(event.relatedTarget)) restart(); });
    restart();
  }
})();
