import lxml.etree as ET
import json
import os

def build_dict():
    files = [
        "merchant_categories_2026-10-13-1733.xml",
        "merchant_categories_2026-10-13-1743.xml"
    ]
    
    attr_names = set()
    val_map = {}
    cat_expected_attrs = {}
    
    for fname in files:
        if not os.path.exists(fname):
            print(f"[WARN] File not found: {fname}")
            continue
        print(f"Reading {fname}...")
        context = ET.iterparse(fname, events=("end",), tag="category")
        for event, elem in context:
            pid = elem.get("portal_id")
            name_uk = elem.get("nameUK")
            cat_attrs = []
            
            for a in elem.findall("attribute"):
                aname = a.get("nameUK")
                if aname:
                    aname = aname.strip()
                    attr_names.add(aname)
                    cat_attrs.append(aname)
                for v in a.findall("attribute_value"):
                    v_ru = v.get("nameRU")
                    v_uk = v.get("nameUK")
                    if v_ru and v_uk:
                        val_map[v_ru.strip()] = v_uk.strip()
            
            if pid:
                cat_expected_attrs[pid] = {
                    "name_uk": name_uk,
                    "attributes": cat_attrs
                }
            elem.clear()

    out_data = {
        "attribute_names": sorted(list(attr_names)),
        "values_ru_to_uk": val_map,
        "category_expected_attributes": cat_expected_attrs
    }
    
    with open("maudau_dict.json", "w", encoding="utf-8") as f:
        json.dump(out_data, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully created maudau_dict.json:")
    print(f" - Unique attribute names: {len(attr_names)}")
    print(f" - Value translations (RU->UK): {len(val_map)}")
    print(f" - Categories with schemas: {len(cat_expected_attrs)}")

if __name__ == "__main__":
    build_dict()
