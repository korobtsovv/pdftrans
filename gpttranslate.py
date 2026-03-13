#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
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

                page.add_redact_annot(rect, fill=(1,1,1))

        page.apply_redactions()

        for x, y, text, size, color in items:

            # корректируем baseline
            y_corrected = y + size * 0.9

            page.insert_text(
                (x, y_corrected),
                text,
                fontsize=size,
                fontname="helv",
                color=color
            )

    doc.save(output_pdf)


def main():

    if len(sys.argv) < 2:
        print("Usage: python translate_pdf.py file.pdf")
        return

    input_pdf = sys.argv[1]
    output_pdf = input_pdf.replace(".pdf", "_en.pdf")

    translate_pdf(input_pdf, output_pdf)

    print("Done:", output_pdf)


if __name__ == "__main__":
    main()