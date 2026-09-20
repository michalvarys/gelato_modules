/** @odoo-module **/

/**
 * window.gelatoTrack - the single place conversions are reported to.
 *
 * It never switches anything on by itself. It only sends where a filled in ID
 * leads:
 *
 *   - window.dataLayer only exists once Google Tag Manager has been added to
 *     the page, which happens only when a GTM ID is filled in.
 *   - window.fbq only exists once the Meta Pixel has been added, which happens
 *     only when a Pixel ID is filled in.
 *
 * When neither is filled in, both branches are skipped and the function does
 * nothing. That is why no extra on/off switch is needed anywhere.
 */

/**
 * Translate the order data into the shape GA4 understands.
 */
function toGa4Ecommerce(payload) {
    return {
        transaction_id: payload.transaction_id,
        value: payload.value,
        currency: payload.currency || "CZK",
        shipping: payload.shipping || 0,
        coupon: payload.coupon || undefined,
        items: (payload.items || []).map((item) => ({
            item_id: item.item_id,
            item_name: item.item_name,
            item_category: item.item_category,
            price: item.price,
            quantity: item.quantity,
        })),
    };
}

/**
 * Translate the order data into the shape the Meta Pixel understands.
 */
function toMetaPurchase(payload) {
    return {
        value: payload.value,
        currency: payload.currency || "CZK",
        content_type: "product",
        contents: (payload.items || []).map((item) => ({
            id: item.item_id,
            quantity: item.quantity,
            item_price: item.price,
        })),
        num_items: (payload.items || []).reduce(
            (sum, item) => sum + (item.quantity || 0),
            0
        ),
    };
}

function pushToDataLayer(eventName, payload) {
    if (!window.dataLayer) {
        return;
    }
    // GA4 wants ecommerce cleared before each event, otherwise the items from
    // the previous one leak into it.
    window.dataLayer.push({ ecommerce: null });
    window.dataLayer.push({
        event: eventName,
        ecommerce: toGa4Ecommerce(payload),
    });
}

function sendToMetaPixel(eventName, payload) {
    if (typeof window.fbq !== "function") {
        return;
    }
    if (eventName !== "purchase") {
        return;
    }
    // eventID = the order number. If server-side tracking (the Conversions
    // API) is added later, Meta matches the two reports and does not count
    // the purchase twice.
    window.fbq("track", "Purchase", toMetaPurchase(payload), {
        eventID: payload.transaction_id,
    });
}

window.gelatoTrack = function gelatoTrack(eventName, payload) {
    if (!eventName || !payload) {
        return;
    }
    try {
        pushToDataLayer(eventName, payload);
        sendToMetaPixel(eventName, payload);
    } catch (error) {
        // Broken tracking must never break the order confirmation.
        console.warn("gelatoTrack:", error);
    }
};

export default window.gelatoTrack;
