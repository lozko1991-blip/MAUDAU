import json
import os
from typing import Dict, Tuple, Optional

CATEGORY_MAP: Dict[str, dict] = {}

def load_category_mapping(path: str = "category_mapping.json"):
    global CATEGORY_MAP
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(__file__), path)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            CATEGORY_MAP = json.load(f)
    else:
        CATEGORY_MAP = {}

# Initial load
load_category_mapping()

def get_category_info(cat_id: str, default_name: str = "") -> Tuple[str, Optional[str]]:
    """
    Повертає: (name_ua, portal_id)
    Якщо категорія є в словнику - повертає українську назву та portal_id.
    Підтримує як прямий пошук за повним префіксованим ID, так і fallback за числовим ID.
    """
    cat_id_str = str(cat_id).strip()
    if cat_id_str in CATEGORY_MAP:
        info = CATEGORY_MAP[cat_id_str]
        return info.get("name_ua", default_name), info.get("portal_id")

    if "_" in cat_id_str:
        raw = cat_id_str.split("_", 1)[1]
        if raw in CATEGORY_MAP:
            info = CATEGORY_MAP[raw]
            return info.get("name_ua", default_name), info.get("portal_id")
    else:
        for prefix in ["321_", "1000_", "2010_", "3001_"]:
            prefixed = f"{prefix}{cat_id_str}"
            if prefixed in CATEGORY_MAP:
                info = CATEGORY_MAP[prefixed]
                return info.get("name_ua", default_name), info.get("portal_id")

    return default_name, None

def format_category_xml(cat_id: str, name_ua: str, portal_id: Optional[str] = None, parent_id: Optional[str] = None) -> str:
    """
    Форматує рядок <category> під стандарт MAUDAU:
    <category id="123" portal_id="456">Назва</category>
    """
    portal_attr = f' portal_id="{portal_id}"' if portal_id else ""
    parent_attr = f' parentId="{parent_id}"' if parent_id else ""
    clean_name = name_ua.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").strip()
    return f'<category id="{cat_id}"{parent_attr}{portal_attr}>{clean_name}</category>'
