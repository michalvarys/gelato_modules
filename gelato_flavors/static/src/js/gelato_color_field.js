/** @odoo-module **/

import { useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { ColorField, colorField } from "@web/views/fields/color/color_field";

/**
 * The colour picker that keeps up with the finger.
 *
 * Odoo's own colour widget paints its swatch from a `color` getter, and
 * its template answers every `input` event with
 *
 *     this.color = ev.target.value
 *
 * The component has no setter for `color`, so that line writes nowhere.
 * The dot therefore does not move while a colour is being chosen; it
 * only catches up on `change`, which the browser sends when the picker
 * is closed. On a phone that is the whole of the experience - you drag
 * around the wheel and the dot behind it stays on the old colour, so it
 * reads as if the picker were not working at all.
 *
 * This subclass gives `color` the setter the template is already
 * writing to. It is kept to the screen: the record is not touched and
 * nothing is sent to the server until the picker is closed, exactly as
 * before. The preview is tied to the record it was made for, so a tile
 * that gets reused for another flavour cannot inherit it.
 *
 * It is a separate widget rather than a patch of the stock one on
 * purpose - every other colour field in the database goes on behaving
 * as it always did.
 */
export class GelatoColorField extends ColorField {
    setup() {
        super.setup();
        this.preview = useState({ recordId: null, value: null });
    }

    get color() {
        if (this.preview.value && this.preview.recordId === this.props.record.resId) {
            return this.preview.value;
        }
        return super.color;
    }

    set color(value) {
        this.preview.recordId = this.props.record.resId;
        this.preview.value = value;
    }

    onChange(ev) {
        // The chosen colour is now the record's own; the preview has
        // done its job and must not outlive it.
        this.preview.recordId = null;
        this.preview.value = null;
        super.onChange(ev);
    }
}

export const gelatoColorField = {
    ...colorField,
    component: GelatoColorField,
};

registry.category("fields").add("gelato_color", gelatoColorField);
