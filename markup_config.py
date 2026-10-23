# Конфігурація націнок, фільтрів та правил виключення для MAUDAU

SUPPLIER_CONFIGS = {
    "crm.yavshoke.ua": {
        "name": "yavshoke",
        "markup_percent": 1.30,       # +30%
        "markup_fixed": 50,           # +50 грн
        "min_price_final": 300.0,     # Тільки товари, де фінальна ціна на MAUDAU >= 300 грн
        "old_price_multiplier": 1.25, # price_old = price * 1.25 (знижка 20%)
        "id_prefix": "321_",          # Префікс для унікальності offer id та категорій
    },
    "opt-drop.com": {
        "name": "opt-drop",
        "markup_percent": 1.35,       # +35%
        "markup_fixed": 50,           # +50 грн
        "min_price_final": 350.0,     # Тільки товари, де фінальна ціна на MAUDAU >= 350 грн
        "old_price_multiplier": 1.25,
        "id_prefix": "1000_",         # Префікс 1000 для offer id та категорій
    },
    "dropt.in.ua": {
        "name": "dropt",
        "markup_percent": 1.20,       # +20%
        "markup_fixed": 50,           # +50 грн
        "min_price_final": 350.0,     # Тільки товари, де фінальна ціна на MAUDAU >= 350 грн
        "old_price_multiplier": 1.25,
        "id_prefix": "2010_",         # Префікс 2010 для offer id та категорій
    },
    "aveon.net.ua": {
        "name": "aveon",
        "markup_percent": 1.15,       # +15%
        "markup_fixed": 50,           # +50 грн
        "min_price_final": 350.0,     # Тільки товари, де фінальна ціна на MAUDAU >= 350 грн
        "old_price_multiplier": 1.25,
        "id_prefix": "3001_",         # Префікс 3001 для offer id та категорій
    }
}

# Список товарів, які примусово знімаються з наявності на MAUDAU (available="false")
MANUAL_OUT_OF_STOCK_IDS = {
    "321_5155079", "5155079",  # Viluta Ранфорс 5 24290-E/3
    "321_5139163", "5139163",  # Viluta Ранфорс 5 24269-2-2
    "321_5139161", "5139161",  # Viluta Ранфорс 4 24259-2-2
    "321_5139167", "5139167",  # Viluta Ранфорс 3 24288-2-2
}

def is_forced_out_of_stock(offer_id: str, raw_id: str = "") -> bool:
    """Перевіряє, чи повинен товар мати available='false' у фіді MAUDAU."""
    return str(offer_id).strip() in MANUAL_OUT_OF_STOCK_IDS or str(raw_id).strip() in MANUAL_OUT_OF_STOCK_IDS

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

def check_price_anomaly(title: str, raw_price: float, cat_id: str = "") -> tuple[bool, str]:
    """
    Захист від аномальних помилок/описок у прайсах постачальників:
    1. Постільна білизна (комплекти євро, двоспальні, сімейні, полуторні):
       Собівартість комплекту не може бути меншою за 600 грн (відсіює випадки,
       коли постачальник випадково ставить ціну наволочки чи забуває цифру попереду,
       як-от 232 грн замість 1090-1253 грн).
    2. Силове та кліматичне обладнання (генератори, інвертори): собівартість >= 500 грн.
    Повертає: (is_valid: bool, reason: str)
    """
    t = (title or "").lower()

    # 1. Комплекти постільної білизни
    if "постільна білизна" in t or "постельное белье" in t or "комплект білизни" in t or "комплект белья" in t:
        if raw_price < 600.0:
            return False, f"Аномально низька собівартість комплекту білизни ({raw_price} грн < 600 грн)"

    # 2. Генератори, інвертори, зарядні станції
    if any(k in t for k in ["генератор", "інвертор", "инвертор", "зарядна станція", "зарядная станция"]):
        if raw_price < 500.0:
            return False, f"Аномально низька собівартість силового обладнання ({raw_price} грн < 500 грн)"

    return True, "OK"

