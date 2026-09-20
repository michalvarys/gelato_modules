import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class GelatoDeliveryZone(models.Model):
    """A delivery zone drawn on the map, with its own delivery fee.

    The shop draws a shape around the part of town it serves, gives it a
    price, and that is the whole configuration. The customer's address is
    turned into a point and whichever zone contains that point sets the fee.

    Zones may overlap. The one with the lowest sequence wins, which is how
    a small cheap zone can sit inside a bigger expensive one.
    """

    _name = "gelato.delivery.zone"
    _description = "Delivery Zone"
    _order = "sequence, id"

    name = fields.Char(
        string="Zone name",
        required=True,
        translate=True,
        help="What you call it, for example “Centre” or “Zone 1”.",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Zones are checked in this order. When two zones overlap, the "
        "one higher in the list decides the price.",
    )
    active = fields.Boolean(
        string="We deliver here",
        default=True,
        help="Switched off, the zone stops taking orders and disappears from "
        "the website.",
    )
    color = fields.Char(
        string="Colour on the map",
        default="#84c5c3",
        help="Only so you can tell the zones apart while drawing.",
    )
    delivery_fee = fields.Float(
        string="Delivery fee",
        digits=(10, 2),
        default=79.0,
        help="What the customer pays for delivery into this zone.",
    )
    free_from = fields.Float(
        string="Free from",
        digits=(10, 2),
        default=0.0,
        help="Orders above this amount are delivered into this zone for "
        "free. 0 means the fee always applies.",
    )
    min_order = fields.Float(
        string="Minimum order",
        digits=(10, 2),
        default=0.0,
        help="We do not drive to this zone for less than this. 0 means no "
        "minimum.",
    )
    polygon = fields.Text(
        string="Shape",
        help="The outline drawn on the map, stored as a list of points. "
        "Drawn with the map above, not typed in by hand.",
    )
    point_count = fields.Integer(
        string="Points",
        compute="_compute_point_count",
        store=True,
    )

    @api.depends("polygon")
    def _compute_point_count(self):
        for zone in self:
            zone.point_count = len(zone._points())

    @api.constrains("polygon")
    def _check_polygon(self):
        for zone in self:
            if not zone.polygon:
                continue
            points = zone._points()
            if points and len(points) < 3:
                raise ValidationError(
                    _("A zone needs at least three points on the map.")
                )

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------
    def _points(self):
        """The outline as a list of (lat, lng) pairs."""
        self.ensure_one()
        if not self.polygon:
            return []
        try:
            raw = json.loads(self.polygon)
        except (TypeError, ValueError):
            _logger.warning("Zone %s has an unreadable shape.", self.name)
            return []
        points = []
        for item in raw or []:
            try:
                points.append((float(item[0]), float(item[1])))
            except (TypeError, ValueError, IndexError):
                continue
        return points

    def contains(self, lat, lng):
        """Is this point inside the zone?

        Plain ray casting: walk the edges and count how many times a ray
        going east from the point crosses one. An odd number means inside.
        Over a town-sized shape the curvature of the earth is far below the
        accuracy of the address itself, so flat maths is enough.
        """
        self.ensure_one()
        points = self._points()
        if len(points) < 3:
            return False

        inside = False
        count = len(points)
        for index in range(count):
            lat_a, lng_a = points[index]
            lat_b, lng_b = points[(index + 1) % count]
            crosses = (lat_a > lat) != (lat_b > lat)
            if not crosses:
                continue
            # longitude of the edge at the point's latitude
            edge_lng = lng_a + (lat - lat_a) * (lng_b - lng_a) / (lat_b - lat_a)
            if lng < edge_lng:
                inside = not inside
        return inside

    @api.model
    def zone_for(self, lat, lng):
        """The first zone containing the point, or an empty recordset."""
        if lat is None or lng is None:
            return self.browse()
        for zone in self.sudo().search([]):
            if zone.contains(lat, lng):
                return zone
        return self.browse()

    # ------------------------------------------------------------------
    # Pricing
    # ------------------------------------------------------------------
    def fee_for(self, subtotal):
        """The delivery fee for an order of this size into this zone."""
        self.ensure_one()
        if self.free_from and subtotal >= self.free_from:
            return 0.0
        return self.delivery_fee

    # ------------------------------------------------------------------
    # Used by the map editor in the backend
    # ------------------------------------------------------------------
    @api.model
    def zone_map_data(self, current_id=None):
        """Every zone's outline, so the editor can show the neighbours."""
        zones = self.sudo().with_context(active_test=False).search([])
        return [
            {
                "id": zone.id,
                "name": zone.name,
                "color": zone.color or "#84c5c3",
                "points": [list(point) for point in zone._points()],
                "current": zone.id == current_id,
                "active": zone.active,
            }
            for zone in zones
        ]
