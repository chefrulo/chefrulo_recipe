import base64
import csv
import io
from datetime import datetime

from odoo import api, fields, models
from odoo.exceptions import UserError


class IngredientImport(models.TransientModel):
    _name = "recipe.ingredient.import"
    _description = "Import Ingredients from CSV"

    file = fields.Binary(string="CSV File", required=True)
    filename = fields.Char(string="Filename")
    delimiter = fields.Selection(
        [(",", "Comma (,)"), (";", "Semicolon (;)"), ("\t", "Tab")],
        string="Delimiter",
        default=",",
    )
    result_message = fields.Text(string="Result", readonly=True)
    state = fields.Selection(
        [("draft", "Draft"), ("done", "Done")],
        string="State",
        default="draft",
    )

    # UoM mapping dictionary
    UOM_MAPPING = {
        "kg": "uom.product_uom_kgm",
        "kilo": "uom.product_uom_kgm",
        "kilogram": "uom.product_uom_kgm",
        "g": "uom.product_uom_gram",
        "gram": "uom.product_uom_gram",
        "l": "uom.product_uom_litre",
        "liter": "uom.product_uom_litre",
        "litre": "uom.product_uom_litre",
        "ml": "uom.product_uom_millilitre",
        "milliliter": "uom.product_uom_millilitre",
        "millilitre": "uom.product_uom_millilitre",
        "unit": "uom.product_uom_unit",
        "units": "uom.product_uom_unit",
        "pcs": "uom.product_uom_unit",
        "piece": "uom.product_uom_unit",
        "dozen": "uom.product_uom_dozen",
    }

    def _get_uom(self, uom_name):
        """Find UoM by name or mapping."""
        if not uom_name:
            return False

        uom_name_lower = uom_name.lower().strip()

        # Check mapping first
        if uom_name_lower in self.UOM_MAPPING:
            xmlid = self.UOM_MAPPING[uom_name_lower]
            uom = self.env.ref(xmlid, raise_if_not_found=False)
            if uom:
                return uom

        # Search by name
        uom = self.env["uom.uom"].search(
            [("name", "=ilike", uom_name)], limit=1
        )
        return uom

    def _get_or_create_category(self, category_name):
        """Find or create ingredient category."""
        if not category_name:
            return False

        category = self.env["recipe.ingredient.category"].search(
            [("name", "=ilike", category_name.strip())], limit=1
        )
        if not category:
            category = self.env["recipe.ingredient.category"].create(
                {"name": category_name.strip()}
            )
        return category

    def _get_or_create_supplier(self, supplier_name):
        """Find or create supplier partner."""
        if not supplier_name:
            return False

        partner = self.env["res.partner"].search(
            [("name", "=ilike", supplier_name.strip())], limit=1
        )
        if not partner:
            partner = self.env["res.partner"].create({
                "name": supplier_name.strip(),
            })
        return partner

    def _parse_date(self, date_str):
        """Parse date from various formats."""
        if not date_str:
            return False

        date_formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        return False

    def action_import(self):
        """Import ingredients from CSV file."""
        self.ensure_one()

        if not self.file:
            raise UserError("Please select a CSV file to import.")

        # Decode file
        try:
            csv_data = base64.b64decode(self.file).decode("utf-8")
        except UnicodeDecodeError:
            csv_data = base64.b64decode(self.file).decode("latin-1")

        # Parse CSV
        reader = csv.DictReader(
            io.StringIO(csv_data), delimiter=self.delimiter
        )

        # Normalize headers (lowercase, strip)
        if reader.fieldnames:
            reader.fieldnames = [h.lower().strip() for h in reader.fieldnames]

        created = 0
        updated = 0
        errors = []
        row_num = 1

        Ingredient = self.env["recipe.ingredient"]

        for row in reader:
            row_num += 1
            try:
                # Get values from row
                code = row.get("code", "").strip()
                name = row.get("name", "").strip()
                category_name = row.get("category", "").strip()
                price_str = row.get("price", "0").strip()
                uom_name = row.get("uom", row.get("unit", "")).strip()
                supplier_name = row.get("supplier", "").strip()
                date_str = row.get("date", "").strip()

                # Validate required fields
                if not name:
                    errors.append(f"Row {row_num}: Missing name")
                    continue

                if not uom_name:
                    errors.append(f"Row {row_num}: Missing unit of measure")
                    continue

                # Parse price
                try:
                    price = float(price_str.replace(",", "."))
                except ValueError:
                    errors.append(f"Row {row_num}: Invalid price '{price_str}'")
                    continue

                # Find UoM
                uom = self._get_uom(uom_name)
                if not uom:
                    errors.append(f"Row {row_num}: Unknown UoM '{uom_name}'")
                    continue

                # Find or create category
                category = self._get_or_create_category(category_name) if category_name else False

                # Find or create supplier
                supplier = self._get_or_create_supplier(supplier_name) if supplier_name else False

                # Parse date
                price_date = self._parse_date(date_str) or fields.Date.today()

                # Find existing ingredient by code or name
                ingredient = False
                if code:
                    ingredient = Ingredient.search([("code", "=", code)], limit=1)
                if not ingredient:
                    ingredient = Ingredient.search([("name", "=ilike", name)], limit=1)

                # Prepare values
                vals = {
                    "name": name,
                    "price": price,
                    "uom_id": uom.id,
                    "price_date": price_date,
                }
                if code:
                    vals["code"] = code
                if category:
                    vals["category_id"] = category.id
                if supplier:
                    vals["supplier_id"] = supplier.id

                # Create or update
                if ingredient:
                    ingredient.write(vals)
                    updated += 1
                else:
                    Ingredient.create(vals)
                    created += 1

            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")

        # Build result message
        result_lines = [
            f"Import completed!",
            f"Created: {created}",
            f"Updated: {updated}",
        ]
        if errors:
            result_lines.append(f"\nErrors ({len(errors)}):")
            result_lines.extend(errors[:20])  # Show first 20 errors
            if len(errors) > 20:
                result_lines.append(f"... and {len(errors) - 20} more errors")

        self.result_message = "\n".join(result_lines)
        self.state = "done"

        return {
            "type": "ir.actions.act_window",
            "res_model": "recipe.ingredient.import",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
