import json
import re
import os
from typing import List, Tuple, Dict, Optional

# Словник відображення російських назв характеристик на офіційні MAUDAU
PARAM_NAME_MAP = {
    "цвет": "Колір",
    "цвет корпуса": "Колір",
    "материал": "Матеріал",
    "материал ручки": "Матеріал ручки",
    "материал крышки": "Матеріал кришки",
    "материал корпуса": "Матеріал корпусу",
    "диаметр": "Діаметр",
    "диаметр, см": "Діаметр",
    "объем": "Об'єм",
    "объем, л": "Об'єм",
    "объем чаши": "Об'єм чаші",
    "покрытие": "Покриття",
    "антипригарное покрытие": "Антипригарне покриття",
    "размер": "Розмір",
    "размер, см": "Розмір",
    "спальный размер": "Спальний розмір",
    "размер наволочки": "Розмір наволочки",
    "размер простыни": "Розмір простирадла",
    "размер пододеяльника": "Розмір підковдри",
    "количество предметов": "Кількість предметів",
    "количество в упаковке": "Кількість в упаковці",
    "количество персон": "Кількість персон",
    "тип": "Тип",
    "вид": "Вид",
    "форма": "Форма",
    "назначение": "Призначення",
    "особенности": "Особливості",
    "упаковка": "Комплектація",
    "комплектация": "Комплектація",
    "вес": "Вага",
    "вес, кг": "Вага",
    "высота": "Висота",
    "длина": "Довжина",
    "ширина": "Ширина",
    "гарантия": "Гарантія",
    "страна-производитель": "Країна-виробник",
    "страна производитель": "Країна-виробник",
    "бренд": "Бренд",
    "производитель": "Бренд",
    "состояние": "Стан",
    "совместимость с источниками тепла": "Сумісність із джерелами тепла",
    "наличие крышки": "Наявність кришки",
    "застежка": "Застібка",
    "сезон": "Сезон",
}

MAUDAU_DICT = {}
LEGACY_TRANSLATIONS = {}

def load_dictionaries():
    global MAUDAU_DICT, LEGACY_TRANSLATIONS
    base_dir = os.path.dirname(__file__)
    
    # 1. MAUDAU compiled dictionary (11,844 values, 129 attributes)
    mpath = os.path.join(base_dir, "maudau_dict.json")
    if os.path.exists(mpath):
        with open(mpath, "r", encoding="utf-8") as f:
            MAUDAU_DICT = json.load(f)
            
    # 2. Legacy translations dictionary
    tpath = os.path.join(base_dir, "translations.json")
    if os.path.exists(tpath):
        with open(tpath, "r", encoding="utf-8") as f:
            LEGACY_TRANSLATIONS = json.load(f)

load_dictionaries()

def strip_html(text: str) -> str:
    """Видалення будь-яких HTML тегів."""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', ' ', text)
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()

def normalize_param_name(name_raw: str, portal_id: Optional[str] = None) -> str:
    """
    Приведення назви характеристики до офіційного стандарту MAUDAU.
    """
    clean = strip_html(name_raw).strip()
    low = clean.lower()
    
    # Категорійне уточнення
    if portal_id == "271" and low == "материал": # Сковороди
        return "Матеріал сковороди"
    if portal_id == "580" and low == "материал": # Каструлі
        return "Матеріал каструлі"
        
    # Прямий мапінг з таблиці
    if low in PARAM_NAME_MAP:
        return PARAM_NAME_MAP[low]
        
    # Якщо назва вже в списку офіційних атрибутів MAUDAU
    official_attrs = MAUDAU_DICT.get("attribute_names", [])
    for off in official_attrs:
        if off.lower() == low:
            return off
            
    # Fallback до legacy перекладів
    if clean in LEGACY_TRANSLATIONS:
        return LEGACY_TRANSLATIONS[clean]
        
    return clean

def normalize_param_value(val_raw: str) -> str:
    """
    Переклад та нормалізація значення характеристики за базою 11 844 слів MAUDAU.
    """
    clean = strip_html(val_raw).strip()
    if not clean:
        return ""
        
    val_map = MAUDAU_DICT.get("values_ru_to_uk", {})
    
    # 1. Точний збіг у базі MAUDAU
    if clean in val_map:
        return val_map[clean]
        
    # 2. Збіг без урахування регістру
    clean_low = clean.lower()
    for ru_val, uk_val in val_map.items():
        if ru_val.lower() == clean_low:
            return uk_val
            
    # 3. Fallback до legacy перекладів
    if clean in LEGACY_TRANSLATIONS:
        return LEGACY_TRANSLATIONS[clean]
        
    # 4. Базові заміни частих слів (якщо містить російські літери)
    ru_replacements = {
        "черный": "чорний",
        "белый": "білий",
        "красный": "червоний",
        "синий": "синій",
        "зеленый": "зелений",
        "желтый": "жовтий",
        "серый": "сірий",
        "хлопок": "бавовна",
        "чугун": "чавун",
        "стекло": "скло",
        "нержавеющая сталь": "нержавіюча сталь",
        "пластик": "пластик",
        "дерево": "дерево",
        "новое": "новий",
        "новый": "новий",
    }
    for r_word, u_word in ru_replacements.items():
        if r_word == clean_low:
            return u_word.capitalize()
            
    return clean

def normalize_parameters(
    raw_params: List[Tuple[str, str]],
    vendor: str = "",
    country: str = "",
    portal_id: Optional[str] = None
) -> List[Tuple[str, str]]:
    """
    Повна нормалізація характеристик товару для MAUDAU:
    - переклад назв та значень;
    - дедуплікація;
    - забезпечення правила мінімум 3 характеристик.
    """
    seen_names = set()
    result = []
    
    for raw_name, raw_val in raw_params:
        norm_name = normalize_param_name(raw_name, portal_id=portal_id)
        norm_val = normalize_param_value(raw_val)
        
        # Пропуск порожніх значень або службових дублів
        if not norm_name or not norm_val:
            continue
        if len(norm_name) > 255 or len(norm_val) > 255:
            continue
            
        # Дедуплікація: MAUDAU дозволяє лише одну характеристику з однаковим ім'ям
        if norm_name in seen_names:
            continue
            
        seen_names.add(norm_name)
        result.append((norm_name, norm_val))
        
    # Гарантія правила MAUDAU: Мінімум 3 характеристики для успішної публікації
    if len(result) < 3:
        if "Стан" not in seen_names:
            result.append(("Стан", "Новий"))
            seen_names.add("Стан")
            
    if len(result) < 3 and vendor and vendor != "NoBrand":
        if "Бренд" not in seen_names:
            result.append(("Бренд", strip_html(vendor)))
            seen_names.add("Бренд")
            
    if len(result) < 3 and country:
        if "Країна-виробник" not in seen_names:
            result.append(("Країна-виробник", strip_html(country)))
            seen_names.add("Країна-виробник")
            
    # Якщо все ще менше 3 - гарантований дефолтний параметр
    if len(result) < 3:
        if "Гарантія" not in seen_names:
            result.append(("Гарантія", "14 днів"))
            seen_names.add("Гарантія")
            
    return result
