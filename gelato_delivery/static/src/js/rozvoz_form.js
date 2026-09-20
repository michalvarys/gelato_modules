/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

// Where the basket is kept between visits. One key for the whole page;
// there is only ever one basket on it.
const CART_KEY = "gelato.rozvoz.kosik";

// ...and what was typed into the contact details. Kept apart from the
// basket: the two are cleared at different moments.
const FORM_KEY = "gelato.rozvoz.udaje";
const FORM_FIELDS = [
    "gelatoName",
    "gelatoPhone",
    "gelatoEmail",
    "gelatoAddress",
    "gelatoPostcode",
    "gelatoCity",
    "gelatoNote",
];

/**
 * The delivery form.
 *
 * An order is a basket. Thermal boxes, bundles and extras are three rows of
 * cards that swipe sideways; tapping a box asks which flavours go in it and
 * drops the result into the basket. The same box can go in twice with
 * different flavours, which is why the basket exists at all - one order used
 * to mean one box.
 *
 * The price worked out here is only a preview. The binding figure is
 * calculated by the server in the controller, so this code cannot make an
 * order cheaper.
 */
publicWidget.registry.GelatoRozvozForm = publicWidget.Widget.extend({
    selector: "#gelatoRozvozForm",
    events: {
        "click .gl-card": "_onCardClick",
        "click #gelatoPanel": "_onPanelBackdrop",
        "click #gelatoPanelClose": "_onPanelClose",
        "click .gl-opt": "_onPickFlavor",
        "click .gl-row-plus": "_onRowPlus",
        "click .gl-row-minus": "_onRowMinus",
        "click #gelatoAddToCart": "_onAddToCart",
        "click .gl-cart-plus": "_onCartPlus",
        "click .gl-cart-minus": "_onCartMinus",
        "click .gl-cart-drop": "_onCartDrop",
        "click #gelatoContinue": "_onContinue",
        "click #gelatoDrawerClose": "_onDrawerClose",
        "click #gelatoDrawerBackdrop": "_onDrawerClose",
        "click #gelatoDrawerContinue": "_onDrawerContinue",
        "click #gelatoPromoBtn": "_onPromoClick",
        "input #gelatoPromo": "_onPromoInput",
        // Event first, then the selector - Odoo splits on the first
        // space, so this is "input" on "input, textarea".
        "input input, textarea": "_onFieldInput",
        "change input, textarea": "_onFieldInput",
        "blur #gelatoAddress": "_onAddressBlur",
        "blur #gelatoPostcode": "_onAddressBlur",
        "submit": "_onSubmit",
    },

    start() {
        this.cart = [];
        this.nextUid = 1;
        this.draft = null;
        this.flavorQty = {};
        this.submitting = false;
        this.zoneFee = null;
        this.zoneFreeFrom = null;
        this._forgetPromo();

        const config = document.getElementById("gelatoConfig");
        this.deliveryFee = config ? parseFloat(config.dataset.fee || "0") : 0;
        this.freeFrom = config ? parseFloat(config.dataset.freeFrom || "0") : 0;
        this.feeBase = config ? config.dataset.feeBase || "before_discount" : "before_discount";

        // Escape closes whatever is open, the way every other dialog does.
        this._onKeyDown = (ev) => {
            if (ev.key !== "Escape") {
                return;
            }
            if (this.draft) {
                this._closePanel();
            } else {
                this._closeDrawer();
            }
        };
        document.addEventListener("keydown", this._onKeyDown);

        // The confirmation screen is a sibling of this widget, not a child
        // of it, so the delegated handlers never reach the button on it.
        this._doneButton = document.getElementById("gelatoDone");
        if (this._doneButton) {
            this._onDoneClick = () => this._onDone();
            this._doneButton.addEventListener("click", this._onDoneClick);
        }
        this._placeCartInHeader();
        this._watchSliders();
        // Whatever was in the basket when the page was last closed.
        this._loadCart();
        // ...and what was typed into the form last time.
        this._loadForm();

        this._renderCart();
        this._recompute();
        return this._super(...arguments);
    },

    destroy() {
        document.removeEventListener("keydown", this._onKeyDown);
        // The baskets were moved into the header, which is not ours to
        // leave things in.
        for (const bar of this.cartBars || []) {
            const button = bar.querySelector(".gl-cartbtn");
            if (button) {
                button.removeEventListener("click", this._onCartButtonClick);
            }
            bar.remove();
        }
        if (this._doneButton) {
            this._doneButton.removeEventListener("click", this._onDoneClick);
        }
        return this._super(...arguments);
    },

    /**
     * Drop the "Swipe" hint off a row once it has been swiped.
     *
     * It is there to say the row keeps going sideways. Somebody who has
     * already moved it knows, and the hint sitting in the heading from
     * then on is just clutter. A row short enough to fit loses the hint
     * straight away - there is nothing to swipe.
     */
    _watchSliders() {
        for (const slider of this.el.querySelectorAll(".gl-slider")) {
            const label = slider.previousElementSibling;
            const hint = label && label.querySelector(".gl-swipe");
            if (!hint) {
                continue;
            }
            if (slider.scrollWidth <= slider.clientWidth + 4) {
                hint.classList.add("gl-swipe-done");
                continue;
            }
            slider.addEventListener(
                "scroll",
                () => hint.classList.add("gl-swipe-done"),
                { once: true, passive: true }
            );
        }
    },

    // ------------------------------------------------------------------
    // The product cards
    // ------------------------------------------------------------------
    /**
     * A box or a bundle holds gelato, so it opens the panel and asks what
     * goes in it. A bottle does not - one tap and it is in the basket.
     */
    _onCardClick(ev) {
        const card = ev.currentTarget;
        const parts = parseInt(card.dataset.parts || "0", 10);
        const product = {
            kind: card.dataset.kind,
            id: parseInt(card.dataset.id, 10),
            name: card.dataset.name || "",
            price: parseFloat(card.dataset.price || "0"),
            parts: parts,
        };
        if (!parts) {
            // A bottle needs nothing filling in, so it goes straight in -
            // but it still flies to the basket like everything else, or
            // the tap would look like it did nothing at all.
            this._addToCart({ ...product, quantity: 1, flavors: {} });
            this._flyToCart(card, () => this._bumpCart());
            return;
        }
        this._openPanel(product, card);
    },

    // ------------------------------------------------------------------
    // Filling a box
    // ------------------------------------------------------------------
    /**
     * The card opens into its own screen: the picture large at the top and
     * the flavours underneath. Tapping a small card and having a box appear
     * somewhere further down the page read as nothing happening.
     */
    _openPanel(product, card) {
        this.draft = product;
        this.flavorQty = {};
        this.sourceCard = card;

        const panel = this.el.querySelector("#gelatoPanel");
        if (!panel) {
            return;
        }
        this._setText("gelatoPanelName", product.name);
        this._setText("gelatoPanelPrice", `${this._money(product.price)} Kč`);

        // What this one is, in full - the card clips the same line.
        const note = this.el.querySelector("#gelatoPanelNote");
        if (note) {
            note.textContent = card.dataset.note || "";
            note.hidden = !note.textContent;
        }

        // The picture is the one already on the card, badge left behind.
        const photo = this.el.querySelector("#gelatoPanelPhoto");
        const source = card.querySelector(".gl-card-photo");
        if (photo && source) {
            photo.innerHTML = source.innerHTML;
            const tag = photo.querySelector(".gl-card-tag");
            if (tag) {
                tag.remove();
            }
        }

        panel.hidden = false;
        this._renderQty();
        this._syncPartsHint();
        const dialog = panel.querySelector(".gl-panel-card");
        if (dialog) {
            dialog.scrollTop = 0;
        }
        this._zoomFrom(card);
    },

    /**
     * Where the panel sits against the thing it flies to or from.
     *
     * Both directions need the same measurements, so they are worked out
     * in one place: how much smaller the target is than the open panel
     * and how far its middle sits from the panel's middle. On the way in
     * that target is the card that was tapped; on the way out it can be
     * the basket instead.
     */
    _cardGeometry(target) {
        const panel = this.el.querySelector("#gelatoPanel");
        const dialog = panel && panel.querySelector(".gl-panel-card");
        if (!dialog || !target || !target.isConnected || this._reducedMotion()) {
            return null;
        }
        const from = target.getBoundingClientRect();
        const to = dialog.getBoundingClientRect();
        if (!to.width || !to.height || !from.width || !from.height) {
            return null;
        }
        const shift =
            "translate(" +
            (from.left + from.width / 2 - (to.left + to.width / 2)) + "px, " +
            (from.top + from.height / 2 - (to.top + to.height / 2)) + "px)";
        return {
            dialog: dialog,
            backdrop: panel.querySelector(".gl-panel-backdrop"),
            // Just the journey, with no resizing - the closing animation
            // shrinks on its own schedule and needs the two apart.
            shift: shift,
            // Written out as one transform so the browser interpolates it
            // in a single step; translate then scale keeps the target's
            // middle on the panel's middle the whole way.
            shrunk:
                shift + " scale(" +
                from.width / to.width + ", " + from.height / to.height + ")",
        };
    },

    /**
     * Grow the opened product out of the card that was tapped.
     *
     * The panel is measured where it will end up and then played
     * backwards from the card's own place and size, so the two read as
     * one object rather than a box appearing out of nowhere. It is slow
     * enough to be followed and eases into place rather than stopping
     * dead, so it reads as being pulled open rather than switched on.
     */
    _zoomFrom(card) {
        const g = this._cardGeometry(card);
        if (!g) {
            return;
        }
        g.dialog.animate(
            [
                { transform: g.shrunk, opacity: 0.55, borderRadius: "16px", offset: 0 },
                { opacity: 1, offset: 0.45 },
                { transform: "none", opacity: 1, borderRadius: "18px", offset: 1 },
            ],
            { duration: 520, easing: "cubic-bezier(.25,.7,.3,1)" }
        );
        if (g.backdrop) {
            g.backdrop.animate([{ opacity: 0 }, { opacity: 1 }], {
                duration: 380,
                easing: "ease-out",
            });
        }
    },

    _reducedMotion() {
        return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    },

    _onPanelClose() {
        this._closePanel();
    },

    /** A tap on the dark area around the card closes it too. */
    _onPanelBackdrop(ev) {
        if (ev.target === ev.currentTarget) {
            this._closePanel();
        }
    },

    /**
     * Fold the panel down into wherever the product just went.
     *
     * Closed without ordering, it goes back to the card it came from -
     * nothing happened, so nothing moved. Ordered, it flies into the
     * basket in the header instead, because that is where the box now
     * is. Telling those two apart is the whole point of the animation.
     *
     * It has to stay solid nearly the whole way. An earlier version faded
     * it out as it travelled, and because opacity falls faster than the
     * eye follows movement, the panel read as vanishing on the spot
     * rather than going anywhere. Now it keeps its colour until the last
     * third, by which point it is small and sitting over its target, and
     * only then lets go.
     */
    _closePanel(afterClose, target) {
        this.draft = null;
        this.flavorQty = {};
        const panel = this.el.querySelector("#gelatoPanel");
        if (!panel || panel.hidden) {
            return;
        }
        let closed = false;
        const finish = () => {
            if (closed) {
                return;
            }
            closed = true;
            panel.hidden = true;
            this.sourceCard = null;
            if (afterClose) {
                afterClose();
            }
        };

        const g = this._cardGeometry(target || this.sourceCard);
        if (!g) {
            // Nowhere to fly to, or animations turned off: just close.
            finish();
            return;
        }

        if (g.backdrop) {
            // The dark holds while the panel is still big enough to be
            // worth hiding the page behind, and lifts as it lands.
            g.backdrop.animate(
                [
                    { opacity: 1, offset: 0 },
                    { opacity: 1, offset: 0.45 },
                    { opacity: 0, offset: 1 },
                ],
                { duration: target ? 640 : 520, easing: "ease-in", fill: "forwards" }
            );
        }
        // Going to the basket is two moves, not one. The panel first
        // draws itself in where it stands, down to a bit under half, and
        // only then sets off. Straight from full size towards the corner
        // made the whole screen lurch sideways, because at that size the
        // travel is the only thing the eye can follow. Shrinking first
        // turns it into an object small enough to watch being carried,
        // and it keeps shrinking on the way until there is nothing left
        // of it but the basket.
        //
        // Going back to its card is one move: it folds down onto
        // something its own sort of size, so there is nothing to carry
        // and no reason to pass through the middle first.
        const kroky = target
            ? [
                {
                    transform: "none",
                    opacity: 1,
                    borderRadius: "18px",
                    offset: 0,
                    easing: "cubic-bezier(.4,0,.6,1)",
                },
                {
                    // Still in the middle of the screen, just smaller.
                    transform: "scale(.4)",
                    opacity: 1,
                    borderRadius: "16px",
                    offset: 0.4,
                    easing: "cubic-bezier(.35,0,.25,1)",
                },
                { opacity: 1, offset: 0.85 },
                {
                    transform: `${g.shift} scale(.05)`,
                    opacity: 0,
                    borderRadius: "14px",
                    offset: 1,
                },
            ]
            : [
                { transform: "none", opacity: 1, borderRadius: "18px", offset: 0 },
                { opacity: 1, offset: 0.62 },
                { transform: g.shrunk, opacity: 0, borderRadius: "16px", offset: 1 },
            ];
        const closing = g.dialog.animate(kroky, {
            duration: target ? 640 : 520,
            easing: target ? "linear" : "cubic-bezier(.3,.05,.25,1)",
        });
        closing.onfinish = finish;
        closing.oncancel = finish;
        // A timeline that never advances - a background tab, a browser
        // that skips animations - must not leave the overlay stuck open.
        setTimeout(finish, 820);
    },

    _handedOut() {
        return Object.values(this.flavorQty).reduce((sum, q) => sum + q, 0);
    },

    _flavorName(id) {
        const option = this.el.querySelector(`.gl-opt[data-flavor-id="${id}"]`);
        return option ? option.dataset.flavorName : "";
    },

    _setFlavorQty(id, amount) {
        if (amount > 0) {
            this.flavorQty[id] = amount;
        } else {
            delete this.flavorQty[id];
        }
    },

    /**
     * Write the counts back onto the list itself.
     *
     * There is nowhere else to look. A flavour that is in the box says how
     * many and carries its own plus and minus, so the box gets filled
     * without ever leaving the list - which is the whole point, because
     * the list is long and scrolling back to it after every pick was the
     * worst part of ordering.
     */
    _renderQty() {
        const left = this.draft ? this.draft.parts - this._handedOut() : 0;
        for (const row of this.el.querySelectorAll(".gl-opt-row")) {
            const counter = row.querySelector(".gl-opt-qty");
            if (!counter) {
                continue;
            }
            const quantity = this.flavorQty[row.dataset.flavorId] || 0;
            row.classList.toggle("gl-opt-taken", quantity > 0);
            counter.hidden = quantity === 0;
            counter.querySelector(".gl-qty-value").textContent = quantity;
            // A full box takes no more of anything. Saying so on the
            // buttons beats letting them be pressed and do nothing.
            counter.querySelector(".gl-row-plus").disabled = left <= 0;
            row.querySelector(".gl-opt").disabled = left <= 0 && quantity === 0;
        }
    },

    _onPickFlavor(ev) {
        const id = ev.currentTarget.dataset.flavorId;
        if (!this.draft || this._handedOut() >= this.draft.parts) {
            return;
        }
        this._setFlavorQty(id, (this.flavorQty[id] || 0) + 1);
        this._renderQty();
        this._syncPartsHint();
    },

    _onRowPlus(ev) {
        const id = ev.currentTarget.closest(".gl-opt-row").dataset.flavorId;
        if (!this.draft || this._handedOut() >= this.draft.parts) {
            return;
        }
        this._setFlavorQty(id, (this.flavorQty[id] || 0) + 1);
        this._renderQty();
        this._syncPartsHint();
    },

    _onRowMinus(ev) {
        const id = ev.currentTarget.closest(".gl-opt-row").dataset.flavorId;
        this._setFlavorQty(id, (this.flavorQty[id] || 0) - 1);
        this._renderQty();
        this._syncPartsHint();
    },

    /** Tell the customer how much of the box is still unspoken for. */
    _syncPartsHint() {
        const hint = this.el.querySelector("#gelatoPartsHint");
        if (!hint || !this.draft) {
            return;
        }
        const parts = this.draft.parts;
        const left = parts - this._handedOut();

        if (left > 0) {
            hint.textContent = _t("%(left)s of %(parts)s still to hand out.", {
                left: left,
                parts: parts,
            });
            hint.classList.add("gl-rz-hint-warn");
        } else {
            hint.textContent = _t("The box is full.");
            hint.classList.remove("gl-rz-hint-warn");
        }

        const confirm = this.el.querySelector("#gelatoAddToCart");
        if (confirm) {
            confirm.disabled = left !== 0;
        }
    },

    _onAddToCart() {
        if (!this.draft || this._handedOut() !== this.draft.parts) {
            return;
        }
        this._addToCart({
            ...this.draft,
            quantity: 1,
            flavors: { ...this.flavorQty },
        });
        // Into the basket, not back to the shelf.
        const basket = this._cartButton();
        this._closePanel(() => this._bumpCart(), basket);
    },

    // ------------------------------------------------------------------
    // The basket
    // ------------------------------------------------------------------
    /** The same product with the same flavours is one line with a count. */
    _cartKey(entry) {
        const flavors = Object.entries(entry.flavors)
            .map(([id, q]) => `${id}:${q}`)
            .sort()
            .join(",");
        return `${entry.kind}-${entry.id}-${flavors}`;
    },

    _addToCart(entry) {
        const key = this._cartKey(entry);
        const existing = this.cart.find((line) => this._cartKey(line) === key);
        if (existing) {
            existing.quantity += entry.quantity;
        } else {
            this.cart.push({ ...entry, uid: this.nextUid++ });
        }
        this._renderCart();
        this._recompute();
    },

    _cartLine(ev) {
        const uid = parseInt(ev.currentTarget.closest(".gl-cart-line").dataset.uid, 10);
        return this.cart.find((line) => line.uid === uid);
    },

    _onCartPlus(ev) {
        const line = this._cartLine(ev);
        if (line) {
            line.quantity += 1;
            this._renderCart();
            this._recompute();
        }
    },

    _onCartMinus(ev) {
        const line = this._cartLine(ev);
        if (!line) {
            return;
        }
        line.quantity -= 1;
        if (line.quantity <= 0) {
            this.cart = this.cart.filter((other) => other !== line);
        }
        this._renderCart();
        this._recompute();
    },

    _onCartDrop(ev) {
        const line = this._cartLine(ev);
        this.cart = this.cart.filter((other) => other !== line);
        this._renderCart();
        this._recompute();
    },

    _flavorSummary(line) {
        return Object.entries(line.flavors)
            .map(([id, q]) => (q > 1 ? `${q}× ${this._flavorName(id)}` : this._flavorName(id)))
            .join(", ");
    },

    /**
     * Put back what was typed last time.
     *
     * The promo code is deliberately not among them: it has to be
     * checked against the server to mean anything, and a code sitting in
     * the box with no discount behind it reads as if it had been
     * accepted.
     */
    _loadForm() {
        let raw = null;
        try {
            raw = window.localStorage.getItem(FORM_KEY);
        } catch (error) {
            return;
        }
        if (!raw) {
            return;
        }
        let stored = null;
        try {
            stored = JSON.parse(raw);
        } catch (error) {
            this._forgetForm();
            return;
        }
        if (!stored || typeof stored !== "object") {
            this._forgetForm();
            return;
        }
        for (const id of FORM_FIELDS) {
            const field = this.el.querySelector(`#${id}`);
            if (field && typeof stored[id] === "string") {
                field.value = stored[id];
            }
        }
    },

    /** Write down what is in the form now. */
    _saveForm() {
        const values = {};
        for (const id of FORM_FIELDS) {
            const field = this.el.querySelector(`#${id}`);
            if (field) {
                values[id] = field.value;
            }
        }
        try {
            window.localStorage.setItem(FORM_KEY, JSON.stringify(values));
        } catch (error) {
            // Full or blocked storage is not worth an error on screen.
        }
    },

    _forgetForm() {
        try {
            window.localStorage.removeItem(FORM_KEY);
        } catch (error) {
            // Nothing to do about it.
        }
    },

    /** Anything typed into the contact details is worth keeping. */
    _onFieldInput(ev) {
        if (FORM_FIELDS.includes(ev.target.id)) {
            this._saveForm();
        }
    },

    // ------------------------------------------------------------------
    // Keeping the basket across a reload
    // ------------------------------------------------------------------
    /**
     * Read back the basket from the last visit.
     *
     * Every line is checked against what is actually on the page today:
     * a box that has been taken off the site, or a flavour that is not
     * being made any more, is dropped rather than carried along, and the
     * name and price are taken from the card rather than from what was
     * stored - the shop may have changed them since. Nothing here is
     * trusted for money anyway; the server prices the order again.
     */
    _loadCart() {
        let raw = null;
        try {
            raw = window.localStorage.getItem(CART_KEY);
        } catch (error) {
            // Private window, storage switched off - the basket simply
            // does not survive a reload, which is no reason to break.
            return;
        }
        if (!raw) {
            return;
        }
        let stored = null;
        try {
            stored = JSON.parse(raw);
        } catch (error) {
            this._forgetCart();
            return;
        }
        if (!Array.isArray(stored)) {
            this._forgetCart();
            return;
        }
        for (const line of stored) {
            const card = this.el.querySelector(
                `.gl-card[data-kind="${line.kind}"][data-id="${line.id}"]`
            );
            if (!card) {
                continue;
            }
            const flavors = {};
            for (const [id, qty] of Object.entries(line.flavors || {})) {
                if (this.el.querySelector(`.gl-opt[data-flavor-id="${id}"]`)) {
                    flavors[id] = qty;
                }
            }
            const parts = parseInt(card.dataset.parts || "0", 10);
            // A box that came back half filled is no use - it cannot be
            // ordered and cannot be topped up from the basket.
            const handed = Object.values(flavors).reduce((s, q) => s + q, 0);
            if (parts && handed !== parts) {
                continue;
            }
            this.cart.push({
                kind: line.kind,
                id: line.id,
                name: card.dataset.name || "",
                price: parseFloat(card.dataset.price || "0"),
                parts: parts,
                quantity: Math.max(1, parseInt(line.quantity, 10) || 1),
                flavors: flavors,
                uid: this.nextUid++,
            });
        }
    },

    /** Write the basket down after every change to it. */
    _saveCart() {
        try {
            window.localStorage.setItem(
                CART_KEY,
                JSON.stringify(
                    this.cart.map((line) => ({
                        kind: line.kind,
                        id: line.id,
                        quantity: line.quantity,
                        flavors: line.flavors,
                    }))
                )
            );
        } catch (error) {
            // Full or blocked storage is not worth an error on screen.
        }
    },

    _forgetCart() {
        try {
            window.localStorage.removeItem(CART_KEY);
        } catch (error) {
            // Nothing to do about it.
        }
    },

    /**
     * One row of the basket.
     *
     * Built fresh for each list that shows it - the same node cannot hang
     * in two places at once, and the basket is now on the page twice: at
     * the bottom where the order is finished, and in the drawer that the
     * button in the header band opens.
     */
    _cartRow(line) {
        const row = document.createElement("div");
        row.className = "gl-cart-line";
        row.dataset.uid = line.uid;

        const body = document.createElement("span");
        body.className = "gl-cart-body";
        const name = document.createElement("span");
        name.className = "gl-cart-name";
        name.textContent = line.name;
        body.append(name);
        const flavors = this._flavorSummary(line);
        if (flavors) {
            const sub = document.createElement("span");
            sub.className = "gl-cart-sub";
            sub.textContent = flavors;
            body.append(sub);
        }

        const qty = document.createElement("span");
        qty.className = "gl-qty";
        qty.innerHTML =
            '<button type="button" class="gl-qty-btn gl-cart-minus">−</button>' +
            '<span class="gl-qty-value"></span>' +
            '<button type="button" class="gl-qty-btn gl-cart-plus">+</button>';
        qty.querySelector(".gl-qty-value").textContent = line.quantity;

        const price = document.createElement("span");
        price.className = "gl-cart-price";
        price.textContent = `${this._money(line.price * line.quantity)} Kč`;

        const drop = document.createElement("button");
        drop.type = "button";
        drop.className = "gl-cart-drop";
        drop.setAttribute("aria-label", _t("Remove"));
        drop.textContent = "×";

        row.append(body, qty, price, drop);
        return row;
    },

    /**
     * The same figure wherever it is shown.
     *
     * Across the document, not just this widget: the basket lives up in
     * the header now, outside it.
     */
    _setTextAll(selector, text) {
        for (const node of document.querySelectorAll(selector)) {
            node.textContent = text;
        }
    },

    _renderCart() {
        // Every change to the basket comes through here, so this is the
        // one place it needs writing down.
        this._saveCart();
        for (const box of this.el.querySelectorAll(".gl-cart-list")) {
            box.innerHTML = "";
            for (const line of this.cart) {
                box.append(this._cartRow(line));
            }
        }

        // The list at the bottom is a long way down, so the bare total
        // needs saying how many things it covers.
        const things = this.cart.reduce((sum, line) => sum + line.quantity, 0);
        let count = "";
        if (things === 1) {
            count = _t("1 item ·");
        } else if (things < 5) {
            count = _t("%s items ·", things);
        } else if (things) {
            count = _t("%s items in total ·", things);
        }
        this._setTextAll(".js-cart-count", count);
        this._setTextAll(".js-cart-things", things);

        const filled = this.cart.length > 0;
        const empty = this.el.querySelector("#gelatoCartEmpty");
        if (empty) {
            empty.hidden = filled;
        }
        const foot = this.el.querySelector("#gelatoCartFoot");
        if (foot) {
            foot.hidden = !filled;
        }
        // The button in the header stays put whether anything is in it or
        // not - it is where the order lives, and saying so before there is
        // one is the point. Only the count comes and goes.
        for (const badge of document.querySelectorAll(".gl-cartbtn-count")) {
            badge.hidden = !things;
        }
        const drawerEmpty = this.el.querySelector("#gelatoDrawerEmpty");
        if (drawerEmpty) {
            drawerEmpty.hidden = filled;
        }
        const onwards = this.el.querySelector("#gelatoDrawerContinue");
        if (onwards) {
            onwards.disabled = !filled;
        }
        if (!filled) {
            const checkout = this.el.querySelector("#gelatoCheckout");
            if (checkout) {
                checkout.hidden = true;
            }
        }
    },

    // ------------------------------------------------------------------
    // The basket drawer
    // ------------------------------------------------------------------

    /**
     * Move the basket up into the header.
     *
     * The first version left it in the page and copied the header's
     * position onto it on every scroll frame. That can only ever be a
     * chase: the header slides under a CSS transition, the copy is made
     * a frame later, and the button visibly jitters behind it. The
     * slide-out menu needed watching too, so the button could be faded
     * out of its way in time.
     *
     * Being a real child of the header settles all of it at once. It
     * slides when the header slides, it is covered when the menu covers
     * the header, it sits in the row with the search and the burger at
     * every width, and none of that costs a line of script.
     *
     * This theme carries two headers, one for wide screens and one for
     * phones, and hides whichever does not apply. The basket therefore
     * goes in both; the stylesheet hides the one in the header that is
     * hidden anyway, and the counts are written to every copy. With no
     * header at all it stays a floating button in the corner.
     */
    _placeCartInHeader() {
        const source = this.el.querySelector(".gl-cartbar");
        if (!source) {
            return;
        }
        const header = document.querySelector("header");
        const groups = header
            ? [
                  // The row of buttons a phone header keeps on the right.
                  ...header.querySelectorAll(".o_header_mobile_buttons_wrap"),
                  // ...and the same on a wide one.
                  ...header.querySelectorAll("ul.navbar-nav.flex-shrink-0"),
              ]
            : [];
        this.cartBars = [];
        if (!groups.length) {
            source.classList.add("gl-cartbar-loose");
            this.cartBars.push(source);
        } else {
            groups.forEach((group, i) => {
                const bar = i === 0 ? source : source.cloneNode(true);
                group.prepend(bar);
                this.cartBars.push(bar);
            });
        }

        // They have left the widget, so the delegated click no longer
        // reaches them and each has to be tied on by hand.
        this._onCartButtonClick = () => this._onCartBtn();
        for (const bar of this.cartBars) {
            const button = bar.querySelector(".gl-cartbtn");
            if (button) {
                button.addEventListener("click", this._onCartButtonClick);
            }
        }
    },

    /** The copy the customer can actually see right now. */
    _cartButton() {
        for (const bar of this.cartBars || []) {
            const button = bar.querySelector(".gl-cartbtn");
            if (button && button.getBoundingClientRect().width > 0) {
                return button;
            }
        }
        return null;
    },

    /**
     * Send a copy of the card itself up into the basket.
     *
     * A box goes there as the open panel, which the customer is already
     * looking at. A bottle has no panel - one tap and it is in - so
     * there would be nothing to watch at all. A copy of the card makes
     * the same journey instead: shrinks where it stands, then travels
     * and thins out into the basket. Same two moves, same reason.
     *
     * It is a copy because the real card has to stay on the shelf; there
     * is more than one bottle to be had.
     */
    _flyToCart(source, done) {
        const basket = this._cartButton();
        const land = () => {
            if (done) {
                done();
            }
        };
        if (!source || !basket || this._reducedMotion()) {
            land();
            return;
        }
        const from = source.getBoundingClientRect();
        const to = basket.getBoundingClientRect();
        if (!from.width || !from.height || !to.width) {
            land();
            return;
        }

        const ghost = source.cloneNode(true);
        ghost.classList.add("gl-flyer");
        ghost.removeAttribute("id");
        ghost.setAttribute("aria-hidden", "true");
        ghost.style.left = `${from.left}px`;
        ghost.style.top = `${from.top}px`;
        ghost.style.width = `${from.width}px`;
        ghost.style.height = `${from.height}px`;
        // Inside the widget rather than on the body, so it keeps the
        // card styling that hangs off .gl-page.
        this.el.append(ghost);

        const dx = to.left + to.width / 2 - (from.left + from.width / 2);
        const dy = to.top + to.height / 2 - (from.top + from.height / 2);

        let gone = false;
        const clear = () => {
            if (gone) {
                return;
            }
            gone = true;
            ghost.remove();
            land();
        };
        const flight = ghost.animate(
            [
                {
                    transform: "none",
                    opacity: 1,
                    offset: 0,
                    easing: "cubic-bezier(.4,0,.6,1)",
                },
                {
                    transform: "scale(.4)",
                    opacity: 1,
                    offset: 0.4,
                    easing: "cubic-bezier(.35,0,.25,1)",
                },
                { opacity: 1, offset: 0.85 },
                {
                    transform: `translate(${dx}px, ${dy}px) scale(.05)`,
                    opacity: 0,
                    offset: 1,
                },
            ],
            { duration: 640 }
        );
        flight.onfinish = clear;
        flight.oncancel = clear;
        // A timeline that never advances must not leave a copy of a card
        // sitting on the page.
        setTimeout(clear, 820);
    },

    /**
     * A nudge on the basket when something lands in it.
     *
     * The panel flies there and disappears; without the basket reacting,
     * the last thing the eye sees is something vanishing rather than
     * something arriving.
     */
    _bumpCart() {
        const btn = this._cartButton();
        if (!btn) {
            return;
        }
        // Restart the animation even when one is still running, so two
        // things ordered quickly nudge it twice.
        btn.classList.remove("gl-cartbtn-bump");
        void btn.offsetWidth;
        btn.classList.add("gl-cartbtn-bump");
    },

    _onCartBtn() {
        const drawer = this.el.querySelector("#gelatoCartDrawer");
        if (drawer) {
            drawer.hidden = false;
        }
    },

    _closeDrawer() {
        const drawer = this.el.querySelector("#gelatoCartDrawer");
        if (drawer) {
            drawer.hidden = true;
        }
    },

    _onDrawerClose() {
        this._closeDrawer();
    },

    /** Straight from the drawer into filling in the address. */
    _onDrawerContinue() {
        this._closeDrawer();
        this._onContinue();
    },

    /**
     * Put the finished order away.
     *
     * The confirmation makes the same journey everything else makes:
     * draws itself in, flies up to the basket, and as it lands the count
     * falls away and the basket gives one last nudge. That is the order
     * being filed rather than a screen being dismissed - and it leaves
     * the basket visibly empty, which is the truth of it.
     *
     * Nothing reloads. The page is simply itself again, with the
     * products back and an empty basket, which is where anybody who
     * wants to order a second time would want to be anyway.
     */
    _onDone() {
        const done = document.getElementById("gelatoRozvozDone");
        if (!done || this.restarting) {
            this._reopenOrdering();
            return;
        }
        this.restarting = true;
        this._flyToCart(done, () => {
            // Emptied as it lands, so the count goes with it.
            this.cart = [];
            this._renderCart();
            this._recompute();
            this._bumpCart();
            this._reopenOrdering();
        });
        // The copy is already in flight; the original would otherwise sit
        // there while it goes.
        done.hidden = true;
    },

    /** The ordering side of the page, back the way it was. */
    _reopenOrdering() {
        this.restarting = false;
        this.el.classList.remove("gl-ordered");
        const done = document.getElementById("gelatoRozvozDone");
        if (done) {
            done.hidden = true;
        }
        const head = document.querySelector("#objednavka .gl-rz-head");
        if (head) {
            head.hidden = false;
        }
    },

    _onContinue() {
        if (!this.cart.length) {
            return;
        }
        const checkout = this.el.querySelector("#gelatoCheckout");
        if (checkout) {
            checkout.hidden = false;
            checkout.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    },

    // ------------------------------------------------------------------
    // Address
    // ------------------------------------------------------------------
    /**
     * The address decides both whether we drive there and what the delivery
     * costs, so it is worth answering while the customer is still on the
     * field rather than at the end.
     */
    async _onAddressBlur() {
        const input = this.el.querySelector("#gelatoAddress");
        const hint = this.el.querySelector("#gelatoAddressHint");
        if (!input || !hint) {
            return;
        }
        const address = input.value.trim();
        if (!address) {
            hint.textContent = "";
            hint.classList.remove("gl-rz-hint-warn");
            this.zoneFee = null;
            this.zoneFreeFrom = null;
            this._recompute();
            return;
        }
        const postcode = this.el.querySelector("#gelatoPostcode");
        hint.textContent = _t("Looking the address up on the map...");
        hint.classList.remove("gl-rz-hint-warn");
        try {
            const result = await rpc("/rozvoz/overit-adresu", {
                address: address,
                postcode: postcode ? postcode.value.trim() : "",
            });
            hint.textContent = result.message || "";
            hint.classList.toggle("gl-rz-hint-warn", !result.valid || !!result.unsure);
            this.zoneFee = typeof result.fee === "number" ? result.fee : null;
            // A zone can have its own free-from figure; without it the
            // preview would keep using the one from the settings.
            this.zoneFreeFrom =
                typeof result.free_from === "number" ? result.free_from : null;
            this._recompute();
        } catch {
            // the server checks it again on submit, so staying quiet is safe
            hint.textContent = "";
            hint.classList.remove("gl-rz-hint-warn");
            this.zoneFee = null;
            this.zoneFreeFrom = null;
            this._recompute();
        }
    },

    // ------------------------------------------------------------------
    // Promo code
    // ------------------------------------------------------------------
    _onPromoInput() {
        // Editing the code drops the discount until it is checked again.
        if (this.discountPercent) {
            this._forgetPromo();
            this._recompute();
        }
    },

    _forgetPromo() {
        this.discountPercent = 0;
        this.promoCode = "";
        this.promoScope = "all";
        this.promoBoxIds = [];
        this.promoAddonIds = [];
    },

    async _onPromoClick() {
        const input = this.el.querySelector("#gelatoPromo");
        const hint = this.el.querySelector("#gelatoPromoHint");
        const code = input ? input.value.trim() : "";
        if (!code) {
            return;
        }
        try {
            const result = await rpc("/rozvoz/overit-kod", { code: code });
            hint.textContent = result.message || "";
            hint.classList.toggle("gl-rz-hint-warn", !result.valid);
            if (result.valid) {
                this.discountPercent = result.discount_percent;
                this.promoCode = result.code;
                this.promoScope = result.scope || "all";
                this.promoBoxIds = result.box_ids || [];
                this.promoAddonIds = result.addon_ids || [];
            } else {
                this._forgetPromo();
            }
        } catch {
            hint.textContent = _t("We could not check the code. Try again.");
            hint.classList.add("gl-rz-hint-warn");
            this._forgetPromo();
        }
        this._recompute();
    },

    // ------------------------------------------------------------------
    // Price preview
    // ------------------------------------------------------------------
    _subtotal() {
        return this.cart.reduce((sum, line) => sum + line.price * line.quantity, 0);
    },

    /** Does the code that was entered come off this basket line? */
    _promoCovers(line) {
        if (this.promoScope === "all") {
            return true;
        }
        if (this.promoScope !== "products") {
            return false;
        }
        const ids = line.kind === "box" ? this.promoBoxIds : this.promoAddonIds;
        return (ids || []).includes(line.id);
    },

    _recompute() {
        const subtotal = this._subtotal();
        // The same order of operations as the controller: what the code
        // covers comes off the goods first, the fee is worked out on
        // that, and only a code aimed at the drive touches the fee.
        const percent = this.discountPercent / 100;
        let discount = this.cart
            .filter((line) => this._promoCovers(line))
            .reduce((sum, line) => sum + line.price * line.quantity, 0) * percent;
        const afterDiscount = subtotal - discount;

        // Same rule as on the server: the zone's own fee wins once the
        // address has landed in one, and the free delivery threshold is
        // compared before or after the discount depending on the setting.
        const fee = this.zoneFee === null ? this.deliveryFee : this.zoneFee;
        // The zone brings its own free-from figure once the address has
        // landed in one; before that the one from the settings applies.
        const freeFrom =
            this.zoneFreeFrom === null ? this.freeFrom : this.zoneFreeFrom;
        let shipping = fee;
        if (!fee) {
            shipping = 0;
        } else if (freeFrom) {
            const base = this.feeBase === "after_discount" ? afterDiscount : subtotal;
            shipping = base >= freeFrom ? 0 : fee;
        }
        if (this.promoScope === "delivery") {
            discount = shipping * percent;
        }

        this._setTextAll(".js-cart-total", this._money(subtotal));
        this._setText("gelatoSubtotal", this._money(subtotal));
        this._setText("gelatoDiscount", this._money(discount));
        this._setText("gelatoShipping", this._money(shipping));
        // Not afterDiscount + shipping: a code for the drive changes the
        // discount only once the fee above is known.
        this._setText("gelatoTotal", this._money(subtotal - discount + shipping));

        const discountRow = this.el.querySelector("#gelatoDiscountRow");
        if (discountRow) {
            discountRow.hidden = discount <= 0;
        }
    },

    _money(value) {
        return Math.round(value).toLocaleString("cs-CZ");
    },

    _setText(id, text) {
        const node = this.el.querySelector(`#${id}`);
        if (node) {
            node.textContent = text;
        }
    },

    // ------------------------------------------------------------------
    // Sending it
    // ------------------------------------------------------------------
    _value(id) {
        const node = this.el.querySelector(`#${id}`);
        return node ? node.value.trim() : "";
    },

    _setSubmitting(on) {
        this.submitting = on;
        const button = this.el.querySelector("#gelatoSubmit");
        if (button) {
            button.disabled = on;
        }
    },

    _showError(message) {
        const box = this.el.querySelector("#gelatoFormError");
        if (!box) {
            return;
        }
        box.textContent = message;
        box.hidden = false;
        box.scrollIntoView({ behavior: "smooth", block: "center" });
    },

    _showSuccess(result) {
        // The order is in; the basket must not come back on the next
        // visit. It stays in memory so "Done" can be seen emptying it,
        // but nothing written down survives this point.
        this._forgetCart();
        // The note was about this delivery, not the next one, so it is
        // not kept; the name, the phone number and the address are.
        const note = this.el.querySelector("#gelatoNote");
        if (note) {
            note.value = "";
            this._saveForm();
        }
        // Everything to do with ordering goes, but the basket up in the
        // header stays put: the order is still counted in it, and
        // emptying it is what "Done" is about to show.
        this.el.classList.add("gl-ordered");
        // "Put together your box" over a finished order reads as if
        // something still wants doing.
        const head = document.querySelector("#objednavka .gl-rz-head");
        if (head) {
            head.hidden = true;
        }
        const done = document.getElementById("gelatoRozvozDone");
        const ref = document.getElementById("gelatoOrderRef");
        if (ref) {
            ref.textContent = result.order_ref || "";
        }
        if (done) {
            done.hidden = false;
            done.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    },

    _trackPurchase(tracking) {
        if (!tracking) {
            return;
        }
        if (typeof window.gelatoTrack === "function") {
            window.gelatoTrack("purchase", tracking);
        }
    },

    async _onSubmit(ev) {
        ev.preventDefault();
        if (this.submitting) {
            return;
        }
        const errorBox = this.el.querySelector("#gelatoFormError");
        if (errorBox) {
            errorBox.hidden = true;
        }
        if (!this.cart.length) {
            this._showError(_t("Your order is empty. Please pick something first."));
            return;
        }

        const payload = {
            customer_name: this._value("gelatoName"),
            customer_phone: this._value("gelatoPhone"),
            customer_email: this._value("gelatoEmail"),
            delivery_address: this._value("gelatoAddress"),
            delivery_postcode: this._value("gelatoPostcode"),
            delivery_city: this._value("gelatoCity"),
            note: this._value("gelatoNote"),
            items: this.cart.map((line) => ({
                kind: line.kind,
                id: line.id,
                quantity: line.quantity,
                flavors: Object.entries(line.flavors).map(([id, quantity]) => ({
                    id: parseInt(id, 10),
                    quantity: quantity,
                })),
            })),
            promo_code: this.promoCode || this._value("gelatoPromo"),
        };

        this._setSubmitting(true);
        try {
            const result = await rpc("/rozvoz/objednat", payload);
            if (result.success) {
                this._trackPurchase(result.tracking);
                this._showSuccess(result);
            } else {
                this._showError(result.error || _t("The order could not be sent."));
            }
        } catch {
            this._showError(
                _t(
                    "The order could not be sent. Please try again, or call " +
                        "us on +420 773 09 58 09."
                )
            );
        } finally {
            this._setSubmitting(false);
        }
    },
});

export default publicWidget.registry.GelatoRozvozForm;
