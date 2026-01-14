{
    "name": "Recipe & Cost Management",
    "version": "17.0.1.0.0",
    "summary": "Manage recipes, ingredients and calculate costs",
    "description": """
        Recipe and Cost Management for Food Business
        =============================================

        Features:
        - Ingredient management with categories
        - CSV import for ingredient prices
        - Recipe creation with sub-recipes support
        - Cost calculation: ingredients, labor, energy, packaging, extras
        - Configurable labor and energy rates
        - Cost per portion calculation
    """,
    "category": "Food",
    "author": "Chefrulo",
    "license": "LGPL-3",
    "depends": ["base", "uom", "base_setup", "product"],
    "data": [
        "security/ir.model.access.csv",
        "data/recipe_category_data.xml",
        "views/recipe_ingredient_views.xml",
        "views/recipe_recipe_views.xml",
        "views/report_recipe.xml",
        "report/recipe_report.xml",
        "views/res_config_settings_views.xml",
        "wizard/ingredient_import_views.xml",
        "views/recipe_menus.xml",
    ],
    "installable": True,
    "application": True,
}
