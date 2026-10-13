import codecs
import io
import os
import re
import sys
import time
import urllib.request
import xml.sax.saxutils as saxutils
from datetime import datetime
from typing import List, Dict, Set, Tuple, Optional

import lxml.etree as ET

from markup_config import calculate_prices, is_category_excluded
from category_mapper import get_category_info, format_category_xml
from param_normalizer import normalize_parameters, strip_html

# Постачальники для вивантаження на MAUDAU
SOURCES = [
    {
        "id": "yavshoke",
        "domain": "crm.yavshoke.ua",
        "prefix": "321_",
        "url": "https://crm.yavshoke.ua/media/export/all_drop_opt_price.xml"
    }
]

def clean_control_chars(val: str) -> str:
    """Видаляє недруковані керуючі символи ASCII 0-31 (крім табуляції та перенесення рядків)."""
    if not val:
        return ""
    # Дозволені: 9 (\t), 10 (\n), 13 (\r)
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', val)

def escape_xml(val: str) -> str:
    """Екранує спецсимволи XML (&, <, >) та видаляє заборонені керуючі символи."""
    if not val:
        return ""
    clean = clean_control_chars(val)
    return saxutils.escape(clean)

def escape_attr(val: str) -> str:
    """Екранує спецсимволи XML для атрибутів (&, <, >, ", ')."""
    if not val:
        return ""
    clean = clean_control_chars(val)
    return saxutils.escape(clean, entities={'"': '&quot;', "'": '&apos;'})

def clean_cdata(val: str) -> str:
    """Очищає вміст CDATA блоків та нейтралізує закриваючий маркер ]]>."""
    if not val:
        return ""
    clean = clean_control_chars(val)
    return clean.replace("]]>", "]]&gt;")

class SanitizedBytesReader(io.RawIOBase):
    """
    Потоковий декодер, який читає бінарний потік, ігнорує «брудні» байти (наприклад, одиночні 0x96 у Yavshoke)
    та віддає чистий валідний UTF-8 потік у lxml.iterparse, гарантуючи збереження багатобайтових символів на межах чанків.
    """
    def __init__(self, raw_stream, chunk_size=262144):
        self.raw = raw_stream
        self.chunk_size = chunk_size
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='ignore')
        self.buffer = b""

    def readable(self) -> bool:
        return True

    def readinto(self, b) -> int:
        while len(self.buffer) < len(b):
            raw_chunk = self.raw.read(self.chunk_size)
            if not raw_chunk:
                final_str = self.decoder.decode(b"", final=True)
                if final_str:
                    self.buffer += final_str.encode('utf-8')
                break
            decoded_str = self.decoder.decode(raw_chunk, final=False)
            self.buffer += decoded_str.encode('utf-8')

        n = min(len(b), len(self.buffer))
        if n == 0:
            return 0
        b[:n] = self.buffer[:n]
        self.buffer = self.buffer[n:]
        return n

def process_feed(source: dict, output_file: str = "maudau_feed.xml"):
    start_time = time.time()
    print("=" * 70)
    print(f"ПОЧАТОК ГЕНЕРАЦІЇ ФІДУ MAUDAU ДЛЯ: {source.get('id', 'unknown')}")
    print(f"URL: {source['url']}")
    print("=" * 70)

    # Статистика
    stats = {
        "total_source_offers": 0,
        "excluded_category_offers": 0,
        "below_min_price_offers": 0,
        "duplicate_offers": 0,
        "invalid_offers": 0,
        "published_offers": 0,
        "categories_count": 0,
        "mapped_categories_count": 0
    }

    # Створюємо тимчасовий файл для запису офферів
    temp_offers_path = output_file + ".offers.tmp"

    seen_offer_ids: Set[str] = set()
    used_category_ids: Set[str] = set()
    category_definitions: Dict[str, Tuple[str, Optional[str]]] = {} # cat_id -> (name_ru, parent_id)

    print("[1/3] Завантаження та потокова обробка фіду постачальника...")

    req = urllib.request.Request(
        source["url"],
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MAUDAU Feed Builder"}
    )

    with open(temp_offers_path, "w", encoding="utf-8") as out_offers:
        with urllib.request.urlopen(req, timeout=180) as resp:
            # Обгортаємо бінарний потік у SanitizedBytesReader для фільтрації битих байтів
            sanitized_stream = io.BufferedReader(SanitizedBytesReader(resp, chunk_size=262144))
            context = ET.iterparse(
                sanitized_stream,
                events=("end",),
                tag=("category", "offer"),
                recover=True,
                huge_tree=True
            )

            last_log_time = time.time()

            for event, elem in context:
                if elem.tag == "category":
                    cid = elem.get("id")
                    pid = elem.get("parentId")
                    cname = elem.text or ""
                    if cid:
                        category_definitions[cid] = (cname.strip(), pid)
                    
                    elem.clear()
                    while elem.getprevious() is not None:
                        del elem.getparent()[0]

                elif elem.tag == "offer":
                    stats["total_source_offers"] += 1
                    raw_id = elem.get("id", "")
                    available = elem.get("available", "true").lower() == "true"

                    # 1. Категорія товару
                    cat_elem = elem.find("categoryId")
                    raw_cat_id = cat_elem.text.strip() if cat_elem is not None and cat_elem.text else ""
                    cat_name_ru, _ = category_definitions.get(raw_cat_id, ("", None))

                    # 2. Назва товару
                    name_ua_el = elem.find("name_ua")
                    name_ru_el = elem.find("name")
                    title_ua = strip_html(name_ua_el.text if name_ua_el is not None and name_ua_el.text else "")
                    title_ru = strip_html(name_ru_el.text if name_ru_el is not None and name_ru_el.text else "")

                    if not title_ua:
                        title_ua = title_ru
                    if not title_ru:
                        title_ru = title_ua

                    # Перевірка на заборонені категорії (ролети, тарілки)
                    if is_category_excluded(raw_cat_id, cat_name=cat_name_ru, product_title=title_ua):
                        stats["excluded_category_offers"] += 1
                        elem.clear()
                        while elem.getprevious() is not None:
                            del elem.getparent()[0]
                        continue

                    # 3. Ціна та фільтр від 300 грн на MAUDAU
                    price_el = elem.find("price")
                    try:
                        raw_price = float(price_el.text.strip()) if price_el is not None and price_el.text else 0.0
                    except (ValueError, TypeError):
                        raw_price = 0.0

                    final_price, old_price, is_allowed = calculate_prices(source["domain"], raw_price)
                    if not is_allowed:
                        stats["below_min_price_offers"] += 1
                        elem.clear()
                        while elem.getprevious() is not None:
                            del elem.getparent()[0]
                        continue

                    # Перевірка валідності назви
                    if not title_ua or len(title_ua) < 3:
                        stats["invalid_offers"] += 1
                        elem.clear()
                        while elem.getprevious() is not None:
                            del elem.getparent()[0]
                        continue

                    title_ua = escape_xml(title_ua[:255])
                    title_ru = escape_xml(title_ru[:255])

                    # 4. Опис (обгортається в CDATA, очищається)
                    desc_ua_el = elem.find("description_ua")
                    desc_ru_el = elem.find("description")
                    desc_ua = desc_ua_el.text if desc_ua_el is not None and desc_ua_el.text else ""
                    desc_ru = desc_ru_el.text if desc_ru_el is not None and desc_ru_el.text else ""

                    if not desc_ua:
                        desc_ua = desc_ru
                    if not desc_ru:
                        desc_ru = desc_ua
                    if not desc_ua:
                        desc_ua = f"<p>{title_ua}</p>"
                        desc_ru = f"<p>{title_ru}</p>"

                    desc_ua = clean_cdata(desc_ua[:10000])
                    desc_ru = clean_cdata(desc_ru[:10000])

                    # 5. Фотографії (від 1 до 12, без кирилиці/пробілів)
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

                    # 6. Бренд, країна, штрихкод
                    vendor_el = elem.find("vendor")
                    vendor = escape_xml(vendor_el.text.strip() if vendor_el is not None and vendor_el.text else "")

                    country_el = elem.find("country")
                    country = escape_xml(country_el.text.strip() if country_el is not None and country_el.text else "")

                    barcode_el = elem.find("barcode")
                    barcode = escape_xml(barcode_el.text.strip() if barcode_el is not None and barcode_el.text else "")

                    # 7. Характеристики (з авто-підгонкою під базу MAUDAU)
                    raw_params = []
                    for param in elem.findall("param"):
                        pname = param.get("name", "").strip()
                        pval = (param.text or "").strip()
                        if pname and pval:
                            raw_params.append((pname, pval))

                    # Отримуємо portal_id категорії товару для контекстного мапінгу
                    _, portal_id = get_category_info(raw_cat_id, default_name=cat_name_ru)

                    norm_params = normalize_parameters(
                        raw_params,
                        vendor=vendor,
                        country=country,
                        portal_id=portal_id
                    )

                    # Фіксуємо використання категорії
                    used_category_ids.add(raw_cat_id)

                    # Формуємо XML товарної пропозиції
                    offer_id = escape_attr(f"{source['prefix']}{raw_id}")
                    if offer_id in seen_offer_ids:
                        stats["duplicate_offers"] += 1
                        elem.clear()
                        while elem.getprevious() is not None:
                            del elem.getparent()[0]
                        continue
                    seen_offer_ids.add(offer_id)

                    avail_str = "true" if available else "false"

                    out_offers.write(f'        <offer id="{offer_id}" available="{avail_str}">\n')
                    out_offers.write(f'            <price>{final_price}</price>\n')
                    if old_price > final_price:
                        out_offers.write(f'            <price_old>{old_price}</price_old>\n')
                    out_offers.write('            <currencyId>UAH</currencyId>\n')
                    out_offers.write(f'            <categoryId>{source["prefix"]}{raw_cat_id}</categoryId>\n')

                    for pic_url in pictures:
                        out_offers.write(f'            <picture>{pic_url}</picture>\n')

                    out_offers.write(f'            <name_ua>{title_ua}</name_ua>\n')
                    out_offers.write(f'            <name_ru>{title_ru}</name_ru>\n')

                    out_offers.write(f'            <description_ua><![CDATA[{desc_ua}]]></description_ua>\n')
                    out_offers.write(f'            <description_ru><![CDATA[{desc_ru}]]></description_ru>\n')

                    if vendor:
                        out_offers.write(f'            <vendor>{vendor}</vendor>\n')
                    if country:
                        out_offers.write(f'            <country>{country}</country>\n')
                    if barcode:
                        out_offers.write(f'            <barcode>{barcode}</barcode>\n')

                    for pname, pval in norm_params:
                        clean_pname = escape_attr(pname)
                        clean_pval = escape_xml(pval)
                        out_offers.write(f'            <param name="{clean_pname}">{clean_pval}</param>\n')

                    out_offers.write('        </offer>\n')

                    stats["published_offers"] += 1

                    elem.clear()
                    while elem.getprevious() is not None:
                        del elem.getparent()[0]

                    # Періодичне логування
                    if stats["total_source_offers"] % 10000 == 0 or (time.time() - last_log_time > 15):
                        print(f"  [STREAM] Оброблено: {stats['total_source_offers']} товарів | "
                              f"Опубліковано: {stats['published_offers']} | "
                              f"За категоріями: {stats['excluded_category_offers']} | "
                              f"За ціною: {stats['below_min_price_offers']}")
                        last_log_time = time.time()

    print(f"[2/3] Обробка категорій та побудова фінального XML...")

    # Складаємо повне дерево категорій тільки для тих, що реально мають опубліковані товари
    final_cat_ids = set()
    for u_cid in used_category_ids:
        cur = u_cid
        while cur:
            final_cat_ids.add(cur)
            _, pid = category_definitions.get(cur, ("", None))
            cur = pid if pid and pid != cur else None

    # Запис підсумкового файлу
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
            raw_cname, parent_id = category_definitions.get(cid, ("", None))
            name_ua, portal_id = get_category_info(cid, default_name=raw_cname)

            our_cid = f"{source['prefix']}{cid}"
            our_pid = f"{source['prefix']}{parent_id}" if parent_id and parent_id in final_cat_ids else None

            cat_xml = format_category_xml(our_cid, name_ua, portal_id=portal_id, parent_id=our_pid)
            out.write(f'            {cat_xml}\n')

            stats["categories_count"] += 1
            if portal_id:
                stats["mapped_categories_count"] += 1

        out.write('        </categories>\n')
        out.write('        <offers>\n')

        # Переносимо оффери з тимчасового файлу
        with open(temp_offers_path, "r", encoding="utf-8") as in_offers:
            for line in in_offers:
                out.write(line)

        out.write('        </offers>\n')
        out.write('    </shop>\n')
        out.write('</yml_catalog>\n')

    # Видаляємо тимчасовий файл
    if os.path.exists(temp_offers_path):
        os.remove(temp_offers_path)

    # Генерація стисненої копії (.xml.gz) для швидкого завантаження маркетплейсом
    gz_output_file = output_file + ".gz"
    print(f"\n[3/3] Створення архівованої версії {gz_output_file} для блискавичного скачування...")
    import gzip
    import shutil
    with open(output_file, "rb") as f_in:
        with gzip.open(gz_output_file, "wb", compresslevel=6) as f_out:
            shutil.copyfileobj(f_in, f_out)
    gz_size_mb = os.path.getsize(gz_output_file) / (1024 * 1024)

    elapsed = time.time() - start_time
    file_size_mb = os.path.getsize(output_file) / (1024 * 1024)

    print("\n" + "=" * 70)
    print("ГЕНЕРАЦІЮ ЗАВЕРШЕНО УСПІШНО!")
    print(f"Час виконання: {elapsed:.2f} сек")
    print(f"Розмір згенерованого XML: {file_size_mb:.2f} МБ (GZIP: {gz_size_mb:.2f} МБ)")
    print("-" * 70)
    print(f"Всього товарів у постачальника: {stats['total_source_offers']}")
    print(f"Відфільтровано заборонених категорій (ролети/тарілки): {stats['excluded_category_offers']}")
    print(f"Відфільтровано за ціною (< 300 грн на MAUDAU): {stats['below_min_price_offers']}")
    print(f"Відсіяно внутрішніх дублів постачальника: {stats['duplicate_offers']}")
    print(f"Відхилено некоректних (без фото/назви): {stats['invalid_offers']}")
    print(f"Опубліковано унікальних якісних товарів: {stats['published_offers']}")
    print(f"Категорій у фіді: {stats['categories_count']} (з прямим portal_id: {stats['mapped_categories_count']})")
    print("=" * 70)

if __name__ == "__main__":
    process_feed(SOURCES[0], output_file="maudau_feed.xml")
