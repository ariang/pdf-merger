import streamlit as st
from PyPDF2 import PdfMerger
import tempfile
import os

st.title("PDF-Merger")

uploaded_files = st.file_uploader("Wähle mehrere PDFs aus", accept_multiple_files=True, type="pdf")

if uploaded_files and st.button("Zusammenführen"):
    merger = PdfMerger()
    for f in uploaded_files:
        merger.append(f)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        merger.write(tmp.name)
        merger.close()
        with open(tmp.name, "rb") as merged_pdf:
            st.download_button("Download PDF", merged_pdf, "merged.pdf")
