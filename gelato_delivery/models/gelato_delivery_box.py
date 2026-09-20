from odoo import _, api, fields, models


class GelatoDeliveryBox(models.Model):
    _name = "gelato.delivery.box"
    _inherit = ["gelato.image.frame"]
    _description = "Thermal Box"
    _order = "sequence, price"

    name = fields.Char(
        string="Name",
        required=True,
        translate=True,
        help="Shown on the card on the website, for example “1 l”.",
    )
    subtitle = fields.Char(
        string="Subtitle",
        translate=True,
        help="The line under the name, for example “about 8 servings”.",
    )
    price = fields.Float(
        string="Price",
        required=True,
        digits=(10, 2),
    )
    volume_l = fields.Float(
        string="Volume (l)",
        digits=(5, 2),
        help="For your reference in Odoo only.",
    )
    portions = fields.Integer(
        string="Servings",
        help="For your reference in Odoo only.",
    )
    max_flavors = fields.Integer(
        string="Flavours in the box",
        default=0,
        help="How many flavours fit in this box - the website says \"max 4 "
        "flavours\". The customer hands them out, so a box of four can be "
        "two of pistachio and two of vanilla, or all four the same. "
        "0 means no limit.",
    )
    image = fields.Image(
        string="Photo",
        max_width=1024,
        max_height=1024,
        help="Shown on the box card on the website. Without it the card is "
        "just text, and nobody who does not already know you buys from text.",
    )
    features = fields.Text(
        string="Bullet points on the card",
        translate=True,
        help="One bullet per line. Shown on the box card on the website.",
    )
    # Filled in rather than left blank with a hint. What the website says
    # has to be readable here, in the same words - a placeholder saying
    # "max 4 flavours" while the card says something else is no use to
    # anybody. It writes itself from the number above and is overwritten
    # whenever that number changes; type over it and that text stands
    # until the number moves again.
    flavor_note = fields.Char(
        string="Flavours line on the card",
        translate=True,
        help="What the card says under the name. It is written for you "
        "from the number of flavours above; change it to anything you "
        "like.",
    )

    highlight = fields.Boolean(
        string="Badge on the card",
        help="Puts the green badge in the corner of the card on the "
        "delivery page - the “Most popular” one. Switch it off and the "
        "badge is gone.",
    )
    highlight_label = fields.Char(
        string="What the badge says",
        translate=True,
        default="Most popular",
        help="Anything you like: Most popular, New, Best value.",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
    )

    # ------------------------------------------------------------------
    # Keeping the card's line and the back office saying the same thing
    # ------------------------------------------------------------------
    @api.onchange("max_flavors")
    def _onchange_max_flavors(self):
        """Rewrite the line while the number is being changed."""
        self.flavor_note = self._default_flavor_note()

    @api.model_create_multi
    def create(self, vals_list):
        boxes = super().create(vals_list)
        boxes._fill_flavor_note()
        return boxes

    def write(self, vals):
        result = super().write(vals)
        if "max_flavors" in vals or "flavor_note" in vals:
            self._fill_flavor_note()
        return result

    def _fill_flavor_note(self):
        """Never leave the line empty.

        The website falls back to the generated wording anyway, and the
        back office would then show a blank where the card shows text.
        Writing it down keeps the two saying the same thing.
        """
        for record in self:
            if not record.flavor_note:
                note = record._default_flavor_note()
                if note:
                    record.flavor_note = note

    def flavor_limit_label(self):
        """How many flavours fit in the box, as a line for the website.

        Three separate strings on purpose. Odoo keeps one translation per
        source string, but Czech needs three number forms - "1 příchuť",
        "2 příchutě", "5 příchutí" - so the form has to be picked here and
        each one translated on its own.
        """
        self.ensure_one()
        count = self.max_flavors
        if count <= 0:
            return _("any number of flavours")
        if count == 1:
            return _("1 flavour")
        if count < 5:
            return _("up to %s flavours", count)
        return _("up to %s different flavours", count)

    def flavor_limit_short(self):
        """What the card says under the name.

        Whatever stands in flavor_note, which is exactly what the back
        office shows. The generated wording is only a fallback for a box
        whose line somebody emptied by hand.
        """
        self.ensure_one()
        return self.flavor_note or self._default_flavor_note()

    def _default_flavor_note(self):
        """The wording written out from the number of flavours.

        The full line does not fit the width of a phone and was being cut
        off mid-word, hence the short form. Split into number forms for
        the same reason as flavor_limit_label.
        """
        self.ensure_one()
        count = self.max_flavors
        if count <= 0:
            return ""
        if count == 1:
            return _("max 1 flavour")
        if count < 5:
            return _("max %s flavours", count)
        return _("max %s flavours in total", count)

    def feature_list(self):
        """Bullet points split into lines. Called by the QWeb template."""
        self.ensure_one()
        if not self.features:
            return []
        return [line.strip() for line in self.features.splitlines() if line.strip()]
