import unittest
from category_mapper import get_category_info, format_category_xml

class TestCategoryMapper(unittest.TestCase):
    def test_mapped_category(self):
        # 14975 is Сковороды
        name_ua, portal_id = get_category_info("14975")
        self.assertEqual(name_ua, "Сковороди")
        self.assertEqual(portal_id, "271")

    def test_unmapped_fallback(self):
        name_ua, portal_id = get_category_info("99999999", default_name="Резервна категорія")
        self.assertEqual(name_ua, "Резервна категорія")
        self.assertIsNone(portal_id)

    def test_format_xml_with_portal_id(self):
        xml = format_category_xml("14975", "Сковороди", portal_id="271")
        self.assertEqual(xml, '<category id="14975" portal_id="271">Сковороди</category>')

    def test_format_xml_without_portal_id(self):
        xml = format_category_xml("12345", "Нові товари")
        self.assertEqual(xml, '<category id="12345">Нові товари</category>')

if __name__ == "__main__":
    unittest.main()
