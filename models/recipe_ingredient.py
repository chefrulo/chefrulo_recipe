from odoo import api, fields, models


class RecipeIngredientCategory(models.Model):
    _name = "recipe.ingredient.category"
    _description = "Ingredient Category"
    _parent_name = "parent_id"
    _parent_store = True
    _order = "name"

    name = fields.Char(string="Name", required=True)
    parent_id = fields.Many2one(
        "recipe.ingredient.category",
        string="Parent Category",
        index=True,
        ondelete="cascade",
    )
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many(
        "recipe.ingredient.category", "parent_id", string="Child Categories"
    )
    ingredient_count = fields.Integer(
        string="Ingredients", compute="_compute_ingredient_count"
    )

    def _compute_ingredient_count(self):
        for category in self:
            category.ingredient_count = self.env["recipe.ingredient"].search_count(
                [("category_id", "=", category.id)]
            )


class RecipeIngredient(models.Model):
    _name = "recipe.ingredient"
    _description = "Recipe Ingredient"
    _order = "name"

    name = fields.Char(string="Name", required=True)
    code = fields.Char(string="Code", index=True)
    category_id = fields.Many2one(
        "recipe.ingredient.category", string="Category", index=True
    )
    uom_id = fields.Many2one(
        "uom.uom", string="Unit of Measure", required=True
    )
    price = fields.Float(string="Price", digits="Product Price")
    price_date = fields.Date(string="Price Date")
    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        domain="[('supplier_rank', '>', 0)]",
        help="Select a supplier from contacts",
    )
    active = fields.Boolean(string="Active", default=True)
    notes = fields.Text(string="Notes")

    _sql_constraints = [
        ("code_unique", "unique(code)", "Ingredient code must be unique!"),
    ]

    def name_get(self):
        result = []
        for ingredient in self:
            name = ingredient.name
            if ingredient.code:
                name = f"[{ingredient.code}] {name}"
            result.append((ingredient.id, name))
        return result

    @api.model
    def _name_search(self, name, domain=None, operator="ilike", limit=None, order=None):
        domain = domain or []
        if name:
            domain = ["|", ("code", operator, name), ("name", operator, name)] + domain
        return self._search(domain, limit=limit, order=order)
