import unittest
from param_normalizer import (
    normalize_param_name,
    normalize_param_value,
    normalize_parameters,
    strip_html
)

class TestParamNormalizer(unittest.TestCase):
    def test_name_normalization(self):
        self.assertEqual(normalize_param_name("Цвет"), "Колір")
        self.assertEqual(normalize_param_name("Спальный размер"), "Спальний розмір")
        self.assertEqual(normalize_param_name("Материал"), "Матеріал")
        self.assertEqual(normalize_param_name("Материал", portal_id="271"), "Матеріал сковороди")

    def test_value_normalization(self):
        # Official MAUDAU values
        self.assertEqual(normalize_param_value("Двуспальные"), "Двоспальні")
        self.assertEqual(normalize_param_value("Евро"), "Євро")
        self.assertEqual(normalize_param_value("Хлопок"), "Бавовна")

    def test_html_stripping(self):
        self.assertEqual(strip_html("<b>Червоний</b>"), "Червоний")
        self.assertEqual(normalize_param_name("<span>Цвет</span>"), "Колір")

    def test_deduplication(self):
        params = [
            ("Цвет", "Белый"),
            ("Цвет корпуса", "Черный")
        ]
        res = normalize_parameters(params)
        names = [p[0] for p in res]
        self.assertEqual(names.count("Колір"), 1)

    def test_minimum_three_params_guarantee(self):
        # Product with only 1 parameter initially
        params = [
            ("Диаметр", "24 см")
        ]
        res = normalize_parameters(params, vendor="Tefal", country="Франція")
        self.assertGreaterEqual(len(res), 3)
        names = [p[0] for p in res]
        self.assertIn("Діаметр", names)
        self.assertIn("Стан", names)
        self.assertIn("Бренд", names)

if __name__ == "__main__":
    unittest.main()
