/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { _t } from "@web/core/l10n/translation";
import { Component, useState, onWillStart } from "@odoo/owl";

/**
 * Turns the delivery on and off from the same screen where the staff flip
 * the flavours every morning.
 *
 * The switch lives on the website record, which only an administrator may
 * write. The two ORM methods behind it run with sudo on purpose - the point
 * is that whoever is in the shop can close the delivery without being let
 * into Settings.
 */
export class GelatoDeliverySwitch extends Component {
    static template = "gelato_delivery.DeliverySwitch";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loaded: false,
            enabled: true,
            from: "",
            to: "",
            openNow: true,
        });
        onWillStart(() => this.load());
    }

    /** 11.5 on the record is 11:30 in the box. */
    static toClock(value) {
        const total = Math.round((value || 0) * 60);
        const hours = Math.floor(total / 60) % 24;
        const minutes = total % 60;
        return `${hours}:${String(minutes).padStart(2, "0")}`;
    }

    /** And back again; anything unreadable leaves the hour alone. */
    static fromClock(text) {
        const match = /^\s*(\d{1,2})[:.]?(\d{2})?\s*$/.exec(text || "");
        if (!match) {
            return null;
        }
        const hours = parseInt(match[1], 10);
        const minutes = parseInt(match[2] || "0", 10);
        if (hours > 23 || minutes > 59) {
            return null;
        }
        return hours + minutes / 60;
    }

    _apply(data) {
        this.state.enabled = data.enabled;
        this.state.from = this.constructor.toClock(data.order_from);
        this.state.to = this.constructor.toClock(data.order_to);
        this.state.openNow = data.open_now;
    }

    async load() {
        this._apply(await this.orm.call(
            "gelato.delivery.order", "gelato_switch_state", []));
        this.state.loaded = true;
    }

    async _write(values) {
        this._apply(await this.orm.call(
            "gelato.delivery.order", "gelato_switch_write", [values]));
    }

    async onToggle() {
        await this._write({ gelato_delivery_enabled: !this.state.enabled });
    }

    /**
     * The hour is read off the event, not off the state.
     *
     * With t-model on the same input the handler runs before the state has
     * caught up and would save what the box held one keystroke ago.
     */
    async onHourChange(field, ev) {
        const value = this.constructor.fromClock(ev.target.value);
        if (value === null) {
            // Put the stored hour back rather than saving nonsense. The
            // box is written to directly: the state never changed, so
            // there is nothing for a re-render to correct.
            await this.load();
            ev.target.value =
                field === "gelato_order_from" ? this.state.from : this.state.to;
            return;
        }
        await this._write({ [field]: value });
        ev.target.value =
            field === "gelato_order_from" ? this.state.from : this.state.to;
    }

    get labels() {
        return {
            toggle: _t("Switch the delivery on or off"),
            from: _t("Orders from"),
            to: _t("Orders until"),
        };
    }

    get statusLabel() {
        if (!this.state.enabled) {
            return _t("SWITCHED OFF - the website takes no orders");
        }
        if (!this.state.openNow) {
            return _t("Closed now - orders open at %s", this.state.from);
        }
        return _t("Taking orders");
    }
}

export class GelatoBoardController extends KanbanController {
    static template = "gelato_delivery.BoardWithSwitch";
    static components = {
        ...KanbanController.components,
        GelatoDeliverySwitch,
    };
}

registry.category("views").add("gelato_delivery_board", {
    ...kanbanView,
    Controller: GelatoBoardController,
});
