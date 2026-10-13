# Конфігурація націнок, фільтрів та правил виключення для MAUDAU

SUPPLIER_CONFIGS = {
    "crm.yavshoke.ua": {
        "name": "yavshoke",
        "markup_percent": 1.30,      # +30%
        "markup_fixed": 50,          # +50 грн
        "min_price_final": 300.0,    # Тільки товари, де фінальна ціна на MAUDAU >= 300 грн
        "old_price_multiplier": 1.25, # price_old = price * 1.25 (знижка 20%)
        "id_prefix": "yav_",         # Префікс для унікальності offer id
    }
}

# Категорії, які суворо заборонено публікувати з yavshoke
# 40863 - Ролеты, 42166 - Ролеты закрытого типа, 42165 - Ролеты открытого типа
# 15041 - Тарелки и пиалы, 15055 - Детские тарелки и пиалы
EXCLUDED_CATEGORY_IDS = {
    "40863", "42166", "42165",
    "15041", "15055"
}

# Ключові слова для додаткової фільтрації ролетів та тарілок
EXCLUDED_KEYWORDS = [
    "ролет", "роллет", "рулонн",
    "тарілк", "тарелк"
]

def calculate_prices(domain: str, raw_price: float):
    """
    Розрахунок фінальної та старої ціни за формулою постачальника.
    Повертає: (final_price, old_price, is_allowed)
    """
    config = SUPPLIER_CONFIGS.get(domain, SUPPLIER_CONFIGS["crm.yavshoke.ua"])
    
    if raw_price <= 0:
        return 0, 0, False
        
    final_price = round(raw_price * config["markup_percent"] + config["markup_fixed"])
    
    # Фільтр мінімальної фінальної ціни
    if final_price < config["min_price_final"]:
        return final_price, 0, False
        
    old_price = round(final_price * config["old_price_multiplier"])
    if old_price <= final_price:
        old_price = final_price + 50
        
    return final_price, old_price, True

def is_category_excluded(cat_id: str, cat_name: str = "", product_title: str = "") -> bool:
    """
    Перевірка чи категорія або товар підпадає під заборону (ролети, тарілки).
    """
    if str(cat_id).strip() in EXCLUDED_CATEGORY_IDS:
        return True
        
    name_lower = (cat_name or "").lower()
    for kw in EXCLUDED_KEYWORDS:
        if kw in name_lower:
            return True
            
    title_lower = (product_title or "").lower()
    for kw in EXCLUDED_KEYWORDS:
        if kw in title_lower:
            return True
            
    return False
