from odoo import api, fields, models


class GelatoFlavor(models.Model):
    _name = "gelato.flavor"
    _description = "Flavour"
    _order = "sequence, name"

    name = fields.Char(
        string="Name",
        required=True,
        translate=True,
    )
    description = fields.Char(
        string="Short description",
        translate=True,
        help="One sentence shown under the flavour name on the website.",
    )
    category_id = fields.Many2one(
        comodel_name="gelato.flavor.category",
        string="Category",
        ondelete="set null",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="A flavour you no longer make. Archiving removes it from the "
        "list and from the website, but past orders keep it.",
    )

    # ------------------------------------------------------------------
    # Daily switch
    # ------------------------------------------------------------------
    available = fields.Boolean(
        string="On the menu today",
        default=False,
        help="A flavour that is switched on shows up on the website "
        "immediately. Switching it off hides it.",
    )
    available_since = fields.Datetime(
        string="Switched on",
        readonly=True,
        help="When the flavour was last switched on. For your information only.",
    )

    # ------------------------------------------------------------------
    # Website extras
    # ------------------------------------------------------------------
    color = fields.Char(
        string="Colour",
        help="The dot beside the flavour on the website. Left alone, the "
        "flavour takes the colour of its category - an untouched picker "
        "shows black, and the line below says what is really used.",
    )
    image = fields.Image(
        string="Photo",
        max_width=1024,
        max_height=1024,
    )
    tag_ids = fields.Many2many(
        comodel_name="gelato.flavor.tag",
        relation="gelato_flavor_tag_rel",
        column1="flavor_id",
        column2="tag_id",
        string="Tags",
        help="Small badges shown next to the flavour on the website. "
        "The list of tags is managed under Configuration.",
    )
    allergens = fields.Char(
        string="Allergens",
        translate=True,
        help="For example “nuts, milk”. Shown on the website in small print.",
    )

    display_color = fields.Char(
        string="Colour on the website",
        compute="_compute_display_color",
    )

    _sql_constraints = [
        (
            "name_uniq",
            "unique(name)",
            "A flavour with this name already exists.",
        ),
    ]

    @api.depends("color", "category_id.color")
    def _compute_display_color(self):
        for record in self:
            record.display_color = (
                record.color or record.category_id.color or "#84c5c3"
            )

    # ------------------------------------------------------------------
    # Remembering when a flavour was switched on
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            if vals.get("available") and not vals.get("available_since"):
                vals["available_since"] = now
        return super().create(vals_list)

    def write(self, vals):
        if "available" in vals and "available_since" not in vals:
            vals = dict(vals)
            vals["available_since"] = (
                fields.Datetime.now() if vals["available"] else False
            )
        return super().write(vals)

    # ------------------------------------------------------------------
    # Buttons for the shop staff
    # ------------------------------------------------------------------
    def action_toggle_available(self):
        """Flip one flavour. Called from the tile on the board."""
        for record in self:
            record.available = not record.available
        return True

    @api.model
    def action_turn_all_off(self):
        """Switch every flavour off. Used in the evening or before a new batch."""
        self.search([("available", "=", True)]).write({"available": False})
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    @api.model
    def get_available_flavors(self):
        """Flavours that are on the menu right now. Used by the website."""
        return self.search([("available", "=", True)])
