#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import fitz
from deep_translator import GoogleTranslator

translator = GoogleTranslator(source="uk", target="en")
cache = {}


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
    except:
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
            fontname="helv",
            color=color
        )

        width = fitz.get_text_length(char, fontsize=size)

        cursor += width * compression


def draw_text_with_auto_compress(page, x, y, text, size, color):

    page_width = page.rect.width

    text_width = fitz.get_text_length(text, fontsize=size)

    # если текст помещается
    if x + text_width <= page_width:

        page.insert_text(
            (x, y),
            text,
            fontsize=size,
            fontname="helv",
            color=color
        )
        return

    # варианты сжатия
    compressions = [0.95, 0.92, 0.90, 0.88, 0.85]

    for c in compressions:

        width = sum(fitz.get_text_length(ch, fontsize=size) * c for ch in text)

        if x + width <= page_width:

            draw_compressed_text(page, x, y, text, size, color, c)
            return

    # максимум 15%
    draw_compressed_text(page, x, y, text, size, color, 0.85)


def translate_pdf(input_pdf, output_pdf):

    doc = fitz.open(input_pdf)

    for page in doc:

        blocks = page.get_text("dict")["blocks"]

        items = []

        for block in blocks:

            if block["type"] != 0:
                continue

            for line in block["lines"]:

                text = "".join(span["text"] for span in line["spans"]).strip()

                if not text:
                    continue

                translated = translate(text)

                x0 = min(span["bbox"][0] for span in line["spans"])
                y0 = min(span["bbox"][1] for span in line["spans"])

                size = line["spans"][0]["size"]

                color_int = line["spans"][0]["color"]

                r = ((color_int >> 16) & 255) / 255
                g = ((color_int >> 8) & 255) / 255
                b = (color_int & 255) / 255

                items.append((x0, y0, translated, size, (r, g, b)))

                rect = fitz.Rect(
                    min(span["bbox"][0] for span in line["spans"]),
                    min(span["bbox"][1] for span in line["spans"]),
                    max(span["bbox"][2] for span in line["spans"]),
                    max(span["bbox"][3] for span in line["spans"])
                )

                page.add_redact_annot(rect, fill=(1, 1, 1))

        page.apply_redactions()

        for x, y, text, size, color in items:

            y_corrected = y + size * 0.9

            draw_text_with_auto_compress(
                page,
                x,
                y_corrected,
                text,
                size,
                color
            )

    doc.save(output_pdf)


def process_path(path):

    if os.path.isfile(path):

        if path.lower().endswith(".pdf"):

            output_pdf = path.replace(".pdf", "_en.pdf")

            print("Translating:", path)

            translate_pdf(path, output_pdf)

            print("Done:", output_pdf)

    elif os.path.isdir(path):

        for file in os.listdir(path):

            if file.lower().endswith(".pdf"):

                input_pdf = os.path.join(path, file)

                output_pdf = os.path.join(
                    path,
                    file.replace(".pdf", "_en.pdf")
                )

                print("Translating:", input_pdf)

                translate_pdf(input_pdf, output_pdf)

                print("Done:", output_pdf)


def main():

    if len(sys.argv) < 2:
        print("Usage:")
        print("python translate_pdf.py file.pdf")
        print("python translate_pdf.py folder")
        return

    process_path(sys.argv[1])


if __name__ == "__main__":
    main()