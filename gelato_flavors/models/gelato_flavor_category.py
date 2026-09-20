from odoo import fields, models


class GelatoFlavorCategory(models.Model):
    _name = "gelato.flavor.category"
    _description = "Flavour Category"
    _order = "sequence, name"

    name = fields.Char(
        string="Name",
        required=True,
        translate=True,
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )
    color = fields.Char(
        string="Colour",
        default="#84c5c3",
        help="Colour of the dot shown next to flavours on the website. "
        "Use a HEX value, for example #84c5c3.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
    )
    flavor_ids = fields.One2many(
        comodel_name="gelato.flavor",
        inverse_name="category_id",
        string="Flavours",
    )
    flavor_count = fields.Integer(
        # A different label from flavor_ids above on purpose: two fields
        # with the same one confuse the place that shows them, and Odoo
        # says so out loud on every install.
        string="How many flavours",
        compute="_compute_flavor_count",
    )

    _sql_constraints = [
        (
            "name_uniq",
            "unique(name)",
            "A category with this name already exists.",
        ),
    ]

    def _compute_flavor_count(self):
        data = self.env["gelato.flavor"]._read_group(
            [("category_id", "in", self.ids)],
            groupby=["category_id"],
            aggregates=["__count"],
        )
        counts = {category.id: count for category, count in data}
        for record in self:
            record.flavor_count = counts.get(record.id, 0)
