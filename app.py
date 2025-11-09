import streamlit as st
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
import io

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
                    # Streamlit uploaded file is a file-like object; PdfMerger akzeptiert das direkt
                    merger.append(name_to_file[name])

                buf = io.BytesIO()
                merger.write(buf)
                merger.close()
                buf.seek(0)
                st.download_button(
                    "📥 Zusammengeführte PDF herunterladen",
                    buf,
                    file_name="merged.pdf",
                    mime="application/pdf",
                )

# --- AUFTEILEN ---
else:
    uploaded_file = st.file_uploader("Wähle eine PDF-Datei", type="pdf")

    if uploaded_file:
        try:
            reader = PdfReader(uploaded_file)
        except Exception as e:
            st.error(f"Kann die PDF nicht lesen: {e}")
        else:
            total_pages = len(reader.pages)
            st.info(f"Diese PDF hat {total_pages} Seiten.")

            page_selection = st.text_input(
                "Welche Seiten extrahieren?",
                placeholder="z. B. 1,3-5,7",
                help="Kommagetrennt: einzelne Seiten (1,3) oder Bereiche (3-5).",
            )

            if st.button("Aufteilen"):
                if not page_selection.strip():
                    st.warning("Bitte Seiten angeben.")
                else:
                    pages_to_extract = []
                    valid = True
                    for part in page_selection.split(","):
                        part = part.strip()
                        if not part:
                            continue
                        if "-" in part:
                            try:
                                start_s, end_s = part.split("-", 1)
                                start = int(start_s)
                                end = int(end_s)
                            except Exception:
                                valid = False
                                break
                            if start > end:
                                valid = False
                                break
                            pages_to_extract.extend(range(start, end + 1))
                        else:
                            try:
                                pages_to_extract.append(int(part))
                            except Exception:
                                valid = False
                                break

                    # filter valid page numbers and convert to 0-based
                    pages_to_extract = [p - 1 for p in pages_to_extract if 0 < p <= total_pages]

                    if not valid or not pages_to_extract:
                        st.error("Ungültige Seitenangabe oder Seiten ausserhalb des Bereichs.")
                    else:
                        writer = PdfWriter()
                        for p in pages_to_extract:
                            writer.add_page(reader.pages[p])

                        buf = io.BytesIO()
                        writer.write(buf)
                        # PdfWriter hat keine close()-Methode in manchen Versionen. safe to just seek.
                        buf.seek(0)
                        st.download_button(
                            "📥 Extrahierte Seiten herunterladen",
                            buf,
                            file_name="extracted_pages.pdf",
                            mime="application/pdf",
                        )
