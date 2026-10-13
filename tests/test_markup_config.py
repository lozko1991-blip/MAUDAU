import unittest
from markup_config import calculate_prices, is_category_excluded

class TestMarkupConfig(unittest.TestCase):
    def test_price_calculation_allowed(self):
        final_p, old_p, allowed = calculate_prices("crm.yavshoke.ua", 200.0)
        self.assertTrue(allowed)
        self.assertEqual(final_p, 310)
        self.assertGreater(old_p, final_p)

    def test_price_calculation_below_threshold(self):
        final_p, old_p, allowed = calculate_prices("crm.yavshoke.ua", 150.0)
        self.assertFalse(allowed)
        self.assertEqual(final_p, 245)

    def test_category_excluded_by_id(self):
        self.assertTrue(is_category_excluded("40863"))
        self.assertTrue(is_category_excluded("42166"))
        self.assertTrue(is_category_excluded("42165"))
        self.assertTrue(is_category_excluded("15041"))
        self.assertTrue(is_category_excluded("15055"))

    def test_category_excluded_by_keyword(self):
        self.assertTrue(is_category_excluded("99999", cat_name="Тканинні ролети день-ніч"))
        self.assertTrue(is_category_excluded("99999", product_title="Тарілка десертна біла"))

    def test_category_allowed(self):
        self.assertFalse(is_category_excluded("14975", cat_name="Сковороди", product_title="Сковорода Tefal 24 см"))

if __name__ == "__main__":
    unittest.main()
