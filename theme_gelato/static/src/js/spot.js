/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";

// Scroll-scrub video spot: sekce 700vh, sticky stage uvnitř přehrává WebP
// framy podle pozice scrollu. Autoplay jemně scrolluje stránku dolů, jakýkoli
// zásah uživatele ho pozastaví (scroll nahoru tedy normálně vrací zpět).
publicWidget.registry.GlSpotScrub = publicWidget.Widget.extend({
    selector: '.s_gelato_spot',
    disabledInEditableMode: true,

    start() {
        this._super(...arguments);
        const el = this.el;

        this.frameCount = parseInt(el.dataset.frameCount, 10) || 0;
        this.frameBase = el.dataset.frameBase || '';
        this.autoSpeed = parseFloat(el.dataset.autoSpeed) || 0;

        this.canvas = el.querySelector('.gl-spot-canvas');
        this.loaderEl = el.querySelector('.gl-spot-loader');
        this.loaderFill = el.querySelector('.gl-spot-loader-bar i');
        this.progressFill = el.querySelector('.gl-spot-progress i');
        this.captions = [...el.querySelectorAll('.gl-spot-caption')];
        if (!this.canvas || !this.frameCount) {
            return Promise.resolve();
        }
        this.ctx = this.canvas.getContext('2d');

        this.reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        this.frames = new Array(this.frameCount);
        this.loadedCount = 0;
        this.ready = false;
        this.preloadStarted = false;
        this.currentFrame = -1;
        this.targetP = 0;
        this.smoothP = 0;
        this.lerpRaf = null;
        this.autoRaf = null;
        this.autoPaused = false;
        this.pauseTimer = null;
        this.lastT = null;
        this.inView = false;

        this._onScroll = () => this._requestRender();
        this._onResize = () => this._resizeCanvas();
        this._onUserInput = () => this._pauseAuto();
        window.addEventListener('scroll', this._onScroll, { passive: true });
        window.addEventListener('resize', this._onResize);
        ['wheel', 'touchstart', 'touchmove', 'keydown'].forEach((ev) =>
            window.addEventListener(ev, this._onUserInput, { passive: true })
        );

        // preload framů až když se sekce blíží do viewportu
        this._preloadObserver = new IntersectionObserver(
            (entries) => {
                if (entries.some((e) => e.isIntersecting)) {
                    this._preload();
                    this._preloadObserver.disconnect();
                    this._preloadObserver = null;
                }
            },
            { rootMargin: '150% 0px' }
        );
        this._preloadObserver.observe(el);

        // rAF smyčky běží jen, když je sekce na obrazovce
        this._viewObserver = new IntersectionObserver((entries) => {
            this.inView = entries.some((e) => e.isIntersecting);
            if (this.inView) {
                this.lastT = null;
                this._startAuto();
                this._requestRender();
            }
        });
        this._viewObserver.observe(el);

        this._resizeCanvas();
        return Promise.resolve();
    },

    destroy() {
        window.removeEventListener('scroll', this._onScroll);
        window.removeEventListener('resize', this._onResize);
        ['wheel', 'touchstart', 'touchmove', 'keydown'].forEach((ev) =>
            window.removeEventListener(ev, this._onUserInput)
        );
        if (this._preloadObserver) this._preloadObserver.disconnect();
        if (this._viewObserver) this._viewObserver.disconnect();
        cancelAnimationFrame(this.lerpRaf);
        cancelAnimationFrame(this.autoRaf);
        clearTimeout(this.pauseTimer);
        this.frames = [];
        // reset stavu, aby editor uložil čisté HTML
        if (this.loaderEl) this.loaderEl.classList.remove('gl-loading');
        if (this.loaderFill) this.loaderFill.style.width = '';
        if (this.progressFill) this.progressFill.style.height = '';
        this.captions.forEach((c) => c.classList.remove('gl-visible'));
        this._super(...arguments);
    },

    // ------------------------------------------------------------------
    // preload
    // ------------------------------------------------------------------
    _framePath(i) {
        return this.frameBase + String(i + 1).padStart(3, '0') + '.webp';
    },

    _preload() {
        if (this.preloadStarted) return;
        this.preloadStarted = true;
        if (this.loaderEl) this.loaderEl.classList.add('gl-loading');
        const settle = () => {
            this.loadedCount++;
            if (this.loaderFill) {
                this.loaderFill.style.width =
                    Math.round((this.loadedCount / this.frameCount) * 100) + '%';
            }
            if (this.loadedCount >= this.frameCount) {
                this.ready = true;
                if (this.loaderEl) this.loaderEl.classList.remove('gl-loading');
                this.currentFrame = -1;
                this._requestRender();
                this._startAuto();
            }
        };
        for (let i = 0; i < this.frameCount; i++) {
            const img = new Image();
            img.onload = settle;
            img.onerror = settle;
            img.src = this._framePath(i);
            this.frames[i] = img;
        }
    },

    // ------------------------------------------------------------------
    // kreslení + plynulý scrub
    // ------------------------------------------------------------------
    _resizeCanvas() {
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = Math.round(rect.width * dpr);
        this.canvas.height = Math.round(rect.height * dpr);
        this.currentFrame = -1;
        this._requestRender();
    },

    _drawFrame(i) {
        const img = this.frames[i];
        if (!img || !img.complete || !img.naturalWidth) return;
        const cw = this.canvas.width;
        const ch = this.canvas.height;
        const scale = Math.max(cw / img.naturalWidth, ch / img.naturalHeight);
        const w = img.naturalWidth * scale;
        const h = img.naturalHeight * scale;
        this.ctx.drawImage(img, (cw - w) / 2, (ch - h) / 2, w, h);
        this.currentFrame = i;
    },

    _getProgress() {
        const rect = this.el.getBoundingClientRect();
        const total = rect.height - window.innerHeight;
        if (total <= 0) return 0;
        return Math.min(1, Math.max(0, -rect.top / total));
    },

    _paint(p) {
        if (this.ready) {
            const idx = Math.min(this.frameCount - 1, Math.round(p * (this.frameCount - 1)));
            if (idx !== this.currentFrame) this._drawFrame(idx);
        }
        if (this.progressFill) {
            this.progressFill.style.height = (p * 100).toFixed(1) + '%';
        }
        this.captions.forEach((c) => {
            const from = parseFloat(c.dataset.from);
            const to = parseFloat(c.dataset.to);
            c.classList.toggle('gl-visible', p >= from && p <= to);
        });
    },

    _requestRender() {
        this.targetP = this._getProgress();
        if (this.reduced) {
            // bez animace: kresli přímo cílovou pozici
            this.smoothP = this.targetP;
            this._paint(this.targetP);
            return;
        }
        if (this.lerpRaf === null || this.lerpRaf === undefined) {
            this.lerpRaf = requestAnimationFrame(() => this._lerpTick());
        }
    },

    _lerpTick() {
        this.lerpRaf = null;
        this.smoothP += (this.targetP - this.smoothP) * 0.14;
        if (Math.abs(this.targetP - this.smoothP) < 0.0004) {
            this.smoothP = this.targetP;
        }
        this._paint(this.smoothP);
        if (this.smoothP !== this.targetP && this.inView) {
            this.lerpRaf = requestAnimationFrame(() => this._lerpTick());
        }
    },

    // ------------------------------------------------------------------
    // autoplay: sekce sama scrolluje stránku dolů, dokud spot neskončí
    // ------------------------------------------------------------------
    _pauseAuto() {
        this.autoPaused = true;
        clearTimeout(this.pauseTimer);
        this.pauseTimer = setTimeout(() => {
            this.autoPaused = false;
            this.lastT = null;
        }, 1500);
    },

    _startAuto() {
        if (this.reduced || !this.autoSpeed) return;
        if (this.autoRaf !== null && this.autoRaf !== undefined) return;
        this.autoRaf = requestAnimationFrame((t) => this._autoTick(t));
    },

    _autoTick(t) {
        this.autoRaf = null;
        if (!this.inView) return; // smyčka se restartuje, až bude sekce vidět
        this.autoRaf = requestAnimationFrame((tt) => this._autoTick(tt));
        const dt = this.lastT === null ? 0 : Math.min((t - this.lastT) / 1000, 0.05);
        this.lastT = t;
        if (!this.ready || this.autoPaused || dt === 0) return;
        const p = this._getProgress();
        if (p <= 0 || p >= 1) return; // autoplay jen uvnitř spotu
        window.scrollBy(0, this.autoSpeed * dt);
    },
});
