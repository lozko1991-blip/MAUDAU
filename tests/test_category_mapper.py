import unittest
from category_mapper import get_category_info, format_category_xml, load_category_mapping

class TestCategoryMapper(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_category_mapping()

    def test_mapped_category(self):
        # 14975 is Сковороды
        name_ua, portal_id = get_category_info("14975")
        self.assertEqual(name_ua, "Сковороди")
        self.assertEqual(portal_id, "271")

    def test_unmapped_fallback(self):
        name_ua, portal_id = get_category_info("99999999999", default_name="Резервна категорія")
        self.assertEqual(name_ua, "Резервна категорія")
        self.assertIsNone(portal_id)

    def test_format_xml_with_portal_id(self):
        xml = format_category_xml("14975", "Сковороди", portal_id="271")
        self.assertEqual(xml, '<category id="14975" portal_id="271">Сковороди</category>')

    def test_format_xml_without_portal_id(self):
        xml = format_category_xml("12345", "Нові товари")
        self.assertEqual(xml, '<category id="12345">Нові товари</category>')

    def test_format_xml_with_prefix_321(self):
        xml = format_category_xml("321_14975", "Сковороди", portal_id="271", parent_id="321_1000")
        self.assertEqual(xml, '<category id="321_14975" parentId="321_1000" portal_id="271">Сковороди</category>')

    def test_websklad_mapped_categories(self):
        # Blenders
        name_ua, pid = get_category_info("9999_274548020")
        self.assertEqual(pid, "1686")
        # Dual key parity for unprefixed
        name_raw, pid_raw = get_category_info("274548020")
        self.assertEqual(pid_raw, "1686")
        self.assertEqual(name_ua, name_raw)

        # Kids playpens / tents
        _, pid_tent = get_category_info("9999_3581823412")
        self.assertEqual(pid_tent, "104")

        # Kids strollers
        _, pid_stroller = get_category_info("9999_1744618505")
        self.assertEqual(pid_stroller, "158")

        # 3D pens
        _, pid_3dpen = get_category_info("9999_1174147754")
        self.assertEqual(pid_3dpen, "149")

        # Skmei watches
        _, pid_skmei = get_category_info("9999_2393578841")
        self.assertEqual(pid_skmei, "2389")

    def test_posudograd_mapped_categories(self):
        # Shot glasses / чарки
        name_ua, pid = get_category_info("7777_70")
        self.assertEqual(pid, "1446")
        # Dual key parity
        name_raw, pid_raw = get_category_info("70")
        self.assertEqual(pid_raw, "1446")
        self.assertEqual(name_ua, name_raw)

        # Stemware / келихи
        _, pid_glasses = get_category_info("7777_82")
        self.assertEqual(pid_glasses, "279")

        # Kitchen knives
        _, pid_knives = get_category_info("7777_104")
        self.assertEqual(pid_knives, "584")

        # Cookware pots
        _, pid_pots = get_category_info("7777_106")
        self.assertEqual(pid_pots, "580")

        # Baby feeding bottles
        _, pid_bottles = get_category_info("7777_314")
        self.assertEqual(pid_bottles, "38")

        # Decorative figurines
        _, pid_figurines = get_category_info("7777_310")
        self.assertEqual(pid_figurines, "570")

    def test_forus_mapped_categories(self):
        # Cosmetic bags / косметички
        name_ua, pid = get_category_info("1100_00710")
        self.assertEqual(pid, "1177")
        # Dual key parity
        name_raw, pid_raw = get_category_info("00710")
        self.assertEqual(pid_raw, "1177")
        self.assertEqual(name_ua, name_raw)

        # Camp burners
        _, pid_burners = get_category_info("1100_0079")
        self.assertEqual(pid_burners, "1171")

        # Mugs / cups
        _, pid_cups = get_category_info("1100_007108")
        self.assertEqual(pid_cups, "276")

        # Aprons
        _, pid_aprons = get_category_info("1100_007170")
        self.assertEqual(pid_aprons, "1533")

        # Doormats
        _, pid_mats = get_category_info("1100_007243")
        self.assertEqual(pid_mats, "1530")

        # Electric kettles
        _, pid_kettles = get_category_info("1100_007387")
        self.assertEqual(pid_kettles, "1675")

if __name__ == "__main__":
    unittest.main()
