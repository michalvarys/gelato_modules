/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";
import { Component, useRef, useState, onMounted, onWillUnmount } from "@odoo/owl";

// The gelateria, so a brand new zone opens on the right town.
const HOME = [50.2339, 12.8546];

/**
 * Draws the delivery zone on a map instead of asking anybody to type
 * coordinates. Click to drop a corner, drag a corner to move it, click a
 * corner to remove it. The shape is stored as a plain list of points.
 */
export class ZoneMapField extends Component {
    static template = "gelato_delivery.ZoneMapField";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.mapRef = useRef("map");
        this.state = useState({ points: [], drawing: false, ready: false });

        onMounted(() => this.mount());
        onWillUnmount(() => this.map && this.map.remove());
    }

    get labels() {
        return {
            draw: _t("Draw a zone"),
            stop: _t("Finish drawing"),
            clear: _t("Clear the zone"),
            hint: _t(
                "Click on the map to drop a corner. Drag a corner to move it, click one to remove it."
            ),
            empty: _t("No shape yet - press Draw a zone and click around the area you deliver to."),
            count: _t("Corners: %s", this.state.points.length),
        };
    }

    async mount() {
        this.state.points = this.parse(this.props.record.data[this.props.name]);

        this.map = L.map(this.mapRef.el, { scrollWheelZoom: true });
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: "© OpenStreetMap",
        }).addTo(this.map);

        this.layer = L.layerGroup().addTo(this.map);
        this.othersLayer = L.layerGroup().addTo(this.map);
        this.map.on("click", (ev) => this.onMapClick(ev));

        await this.drawNeighbours();
        this.redraw();
        this.fit();
        this.state.ready = true;

        // The form often renders while the map is still hidden, which leaves
        // Leaflet convinced it is zero pixels wide.
        setTimeout(() => this.map.invalidateSize(), 200);
    }

    parse(value) {
        if (!value) {
            return [];
        }
        try {
            const raw = JSON.parse(value);
            return (raw || [])
                .map((point) => [Number(point[0]), Number(point[1])])
                .filter((point) => !isNaN(point[0]) && !isNaN(point[1]));
        } catch {
            return [];
        }
    }

    get color() {
        return this.props.record.data.color || "#84c5c3";
    }

    async drawNeighbours() {
        const currentId = this.props.record.resId || 0;
        let zones = [];
        try {
            zones = await this.orm.call(
                "gelato.delivery.zone",
                "zone_map_data",
                [currentId]
            );
        } catch {
            return;
        }
        this.othersLayer.clearLayers();
        for (const zone of zones) {
            if (zone.current || zone.points.length < 3) {
                continue;
            }
            L.polygon(zone.points, {
                color: zone.color,
                weight: 1,
                opacity: zone.active ? 0.7 : 0.3,
                fillOpacity: zone.active ? 0.12 : 0.05,
                dashArray: "4 4",
                interactive: false,
            })
                .bindTooltip(zone.name, { permanent: false })
                .addTo(this.othersLayer);
        }
    }

    onMapClick(ev) {
        if (!this.state.drawing) {
            return;
        }
        this.state.points.push([ev.latlng.lat, ev.latlng.lng]);
        this.save();
        this.redraw();
    }

    onToggleDraw() {
        this.state.drawing = !this.state.drawing;
        this.mapRef.el.classList.toggle("o_gelato_zone_drawing", this.state.drawing);
    }

    onClear() {
        this.state.points = [];
        this.state.drawing = true;
        this.save();
        this.redraw();
    }

    redraw() {
        this.layer.clearLayers();
        const points = this.state.points;

        if (points.length >= 3) {
            // A white casing under the outline, otherwise a coloured line on
            // a green map reads as just another road.
            L.polygon(points, {
                color: "#fff",
                weight: 6,
                opacity: 0.9,
                fill: false,
                interactive: false,
            }).addTo(this.layer);
            L.polygon(points, {
                color: this.color,
                weight: 3,
                opacity: 1,
                fillOpacity: 0.35,
                interactive: false,
            }).addTo(this.layer);
        } else if (points.length === 2) {
            L.polyline(points, {
                color: this.color,
                weight: 2,
                interactive: false,
            }).addTo(this.layer);
        }

        points.forEach((point, index) => {
            const handle = L.circleMarker(point, {
                radius: 6,
                color: "#fff",
                weight: 2,
                fillColor: this.color,
                fillOpacity: 1,
                draggable: true,
            }).addTo(this.layer);
            handle.on("click", (ev) => {
                L.DomEvent.stopPropagation(ev);
                this.state.points.splice(index, 1);
                this.save();
                this.redraw();
            });
            handle.on("mousedown", () => this.startDrag(index, handle));
        });
    }

    startDrag(index, handle) {
        this.map.dragging.disable();
        const move = (ev) => {
            this.state.points[index] = [ev.latlng.lat, ev.latlng.lng];
            handle.setLatLng(ev.latlng);
            this.redrawShapeOnly();
        };
        const stop = () => {
            this.map.off("mousemove", move);
            this.map.off("mouseup", stop);
            this.map.dragging.enable();
            this.save();
            this.redraw();
        };
        this.map.on("mousemove", move);
        this.map.on("mouseup", stop);
    }

    redrawShapeOnly() {
        if (!this.shape) {
            return;
        }
        this.shape.setLatLngs(this.state.points);
    }

    fit() {
        if (this.state.points.length >= 2) {
            this.map.fitBounds(L.latLngBounds(this.state.points), { padding: [24, 24] });
        } else {
            this.map.setView(HOME, 13);
        }
    }

    save() {
        const value = this.state.points.length
            ? JSON.stringify(this.state.points.map((p) => [
                  Number(p[0].toFixed(6)),
                  Number(p[1].toFixed(6)),
              ]))
            : false;
        this.props.record.update({ [this.props.name]: value });
    }
}

export const zoneMapField = {
    component: ZoneMapField,
    supportedTypes: ["text"],
};

registry.category("fields").add("gelato_zone_map", zoneMapField);
