import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_bytes
from streamlit_sortables import sortables
from PIL import Image
import tempfile
import io

st.set_page_config(page_title="📎 PDF Pro Editor", layout="wide")
st.title("📎 PDF Pro Editor - Visuell & Drag&Drop")

uploaded_file = st.file_uploader("PDF hochladen", type="pdf")

if uploaded_file:
    reader = PdfReader(uploaded_file)
    pages = reader.pages
    total_pages = len(pages)
    
    # PDF in Thumbnails umwandeln
    images = convert_from_bytes(uploaded_file.read(), dpi=100)
    
    # Seiten als Dictionary speichern
    page_data = [{"index": i, "image": img, "rotation": 0, "keep": True} for i, img in enumerate(images)]
    
    st.subheader("Seiten bearbeiten & anordnen")
    
    # Sortierbare Liste anzeigen
    sorted_pages = sortables(
        page_data,
        key="index",
        render=lambda page: (
            page["image"].resize((150, int(page["image"].height * 150 / page["image"].width))),
            f'Seite {page["index"] + 1}',
            st.checkbox("Beibehalten", value=True, key=f"keep_{page['index']}"),
            st.radio("Rotation", [0, 90, 180, 270], index=page["rotation"]//90, key=f"rot_{page['index']}")
        ),
        direction="horizontal"
    )
    
    if st.button("📥 PDF erstellen"):
        writer = PdfWriter()
        for p in sorted_pages:
            if st.session_state.get(f"keep_{p['index']}", True):
                page = pages[p["index"]]
                rot = st.session_state.get(f"rot_{p['index']}", 0)
                if rot != 0:
                    page.rotate_clockwise(rot)
                writer.add_page(page)
        
        # Temporäre Datei zum Download
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            writer.write(tmp)
            tmp_path = tmp.name
        
        with open(tmp_path, "rb") as f:
            st.download_button("Download PDF", f, "edited.pdf")
