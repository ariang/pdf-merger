import streamlit as st
from PyPDF2 import PdfMerger
import tempfile

st.set_page_config(page_title="PDF Merger", page_icon="📎")
st.title("📎 PDF Merger mit Reihenfolge-Auswahl")

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
