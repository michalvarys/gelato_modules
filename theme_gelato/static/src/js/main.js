/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.GlHeroSlider = publicWidget.Widget.extend({
    selector: '.gl-hero',
    disabledInEditableMode: true,

    start() {
        this._super(...arguments);
        this.current = 0;
        this.timer = null;
        this._paused = false;
        this._slideIntervals = [];

        // Pause only while a real mouse hovers actionable elements (CTA, dots).
        // A full-section hover pause froze the slider: the hero fills the whole
        // viewport, and touch devices fire pointerenter without a matching leave.
        const PAUSE_TARGETS = '.gl-hero-cta, .gl-hero-slide-nav';
        this._onPointerOver = (ev) => {
            if (ev.pointerType !== 'mouse') return;
            if (ev.target.closest && ev.target.closest(PAUSE_TARGETS)) {
                this._paused = true;
                clearTimeout(this.timer);
            }
        };
        this._onPointerOut = (ev) => {
            if (ev.pointerType !== 'mouse' || !this._paused) return;
            const to = ev.relatedTarget;
            if (!to || !to.closest || !to.closest(PAUSE_TARGETS)) {
                this._paused = false;
                this._resetTimer();
            }
        };
        this.el.addEventListener('pointerover', this._onPointerOver);
        this.el.addEventListener('pointerout', this._onPointerOut);

        this._touchStartX = 0;
        this._touchStartY = 0;
        this._onTouchStart = (ev) => {
            this._touchStartX = ev.touches[0].clientX;
            this._touchStartY = ev.touches[0].clientY;
        };
        this._onTouchEnd = (ev) => {
            const dx = ev.changedTouches[0].clientX - this._touchStartX;
            const dy = ev.changedTouches[0].clientY - this._touchStartY;
            if (Math.abs(dx) < 40 || Math.abs(dy) > Math.abs(dx)) return;
            if (dx < 0) {
                this._goTo((this.current + 1) % this.total);
            } else {
                this._goTo((this.current - 1 + this.total) % this.total);
            }
        };
        this.el.addEventListener('touchstart', this._onTouchStart, { passive: true });
        this.el.addEventListener('touchend', this._onTouchEnd, { passive: true });

        this._cleanSavedState();
        return this._loadSlides();
    },

    _cleanSavedState() {
        this.el.classList.add('gl-no-transition');
        this.el.classList.remove('gl-loaded', 'gl-slide-image-only', 'gl-slide-no-overlay');
        const bg = this.el.querySelector('.gl-hero-bg');
        const content = this.el.querySelector('.gl-hero-slides-wrap');
        const nav = this.el.querySelector('.gl-hero-slide-nav');
        if (bg) bg.innerHTML = '';
        if (content) content.innerHTML = '';
        if (nav) nav.innerHTML = '';
    },

    destroy() {
        clearTimeout(this.timer);
        this.el.removeEventListener('pointerover', this._onPointerOver);
        this.el.removeEventListener('pointerout', this._onPointerOut);
        this.el.removeEventListener('touchstart', this._onTouchStart);
        this.el.removeEventListener('touchend', this._onTouchEnd);
        if (this._observer) {
            this._observer.disconnect();
        }
        document.body.classList.remove('gl-header-solid');
        const bg = this.el.querySelector('.gl-hero-bg');
        const content = this.el.querySelector('.gl-hero-slides-wrap');
        const nav = this.el.querySelector('.gl-hero-slide-nav');
        if (bg) bg.innerHTML = '';
        if (content) content.innerHTML = '';
        if (nav) nav.innerHTML = '';
        this.el.classList.remove('gl-loaded', 'gl-no-transition', 'gl-slide-image-only', 'gl-slide-no-overlay');
        this._super(...arguments);
    },

    async _loadSlides() {
        let slides;
        try {
            slides = await rpc('/theme_gelato/hero_slides', {
                page_url: window.location.pathname,
            });
        } catch {
            this._dismissLoader();
            return;
        }
        if (!slides || !slides.length) {
            this._dismissLoader();
            return;
        }

        this._renderSlides(slides);
        this.total = slides.length;
        this._buildDots();

        this._dismissLoaderAndReveal();

        this._observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((e) => {
                    if (e.isIntersecting) {
                        this._resetTimer();
                        document.body.classList.remove('gl-header-solid');
                    } else {
                        clearTimeout(this.timer);
                        document.body.classList.add('gl-header-solid');
                    }
                });
            },
            { threshold: 0.3 },
        );
        this._observer.observe(this.el);
    },

    _renderSlides(slides) {
        const bgContainer = this.el.querySelector('.gl-hero-bg');
        const contentContainer = this.el.querySelector('.gl-hero-slides-wrap');

        // Clear existing (prevents duplicates on re-init)
        bgContainer.innerHTML = '';
        contentContainer.innerHTML = '';

        slides.forEach((slide, i) => {
            // Background slide
            const bgDiv = document.createElement('div');
            bgDiv.className = 'gl-hero-bg-slide' + (i === 0 ? ' active' : '');
            bgDiv.dataset.slide = i;
            if (slide.image_url) {
                bgDiv.style.backgroundImage = `url('${slide.image_url}')`;
            }
            bgContainer.appendChild(bgDiv);

            // Content slide
            const content = document.createElement('div');
            content.className = 'gl-hero-slide-content' + (i === 0 ? ' active' : '');
            content.dataset.slide = i;

            let html = '';
            if (slide.image_only) {
                // pure-image slide: no badge, headline, subtitle or button
                content.innerHTML = '';
                contentContainer.appendChild(content);
                return;
            }
            if (slide.name) {
                html += `<div class="gl-hero-badge">${this._esc(slide.name)}</div>`;
            }
            if (slide.headline || slide.headline_accent) {
                html += `<h2 class="gl-hero-headline">`;
                if (slide.headline) html += this._esc(slide.headline);
                if (slide.headline_accent) {
                    if (slide.headline) html += '<br/>';
                    html += `<span class="gl-accent">${this._esc(slide.headline_accent)}</span>`;
                }
                html += '</h2>';
            }
            if (slide.subtitle) {
                html += `<p class="gl-hero-sub">${this._esc(slide.subtitle)}</p>`;
            }
            if (slide.button_text) {
                html += `<div class="gl-hero-cta">
                    <a href="${this._esc(slide.button_url)}" class="gl-btn-hero gl-btn-hero-primary">
                        ${this._esc(slide.button_text)}
                        <svg viewBox="0 0 24 24"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                    </a>
                </div>`;
            }
            content.innerHTML = html;
            contentContainer.appendChild(content);
        });

        this.bgSlides = [...bgContainer.querySelectorAll('.gl-hero-bg-slide')];
        this.contentSlides = [...contentContainer.querySelectorAll('.gl-hero-slide-content')];
        this._slideIntervals = slides.map((s) => (s.display_time || 8) * 1000);
        this.slidesData = slides;
        this._applySlideFlags();
    },

    // Per-slide appearance flags: image-only hides the hero logos,
    // hide-overlay fades out the dark gradient (+ grain) for a clean photo
    _applySlideFlags() {
        const s = (this.slidesData && this.slidesData[this.current]) || {};
        this.el.classList.toggle('gl-slide-image-only', !!s.image_only);
        this.el.classList.toggle('gl-slide-no-overlay', !!s.hide_overlay);
    },

    _esc(str) {
        const el = document.createElement('span');
        el.textContent = str;
        return el.innerHTML;
    },

    _buildDots() {
        const navContainer = this.el.querySelector('.gl-hero-slide-nav');
        if (!navContainer) {
            return;
        }
        navContainer.innerHTML = '';
        for (let i = 0; i < this.total; i++) {
            const dot = document.createElement('div');
            dot.className = 'gl-hero-slide-dot' + (i === 0 ? ' active' : '');
            dot.dataset.slide = i;
            const duration = this._slideIntervals[i] || 8000;
            dot.style.setProperty('--gl-dot-duration', `${duration}ms`);
            dot.addEventListener('click', () => this._goTo(i));
            navContainer.appendChild(dot);
        }
        this.dots = [...navContainer.querySelectorAll('.gl-hero-slide-dot')];
    },

    _goTo(index) {
        if (index === this.current) {
            return;
        }
        this.bgSlides[this.current].classList.remove('active');
        this.contentSlides[this.current].classList.remove('active');
        this.dots[this.current].classList.remove('active');
        this.dots[this.current].classList.add('done');

        this.current = ((index % this.total) + this.total) % this.total;

        this.dots.forEach((d, i) => {
            d.classList.remove('active', 'done');
            if (i < this.current) {
                d.classList.add('done');
            }
        });

        this.bgSlides[this.current].classList.add('active');
        this.contentSlides[this.current].classList.add('active');
        this.dots[this.current].classList.add('active');
        this._applySlideFlags();
        this._resetTimer();
    },

    _next() {
        this._goTo((this.current + 1) % this.total);
    },

    _resetTimer() {
        clearTimeout(this.timer);
        if (this._paused) return;
        const delay = this._slideIntervals[this.current] || 8000;
        this.timer = setTimeout(() => this._next(), delay);
    },

    _dismissLoader() {
        const loader = document.getElementById('gl-loader');
        if (!loader) return;
        loader.classList.add('gl-loader-done');
        loader.addEventListener('animationend', () => loader.remove(), { once: true });
        setTimeout(() => loader.remove(), 800);
    },

    async _dismissLoaderAndReveal() {
        const loader = document.getElementById('gl-loader');
        if (loader) {
            await new Promise((resolve) => setTimeout(resolve, 600));
            loader.classList.add('gl-loader-done');
            await new Promise((resolve) => {
                loader.addEventListener('animationend', () => {
                    loader.remove();
                    resolve();
                }, { once: true });
                setTimeout(resolve, 500);
            });
        }

        const firstSlide = this.contentSlides[0];
        if (firstSlide) {
            firstSlide.classList.add('gl-initial');
            firstSlide.addEventListener('animationend', () => {
                firstSlide.classList.remove('gl-initial');
            }, { once: true });
        }
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                this.el.classList.remove('gl-no-transition');
                this.el.classList.add('gl-loaded');
                this._resetTimer();
            });
        });
    },
});

publicWidget.registry.GlFadeUp = publicWidget.Widget.extend({
    selector: '.gl-why',
    disabledInEditableMode: true,

    start() {
        this._super(...arguments);
        this._targets = this.el.querySelectorAll('.gl-fade-up');
        this._observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('gl-visible');
                    }
                });
            },
            { threshold: 0.1 },
        );
        this._targets.forEach((el) => this._observer.observe(el));
    },

    destroy() {
        if (this._observer) {
            this._observer.disconnect();
        }
        this._super(...arguments);
    },
});

publicWidget.registry.GlGallery = publicWidget.Widget.extend({
    selector: '.gl-gallery',
    disabledInEditableMode: true,

    start() {
        this._super(...arguments);
        return this._loadImages();
    },

    async _loadImages() {
        let images;
        try {
            images = await rpc('/theme_gelato/gallery_images', {});
        } catch {
            return;
        }
        if (!images || !images.length) {
            return;
        }

        const grid = this.el.querySelector('.gl-gallery-grid');
        if (!grid) {
            return;
        }
        grid.innerHTML = '';

        images.forEach((img) => {
            const item = document.createElement('div');
            item.className = 'gl-gallery-item';

            const imgEl = document.createElement('img');
            imgEl.src = img.image_url;
            imgEl.alt = img.name;
            imgEl.loading = 'lazy';
            imgEl.decoding = 'async';
            item.appendChild(imgEl);

            const overlay = document.createElement('div');
            overlay.className = 'gl-gallery-item-overlay';
            const span = document.createElement('span');
            span.textContent = img.name;
            overlay.appendChild(span);
            item.appendChild(overlay);

            grid.appendChild(item);
        });
    },
});

publicWidget.registry.GlLightbox = publicWidget.Widget.extend({
    selector: '.gl-gallery',
    disabledInEditableMode: true,
    events: {
        'click .gl-gallery-item': '_onItemClick',
    },

    start() {
        this._super(...arguments);
        this._overlay = null;
        this._onKeyDown = (ev) => {
            if (!this._overlay) return;
            if (ev.key === 'Escape') this._close();
            else if (ev.key === 'ArrowRight') this._show(this._index + 1);
            else if (ev.key === 'ArrowLeft') this._show(this._index - 1);
        };
    },

    destroy() {
        this._close();
        this._super(...arguments);
    },

    _onItemClick(ev) {
        const items = [...this.el.querySelectorAll('.gl-gallery-item')];
        this._items = items.map((it) => {
            const img = it.querySelector('img');
            const cap = it.querySelector('.gl-gallery-item-overlay');
            return {
                src: img ? img.src : '',
                caption: cap ? cap.textContent.trim() : (img ? img.alt : ''),
            };
        }).filter((it) => it.src);
        const index = items.indexOf(ev.currentTarget);
        if (index < 0 || !this._items.length) return;
        this._open(index);
    },

    _open(index) {
        this._close();
        const ov = document.createElement('div');
        ov.className = 'gl-lightbox';
        ov.innerHTML = `
            <button type="button" class="gl-lightbox-close" aria-label="Zavřít">&#10005;</button>
            <button type="button" class="gl-lightbox-prev" aria-label="Předchozí">&#10094;</button>
            <figure class="gl-lightbox-figure">
                <img class="gl-lightbox-img" alt=""/>
                <figcaption class="gl-lightbox-caption"></figcaption>
            </figure>
            <button type="button" class="gl-lightbox-next" aria-label="Další">&#10095;</button>
            <div class="gl-lightbox-counter"></div>`;
        document.body.appendChild(ov);
        document.body.classList.add('gl-lightbox-open');
        this._overlay = ov;

        ov.querySelector('.gl-lightbox-close').addEventListener('click', () => this._close());
        ov.querySelector('.gl-lightbox-prev').addEventListener('click', (e) => {
            e.stopPropagation();
            this._show(this._index - 1);
        });
        ov.querySelector('.gl-lightbox-next').addEventListener('click', (e) => {
            e.stopPropagation();
            this._show(this._index + 1);
        });
        ov.addEventListener('click', (e) => {
            if (e.target === ov || e.target.classList.contains('gl-lightbox-figure')) this._close();
        });

        let sx = 0, sy = 0;
        ov.addEventListener('touchstart', (e) => {
            sx = e.touches[0].clientX;
            sy = e.touches[0].clientY;
        }, { passive: true });
        ov.addEventListener('touchend', (e) => {
            const dx = e.changedTouches[0].clientX - sx;
            const dy = e.changedTouches[0].clientY - sy;
            if (Math.abs(dx) < 40 || Math.abs(dy) > Math.abs(dx)) return;
            this._show(this._index + (dx < 0 ? 1 : -1));
        }, { passive: true });

        document.addEventListener('keydown', this._onKeyDown);
        this._show(index);
    },

    _show(index) {
        const n = this._items.length;
        this._index = ((index % n) + n) % n;
        const item = this._items[this._index];
        const img = this._overlay.querySelector('.gl-lightbox-img');
        img.src = item.src;
        img.alt = item.caption;
        this._overlay.querySelector('.gl-lightbox-caption').textContent = item.caption;
        this._overlay.querySelector('.gl-lightbox-counter').textContent = `${this._index + 1} / ${n}`;
    },

    _close() {
        document.removeEventListener('keydown', this._onKeyDown);
        if (this._overlay) {
            this._overlay.remove();
            this._overlay = null;
        }
        document.body.classList.remove('gl-lightbox-open');
    },
});

publicWidget.registry.GlFaq = publicWidget.Widget.extend({
    selector: '.s_gelato_faq',
    disabledInEditableMode: true,

    start() {
        this._super(...arguments);
        this._injectSchema();
    },

    destroy() {
        if (this._schemaEl) {
            this._schemaEl.remove();
            this._schemaEl = null;
        }
        this._super(...arguments);
    },

    // FAQPage JSON-LD is built from the rendered content so it always matches
    // what the editor saved (a static script tag would be stripped on save).
    _injectSchema() {
        const items = [...this.el.querySelectorAll('.gl-faq-item')].map((it) => {
            const q = it.querySelector('summary');
            const a = it.querySelector('.gl-faq-answer');
            if (!q || !a) return null;
            return {
                '@type': 'Question',
                name: q.textContent.trim(),
                acceptedAnswer: {
                    '@type': 'Answer',
                    text: a.textContent.replace(/\s+/g, ' ').trim(),
                },
            };
        }).filter(Boolean);
        if (!items.length) return;
        const script = document.createElement('script');
        script.type = 'application/ld+json';
        script.text = JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'FAQPage',
            mainEntity: items,
        });
        document.head.appendChild(script);
        this._schemaEl = script;
    },
});

const GL_MAP_PLACES = [
    {
        lat: 50.2339, lng: 12.8546,
        name: 'Gelaterie Gelato!',
        desc: 'Sokolovská 101, Rybáře — celoročně',
        main: true,
    },
    {
        lat: 50.2191, lng: 12.8788,
        name: 'Vozík u Grandhotelu Pupp',
        desc: 'Mírové náměstí — v sezóně',
    },
    {
        lat: 50.2275, lng: 12.8782,
        name: 'Vozík v Dvořákových sadech',
        desc: 'u Sadové kolonády — v sezóně',
    },
];

publicWidget.registry.GlMap = publicWidget.Widget.extend({
    selector: '.gl-map-container',
    disabledInEditableMode: true,

    async start() {
        this._super(...arguments);
        this._iframe = this.el.querySelector('iframe');
        try {
            await this._loadLeaflet();
        } catch {
            return; // Leaflet unavailable — keep the iframe fallback
        }
        this._initMap();
    },

    destroy() {
        if (this._map) {
            this._map.remove();
            this._map = null;
        }
        if (this._mapEl) {
            this._mapEl.remove();
            this._mapEl = null;
        }
        if (this._iframe) {
            this._iframe.style.display = '';
        }
        this._super(...arguments);
    },

    _loadLeaflet() {
        if (window.L && window.L.map) {
            return Promise.resolve();
        }
        if (!document.getElementById('gl-leaflet-css')) {
            const link = document.createElement('link');
            link.id = 'gl-leaflet-css';
            link.rel = 'stylesheet';
            link.href = '/theme_gelato/static/lib/leaflet/leaflet.css';
            document.head.appendChild(link);
        }
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = '/theme_gelato/static/lib/leaflet/leaflet.js';
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    },

    _initMap() {
        const L = window.L;
        if (this._iframe) {
            this._iframe.style.display = 'none';
        }
        this._mapEl = document.createElement('div');
        this._mapEl.className = 'gl-map-leaflet';
        this.el.appendChild(this._mapEl);

        const map = L.map(this._mapEl, { scrollWheelZoom: false });
        this._map = map;
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        }).addTo(map);

        const bounds = [];
        GL_MAP_PLACES.forEach((place) => {
            const icon = L.divIcon({
                className: 'gl-map-marker-wrap',
                html: '<div class="gl-map-marker' + (place.main ? ' gl-map-marker-main' : '') + '"></div>',
                iconSize: [26, 26],
                iconAnchor: [13, 13],
                popupAnchor: [0, -14],
            });
            const marker = L.marker([place.lat, place.lng], { icon, title: place.name })
                .addTo(map)
                .bindPopup('<strong>' + place.name + '</strong><br/>' + place.desc);
            if (place.main) {
                marker.openPopup();
            }
            bounds.push([place.lat, place.lng]);
        });
        map.fitBounds(bounds, { padding: [50, 50] });
    },
});

publicWidget.registry.GlBodyClass = publicWidget.Widget.extend({
    selector: '#wrapwrap',
    disabledInEditableMode: false,

    start() {
        this._super(...arguments);
        document.body.classList.add('theme_gelato_body');
        this._dismissLoaderIfNoHero();
    },

    _dismissLoaderIfNoHero() {
        const hasHero = !!document.querySelector('.gl-hero');
        if (hasHero) {
            return;
        }
        const loader = document.getElementById('gl-loader');
        if (!loader) {
            return;
        }
        loader.classList.add('gl-loader-done');
        loader.addEventListener('animationend', () => loader.remove(), { once: true });
        setTimeout(() => loader.remove(), 800);
    },
});

publicWidget.registry.GlMobileNav = publicWidget.Widget.extend({
    selector: '#wrapwrap',
    disabledInEditableMode: true,

    start() {
        this._super(...arguments);
        this._header = this.el.querySelector('header');
        if (!this._header) {
            return;
        }

        this._offcanvas = this._header.querySelector('.offcanvas');
        this._collapse = this._header.querySelector('.navbar-collapse');
        this._drawer = this._offcanvas || this._collapse;
        if (!this._drawer) {
            return;
        }

        this._onShow = () => this._header.classList.add('gl-drawer-open');
        this._onHidden = () => this._header.classList.remove('gl-drawer-open');

        if (this._offcanvas) {
            this._offcanvas.addEventListener('show.bs.offcanvas', this._onShow);
            this._offcanvas.addEventListener('hidden.bs.offcanvas', this._onHidden);
        }
        if (this._collapse) {
            this._collapse.addEventListener('show.bs.collapse', this._onShow);
            this._collapse.addEventListener('hidden.bs.collapse', this._onHidden);
        }

        this._onLinkClick = (ev) => {
            const href = ev.currentTarget.getAttribute('href');
            if (!href || !href.includes('#')) {
                return;
            }
            const closeBtn = this._header.querySelector(
                '[data-bs-dismiss="offcanvas"], [data-bs-dismiss="collapse"], .navbar-toggler'
            );
            if (closeBtn) {
                closeBtn.click();
            }
        };
        this._header.querySelectorAll('.navbar-nav .nav-link, .navbar-nav a')
            .forEach((link) => link.addEventListener('click', this._onLinkClick));
    },

    destroy() {
        if (this._offcanvas) {
            this._offcanvas.removeEventListener('show.bs.offcanvas', this._onShow);
            this._offcanvas.removeEventListener('hidden.bs.offcanvas', this._onHidden);
        }
        if (this._collapse) {
            this._collapse.removeEventListener('show.bs.collapse', this._onShow);
            this._collapse.removeEventListener('hidden.bs.collapse', this._onHidden);
        }
        if (this._header) {
            this._header.classList.remove('gl-drawer-open');
            this._header.querySelectorAll('.navbar-nav .nav-link, .navbar-nav a')
                .forEach((link) => link.removeEventListener('click', this._onLinkClick));
        }
        this._super(...arguments);
    },
});

publicWidget.registry.GlSmoothScroll = publicWidget.Widget.extend({
    selector: '#wrapwrap',
    events: {
        'click a[href^="#"]': '_onAnchorClick',
        'click a[href^="/#"]': '_onAnchorClick',
    },

    _onAnchorClick(ev) {
        const href = ev.currentTarget.getAttribute('href');
        if (!href || href === '#') {
            return;
        }
        const hash = href.includes('#') ? '#' + href.split('#')[1] : null;
        if (!hash || hash === '#') {
            return;
        }
        const target = document.querySelector(hash);
        if (target) {
            ev.preventDefault();
            const closeBtn = document.querySelector(
                '[data-bs-dismiss="offcanvas"], .navbar-toggler[aria-expanded="true"]'
            );
            if (closeBtn) {
                closeBtn.click();
            }
            const headerOffset = 80;
            const top = target.getBoundingClientRect().top + window.pageYOffset - headerOffset;
            window.scrollTo({ top, behavior: 'smooth' });
        }
    },
});

publicWidget.registry.GlScrollSpy = publicWidget.Widget.extend({
    selector: '#wrapwrap',
    disabledInEditableMode: true,

    start() {
        this._super(...arguments);
        // State fields must exist before any early return — the editor calls
        // destroy() on every widget even when start() bailed out (new empty
        // pages have no anchor sections and crashed the editor on 'forEach').
        this._activeLinks = [];
        this._navLinks = [...document.querySelectorAll(
            'header .navbar-nav .nav-link[href*="#"], header .navbar-nav a[href*="#"]'
        )];
        if (!this._navLinks.length) {
            return;
        }

        this._sectionMap = new Map();
        for (const link of this._navLinks) {
            const href = link.getAttribute('href');
            const hash = href.includes('#') ? href.split('#')[1] : null;
            if (hash) {
                const section = document.getElementById(hash);
                if (section) {
                    if (!this._sectionMap.has(section)) {
                        this._sectionMap.set(section, []);
                    }
                    this._sectionMap.get(section).push(link);
                }
            }
        }
        if (!this._sectionMap.size) {
            return;
        }

        this._activeLinks = [];
        this._observer = new IntersectionObserver(
            (entries) => this._onIntersect(entries),
            { rootMargin: '-20% 0px -60% 0px' },
        );
        for (const section of this._sectionMap.keys()) {
            this._observer.observe(section);
        }
    },

    destroy() {
        if (this._observer) {
            this._observer.disconnect();
        }
        (this._activeLinks || []).forEach(l => l.classList.remove('gl-scrollspy-active'));
        this._super(...arguments);
    },

    _onIntersect(entries) {
        for (const entry of entries) {
            if (entry.isIntersecting) {
                const links = this._sectionMap.get(entry.target);
                if (!links) continue;
                this._activeLinks.forEach(l => l.classList.remove('gl-scrollspy-active'));
                links.forEach(l => l.classList.add('gl-scrollspy-active'));
                this._activeLinks = links;
            }
        }
    },
});

publicWidget.registry.GlFormFeedback = publicWidget.Widget.extend({
    selector: '.gl-inquiry',
    disabledInEditableMode: true,

    start() {
        this._super(...arguments);
        const params = new URLSearchParams(window.location.search);
        const status = params.get('form');
        if (!status) {
            return;
        }

        const form = this.el.querySelector('.gl-inquiry-form');
        if (!form) {
            return;
        }

        const banner = document.createElement('div');
        banner.className = 'gl-form-feedback gl-form-feedback-' + (status === 'ok' ? 'ok' : 'error');
        banner.textContent = status === 'ok'
            ? 'Děkujeme! Vaše poptávka byla odeslána. Ozveme se vám do 24 hodin.'
            : 'Omlouváme se, při odesílání nastala chyba. Zkuste to prosím znovu.';
        form.prepend(banner);

        this.el.scrollIntoView({ behavior: 'smooth', block: 'center' });

        if (status === 'ok') {
            window.history.replaceState({}, '', window.location.pathname + window.location.hash);
        }
    },
});
