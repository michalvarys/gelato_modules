from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class GelatoDeliveryAddon(models.Model):
    """An extra for a delivery: a bottle, a seasonal item or a bundle deal.

    An extra is always **added** to the price of the thermal box. For a bundle
    that is awkward: the leaflet says “1 l of gelato and a bottle of prosecco
    for 799 CZK”, not “surcharge 349 CZK”. So a bundle stores the advertised
    price and the surcharge is derived from it.

    That way the box price can change without leaving the bundle stuck on an
    old figure - the surcharge simply recalculates.
    """

    _name = "gelato.delivery.addon"
    _inherit = ["gelato.image.frame"]
    _description = "Delivery Extra"
    _order = "sequence, price"

    name = fields.Char(
        string="Name",
        required=True,
        translate=True,
    )
    description = fields.Char(
        string="Description",
        translate=True,
        help="One sentence under the name on the website.",
    )
    kind = fields.Selection(
        selection=[
            ("drink", "Drink"),
            ("bundle", "Bundle"),
            ("other", "Other"),
        ],
        string="Type",
        default="drink",
        required=True,
        help="A bundle behaves differently: you enter its total price "
        "including the thermal box. Seasonality is not a type - hide an "
        "out-of-season extra with the Available switch.",
    )
    is_bundle = fields.Boolean(
        string="Is a bundle",
        compute="_compute_is_bundle",
        store=True,
    )

    # ------------------------------------------------------------------
    # Prices
    # ------------------------------------------------------------------
    price_extra = fields.Float(
        string="Price of the extra",
        digits=(10, 2),
        help="How much is added to the price of the thermal box. Used for "
        "everything except bundles.",
    )
    bundle_box_id = fields.Many2one(
        comodel_name="gelato.delivery.box",
        string="Bundle goes with box",
        ondelete="restrict",
        help="Which thermal box the bundle is priced for. The customer "
        "cannot combine it with a different box.",
    )
    bundle_total = fields.Float(
        string="Total bundle price",
        digits=(10, 2),
        help="The price the customer sees on the leaflet, box included. "
        "The surcharge is derived from it.",
    )
    price = fields.Float(
        string="Surcharge on top of the box",
        compute="_compute_price",
        store=True,
        digits=(10, 2),
        help="The amount actually added to the order. For a bundle it is "
        "derived from the total price and never typed in by hand.",
    )

    max_quantity = fields.Integer(
        string="Max. quantity",
        default=10,
        help="How many units the customer may order at once.",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="An extra that is switched off disappears from the website. "
        "That is how eggnog hides out of season and comes back with one click.",
    )
    image = fields.Image(
        string="Photo",
        max_width=1024,
        max_height=1024,
    )

    @api.depends("kind")
    def _compute_is_bundle(self):
        for record in self:
            record.is_bundle = record.kind == "bundle"

    @api.depends("kind", "price_extra", "bundle_total", "bundle_box_id.price")
    def _compute_price(self):
        for record in self:
            if record.kind == "bundle" and record.bundle_box_id:
                record.price = record.bundle_total - record.bundle_box_id.price
            else:
                record.price = record.price_extra

    @api.constrains("kind", "bundle_box_id", "bundle_total", "price")
    def _check_bundle(self):
        for record in self:
            if record.kind != "bundle":
                continue
            if not record.bundle_box_id:
                raise ValidationError(
                    _("Pick the thermal box that bundle “%s” goes with.")
                    % record.name
                )
            if record.bundle_total <= 0:
                raise ValidationError(
                    _("Fill in the total price of bundle “%s”.") % record.name
                )
            if record.price < 0:
                raise ValidationError(
                    _(
                        "Bundle “%(name)s” costs %(total)s CZK, but the "
                        "%(box)s box alone costs %(box_price)s CZK. A bundle "
                        "cannot be cheaper than the box it contains."
                    )
                    % {
                        "name": record.name,
                        "total": record.bundle_total,
                        "box": record.bundle_box_id.name,
                        "box_price": record.bundle_box_id.price,
                    }
                )

    # ------------------------------------------------------------------
    # For the website
    # ------------------------------------------------------------------
    def display_price(self):
        """The price the customer sees.

        For a bundle that is the total including the box, otherwise the
        surcharge.
        """
        self.ensure_one()
        return self.bundle_total if self.is_bundle else self.price

    def display_note(self):
        """The extra line under the price on the website."""
        self.ensure_one()
        if self.is_bundle and self.bundle_box_id:
            return _("%s thermal box included") % self.bundle_box_id.name
        return ""
