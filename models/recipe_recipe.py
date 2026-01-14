from odoo import api, fields, models


class RecipeCategory(models.Model):
    _name = "recipe.category"
    _description = "Recipe Category"
    _parent_name = "parent_id"
    _parent_store = True
    _order = "name"

    name = fields.Char(string="Name", required=True)
    parent_id = fields.Many2one(
        "recipe.category",
        string="Parent Category",
        index=True,
        ondelete="cascade",
    )
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many("recipe.category", "parent_id", string="Child Categories")
    recipe_count = fields.Integer(string="Recipes", compute="_compute_recipe_count")

    def _compute_recipe_count(self):
        for category in self:
            category.recipe_count = self.env["recipe.recipe"].search_count(
                [("category_id", "=", category.id)]
            )


class Recipe(models.Model):
    _name = "recipe.recipe"
    _description = "Recipe"
    _order = "name"

    name = fields.Char(string="Name", required=True)
    code = fields.Char(string="Code", index=True)
    image = fields.Binary(string="Image", attachment=True)
    category_id = fields.Many2one("recipe.category", string="Category", index=True)
    product_id = fields.Many2one(
        "product.product",
        string="Linked Product",
        help="Used by Update Product Cost to set the product standard cost.",
    )
    portions = fields.Integer(string="Portions", default=1)
    description = fields.Text(string="Description")
    instructions = fields.Html(string="Instructions")
    active = fields.Boolean(string="Active", default=True)

    # Recipe lines
    line_ids = fields.One2many("recipe.recipe.line", "recipe_id", string="Ingredients")

    # Cost fields - computed
    ingredient_cost = fields.Float(
        string="Ingredient Cost",
        compute="_compute_costs",
        store=True,
        digits="Product Price",
    )

    # Time-based costs
    labor_hours = fields.Float(string="Labor Hours", default=0)
    energy_hours = fields.Float(string="Energy Hours", default=0)
    labor_cost = fields.Float(
        string="Labor Cost",
        compute="_compute_costs",
        store=True,
        digits="Product Price",
    )
    energy_cost = fields.Float(
        string="Energy Cost",
        compute="_compute_costs",
        store=True,
        digits="Product Price",
    )

    # Manual costs
    packaging_cost = fields.Float(string="Packaging Cost", digits="Product Price")
    extra_cost = fields.Float(string="Extra Cost", digits="Product Price")

    # Totals
    total_cost = fields.Float(
        string="Total (without Labor)",
        compute="_compute_costs",
        store=True,
        digits="Product Price",
        help="Ingredients + Energy + Packaging + Extra (excludes Labor)",
    )
    grand_total = fields.Float(
        string="Grand Total",
        compute="_compute_costs",
        store=True,
        digits="Product Price",
        help="Total including Labor",
    )
    cost_per_portion = fields.Float(
        string="Cost per Portion (with Labor)",
        compute="_compute_costs",
        store=True,
        digits="Product Price",
        help="Grand Total divided by portions",
    )
    cost_per_portion_no_labor = fields.Float(
        string="Cost per Portion (no Labor)",
        compute="_compute_costs",
        store=True,
        digits="Product Price",
        help="Total without labor divided by portions",
    )

    _sql_constraints = [
        ("code_unique", "unique(code)", "Recipe code must be unique!"),
    ]

    @api.depends(
        "line_ids.cost",
        "labor_hours",
        "energy_hours",
        "packaging_cost",
        "extra_cost",
        "portions",
    )
    def _compute_costs(self):
        # Get rates from config
        labor_rate = float(
            self.env["ir.config_parameter"].sudo().get_param(
                "chefrulo_recipe.labor_rate", "0"
            )
        )
        energy_rate = float(
            self.env["ir.config_parameter"].sudo().get_param(
                "chefrulo_recipe.energy_rate", "0"
            )
        )

        for recipe in self:
            # Ingredient cost from lines
            ingredient_cost = sum(recipe.line_ids.mapped("cost"))

            # Time-based costs
            labor_cost = recipe.labor_hours * labor_rate
            energy_cost = recipe.energy_hours * energy_rate

            # Total without labor (ingredients + energy + packaging + extra)
            total_cost = (
                ingredient_cost
                + energy_cost
                + recipe.packaging_cost
                + recipe.extra_cost
            )

            # Grand total (including labor)
            grand_total = total_cost + labor_cost

            # Cost per portion (no labor)
            cost_per_portion_no_labor = (
                total_cost / recipe.portions if recipe.portions else 0
            )

            # Cost per portion (with labor)
            cost_per_portion = grand_total / recipe.portions if recipe.portions else 0

            recipe.ingredient_cost = ingredient_cost
            recipe.labor_cost = labor_cost
            recipe.energy_cost = energy_cost
            recipe.total_cost = total_cost
            recipe.grand_total = grand_total
            recipe.cost_per_portion = cost_per_portion
            recipe.cost_per_portion_no_labor = cost_per_portion_no_labor

    def action_recompute_costs(self):
        """Manual action to recompute costs."""
        self._compute_costs()
        return True

    def action_update_product_cost(self):
        """Copy cost per portion (with labor) to linked product standard_price."""
        for recipe in self:
            if recipe.product_id:
                recipe.product_id.sudo().write(
                    {"standard_price": recipe.cost_per_portion}
                )
        return True


class RecipeRecipeLine(models.Model):
    _name = "recipe.recipe.line"
    _description = "Recipe Line"
    _order = "sequence, id"

    sequence = fields.Integer(string="Sequence", default=10)
    recipe_id = fields.Many2one(
        "recipe.recipe", string="Recipe", required=True, ondelete="cascade"
    )
    ingredient_id = fields.Many2one("recipe.ingredient", string="Ingredient")
    sub_recipe_id = fields.Many2one("recipe.recipe", string="Sub-Recipe")
    quantity = fields.Float(string="Quantity", required=True, default=1)
    uom_id = fields.Many2one("uom.uom", string="Unit of Measure", required=True)
    cost = fields.Float(
        string="Cost", compute="_compute_cost", store=True, digits="Product Price"
    )

    @api.depends("ingredient_id", "sub_recipe_id", "quantity", "uom_id")
    def _compute_cost(self):
        for line in self:
            cost = 0
            if line.ingredient_id and line.quantity:
                # Convert quantity to ingredient's UoM and calculate cost
                if line.uom_id and line.ingredient_id.uom_id:
                    try:
                        qty_in_ingredient_uom = line.uom_id._compute_quantity(
                            line.quantity, line.ingredient_id.uom_id
                        )
                        cost = qty_in_ingredient_uom * line.ingredient_id.price
                    except Exception:
                        # If UoM conversion fails, use direct multiplication
                        cost = line.quantity * line.ingredient_id.price
                else:
                    cost = line.quantity * line.ingredient_id.price
            elif line.sub_recipe_id and line.quantity:
                # Sub-recipe cost (use total_cost of sub-recipe × quantity)
                cost = line.quantity * line.sub_recipe_id.total_cost
            line.cost = cost

    @api.onchange("ingredient_id")
    def _onchange_ingredient_id(self):
        if self.ingredient_id:
            self.uom_id = self.ingredient_id.uom_id
            self.sub_recipe_id = False

    @api.onchange("sub_recipe_id")
    def _onchange_sub_recipe_id(self):
        if self.sub_recipe_id:
            self.ingredient_id = False
            # Default UoM for sub-recipes is "Units"
            unit_uom = self.env.ref("uom.product_uom_unit", raise_if_not_found=False)
            if unit_uom:
                self.uom_id = unit_uom
