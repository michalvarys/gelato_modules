from odoo import models


class IrHttp(models.AbstractModel):
    """Let the delivery form speak the visitor's language.

    Odoo only ships the JavaScript translations of a short list of modules to
    the public website. Without this hook the page itself would be translated
    but the messages the form writes from JavaScript - "the box is full",
    "we could not check the code" - would stay in English.
    """

    _inherit = "ir.http"

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        mods = super()._get_translation_frontend_modules_name()
        return mods + ["gelato_delivery"]
