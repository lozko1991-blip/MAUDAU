import unittest
import lxml.etree as ET
import os
import re
from markup_config import is_forced_out_of_stock

FEED_FILE = "maudau_feed.xml"
VALID_PREFIXES = ("321_", "1000_", "2010_", "3001_", "9999_", "5555_", "3333_", "1100_", "7777_")
VALID_CAT_PREFIXES = ("321_", "1000_", "2010_", "3001_", "9999_", "5555_", "3333_", "1100_", "7777_", "1200")

class TestMaudauFeed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.feed_exists = os.path.exists(FEED_FILE)
        
    def test_file_exists_and_non_empty(self):
        if not self.feed_exists:
            self.skipTest(f"Feed file {FEED_FILE} not created yet")
        size = os.path.getsize(FEED_FILE)
        self.assertGreater(size, 1024, "Feed file must be larger than 1KB")

    def test_xml_structure_and_root(self):
        if not self.feed_exists:
            self.skipTest("Feed file not created yet")
            
        parser = ET.XMLParser(huge_tree=True)
        with open(FEED_FILE, "rb") as f:
            tree = ET.parse(f, parser=parser)
            root = tree.getroot()
        self.assertEqual(root.tag, "yml_catalog")
        self.assertIn("date", root.attrib)
        
        shop = root.find("shop")
        self.assertIsNotNone(shop, "Root must contain <shop>")
        
        currencies = shop.find("currencies")
        self.assertIsNotNone(currencies, "<shop> must contain <currencies>")
        uah = currencies.find("./currency[@id='UAH']")
        self.assertIsNotNone(uah, "<currencies> must contain UAH")

    def test_categories_validity(self):
        if not self.feed_exists:
            self.skipTest("Feed file not created yet")
            
        parser = ET.XMLParser(huge_tree=True)
        with open(FEED_FILE, "rb") as f:
            tree = ET.parse(f, parser=parser)
            categories = tree.findall("./shop/categories/category")
        self.assertGreater(len(categories), 0, "Feed must contain categories")
        
        seen_ids = set()
        for c in categories:
            cid = c.get("id")
            self.assertTrue(bool(cid), "Category must have id")
            self.assertTrue(any(cid.startswith(p) for p in VALID_CAT_PREFIXES), f"Category ID {cid} must have a valid supplier prefix")
            self.assertNotIn(cid, seen_ids, f"Duplicate category id: {cid}")
            seen_ids.add(cid)
            name = c.text or ""
            self.assertTrue(bool(name.strip()), f"Category {cid} must have non-empty name")
            # Verify no HTML in category name
            self.assertIsNone(re.search(r'<[^>]+>', name))

    def test_sample_offers_validation(self):
        if not self.feed_exists:
            self.skipTest("Feed file not created yet")
            
        context = ET.iterparse(FEED_FILE, events=("end",), tag="offer")
        offer_count = 0
        
        for event, elem in context:
            offer_count += 1
            if offer_count > 1000: # test sample of up to 1000 offers
                break
                
            oid = elem.get("id")
            avail = elem.get("available")
            self.assertTrue(bool(oid), "Offer must have id")
            self.assertTrue(any(oid.startswith(p) for p in VALID_PREFIXES), f"Offer ID {oid} must have valid prefix")
            if not is_forced_out_of_stock(oid):
                self.assertEqual(avail, "true", f"Only in-stock items should be published (got {avail} for {oid})")
            else:
                self.assertEqual(avail, "false", f"Forced out-of-stock items must have available='false'")
            self.assertIsNone(re.search(r'[\s\u0400-\u04FF]', oid), f"Offer ID {oid} cannot contain Cyrillic or spaces")
            
            cat_el = elem.find("categoryId")
            self.assertIsNotNone(cat_el, f"Offer {oid} must have categoryId")
            self.assertTrue(any(cat_el.text.startswith(p) for p in VALID_CAT_PREFIXES), f"Category ID {cat_el.text} must have valid prefix")
            
            # Price threshold check
            price_el = elem.find("price")
            self.assertIsNotNone(price_el)
            price = float(price_el.text)
            if oid.startswith("321_") or oid.startswith("5555_"):
                self.assertGreaterEqual(price, 300.0, f"Offer {oid} price {price} must be >= 300")
            else:
                self.assertGreaterEqual(price, 350.0, f"Offer {oid} price {price} must be >= 350")
            
            # Price old > price if present
            old_p_el = elem.find("price_old")
            if old_p_el is not None and old_p_el.text:
                old_p = float(old_p_el.text)
                self.assertGreater(old_p, price, f"Offer {oid} price_old must be > price")
                
            # Pictures
            pics = elem.findall("picture")
            self.assertGreaterEqual(len(pics), 1, f"Offer {oid} must have at least 1 picture")
            self.assertLessEqual(len(pics), 12, f"Offer {oid} must have at most 12 pictures")
            for pic in pics:
                purl = pic.text or ""
                self.assertNotIn(" ", purl, f"Picture URL cannot contain spaces: {purl}")
                self.assertIsNone(re.search(r'[\u0400-\u04FF]', purl), f"Picture URL cannot contain Cyrillic: {purl}")
                
            # Name UA - no HTML
            name_ua_el = elem.find("name_ua")
            self.assertIsNotNone(name_ua_el, f"Offer {oid} must have name_ua")
            name_ua = name_ua_el.text or ""
            self.assertLessEqual(len(name_ua), 255)
            self.assertIsNone(re.search(r'<[^>]+>', name_ua), f"Offer {oid} name_ua must not contain HTML")
            
            # Param count >= 3, no duplicates
            params = elem.findall("param")
            self.assertGreaterEqual(len(params), 3, f"Offer {oid} must have at least 3 params (got {len(params)})")
            param_names = [p.get("name") for p in params]
            self.assertEqual(len(param_names), len(set(param_names)), f"Offer {oid} has duplicate param names")
            for p in params:
                pname = p.get("name") or ""
                pval = p.text or ""
                self.assertTrue(bool(pname.strip()), f"Offer {oid} param name cannot be empty")
                self.assertTrue(bool(pval.strip()), f"Offer {oid} param value cannot be empty")
                self.assertIsNone(re.search(r'<[^>]+>', pname), f"Param name cannot contain HTML: {pname}")
                self.assertIsNone(re.search(r'<[^>]+>', pval), f"Param value cannot contain HTML: {pval}")
                
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]

        self.assertGreater(offer_count, 0, "Feed must contain offers")

if __name__ == "__main__":
    unittest.main()
