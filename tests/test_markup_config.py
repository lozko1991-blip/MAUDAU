import unittest
from markup_config import calculate_prices, is_category_excluded, check_price_anomaly, is_forced_out_of_stock

class TestMarkupConfig(unittest.TestCase):
    def test_forced_out_of_stock(self):
        self.assertTrue(is_forced_out_of_stock("321_5155079"))
        self.assertTrue(is_forced_out_of_stock("5155079"))
        self.assertTrue(is_forced_out_of_stock("321_5139163"))
        self.assertFalse(is_forced_out_of_stock("321_9999999"))
    def test_price_anomaly_bedding_set(self):
        # 232 UAH for an euro bedding set is an anomaly and must be blocked
        allowed, reason = check_price_anomaly("Постільна білизна євро Viluta Ранфорс 5 24290-E/3 220х200 см", 232.0)
        self.assertFalse(allowed)
        self.assertIn("Аномально низька", reason)

        # 1090 UAH for an euro bedding set is valid and allowed
        allowed, reason = check_price_anomaly("Постільна білизна євро Viluta Ранфорс 5 24290-E/3 220х200 см", 1090.0)
        self.assertTrue(allowed)

        # Non-set bedding (single pillowcase or sheet) is allowed
        allowed, reason = check_price_anomaly("Простирадло на резинці Viluta 160х200х25 см", 250.0)
        self.assertTrue(allowed)

    def test_price_anomaly_power_equipment(self):
        allowed, reason = check_price_anomaly("Бензиновий генератор 3 кВт", 250.0)
        self.assertFalse(allowed)
        allowed, reason = check_price_anomaly("Бензиновий генератор 3 кВт", 8500.0)
        self.assertTrue(allowed)
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

    def test_supplier_prefix_321(self):
        from markup_config import SUPPLIER_CONFIGS
        self.assertEqual(SUPPLIER_CONFIGS["crm.yavshoke.ua"]["id_prefix"], "321_")
        self.assertEqual(SUPPLIER_CONFIGS["websklad.biz.ua"]["id_prefix"], "9999_")
        self.assertEqual(SUPPLIER_CONFIGS["dwn.royaltoys.com.ua"]["id_prefix"], "5555_")
        self.assertEqual(SUPPLIER_CONFIGS["feed.lugi.com.ua"]["id_prefix"], "3333_")
        self.assertEqual(SUPPLIER_CONFIGS["forus.com.ua"]["id_prefix"], "1100_")
        self.assertEqual(SUPPLIER_CONFIGS["posudograd.ua"]["id_prefix"], "7777_")

    def test_new_suppliers_price_calculation(self):
        # Lugi: +10% + 50 грн, 300 грн -> 300 * 1.10 + 50 = 380 грн
        final_p, old_p, allowed = calculate_prices("feed.lugi.com.ua", 300.0)
        self.assertTrue(allowed)
        self.assertEqual(final_p, 380)

        # RoyalToys: +35% + 50 грн, 200 грн -> 200 * 1.35 + 50 = 320 грн
        final_p, old_p, allowed = calculate_prices("dwn.royaltoys.com.ua", 200.0)
        self.assertTrue(allowed)
        self.assertEqual(final_p, 320)

        # Posudograd: +17% + 50 грн, 300 грн -> 300 * 1.17 + 50 = 401 грн
        final_p, old_p, allowed = calculate_prices("posudograd.ua", 300.0)
        self.assertTrue(allowed)
        self.assertEqual(final_p, 401)

if __name__ == "__main__":
    unittest.main()
