from odoo import fields, models

# Domains the tracking scripts load from. They are blocked until the visitor
# accepts optional cookies - see _get_blocked_third_party_domains_list below.
TRACKING_DOMAINS = [
    "googletagmanager.com",
    "connect.facebook.net",
    "facebook.com",
]


class Website(models.Model):
    """Tracking IDs belong to one specific website, not to the whole database.

    If they lived in ir.config_parameter, one website would start sending data
    into the account of another website in the same database.
    """

    _inherit = "website"

    gelato_gtm_id = fields.Char(
        string="Google Tag Manager ID",
        help="In the form GTM-XXXXXXX. An empty field switches tracking off "
        "entirely - no script is added to the page.",
    )
    gelato_meta_pixel_id = fields.Char(
        string="Meta Pixel ID",
        help="The pixel number from the Facebook Events Manager. "
        "An empty field switches tracking off entirely.",
    )

    def _get_blocked_third_party_domains_list(self):
        """Hold the tracking scripts back until cookies are accepted.

        Odoo blocks third party scripts by domain: it swaps their src for
        about:blank and re-creates them once the visitor accepts optional
        cookies. Adding our domains here means Google and Meta cannot load,
        and cannot set a single cookie, before that consent.

        Without it the pixel would fire on the first page view, which is not
        something a European site may do.

        Note this only bites when the cookies bar is switched on. With the bar
        off Odoo assumes consent is handled elsewhere and blocks nothing -
        that is why the settings screen warns about exactly that case.
        """
        domains = super()._get_blocked_third_party_domains_list()
        # Only for a website that actually measures. Another website in the
        # same database has nothing to do with our Google or Meta account and
        # must not get its own scripts blocked because of us.
        if not (self.gelato_gtm_id or self.gelato_meta_pixel_id):
            return domains
        for domain in TRACKING_DOMAINS:
            if domain not in domains:
                domains.append(domain)
        return domains
