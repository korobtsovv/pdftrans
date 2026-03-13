import sys
import os
import zipfile
import shutil

from pdf2docx import Converter
from deep_translator import GoogleTranslator
from lxml import etree
from docx2pdf import convert


translator = GoogleTranslator(source="uk", target="en")


def translate_text(text):

    if not text or not text.strip():
        return text

    try:
        result = translator.translate(text)
        return result if result else text
    except:
        return text


def shrink_font(run):

    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    rpr = run.find("w:rPr", namespaces=ns)

    if rpr is None:
        return

    sz = rpr.find("w:sz", namespaces=ns)

    if sz is None:
        return

    val = sz.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val")

    if val:
        try:
            new_val = max(int(val) - 1, 2)
            sz.set("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val", str(new_val))
        except:
            pass


def distribute_text(runs, translated_text, ns):

    total_chars = sum(len(run.find("w:t", namespaces=ns).text or "") for run in runs)

    if total_chars == 0:
        return

    pos = 0
    length = len(translated_text)

    for i, run in enumerate(runs):

        node = run.find("w:t", namespaces=ns)
        original = node.text or ""

        if i == len(runs) - 1:
            # последний run получает остаток
            node.text = translated_text[pos:]
        else:
            share = int(length * len(original) / total_chars)
            node.text = translated_text[pos:pos+share]
            pos += share


def translate_docx_xml(docx_path):

    temp_dir = "docx_tmp"

    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

    os.mkdir(temp_dir)

    with zipfile.ZipFile(docx_path) as z:
        z.extractall(temp_dir)

    xml_file = os.path.join(temp_dir, "word/document.xml")

    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(xml_file, parser)

    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    paragraphs = tree.xpath("//w:p", namespaces=ns)

    print("Paragraphs:", len(paragraphs))

    for p in paragraphs:

        runs = p.xpath(".//w:r[w:t]", namespaces=ns)

        if not runs:
            continue

        texts = []

        for r in runs:

            node = r.find("w:t", namespaces=ns)

            if node is not None and node.text:
                texts.append(node.text)

        paragraph_text = "".join(texts)

        if not paragraph_text.strip():
            continue

        translated = translate_text(paragraph_text)

        if not translated:
            continue

        distribute_text(runs, translated, ns)

        for r in runs:
            shrink_font(r)

    tree.write(xml_file, pretty_print=True, xml_declaration=True, encoding="UTF-8")

    with zipfile.ZipFile(docx_path, "w") as docx:

        for folder, subs, files in os.walk(temp_dir):

            for file in files:

                path = os.path.join(folder, file)
                arc = os.path.relpath(path, temp_dir)

                docx.write(path, arc)

    shutil.rmtree(temp_dir)


def translate_pdf(input_pdf):

    if not os.path.exists(input_pdf):
        print("File not found:", input_pdf)
        return

    base = os.path.splitext(input_pdf)[0]

    docx_file = base + "_translated.docx"
    output_pdf = base + "_translated.pdf"

    print("1) PDF → DOCX")

    cv = Converter(input_pdf)
    cv.convert(docx_file)
    cv.close()

    print("2) Translating")

    translate_docx_xml(docx_file)

    print("3) DOCX → PDF")

    convert(docx_file, output_pdf)

    if os.path.exists(docx_file):
        os.remove(docx_file)

    print("Done:", output_pdf)


def main():

    if len(sys.argv) < 2:
        print("Usage: python translate_pdf.py file.pdf")
        return

    translate_pdf(sys.argv[1])


if __name__ == "__main__":
    main()