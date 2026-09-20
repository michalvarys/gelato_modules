from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    gelato_delivery_site = fields.Boolean(
        related="website_id.gelato_delivery_site",
        readonly=False,
    )
    gelato_delivery_email = fields.Char(
        related="website_id.gelato_delivery_email",
        readonly=False,
    )
    gelato_delivery_fee = fields.Float(
        related="website_id.gelato_delivery_fee",
        readonly=False,
    )
    gelato_delivery_free_from = fields.Float(
        related="website_id.gelato_delivery_free_from",
        readonly=False,
    )
    gelato_delivery_fee_base = fields.Selection(
        related="website_id.gelato_delivery_fee_base",
        readonly=False,
    )
    gelato_delivery_promo_note = fields.Char(
        related="website_id.gelato_delivery_promo_note",
        readonly=False,
    )
    # These two are also on the switch above the flavour board, which is
    # where the shop actually moves them - here for whoever is in Settings
    # anyway.
    gelato_order_from = fields.Float(
        related="website_id.gelato_order_from",
        readonly=False,
    )
    gelato_order_to = fields.Float(
        related="website_id.gelato_order_to",
        readonly=False,
    )
