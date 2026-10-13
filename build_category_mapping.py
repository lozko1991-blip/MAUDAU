import json
import re
import os

# Словник базових перекладів для назв категорій (RU -> UA)
RU_TO_UA_WORDS = {
    "посуда": "посуд",
    "аксессуары": "аксесуари",
    "готовка": "приготування",
    "готовки": "приготування їжі",
    "наборы": "набори",
    "кастрюль": "каструль",
    "кастрюли": "каструлі",
    "по штучно": "поштучно",
    "чайники": "чайники",
    "сковороды": "сковороди",
    "формы": "форми",
    "выпечки": "випічки",
    "противни": "дека",
    "сервировка": "сервірування",
    "сервировки": "сервірування столу",
    "напитков": "напоїв",
    "бокалы": "келихи",
    "фужеры": "фужери",
    "стаканы": "склянки",
    "стопки": "чарки",
    "рюмки": "чарки",
    "столовые": "столові",
    "приборы": "прибори",
    "чашки": "чашки",
    "кружки": "кружки",
    "кухня": "кухня",
    "кухни": "кухні",
    "ножи": "ножі",
    "детская": "дитяча",
    "детские": "дитячі",
    "бытовая": "побутова",
    "техника": "техніка",
    "мелкая": "дрібна",
    "блендеры": "блендери",
    "весы": "ваги",
    "электрочайники": "електрочайники",
    "пылесосы": "пилососи",
    "текстиль": "текстиль",
    "спальня": "спальня",
    "спальни": "спальні",
    "постельное": "постільна",
    "белье": "білизна",
    "белья": "білизни",
    "подушки": "подушки",
    "одеяла": "ковдри",
    "пледы": "пледи",
    "покрывала": "покривала",
    "простыни": "простирадла",
    "наволочки": "наволочки",
    "пододеяльники": "підковдри",
    "полотенца": "рушники",
    "красота": "краса",
    "здоровье": "здоров'я",
    "электроника": "електроніка",
    "смартфоны": "смартфони",
    "наушники": "навушники",
    "чехлы": "чохли",
    "телефонов": "телефонів",
    "игрушки": "іграшки",
    "куклы": "ляльки",
    "конструкторы": "конструктори"
}

def translate_cat_name(name_ru: str) -> str:
    name = name_ru.strip()
    # Direct manual overrides
    overrides = {
        "Посуда и аксессуары": "Посуд та аксесуари",
        "Посуда для готовки": "Посуд для приготування їжі",
        "Наборы посуды, наборы кастрюль": "Набори посуду для приготування",
        "Кастрюли по штучно": "Каструлі",
        "Сковороды": "Сковороди",
        "Чайники на плиту": "Чайники",
        "Сотейники": "Сотейники",
        "Гейзерные кофеварки": "Гейзерні кавоварки",
        "Гусятницы": "Гусятниці",
        "Крышки для посуды": "Кришки для посуду",
        "Кухонные ковши и кокотницы": "Ковші для кухні",
        "Формы для выпечки и противни": "Форми для випічки та запікання",
        "Посуда для сервировки": "Посуд для сервірування столу",
        "Бокалы и фужеры": "Келихи",
        "Стаканы": "Склянки",
        "Стопки и рюмки": "Чарки",
        "Столовые приборы": "Столові прибори",
        "Столовые сервизы": "Столові сервізи",
        "Салатницы, миски": "Салатники",
        "Чашки и кружки": "Чашки та кружки",
        "Аксессуары для кухни": "Аксесуари для кухні",
        "Кухонные ножи и принадлежности": "Кухонні ножі та приладдя",
        "Детская посуда": "Дитячий посуд",
        "Комплекты постельного белья": "Комплекти постільної білизни",
        "Подушки": "Подушки",
        "Одеяла": "Ковдри",
        "Пледы": "Пледи",
        "Покрывала": "Покривала",
        "Простыни": "Простирадла",
        "Наволочки": "Наволочки",
        "Пододеяльники": "Підковдри",
        "Полотенца": "Рушники",
        "Текстиль для спальни": "Текстиль для спальні",
        "Текстиль для кухни": "Текстиль для кухні",
        "Текстиль для ванной": "Текстиль для ванної",
        "Чехлы для телефонов": "Чохли для телефонів",
        "Зарядные устройства и адаптеры": "Зарядні пристрої для телефонів",
        "Наушники": "Навушники",
        "Пылесосы": "Пилососи",
        "Электрочайники": "Електрочайники",
        "Блендеры": "Блендери",
        "Куклы": "Ляльки",
        "Конструкторы": "Конструктори",
        "Зубные электрощетки": "Електричні зубні щітки",
    }
    if name in overrides:
        return overrides[name]
        
    # Word-by-word replace
    words = re.split(r'(\s+|[,/\\-])', name)
    out = []
    for w in words:
        low = w.lower()
        if low in RU_TO_UA_WORDS:
            rep = RU_TO_UA_WORDS[low]
            if w.istitle():
                rep = rep.capitalize()
            out.append(rep)
        else:
            out.append(w)
    return "".join(out).strip()

def build():
    # Load Yavshoke categories
    with open("C:/Users/lozko/.gemini/antigravity/brain/167a245f-a808-4efc-a6ed-d658a20b4eac/scratch/yavshoke_categories.json", "r", encoding="utf-8") as f:
        yav_cats = json.load(f)
        
    # Load MAUDAU categories database
    with open("C:/Users/lozko/.gemini/antigravity/brain/167a245f-a808-4efc-a6ed-d658a20b4eac/scratch/maudau_categories.json", "r", encoding="utf-8") as f:
        mau_cats = json.load(f)

    # Index MAUDAU categories
    mau_by_name_ua = {}
    mau_by_name_ru = {}
    for m in mau_cats:
        k_ua = m["name_ua"].lower().strip()
        k_ru = m["name_ru"].lower().strip()
        # Prefer leaf categories
        if k_ua not in mau_by_name_ua or m["is_leaf"]:
            mau_by_name_ua[k_ua] = m["id"]
        if k_ru not in mau_by_name_ru or m["is_leaf"]:
            mau_by_name_ru[k_ru] = m["id"]

    # Also load the 45 rich categories
    with open("C:/Users/lozko/.gemini/antigravity/brain/167a245f-a808-4efc-a6ed-d658a20b4eac/scratch/maudau_attributes_summary.json", "r", encoding="utf-8") as f:
        rich_cats = json.load(f)
    for rc in rich_cats:
        k_ua = rc["name_uk"].lower().strip()
        k_ru = rc["name_ru"].lower().strip()
        mau_by_name_ua[k_ua] = rc["portal_id"]
        mau_by_name_ru[k_ru] = rc["portal_id"]

    excluded_ids = {"40863", "42166", "42165", "15041", "15055"}
    
    mapping = {}
    mapped_count = 0
    
    for c in yav_cats:
        cid = c["id"]
        if cid in excluded_ids:
            continue
        cname_ru = c["name"].strip()
        
        # Check exclusion keywords
        if any(kw in cname_ru.lower() for kw in ["ролет", "роллет", "рулонн", "тарілк", "тарелк"]):
            continue
            
        cname_ua = translate_cat_name(cname_ru)
        
        # Try matching portal_id
        portal_id = (
            mau_by_name_ua.get(cname_ua.lower()) or
            mau_by_name_ru.get(cname_ru.lower()) or
            mau_by_name_ua.get(cname_ru.lower())
        )
        
        if portal_id:
            mapped_count += 1
            
        mapping[cid] = {
            "name_ua": cname_ua,
            "name_ru": cname_ru,
            "portal_id": str(portal_id) if portal_id else None,
            "parentId": c.get("parentId")
        }

    with open("category_mapping.json", "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
        
    print(f"Created category_mapping.json:")
    print(f" - Total valid categories: {len(mapping)}")
    print(f" - Auto-mapped portal_id: {mapped_count} ({mapped_count/len(mapping)*100:.1f}%)")

if __name__ == "__main__":
    build()
