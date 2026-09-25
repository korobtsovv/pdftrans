#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import fitz
import logging
# from deep_translator import GoogleTranslator
from deep_translator import MyMemoryTranslator


# Путь к скачанному файлу шрифта в папке проекта
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(SCRIPT_DIR, "Arial.ttf")
FONT_NAME = "custom_font"

# Загружаем шрифт из TTF-файла
font_obj = fitz.Font(fontfile=FONT_PATH)

# translator = GoogleTranslator(source="uk", target="en")
translator = MyMemoryTranslator(source="uk-UA", target="en-US")
cache = {}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def translate(text):
    text = text.strip()
    if not text:
        return text

    if text in cache:
        return cache[text]

    try:
        t = translator.translate(text)
        if not t:
            t = text
    except Exception as e:
        logger.error(f"Ошибка перевода строки '{text}': {e}")
        t = text

    cache[text] = t
    return t


def draw_compressed_text(page, x, y, text, size, color, compression):
    cursor = x

    for char in text:
        page.insert_text(
            (cursor, y),
            char,
            fontsize=size,
            fontname=FONT_NAME,
            fontfile=FONT_PATH,
            color=color
        )

        width = font_obj.text_length(char, fontsize=size)
        cursor += width * compression


def draw_text_with_auto_compress(page, x, y, text, size, color):
    page_width = page.rect.width
    text_width = font_obj.text_length(text, fontsize=size)

    # если текст помещается
    if x + text_width <= page_width:
        page.insert_text(
            (x, y),
            text,
            fontsize=size,
            fontname=FONT_NAME,
            fontfile=FONT_PATH,
            color=color
        )
        return

    # варианты сжатия
    compressions = [0.95, 0.92, 0.90, 0.88, 0.85]

    for c in compressions:
        width = sum(font_obj.text_length(ch, fontsize=size) * c for ch in text)

        if x + width <= page_width:
            draw_compressed_text(page, x, y, text, size, color, c)
            return

    # максимум 15% сжатия
    draw_compressed_text(page, x, y, text, size, color, 0.85)


def translate_pdf(input_pdf, output_pdf):
    doc = fitz.open(input_pdf)

    for page in doc:
        # Внедряем шрифт на страницу
        page.insert_font(fontname=FONT_NAME, fontfile=FONT_PATH)

        blocks = page.get_text("dict")["blocks"]
        items = []
        texts_to_translate = []

        # 1. Собираем все строки и координаты
        for block in blocks:
            if block["type"] != 0:
                continue

            for line in block["lines"]:
                text = "".join(span["text"] for span in line["spans"]).strip()

                if not text:
                    continue

                x0 = min(span["bbox"][0] for span in line["spans"])
                y0 = min(span["bbox"][1] for span in line["spans"])

                size = line["spans"][0]["size"]
                color_int = line["spans"][0]["color"]

                r = ((color_int >> 16) & 255) / 255
                g = ((color_int >> 8) & 255) / 255
                b = (color_int & 255) / 255

                items.append({
                    "text": text,
                    "x0": x0,
                    "y0": y0,
                    "size": size,
                    "color": (r, g, b),
                    "rect": fitz.Rect(
                        min(span["bbox"][0] for span in line["spans"]),
                        min(span["bbox"][1] for span in line["spans"]),
                        max(span["bbox"][2] for span in line["spans"]),
                        max(span["bbox"][3] for span in line["spans"])
                    )
                })

                # Накопление уникальных строк для пакетного перевода
                if text not in cache and text not in texts_to_translate:
                    texts_to_translate.append(text)

                # Накладываем плашку стирания (redaction)
                page.add_redact_annot(items[-1]["rect"], fill=(1, 1, 1))

        # 2. Пакетный перевод (одним запросом за раз)
        if texts_to_translate:
            try:
                translated_list = translator.translate_batch(texts_to_translate)
                for orig, trans in zip(texts_to_translate, translated_list):
                    cache[orig] = trans if trans else orig
            except Exception as e:
                logger.error(f"Ошибка пакетного перевода: {e}")
                # Если пакетный перевод упал, оставляем оригиналы
                for orig in texts_to_translate:
                    cache[orig] = orig

        # Применяем скрытие оригинального текста
        page.apply_redactions()

        # 3. Отрисовываем переведенный текст
        for item in items:
            y_corrected = item["y0"] + item["size"] * 0.9
            translated_text = cache.get(item["text"], item["text"])

            draw_text_with_auto_compress(
                page,
                item["x0"],
                y_corrected,
                translated_text,
                item["size"],
                item["color"]
            )

    doc.save(output_pdf)


def process_path(path):
    if os.path.isfile(path):
        if path.lower().endswith(".pdf"):
            output_pdf = path.replace(".pdf", "_en.pdf")
            logger.info(f"Translating: {path}")
            translate_pdf(path, output_pdf)
            logger.info(f"Done: {output_pdf}")

    elif os.path.isdir(path):
        for file in os.listdir(path):
            if file.lower().endswith(".pdf"):
                input_pdf = os.path.join(path, file)
                output_pdf = os.path.join(
                    path,
                    file.replace(".pdf", "_en.pdf")
                )
                logger.info(f"Translating: {input_pdf}")
                translate_pdf(input_pdf, output_pdf)
                logger.info(f"Done: {output_pdf}")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("python translate.py file.pdf")
        print("python translate.py folder")
        return

    process_path(sys.argv[1])


if __name__ == "__main__":
    main()