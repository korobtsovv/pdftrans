#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import tkinter as tk
from tkinter import filedialog
import subprocess

def select_file():
    path = filedialog.askopenfilename(filetypes=[("PDF files","*.pdf")])
    if path:
        subprocess.run(["python3", "gpttranslate.py", path])

root = tk.Tk()
root.title("PDF Translator")

btn = tk.Button(root, text="Select PDF", command=select_file)
btn.pack(padx=40, pady=40)

root.mainloop()