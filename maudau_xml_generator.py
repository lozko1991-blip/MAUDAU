import codecs
import gzip
import io
import os
import re
import shutil
import sys
import time
import requests
import xml.sax.saxutils as saxutils
from collections import Counter
from datetime import datetime
from html import unescape
from typing import List, Dict, Set, Tuple, Optional

import lxml.etree as ET

from markup_config import calculate_prices, is_category_excluded
from category_mapper import get_category_info, format_category_xml
from param_normalizer import normalize_parameters, strip_html

# 4 постачальники для інтеграції в єдиний MAUDAU XML фід
SOURCES = [
    {
        "id": "yavshoke",
        "domain": "crm.yavshoke.ua",
        "prefix": "321_",
        "url": "https://crm.yavshoke.ua/media/export/all_drop_opt_price.xml"
    },
    {
        "id": "opt-drop",
        "domain": "opt-drop.com",
        "prefix": "1000_",
        "url": "https://opt-drop.com/storage/xml/opt-drop-1.xml"
    },
    {
        "id": "dropt",
        "domain": "dropt.in.ua",
        "prefix": "2010_",
        "url": "https://dropt.in.ua/index.php?route=export/prom&markup=15&ids=uniq"
    },
    {
        "id": "aveon",
        "domain": "aveon.net.ua",
        "prefix": "3001_",
        "url": "https://aveon.net.ua/products_feed.xml?hash_tag=7b71fadcc4a12f03cf26a304da032fba&sales_notes=&product_ids=&label_ids=&exclude_fields=&html_description=0&yandex_cpa=&process_presence_sure=&languages=uk%2Cru&extra_fields=keywords&group_ids="
    }
]

def clean_control_chars(val: str) -> str:
    """Видаляє недруковані керуючі символи ASCII 0-31 (крім табуляції та перенесення рядків)."""
    if not val:
        return ""
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(val))

def escape_xml(val: str) -> str:
    """Екранує спецсимволи XML (&, <, >) та видаляє недруковані керуючі символи."""
    if not val:
        return ""
    clean = clean_control_chars(val)
    return saxutils.escape(clean)

def escape_attr(val: str) -> str:
    """Екранує спецсимволи XML для атрибутів (&, <, >, \", ')."""
    if not val:
        return ""
    clean = clean_control_chars(val)
    return saxutils.escape(clean, entities={'"': '&quot;', "'": '&apos;'})

def clean_description_html(raw_html: str, title: str = "", vendor: str = "") -> str:
    """
    Повне глибоке очищення та форматування HTML-опису товару під вимоги MAUDAU:
    1. Подвійний unescape (для постачальників типу opt-drop з закодованим &lt;p&gt;).
    2. Видалення службових керуючих байтів XML.
    3. Видалення скриптів, стилів, iframe, video, audio та вбудованих тегів <img>.
    4. Видалення зовнішніх URL, доменів, посилань на сторонні сайти.
    5. Видалення контактних номерів телефонів (українські формати +380 / 0xx...).
    6. Видалення месенджерів (Viber, Telegram, WhatsApp, Instagram, Facebook) та рекламних закликів.
    7. Очищення inline-стилів (style, class, id, align, color, loading тощо).
    8. Форматування тексту в читабельні абзаци <p>...</p>, <ul>, <li>, <br/>.
    9. Захист від зламу CDATA (заміна ]]> на ]]&gt;).
    """
    fallback = f"<p>{escape_xml(title)}</p>" if title else ""
    if not raw_html:
        return fallback

    # 1. Подвійний unescape
    text = unescape(unescape(str(raw_html)))

    # 2. Видалення недрукованих ASCII
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

    # 3. Видалення скриптів, стилів, медіа та <img>
    text = re.sub(r'<(script|style|iframe|video|audio|svg|canvas|form|input|button)[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<(script|style|iframe|video|audio|img|input)[^>]*\/?>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

    # 4. Видалення посилань URL та доменних імен
    text = re.sub(r'https?://[^\s<>"\'()]+|www\.[^\s<>"\'()]+', '', text)
    text = re.sub(r'\b[a-zA-Z0-9\.\-_]+\.(?:ua|com|net|org|shop|in\.ua|prom\.ua|rozetka|com\.ua|biz\.ua)\b', '', text, flags=re.IGNORECASE)

    # 5. Видалення номерів телефонів
    text = re.sub(r'(?:\+?38\s*)?(?:\(?0\d{2}\)?[\s\-\.]*)\d{3}[\s\-\.]*\d{2}[\s\-\.]*\d{2}', '', text)
    text = re.sub(r'(?:\+?380|\b0)\d{9}\b', '', text)

    # 6. Видалення згадок месенджерів та реклами
    promo_pattern = r'(?i)(?:viber|вайбер|telegram|телеграм|whatsapp|ватсап|instagram|інстаграм|facebook|фейсбук)[\s\:\-\@\w\.\+\/]*'
    text = re.sub(promo_pattern, '', text)
    cta_pattern = r'(?i)(?:дзвоніть|телефонуйте|наш сайт|замовлення приймаються|звертайтесь за телефоном|деталі за телефоном|переходьте за посиланням|підписуйтесь)[^<\n\.]*'
    text = re.sub(cta_pattern, '', text)

    # 7. Видалення inline атрибутів стилів
    text = re.sub(r'\s+(?:style|class|id|align|bgcolor|width|height|loading|onerror|onclick|data-[a-z0-9\-]+)="[^"]*"', '', text, flags=re.IGNORECASE)
    text = re.sub(r"\s+(?:style|class|id|align|bgcolor|width|height|loading|onerror|onclick|data-[a-z0-9\-]+)='[^']*'", '', text, flags=re.IGNORECASE)

    # 8. Розгортання зайвих span та font
    text = re.sub(r'</?(?:span|font)[^>]*>', '', text, flags=re.IGNORECASE)

    # 9. Форматування тексту в семантичні абзаци
    if not re.search(r'<(?:p|div|ul|ol|li|br|h[1-6])\b', text, re.IGNORECASE):
        paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
        if paragraphs:
            text = ''.join(f'<p>{p.replace(chr(10), "<br/>")}</p>' for p in paragraphs)
        else:
            text = f"<p>{text.replace(chr(10), '<br/>')}</p>"

    # Заміна div на p
    text = re.sub(r'<div[^>]*>', '<p>', text, flags=re.IGNORECASE)
    text = re.sub(r'</div>', '</p>', text, flags=re.IGNORECASE)

    # Видалення порожніх тегів (кілька проходів)
    for _ in range(3):
        text = re.sub(r'<(\w+)[^>]*>\s*(?:&nbsp;|\s)*</\1>', '', text, flags=re.IGNORECASE)

    # Нормалізація повторних <br/>
    text = re.sub(r'(?:<br\s*/?>\s*){2,}', '<br/>', text, flags=re.IGNORECASE)

    # Обмеження довжини опису
    DESC_LIMIT = 5000
    if len(text) > DESC_LIMIT:
        cut_pos = text.rfind('>', 0, DESC_LIMIT)
        if cut_pos > 0:
            text = text[:cut_pos + 1]
        else:
            text = text[:DESC_LIMIT]

    text = text.strip()

    # Перевірка на змістовність тексту
    plain = re.sub(r'<[^>]+>', '', text).strip()
    if len(plain) < 20:
        return fallback

    # Захист CDATA
    return text.replace("]]>", "]]&gt;")

class IterContentStream(io.RawIOBase):
    """
    Потоковий декодер на базі requests.iter_content, який стабільно працює
    з chunked encoding, ігнорує «брудні» байти (як одиночні 0x96 у Yavshoke)
    та віддає валідний UTF-8 потік у lxml.iterparse.
    """
    def __init__(self, response, chunk_size=262144):
        self.response = response
        self.chunk_size = chunk_size
        self.iter = response.iter_content(chunk_size=chunk_size)
        self.buffer = b""
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='ignore')

    def readable(self) -> bool:
        return True

    def readinto(self, b) -> int:
        while len(self.buffer) < len(b):
            try:
                chunk = next(self.iter)
            except (StopIteration, GeneratorExit):
                final_str = self.decoder.decode(b"", final=True)
                if final_str:
                    self.buffer += final_str.encode('utf-8')
                break
            except Exception as e:
                print(f"  [STREAM WARNING] Переривання потоку: {e}")
                break

            if chunk:
                decoded_str = self.decoder.decode(chunk, final=False)
                self.buffer += decoded_str.encode('utf-8')

        n = min(len(b), len(self.buffer))
        if n == 0:
            return 0
        b[:n] = self.buffer[:n]
        self.buffer = self.buffer[n:]
        return n

def generate_maudau_feed(sources: List[dict] = SOURCES, output_file: str = "maudau_feed.xml"):
    start_time = time.time()
    print("=" * 75)
    print("СТАРТ ГЕНЕРАЦІЇ МУЛЬТИ-ПОСТАЧАЛЬНИЦЬКОГО ФІДУ MAUDAU XML")
    print(f"Постачальників у списку: {len(sources)}")
    for s in sources:
        print(f"  - [{s['prefix']}] {s['id']} ({s['domain']})")
    print("=" * 75)

    stats = {
        "total_source_offers": 0,
        "out_of_stock_offers": 0,
        "excluded_category_offers": 0,
        "below_min_price_offers": 0,
        "duplicate_offers": 0,
        "invalid_offers": 0,
        "candidate_offers": 0,
        "thin_offers_removed": 0,
        "published_offers": 0,
        "categories_total": 0,
        "categories_pruned_thin": 0,
        "categories_final": 0,
        "categories_mapped_portal_id": 0
    }

    temp_offers_path = output_file + ".offers.tmp"

    seen_offer_ids: Set[str] = set()
    cat_direct_counts: Counter = Counter()
    # all_categories: prefixed_cid -> (name_raw, prefixed_pid)
    all_categories: Dict[str, Tuple[str, Optional[str]]] = {}

    print("\n[КРОК 1/3] Потокове завантаження та фільтрація товарів від усіх постачальників...")

    with open(temp_offers_path, "w", encoding="utf-8") as out_temp:
        for s_idx, source in enumerate(sources, 1):
            s_name = source["id"]
            prefix = source["prefix"]
            domain = source["domain"]
            url = source["url"]

            print(f"\n--- [{s_idx}/{len(sources)}] Обробка: {s_name} (префікс: {prefix}, домен: {domain}) ---")

            try:
                resp = requests.get(
                    url,
                    stream=True,
                    timeout=180,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MAUDAU Feed Aggregator/2.0"}
                )
                resp.raise_for_status()

                stream = io.BufferedReader(IterContentStream(resp, chunk_size=262144))
                context = ET.iterparse(
                    stream,
                    events=("end",),
                    tag=("category", "offer"),
                    recover=True,
                    huge_tree=True
                )

                last_log_time = time.time()
                supplier_offers_count = 0
                supplier_candidates = 0

                for event, elem in context:
                    if elem.tag == "category":
                        raw_cid = (elem.get("id") or "").strip()
                        if not raw_cid:
                            elem.clear()
                            continue

                        # opt-drop може мати parent_id, інші parentId
                        raw_pid = (elem.get("parentId") or elem.get("parent_id") or "").strip()
                        if raw_pid in ("0", "-1", "none", "None", ""):
                            raw_pid = ""

                        cname = (elem.text or "").strip()
                        prefixed_cid = f"{prefix}{raw_cid}"
                        prefixed_pid = f"{prefix}{raw_pid}" if raw_pid else None
                        all_categories[prefixed_cid] = (cname, prefixed_pid)

                        elem.clear()
                        while elem.getprevious() is not None:
                            del elem.getparent()[0]

                    elif elem.tag == "offer":
                        stats["total_source_offers"] += 1
                        supplier_offers_count += 1
                        raw_id = (elem.get("id") or "").strip()
                        avail_val = (elem.get("available") or "true").strip().lower()

                        # 1. Тільки товари в наявності (available == true)
                        if avail_val != "true":
                            stats["out_of_stock_offers"] += 1
                            elem.clear()
                            while elem.getprevious() is not None:
                                del elem.getparent()[0]
                            continue

                        # 2. Категорія товару
                        cat_el = elem.find("categoryId")
                        raw_cat_id = cat_el.text.strip() if cat_el is not None and cat_el.text else ""
                        if not raw_cat_id or raw_cat_id in ("0", "None"):
                            stats["invalid_offers"] += 1
                            elem.clear()
                            while elem.getprevious() is not None:
                                del elem.getparent()[0]
                            continue

                        prefixed_cat_id = f"{prefix}{raw_cat_id}"
                        cat_name_raw, _ = all_categories.get(prefixed_cat_id, ("", None))

                        # 3. Назва товару
                        name_ua_el = elem.find("name_ua")
                        name_ru_el = elem.find("name")
                        title_ua = strip_html(name_ua_el.text if name_ua_el is not None and name_ua_el.text else "")
                        title_ru = strip_html(name_ru_el.text if name_ru_el is not None and name_ru_el.text else "")

                        if not title_ua:
                            title_ua = title_ru
                        if not title_ru:
                            title_ru = title_ua

                        # Перевірка на заборонені категорії (ролети, тарілки у Yavshoke)
                        if is_category_excluded(raw_cat_id, cat_name=cat_name_raw, product_title=title_ua):
                            stats["excluded_category_offers"] += 1
                            elem.clear()
                            while elem.getprevious() is not None:
                                del elem.getparent()[0]
                            continue

                        # 4. Розрахунок цін та фільтр від 300/350 грн
                        price_el = elem.find("price")
                        try:
                            raw_price = float(price_el.text.strip()) if price_el is not None and price_el.text else 0.0
                        except (ValueError, TypeError):
                            raw_price = 0.0

                        final_price, old_price, is_allowed = calculate_prices(domain, raw_price)
                        if not is_allowed:
                            stats["below_min_price_offers"] += 1
                            elem.clear()
                            while elem.getprevious() is not None:
                                del elem.getparent()[0]
                            continue

                        # Валідація назви
                        if not title_ua or len(title_ua) < 3:
                            stats["invalid_offers"] += 1
                            elem.clear()
                            while elem.getprevious() is not None:
                                del elem.getparent()[0]
                            continue

                        title_ua = escape_xml(title_ua[:255])
                        title_ru = escape_xml(title_ru[:255])

                        # 5. Очищення та форматування описів
                        desc_ua_el = elem.find("description_ua")
                        desc_ru_el = elem.find("description")
                        desc_ua_raw = desc_ua_el.text if desc_ua_el is not None and desc_ua_el.text else ""
                        desc_ru_raw = desc_ru_el.text if desc_ru_el is not None and desc_ru_el.text else ""

                        if not desc_ua_raw:
                            desc_ua_raw = desc_ru_raw
                        if not desc_ru_raw:
                            desc_ru_raw = desc_ua_raw

                        vendor_el = elem.find("vendor")
                        vendor = escape_xml(vendor_el.text.strip() if vendor_el is not None and vendor_el.text else "")

                        desc_ua = clean_description_html(desc_ua_raw, title=title_ua, vendor=vendor)
                        desc_ru = clean_description_html(desc_ru_raw, title=title_ru, vendor=vendor)

                        # 6. Фотографії (1-12 шт, валідні URL без пробілів та кирилиці)
                        pictures = []
                        for pic in elem.findall("picture"):
                            purl = (pic.text or "").strip()
                            if purl and " " not in purl and not re.search(r'[\u0400-\u04FF]', purl):
                                pictures.append(escape_xml(purl))
                                if len(pictures) >= 12:
                                    break

                        if not pictures:
                            stats["invalid_offers"] += 1
                            elem.clear()
                            while elem.getprevious() is not None:
                                del elem.getparent()[0]
                            continue

                        # 7. Країна, штрихкод
                        country_el = elem.find("country")
                        country = escape_xml(country_el.text.strip() if country_el is not None and country_el.text else "")

                        barcode_el = elem.find("barcode")
                        barcode = escape_xml(barcode_el.text.strip() if barcode_el is not None and barcode_el.text else "")

                        # 8. Характеристики з авто-підгонкою під базу MAUDAU
                        raw_params = []
                        for param in elem.findall("param"):
                            pname = param.get("name", "").strip()
                            pval = (param.text or "").strip()
                            if pname and pval:
                                raw_params.append((pname, pval))

                        _, portal_id = get_category_info(prefixed_cat_id, default_name=cat_name_raw)

                        norm_params = normalize_parameters(
                            raw_params,
                            vendor=vendor,
                            country=country,
                            portal_id=portal_id
                        )

                        # 9. Унікальність offer id
                        offer_id = escape_attr(f"{prefix}{raw_id}")
                        if offer_id in seen_offer_ids:
                            stats["duplicate_offers"] += 1
                            elem.clear()
                            while elem.getprevious() is not None:
                                del elem.getparent()[0]
                            continue
                        seen_offer_ids.add(offer_id)

                        # 10. Формування фрагменту XML та запис у тимчасовий буфер
                        cat_direct_counts[prefixed_cat_id] += 1
                        supplier_candidates += 1
                        stats["candidate_offers"] += 1

                        out_temp.write(f"###OFFER:{prefixed_cat_id}\n")
                        out_temp.write(f'        <offer id="{offer_id}" available="true">\n')
                        out_temp.write(f'            <price>{final_price}</price>\n')
                        if old_price > final_price:
                            out_temp.write(f'            <price_old>{old_price}</price_old>\n')
                        out_temp.write('            <currencyId>UAH</currencyId>\n')
                        out_temp.write(f'            <categoryId>{prefixed_cat_id}</categoryId>\n')

                        for pic_url in pictures:
                            out_temp.write(f'            <picture>{pic_url}</picture>\n')

                        out_temp.write(f'            <name_ua>{title_ua}</name_ua>\n')
                        out_temp.write(f'            <name_ru>{title_ru}</name_ru>\n')
                        out_temp.write(f'            <description_ua><![CDATA[{desc_ua}]]></description_ua>\n')
                        out_temp.write(f'            <description_ru><![CDATA[{desc_ru}]]></description_ru>\n')

                        if vendor:
                            out_temp.write(f'            <vendor>{vendor}</vendor>\n')
                        if country:
                            out_temp.write(f'            <country>{country}</country>\n')
                        if barcode:
                            out_temp.write(f'            <barcode>{barcode}</barcode>\n')

                        for pname, pval in norm_params:
                            clean_pname = escape_attr(pname)
                            clean_pval = escape_xml(pval)
                            out_temp.write(f'            <param name="{clean_pname}">{clean_pval}</param>\n')

                        out_temp.write('        </offer>\n')
                        out_temp.write('###END_OFFER\n')

                        elem.clear()
                        while elem.getprevious() is not None:
                            del elem.getparent()[0]

                        if supplier_offers_count % 10000 == 0 or (time.time() - last_log_time > 15):
                            print(f"  [STREAM {s_name}] Оброблено: {supplier_offers_count} товарів | Кандидатів: {supplier_candidates}")
                            last_log_time = time.time()

                print(f"  Успішно оброблено {s_name}: всього {supplier_offers_count}, пройшло фільтри {supplier_candidates}")

            except Exception as e:
                print(f"  [ПОМИЛКА] Не вдалося обробити {s_name}: {e}")

    print("\n[КРОК 2/3] Фільтрація категорій (< 3 товарів) та побудова дерева категорій...")

    # Знаходимо всі батьківські категорії
    parent_cids = {pid for _, pid in all_categories.values() if pid and pid in all_categories}

    # Валідація назв категорій: категорія обов'язково повинна мати непусту назву!
    named_categories = set()
    category_names_cache: Dict[str, Tuple[str, Optional[str]]] = {}
    for cid, (raw_cname, _) in all_categories.items():
        name_ua, portal_id = get_category_info(cid, default_name=raw_cname)
        clean_name_ua = (name_ua or "").strip()
        if clean_name_ua:
            named_categories.add(cid)
            category_names_cache[cid] = (clean_name_ua, portal_id)

    # Тонкі категорії: мають < 3 прямих товарів І НЕ є батьківськими категоріями (або не мають валідної назви)
    thin_cat_ids = {
        cid for cid, count in cat_direct_counts.items()
        if (count < 3 and cid not in parent_cids) or (cid not in named_categories)
    }

    stats["categories_pruned_thin"] = len(thin_cat_ids)
    print(f"  Знайдено тонких/невалідних категорій: {len(thin_cat_ids)}")

    # Категорії, які мають >= 3 товарів і мають ім'я
    valid_cat_ids = {cid for cid, count in cat_direct_counts.items() if cid not in thin_cat_ids}

    # Повне дерево: додаємо всі дійсні категорії + всіх їхніх предків (щоб не зламати ієрархію)
    final_cat_ids: Set[str] = set()
    for v_cid in valid_cat_ids:
        cur = v_cid
        while cur:
            if cur in named_categories:
                final_cat_ids.add(cur)
            _, pid = all_categories.get(cur, ("", None))
            cur = pid if pid and pid != cur and pid in all_categories and pid in named_categories else None

    stats["categories_total"] = len(all_categories)
    stats["categories_final"] = len(final_cat_ids)

    print(f"  Всього категорій у джерелах: {stats['categories_total']}")
    print(f"  Фінальних категорій у фіді (активні >= 3 + предки): {stats['categories_final']}")

    print("\n[КРОК 3/3] Запис підсумкового XML та генерація GZIP архіву...")

    cur_date = datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(output_file, "w", encoding="utf-8") as out:
        out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        out.write(f'<yml_catalog date="{cur_date}">\n')
        out.write('    <shop>\n')
        out.write('        <name>MAUDAU Store</name>\n')
        out.write('        <company>MAUDAU Store</company>\n')
        out.write('        <url>https://maudau.com.ua</url>\n')
        out.write('        <currencies>\n')
        out.write('            <currency id="UAH" rate="1"/>\n')
        out.write('        </currencies>\n')
        out.write('        <categories>\n')

        for cid in sorted(list(final_cat_ids)):
            name_ua, portal_id = category_names_cache.get(cid, ("", None))
            if not name_ua:
                continue

            _, pid = all_categories.get(cid, ("", None))
            our_pid = pid if pid and pid in final_cat_ids else None
            cat_xml = format_category_xml(cid, name_ua, portal_id=portal_id, parent_id=our_pid)
            out.write(f'            {cat_xml}\n')

            if portal_id:
                stats["categories_mapped_portal_id"] += 1

        out.write('        </categories>\n')
        out.write('        <offers>\n')

        # Другий прохід: переносимо оффери з тимчасового буфера
        with open(temp_offers_path, "r", encoding="utf-8") as in_temp:
            cur_cat_id = None
            offer_buffer = []

            for line in in_temp:
                if line.startswith("###OFFER:"):
                    cur_cat_id = line[9:].strip()
                    offer_buffer = []
                elif line.startswith("###END_OFFER"):
                    if cur_cat_id and cur_cat_id in final_cat_ids and cur_cat_id not in thin_cat_ids:
                        out.write("".join(offer_buffer))
                        stats["published_offers"] += 1
                    else:
                        stats["thin_offers_removed"] += 1
                    cur_cat_id = None
                    offer_buffer = []
                else:
                    offer_buffer.append(line)

        out.write('        </offers>\n')
        out.write('    </shop>\n')
        out.write('</yml_catalog>\n')

    # Видалення тимчасового буфера
    if os.path.exists(temp_offers_path):
        os.remove(temp_offers_path)

    # Генерація GZIP копії
    gz_output_file = output_file + ".gz"
    with open(output_file, "rb") as f_in:
        with gzip.open(gz_output_file, "wb", compresslevel=6) as f_out:
            shutil.copyfileobj(f_in, f_out)

    elapsed = time.time() - start_time
    file_size_mb = os.path.getsize(output_file) / (1024 * 1024)
    gz_size_mb = os.path.getsize(gz_output_file) / (1024 * 1024)

    print("\n" + "=" * 75)
    print("ГЕНЕРАЦІЮ ЗАВЕРШЕНО УСПІШНО!")
    print(f"Час виконання: {elapsed:.2f} сек")
    print(f"Розмір згенерованого XML: {file_size_mb:.2f} МБ (GZIP: {gz_size_mb:.2f} МБ)")
    print("-" * 75)
    print(f"Всього товарів у джерелах: {stats['total_source_offers']}")
    print(f"Відсіяно не в наявності (available != true): {stats['out_of_stock_offers']}")
    print(f"Відсіяно заборонених категорій (ролети/тарілки): {stats['excluded_category_offers']}")
    print(f"Відсіяно за ціною (< 300 / < 350 грн на MAUDAU): {stats['below_min_price_offers']}")
    print(f"Відсіяно з категорій з < 3 товарів / без назви: {stats['thin_offers_removed']}")
    print(f"Відсіяно некоректних (без фото/назви/категорії): {stats['invalid_offers']}")
    print(f"Відсіяно дублів: {stats['duplicate_offers']}")
    print(f"ОПУБЛІКОВАНО ТОВАРІВ У ФІДІ: {stats['published_offers']}")
    print(f"Категорій у фіді: {stats['categories_final']} (з прив'язаним portal_id: {stats['categories_mapped_portal_id']})")
    print(f"Видалено тонких/некоректних категорій: {stats['categories_pruned_thin']}")
    print("=" * 75)

if __name__ == "__main__":
    generate_maudau_feed(SOURCES, output_file="maudau_feed.xml")
