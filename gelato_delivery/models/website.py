import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# The delivery page, and the item in the top menu that points at it.
GELATO_MENU_NAME = "Rozvoz"
GELATO_MENU_URL = "/rozvoz"


class Website(models.Model):
    """Delivery settings belong to one specific website.

    A single database can host several websites. If these values lived in
    ir.config_parameter they would leak between them and the Gelato delivery
    would show up where it does not belong.
    """

    _inherit = "website"

    gelato_delivery_enabled = fields.Boolean(
        string="Delivery is running",
        default=True,
        help="When switched off, the /rozvoz page stays but shows a notice "
        "instead of the order form.",
    )
    gelato_delivery_site = fields.Boolean(
        string="Delivery lives on this website",
        default=False,
        help="Only the website with this ticked serves the /rozvoz page. "
        "One database can host several websites and the gelateria's delivery "
        "has no business appearing on somebody else's site.",
    )
    gelato_delivery_email = fields.Char(
        string="Email for orders",
        default="gelatokv@seznam.cz",
        help="Where new delivery orders are sent.",
    )
    gelato_delivery_fee = fields.Float(
        string="Delivery fee",
        digits=(10, 2),
        default=79.0,
    )
    gelato_delivery_free_from = fields.Float(
        string="Free delivery from",
        digits=(10, 2),
        default=800.0,
        help="Orders above this amount are delivered for free. "
        "0 means delivery is always free.",
    )
    gelato_delivery_fee_base = fields.Selection(
        selection=[
            ("before_discount", "On the price before the discount"),
            ("after_discount", "On the price after the discount"),
        ],
        string="Apply the free delivery threshold",
        default="before_discount",
        required=True,
        help="Decides whether a promo code can push an order below the free "
        "delivery threshold. “Before the discount” is the friendlier option: "
        "someone who orders above the threshold keeps free delivery even "
        "after applying a code.",
    )
    gelato_delivery_promo_note = fields.Char(
        string="Note above the promo code field",
        translate=True,
        help="For example “Got a code from Instagram? Enter it here.” "
        "An empty field hides the note.",
    )

    def gelato_delivery_fee_for(self, subtotal, discount=0.0):
        """Work out the delivery fee.

        `subtotal` is the price of the goods before the discount and
        `discount` is the discount in CZK. Depending on the setting, the free
        delivery threshold is compared either against the price before the
        discount or against what the customer actually pays.
        """
        self.ensure_one()
        if not self.gelato_delivery_fee:
            return 0.0
        if not self.gelato_delivery_free_from:
            return self.gelato_delivery_fee

        base = subtotal
        if self.gelato_delivery_fee_base == "after_discount":
            base = subtotal - discount

        if base >= self.gelato_delivery_free_from:
            return 0.0
        return self.gelato_delivery_fee

    # ------------------------------------------------------------------
    # When is the delivery taking orders?
    #
    # Nobody books a slot - the customer orders and the gelateria drives
    # out. But the gelateria does not drive at four in the morning, so the
    # page only takes orders between these two hours. Both left at zero
    # means round the clock.
    # ------------------------------------------------------------------
    gelato_order_from = fields.Float(
        string="Orders from",
        default=11.0,
        help="From what time the website takes orders. 11.5 means half "
        "past eleven. Leave both at 0 for round the clock.",
    )
    gelato_order_to = fields.Float(
        string="Orders until",
        default=20.0,
        help="Until what time the website takes orders. Somebody still has "
        "to make it and drive out, so this is usually earlier than closing "
        "time.",
    )

    def _gelato_hours_set(self):
        """Are the hours actually set, or is it round the clock?"""
        self.ensure_one()
        return bool(self.gelato_order_from or self.gelato_order_to)

    @staticmethod
    def _gelato_format_hour(value):
        """11.5 reads as 11:30 - nobody writes opening hours in decimals."""
        hours = int(value) % 24
        minutes = int(round((value - int(value)) * 60))
        if minutes >= 60:
            hours, minutes = (hours + 1) % 24, 0
        return "%d:%02d" % (hours, minutes)

    def _gelato_shop_tz(self):
        """The gelateria's own clock.

        Never the reader's. The hours say when the gelateria takes orders,
        so somebody opening the page from Bangkok has to be told what is
        true in Karlovy Vary. This used to take the timezone off the
        logged-in user, which closed the page in the middle of a Czech
        afternoon for anyone travelling - and would have done the same to
        the shop the moment a staff account had a timezone set on it.

        The company keeps the real one; Prague is the fallback, because a
        gelateria in Karlovy Vary is not going to be anywhere else.
        """
        partner = self.company_id.partner_id if self.company_id else False
        return (partner and partner.tz) or "Europe/Prague"

    def _gelato_local_now(self):
        """The time in the shop, not on the server and not on the visitor."""
        self.ensure_one()
        return fields.Datetime.context_timestamp(
            self.with_context(tz=self._gelato_shop_tz()),
            fields.Datetime.now(),
        )

    def gelato_order_hours_label(self):
        """The hours on one line, for the website and for the switch."""
        self.ensure_one()
        if not self._gelato_hours_set():
            return ""
        return "%s – %s" % (
            self._gelato_format_hour(self.gelato_order_from),
            self._gelato_format_hour(self.gelato_order_to),
        )

    def gelato_orders_open(self):
        """Is the website taking orders right now?

        The switch comes first: it is for a holiday or a broken freezer and
        it beats the clock. Then the hours, so somebody at two in the
        morning is told when to come back instead of sending an order that
        nobody reads until lunchtime.

        Returns (open, reason). The reason is filled in only when the clock
        closed the page - a delivery switched off has its own wording.
        """
        self.ensure_one()
        if not self.gelato_delivery_enabled:
            return False, ""
        if not self._gelato_hours_set():
            return True, ""

        now = self._gelato_local_now()
        minutes = now.hour * 60 + now.minute
        start = int(round(self.gelato_order_from * 60))
        end = int(round(self.gelato_order_to * 60))

        # An evening that runs past midnight is a window that wraps round.
        if start <= end:
            inside = start <= minutes < end
        else:
            inside = minutes >= start or minutes < end

        if inside:
            return True, ""
        return False, _(
            "We take orders %(hours)s. Come back then, or give us a ring."
        ) % {"hours": self.gelato_order_hours_label()}

    # ------------------------------------------------------------------
    # Which website the delivery belongs to
    # ------------------------------------------------------------------
    @api.model
    def _gelato_claim_delivery_site(self):
        """Pick the website the delivery lives on, at install time.

        Only when there is exactly one - then there is nothing to guess.
        A database that already hosts somebody else's site gets nothing
        ticked, because putting the gelateria's order form on a stranger's
        website is a worse outcome than the shop having to tick one box
        under Website settings. The page itself refuses to answer on a
        website that is not ticked, so nothing leaks either way.
        """
        websites = self.search([])
        if len(websites) != 1:
            _logger.info(
                "gelato_delivery: %d websites in this database, so none was "
                "claimed. Tick 'Delivery lives on this website' under "
                "Website settings on the one that should serve /rozvoz.",
                len(websites),
            )
            return self.browse()
        # The write puts the menu item there as well.
        websites.gelato_delivery_site = True
        return websites

    def _gelato_delivery_menu(self):
        """The item pointing at /rozvoz, for the websites in self."""
        return self.env["website.menu"].search([
            ("website_id", "in", self.ids),
            ("url", "=", GELATO_MENU_URL),
        ])

    def _gelato_sync_delivery_menu(self):
        """Put the item in the top menu, or take it away again.

        Hung off the switch rather than off the install, so a shop that
        turns the delivery on later - or moves it to another website -
        gets the menu without anybody touching the database. The item
        always carries website_id: one without it shows up on every
        website there is.
        """
        Menu = self.env["website.menu"]
        for website in self:
            existing = website._gelato_delivery_menu()
            if not website.gelato_delivery_site:
                existing.unlink()
                continue
            if existing:
                continue
            top = Menu.search(
                [("website_id", "=", website.id), ("parent_id", "=", False)],
                limit=1,
            )
            Menu.create({
                "name": GELATO_MENU_NAME,
                "url": GELATO_MENU_URL,
                "parent_id": top.id if top else False,
                "website_id": website.id,
                "sequence": 15,
            })

    def write(self, vals):
        res = super().write(vals)
        if "gelato_delivery_site" in vals:
            self._gelato_sync_delivery_menu()
        return res
