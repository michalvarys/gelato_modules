import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)


class GelatoDeliveryOrder(models.Model):
    _name = "gelato.delivery.order"
    _description = "Delivery Order"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "delivery_date desc, id desc"

    name = fields.Char(
        string="Order number",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
    )

    # ------------------------------------------------------------------
    # Customer
    # ------------------------------------------------------------------
    customer_name = fields.Char(string="Customer name", required=True, tracking=True)
    customer_phone = fields.Char(string="Phone", required=True, tracking=True)
    customer_email = fields.Char(string="Email", tracking=True)

    # ------------------------------------------------------------------
    # Delivery
    # ------------------------------------------------------------------
    delivery_address = fields.Char(
        string="Delivery address",
        required=True,
        help="Street and number, floor, doorbell.",
    )
    delivery_postcode = fields.Char(
        string="Postcode",
        help="Only written down for the driver - the zone is decided by the "
        "address on the map.",
    )
    delivery_city = fields.Char(
        string="Town",
        default="Karlovy Vary",
        help="The town the customer wrote on the delivery page. The field "
        "starts on Karlovy Vary, but they can put anything in it.",
    )
    zone_id = fields.Many2one(
        comodel_name="gelato.delivery.zone",
        string="Zone",
        ondelete="set null",
        help="Which drawn zone the address landed in. Empty means the "
        "address could not be put on the map.",
    )
    latitude = fields.Float(string="Latitude", digits=(10, 7))
    longitude = fields.Float(string="Longitude", digits=(10, 7))
    address_located = fields.Boolean(
        string="Address found on the map",
        help="When this is off the address could not be located, the order "
        "was let through anyway and the fee needs confirming on the phone.",
    )
    # Orders are for now, not for a slot somebody picks. The date is kept
    # because the overviews and the customer history group by it, but nobody
    # types it in - it is the day the order came.
    delivery_date = fields.Date(
        string="Ordered on",
        required=True,
        tracking=True,
        default=fields.Date.context_today,
    )
    note = fields.Text(
        string="Customer note",
        help="Split between flavours, allergies, gift wrapping and so on.",
    )
    internal_note = fields.Text(string="Internal note")

    # ------------------------------------------------------------------
    # What was ordered
    #
    # One order is a basket. A customer buys a 1 l box for themselves and a
    # half-litre for the neighbour, each with its own flavours, so the box
    # cannot live on the order itself - every line is its own item.
    # ------------------------------------------------------------------
    item_ids = fields.One2many(
        comodel_name="gelato.delivery.order.item",
        inverse_name="order_id",
        string="Items",
    )
    flavor_line_ids = fields.One2many(
        comodel_name="gelato.delivery.order.flavor",
        inverse_name="order_id",
        string="Flavours",
        readonly=True,
        help="Every flavour in the order, across all the boxes. Filled in "
        "through the items.",
    )
    flavor_ids = fields.Many2many(
        comodel_name="gelato.flavor",
        string="Chosen flavours",
        compute="_compute_flavor_ids",
        store=True,
        help="Which flavours are in the order, without the counts. Kept so "
        "the list can be searched and grouped by flavour.",
    )

    # ------------------------------------------------------------------
    customer_id = fields.Many2one(
        comodel_name="gelato.customer",
        string="Customer record",
        ondelete="set null",
        index=True,
        help="The one row in Customers this order belongs to. Filled in "
        "automatically from the phone and the email.",
    )

    order_summary = fields.Char(
        string="What was ordered",
        compute="_compute_order_summary",
        store=True,
        help="Box, flavours and extras on one line.",
    )

    # ------------------------------------------------------------------
    # Amounts
    # ------------------------------------------------------------------
    amount_items = fields.Float(
        string="Items total",
        compute="_compute_amounts",
        store=True,
        digits=(10, 2),
    )
    amount_subtotal = fields.Float(
        string="Subtotal",
        compute="_compute_amounts",
        store=True,
        digits=(10, 2),
    )
    promo_code_id = fields.Many2one(
        comodel_name="gelato.promo.code",
        string="Promo code",
        ondelete="set null",
    )
    discount_percent = fields.Float(
        string="Discount (%)",
        digits=(5, 2),
        help="Written down when the order is created, so a later change to "
        "the code does not change the price of an old order.",
    )
    # Written down rather than derived. A code can be for the whole
    # order, for one product or for the drive, so the percentage alone no
    # longer says what came off - and an order already driven must not
    # reprice itself because somebody edited the code afterwards.
    amount_discount = fields.Float(
        string="Discount",
        digits=(10, 2),
    )
    delivery_fee = fields.Float(string="Delivery", digits=(10, 2))
    amount_total = fields.Float(
        string="Total",
        compute="_compute_amounts",
        store=True,
        digits=(10, 2),
        tracking=True,
    )
    website_id = fields.Many2one(
        comodel_name="website",
        string="Website",
        ondelete="set null",
    )
    source = fields.Selection(
        selection=[("website", "Website"), ("manual", "Entered by hand")],
        string="Source",
        default="manual",
        required=True,
    )

    # ------------------------------------------------------------------
    # Computations
    # ------------------------------------------------------------------
    @api.depends(
        "item_ids.price_subtotal",
        "amount_discount",
        "delivery_fee",
    )
    def _compute_amounts(self):
        """Work out the totals.

        There is one price per thing and that is the whole of it. VAT is
        not split out anywhere - not on the products, not on the order, not
        in the emails: the gelateria wants one figure the customer pays.
        """
        for order in self:
            subtotal = sum(order.item_ids.mapped("price_subtotal"))
            order.amount_items = subtotal
            order.amount_subtotal = subtotal
            order.amount_total = (
                subtotal - (order.amount_discount or 0.0) + (order.delivery_fee or 0.0)
            )

    @api.onchange("promo_code_id", "item_ids", "delivery_fee")
    def _onchange_promo_code_id(self):
        """Fill in the discount for an order typed in by hand.

        The same sum the website does: only what the code covers, plus
        the fee if the code is for the drive.
        """
        promo = self.promo_code_id
        self.discount_percent = promo.discount_percent or 0.0
        if not promo:
            self.amount_discount = 0.0
            return
        lines = [
            (line.box_id or line.addon_id, line.quantity, line.price_unit)
            for line in self.item_ids
            if line.box_id or line.addon_id
        ]
        self.amount_discount = (
            promo.product_discount(lines)
            + promo.delivery_discount(self.delivery_fee)
        )

    # ------------------------------------------------------------------
    # Numbering
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "gelato.delivery.order"
                ) or _("New")
        orders = super().create(vals_list)
        orders._link_customer()
        return orders

    # ------------------------------------------------------------------
    # The on/off bar above the flavour board
    # ------------------------------------------------------------------
    # The switch lives on the website record, which only an administrator
    # may write. These two run with sudo on purpose: the whole point is
    # that whoever is in the shop can close the delivery without being let
    # into Settings.
    #
    SWITCH_FIELDS = (
        "gelato_delivery_enabled",
        "gelato_order_from",
        "gelato_order_to",
    )

    @api.model
    def gelato_switch_state(self):
        site = self.env["website"].sudo().get_current_website()
        open_now, note = site.gelato_orders_open()
        return {
            "enabled": site.gelato_delivery_enabled,
            "order_from": site.gelato_order_from,
            "order_to": site.gelato_order_to,
            "hours_label": site.gelato_order_hours_label(),
            "open_now": open_now,
            "note": note,
        }

    @api.model
    def gelato_switch_write(self, values):
        site = self.env["website"].sudo().get_current_website()
        # Only the three operational fields, never anything else that
        # happens to sit on the website record.
        site.write({
            key: value
            for key, value in (values or {}).items()
            if key in self.SWITCH_FIELDS
        })
        return self.gelato_switch_state()


    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _link_customer(self):
        """Attach every order to its one row in Customers.

        Done here rather than in the controller so an order typed in by hand
        in Odoo builds the contact list too.
        """
        Customer = self.env["gelato.customer"].sudo()
        for order in self:
            if order.customer_id:
                continue
            if not (order.customer_phone or order.customer_email):
                continue
            order.customer_id = Customer.find_or_create(
                order.customer_name,
                order.customer_email,
                order.customer_phone,
            )

    @api.depends("flavor_line_ids.flavor_id")
    def _compute_flavor_ids(self):
        for order in self:
            order.flavor_ids = [(6, 0, order.flavor_line_ids.flavor_id.ids)]

    def flavor_names(self):
        """Every flavour in the order with its count, across all the boxes."""
        self.ensure_one()
        return ", ".join(
            item.flavor_names() for item in self.item_ids if item.flavor_line_ids
        )

    @api.depends("item_ids.label", "item_ids.quantity")
    def _compute_order_summary(self):
        """What was ordered, on one line.

        Stored so the list can show it without opening every order, and so
        it can be searched - "who ordered pistachio" is a question the shop
        actually asks.
        """
        for order in self:
            order.order_summary = " · ".join(
                item.label for item in order.item_ids if item.label
            )

    def tracking_payload(self):
        """Data for GTM and the Meta Pixel, shaped like a purchase event.

        The item categories are deliberately left untranslated. GA4 and Meta
        group by the literal string, so a translated category would split one
        product line into a separate row per language of the visitor.
        """
        self.ensure_one()
        items = []
        for line in self.item_ids:
            if line.box_id:
                ref, name, category = (
                    f"box-{line.box_id.id}", line.box_id.name, "Thermal box")
            else:
                category = "Bundle" if line.addon_id.is_bundle else "Extra"
                ref, name = f"addon-{line.addon_id.id}", line.addon_id.name
            items.append(
                {
                    "item_id": ref,
                    "item_name": name,
                    "item_category": category,
                    "price": round(line.price_unit, 2),
                    "quantity": line.quantity,
                }
            )
        return {
            "transaction_id": self.name,
            "value": round(self.amount_total, 2),
            "currency": "CZK",
            "shipping": round(self.delivery_fee, 2),
            "discount": round(self.amount_discount, 2),
            "coupon": self.promo_code_id.code or "",
            "items": items,
        }

    def _send_confirmation_email(self):
        """Email the shop and the customer. Two different letters.

        The shop gets the whole order to make and drive; the customer gets a
        short confirmation that it arrived. Sent straight from here, not out
        of any workflow - an order has no states to walk through.

        Sent there and then, not left in the queue. Queued mail waits for
        Odoo's scheduler, which runs once an hour: an order placed at ten
        past would sit unseen until eleven, and gelato ordered for now
        does not keep. The order is already saved by the time this runs,
        so a mail server having a bad day costs a notification, never an
        order.

        A missing template or a bad address must never block an order, so
        each is attempted on its own and failures are only logged.
        """
        shop = self.env.ref(
            "gelato_delivery.mail_template_delivery_order",
            raise_if_not_found=False,
        )
        customer = self.env.ref(
            "gelato_delivery.mail_template_order_confirmation",
            raise_if_not_found=False,
        )
        for order in self:
            for template, needs_address in ((shop, False), (customer, True)):
                if not template or (needs_address and not order.customer_email):
                    continue
                try:
                    template.sudo().send_mail(order.id, force_send=True)
                except Exception as error:
                    _logger.warning(
                        "Order %s: could not send %s: %s",
                        order.name, template.name, error,
                    )
        return True


class GelatoDeliveryOrderItem(models.Model):
    """One thing in the basket: a thermal box, a bundle or an extra.

    A box and a bundle are filled with flavours, an extra is not. They are
    one model rather than three because the basket, the price, the email
    and the list all treat them the same - it is a line with a name, a
    count and a price.
    """

    _name = "gelato.delivery.order.item"
    _description = "Item on a Delivery Order"
    _order = "id"

    order_id = fields.Many2one(
        comodel_name="gelato.delivery.order",
        string="Order",
        required=True,
        ondelete="cascade",
    )
    box_id = fields.Many2one(
        comodel_name="gelato.delivery.box",
        string="Thermal box",
        ondelete="restrict",
    )
    addon_id = fields.Many2one(
        comodel_name="gelato.delivery.addon",
        string="Bundle or extra",
        ondelete="restrict",
    )
    quantity = fields.Integer(string="Quantity", default=1, required=True)
    price_unit = fields.Float(string="Unit price", digits=(10, 2))
    price_subtotal = fields.Float(
        string="Total",
        compute="_compute_price_subtotal",
        store=True,
        digits=(10, 2),
    )
    flavor_line_ids = fields.One2many(
        comodel_name="gelato.delivery.order.flavor",
        inverse_name="item_id",
        string="Flavours",
    )
    label = fields.Char(
        string="Item",
        compute="_compute_label",
        store=True,
        help="The name with its flavours, for the list and the email.",
    )

    _sql_constraints = [
        (
            "box_or_addon",
            "CHECK((box_id IS NULL) != (addon_id IS NULL))",
            "An item is either a thermal box or a bundle/extra, not both "
            "and not neither.",
        ),
        (
            "quantity_positive",
            "CHECK(quantity > 0)",
            "An item with no quantity does not belong on the order.",
        ),
    ]

    @api.depends("quantity", "price_unit")
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

    @api.depends("box_id", "addon_id", "quantity",
                 "flavor_line_ids.flavor_id", "flavor_line_ids.quantity")
    def _compute_label(self):
        for line in self:
            name = line.box_id.name or line.addon_id.name or ""
            if line.quantity > 1:
                name = "%d× %s" % (line.quantity, name)
            flavors = line.flavor_names()
            line.label = "%s (%s)" % (name, flavors) if flavors else name

    def flavor_names(self):
        """Flavours with their counts.

        A count of one is written plain - "Pistachio, Vanilla" reads better
        than "1x Pistachio, 1x Vanilla" and means the same thing.
        """
        self.ensure_one()
        parts = []
        for line in self.flavor_line_ids:
            if line.quantity > 1:
                parts.append("%d× %s" % (line.quantity, line.flavor_id.name))
            else:
                parts.append(line.flavor_id.name)
        return ", ".join(parts)

    def flavor_capacity(self):
        """How many parts this item is handed out in. Zero means no flavours."""
        self.ensure_one()
        if self.box_id:
            return self.box_id.max_flavors
        if self.addon_id.bundle_box_id:
            return self.addon_id.bundle_box_id.max_flavors
        return 0

    @api.onchange("box_id", "addon_id")
    def _onchange_product(self):
        if self.box_id:
            self.price_unit = self.box_id.price
        elif self.addon_id:
            # display_price, not price: a bundle's own price field is the
            # surcharge over its box, and as one basket line it is sold
            # for the whole figure on the leaflet.
            self.price_unit = self.addon_id.display_price()



class GelatoDeliveryOrderFlavor(models.Model):
    """One flavour in one box, and how much of that box it takes.

    The box is handed out in parts; this says how many of them go to this
    flavour. Two parts pistachio and one vanilla in a box split into three
    means two thirds of it is pistachio. It hangs off the item, not the
    order, because each box in a basket is filled on its own.
    """

    _name = "gelato.delivery.order.flavor"
    _description = "Flavour on a Delivery Order"
    _order = "id"

    item_id = fields.Many2one(
        comodel_name="gelato.delivery.order.item",
        string="Item",
        required=True,
        ondelete="cascade",
    )
    order_id = fields.Many2one(
        comodel_name="gelato.delivery.order",
        string="Order",
        related="item_id.order_id",
        store=True,
        index=True,
    )
    flavor_id = fields.Many2one(
        comodel_name="gelato.flavor",
        string="Flavour",
        required=True,
        ondelete="restrict",
    )
    quantity = fields.Integer(
        string="Parts",
        default=1,
        required=True,
        help="How many parts of the box this flavour takes.",
    )

    _sql_constraints = [
        (
            "flavor_once_per_item",
            "unique(item_id, flavor_id)",
            "A flavour can only be in one box once - raise its count "
            "instead of adding it twice.",
        ),
        (
            "quantity_positive",
            "CHECK(quantity > 0)",
            "A flavour with zero parts does not belong on the order.",
        ),
    ]
