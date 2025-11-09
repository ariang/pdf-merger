import streamlit as st
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
import tempfile

st.set_page_config(page_title="PDF Tool", page_icon="📎")
st.title("📎 PDF Merger & Splitter")

mode = st.radio("Funktion wählen", ["PDFs zusammenführen", "PDF aufteilen"])

# --- ZUSAMMENFÜHREN ---
if mode == "PDFs zusammenführen":
    uploaded_files = st.file_uploader(
        "Wähle mehrere PDFs aus", accept_multiple_files=True, type="pdf"
    )

    if uploaded_files:
        st.subheader("Reihenfolge der Dateien")
        filenames = [f.name for f in uploaded_files]
        order = st.multiselect(
            "Reihenfolge festlegen",
            options=filenames,
            default=filenames,
            help="Wähle oder ordne die PDFs in der gewünschten Reihenfolge an.",
        )

        if st.button("Zusammenführen"):
            if not order:
                st.warning("Bitte Reihenfolge auswählen.")
            else:
                merger = PdfMerger()
                name_to_file = {f.name: f for f in uploaded_files}
                for name in order:
                    merger.append(name_to_file[name])

                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    merger.write(tmp.name)
                    merger.close()
                    with open(tmp.name, "rb") as merged_pdf:
                        st.download_button(
                            "📥 Zusammengeführte PDF herunterladen",
                            merged_pdf,
                            "merged.pdf",
                        )

# --- AUFTEILEN ---
else:
    uploaded_file = st.file_uploader("Wähle eine PDF-Datei", type="pdf")

    if uploaded_file:
        reader = PdfReader(uploaded_file)
        total_pages = len(reader.pages)
        st.info(f"Diese PDF hat {total_pages} Seiten.")

        page_selection = st.text_input(
            "Welche Seiten extrahieren?",
            placeholder="z. B. 1,3-5,7",
            help="Kommagetrennt: einzelne Seiten (1,3) oder Bereiche (3-5).",
        )

        if st.button("Aufteilen"):
            if not page_selection:
                st.warning("Bitte Seiten angeben.")
            else:
                pages_to_extract = []
                for part in page_selection.split(","):
                    if "-" in part:
                        start, end = map(int, part.split("-"))
                        pages_to_extract.extend(range(start, end + 1))
                    else:
                        pages_to_extract.append(int(part))
                pages_to_extract = [p - 1 for p in pages_to_extract if 0 < p <= total_pages]

                writer = PdfWriter()
                for p in pages_to_extract:
                    writer.add_page(reader.pages[p])

                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    writer.write(tmp)
                    writer.close()
                    with open(tmp.name, "rb") as split_pdf:
                        st.download_button(
                            "📥 Extrahierte Seiten herunterladen",
                            split_pdf,
                            "extracted_pages.pdf",
                        )
