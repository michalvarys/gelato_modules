import re

from odoo import _, api, fields, models


class GelatoCustomer(models.Model):
    """Everybody who has ever ordered, once each.

    Built up from the orders themselves - nobody types these in. The point
    is to end up with a list of contacts the shop can write to later, so the
    same person ordering every fortnight has to stay one row, not thirty.
    """

    _name = "gelato.customer"
    _description = "Delivery Customer"
    _order = "last_order_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(string="Name", required=True)
    email = fields.Char(string="Email", index=True)
    phone = fields.Char(string="Phone")
    # What the matching actually runs on. A phone written as +420 777 111 222
    # and one written as 777111222 are the same customer.
    phone_key = fields.Char(
        string="Phone digits",
        index=True,
        help="The phone reduced to its last nine digits. Used to recognise a "
        "returning customer, not meant to be read.",
    )
    active = fields.Boolean(string="Active", default=True)

    order_ids = fields.One2many(
        comodel_name="gelato.delivery.order",
        inverse_name="customer_id",
        string="Orders",
    )
    order_count = fields.Integer(
        string="How many orders",
        compute="_compute_orders",
        store=True,
    )
    amount_spent = fields.Float(
        string="Spent in total",
        compute="_compute_orders",
        store=True,
        digits=(10, 2),
    )
    first_order_date = fields.Date(
        string="First order",
        compute="_compute_orders",
        store=True,
    )
    last_order_date = fields.Date(
        string="Last order",
        compute="_compute_orders",
        store=True,
    )
    last_address = fields.Char(
        string="Last address",
        compute="_compute_orders",
        store=True,
    )
    zone_id = fields.Many2one(
        comodel_name="gelato.delivery.zone",
        string="Usual zone",
        compute="_compute_orders",
        store=True,
        ondelete="set null",
    )

    marketing_ok = fields.Boolean(
        string="May be contacted",
        default=False,
        help="Tick this only for people who agreed to hear from you. An "
        "address collected from an order is not on its own permission to "
        "send them offers.",
    )
    note = fields.Text(string="Note")

    _sql_constraints = [
        (
            "phone_key_unique",
            "unique(phone_key)",
            "A customer with this phone number already exists.",
        ),
    ]

    @api.depends("order_ids", "order_ids.amount_total",
                 "order_ids.delivery_date", "order_ids.delivery_address",
                 "order_ids.zone_id")
    def _compute_orders(self):
        for customer in self:
            orders = customer.order_ids.sorted("delivery_date")
            customer.order_count = len(orders)
            customer.amount_spent = sum(orders.mapped("amount_total"))
            customer.first_order_date = orders[:1].delivery_date or False
            customer.last_order_date = orders[-1:].delivery_date or False
            customer.last_address = orders[-1:].delivery_address or False
            customer.zone_id = orders[-1:].zone_id.id or False

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------
    @api.model
    def _phone_key(self, phone):
        """The last nine digits, which is what identifies a Czech number.

        Country code, spaces, slashes and dashes all get written differently
        by different people and none of them tell two customers apart.
        """
        digits = re.sub(r"\D", "", phone or "")
        if digits.startswith("00420"):
            digits = digits[5:]
        elif digits.startswith("420") and len(digits) > 9:
            digits = digits[3:]
        return digits[-9:] if len(digits) >= 9 else digits

    @api.model
    def _email_key(self, email):
        return (email or "").strip().lower()

    @api.model
    def find_or_create(self, name, email=None, phone=None):
        """The one row for this person, made if it is their first time.

        The phone decides first: people mistype their email or leave it out,
        but the number is what the shop rings. Only then the email. A new
        order filling in something the customer left blank last time tops up
        the existing row instead of starting a second one.
        """
        phone_key = self._phone_key(phone)
        email_key = self._email_key(email)
        name = (name or "").strip()

        customer = self.browse()
        if phone_key:
            customer = self.search([("phone_key", "=", phone_key)], limit=1)
        if not customer and email_key:
            customer = self.search([("email", "=ilike", email_key)], limit=1)

        if customer:
            filled = {}
            if not customer.email and email_key:
                filled["email"] = email_key
            if not customer.phone and phone:
                filled["phone"] = phone
                filled["phone_key"] = phone_key
            elif phone_key and not customer.phone_key:
                filled["phone_key"] = phone_key
            # A name is only replaced when there was none - the shop may have
            # tidied it up by hand and the form should not undo that.
            if not customer.name and name:
                filled["name"] = name
            if filled:
                customer.write(filled)
            return customer

        return self.create({
            "name": name or email_key or phone or _("Unnamed"),
            "email": email_key or False,
            "phone": phone or False,
            "phone_key": phone_key or False,
        })

    def action_view_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Orders"),
            "res_model": "gelato.delivery.order",
            "view_mode": "list,kanban,form",
            "domain": [("customer_id", "=", self.id)],
            "context": {"default_customer_id": self.id},
        }
