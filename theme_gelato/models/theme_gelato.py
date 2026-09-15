from odoo import models


class ThemeGelato(models.AbstractModel):
    _inherit = 'theme.utils'

    def _theme_gelato_post_copy(self, mod):
        self.disable_view('website.footer_custom')
