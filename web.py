#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import gradio as gr
import subprocess


def translate(file):

    if file is None:
        return "Please upload a PDF file."

    try:
        subprocess.run(
            ["python3", "gpttranslate.py", file.name],
            check=True
        )

        return "Translation finished."

    except Exception as e:
        return f"Error: {e}"


demo = gr.Interface(
    fn=translate,
    inputs=gr.File(file_types=[".pdf"]),
    outputs="text",
    title="PDF Translator",
    description="Upload a Ukrainian PDF to translate it to English"
)

demo.launch()