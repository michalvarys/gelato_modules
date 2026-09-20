from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    gelato_gtm_id = fields.Char(
        related="website_id.gelato_gtm_id",
        readonly=False,
    )
    gelato_meta_pixel_id = fields.Char(
        related="website_id.gelato_meta_pixel_id",
        readonly=False,
    )
    # Odoo own setting, surfaced here because tracking without it is not legal
    # in the EU - the two belong on one screen.
    cookies_bar = fields.Boolean(
        related="website_id.cookies_bar",
        readonly=False,
    )
