import streamlit as st
from pypdf import PdfReader, PdfWriter
from pdf2image import convert_from_path
from pdf2image import convert_from_bytes
from streamlit_sortables import sort_items
from PIL import Image
import io
import tempfile
import os

# --- HELPER ---
def bytes_to_human_readable(size_bytes):
    if size_bytes == 0:
        return "0 Bytes"
    size_name = ("Bytes", "KB", "MB", "GB", "TB")
    i = 0
    while size_bytes >= 1024 and i < len(size_name) - 1:
        size_bytes /= 1024
        i += 1
    return f"{size_bytes:.2f} {size_name[i]}"

st.set_page_config(page_title="PDF Pro Editor", page_icon="📎", layout="wide")

st.title("📎 PDF Pro Editor")
st.markdown("Laden Sie ein PDF hoch, um Seiten visuell zu bearbeiten, zu drehen, zu entfernen oder zu komprimieren.")

# --- STATE ---
if 'pdf_pages' not in st.session_state:
    st.session_state.pdf_pages = []
if 'current_file_id' not in st.session_state:
    st.session_state.current_file_id = None
if 'file_uploaded' not in st.session_state:
    st.session_state.file_uploaded = False
if 'source_pdf_path' not in st.session_state:
    st.session_state.source_pdf_path = None

# --- DATEI UPLOAD ---
uploaded_file = st.file_uploader("PDF hier ablegen", type="pdf")

if uploaded_file:
    # NEU: Lese den Inhalt nur einmal in eine lokale Variable
    pdf_bytes = uploaded_file.getvalue()
    
    if uploaded_file.file_id != st.session_state.current_file_id:
        with st.spinner('PDF wird verarbeitet... Bitte warten.'):
            try:
                # 1. PDF-Inhalt einmalig speichern
                st.session_state.source_pdf_bytes = pdf_bytes
                
                # 2. PDF lesen für spätere Extraktion (verwende BytesIO für pypdf)
                # ACHTUNG: Dies ist technisch gesehen nicht nötig, da st.session_state.source_pdf_bytes 
                # später im Export-Tab gelesen wird. Lassen wir es für die Struktur.
                # WICHTIGER ist die Konvertierung:
                
                # 3. Vorschau-Bilder generieren (verwende die lokale Variable)
                # Der Aufruf convert_from_bytes liest den Stream, aber da wir Bytes übergeben, 
                # ist es eine Kopie und der Fehler sollte behoben sein.
                images = convert_from_bytes(pdf_bytes, dpi=100)
                
                # 4. State initialisieren
                st.session_state.pdf_pages = []
                for i, img in enumerate(images):
                    st.session_state.pdf_pages.append({
                        "orig_index": i,      
                        "thumb": img,
                        "rotation": 0,
                        "is_active": True,
                        "id": f"page_{i}"
                    })
                
                st.session_state.current_file_id = uploaded_file.file_id
                st.session_state.file_uploaded = True
                
                # Speichern der Originalgröße
                st.session_state.original_size = len(st.session_state.source_pdf_bytes)
                st.rerun()
            except Exception as e:
                # ... (Fehlerbehandlung beibehalten)
                st.error(f"Fehler beim Verarbeiten der PDF. Ist 'Poppler' installiert?\nDetails: {e}")
                st.session_state.file_uploaded = False
                st.session_state.current_file_id = None # Wichtig bei Fehler

# --- HAUPTANSICHT ---
if st.session_state.file_uploaded and st.session_state.pdf_pages:
    tab_edit, tab_sort, tab_export = st.tabs(["🛠️ Bearbeiten", "🔃 Reihenfolge", "📥 Exportieren"])

    # --- TAB 1: Bearbeiten ---
    with tab_edit:
        st.subheader("Seiten bearbeiten")
        cols_per_row = 4
        all_pages = st.session_state.pdf_pages
        for i in range(0, len(all_pages), cols_per_row):
            cols = st.columns(cols_per_row)
            for j in range(cols_per_row):
                if i + j < len(all_pages):
                    page_data = all_pages[i + j]
                    with cols[j]:
                        status_icon = "✅" if page_data['is_active'] else "❌"
                        st.write(f"**Seite {page_data['orig_index'] + 1}** {status_icon}")
                        preview_img = page_data['thumb'].rotate(-page_data['rotation'], expand=True)
                        if not page_data['is_active']:
                            preview_img = preview_img.point(lambda p: p * 0.5)
                        st.image(preview_img, use_container_width=True)

                        c1, c2, c3 = st.columns(3)
                        if c1.button("↺", key=f"rotL_{page_data['orig_index']}"):
                            page_data['rotation'] = (page_data['rotation'] - 90) % 360
                            st.experimental_rerun()
                        if c2.button("↻", key=f"rotR_{page_data['orig_index']}"):
                            page_data['rotation'] = (page_data['rotation'] + 90) % 360
                            st.experimental_rerun()
                        btn_label = "🗑️ Entfernen" if page_data['is_active'] else "Wiederherstellen"
                        if c3.button(btn_label, key=f"del_{page_data['orig_index']}"):
                            page_data['is_active'] = not page_data['is_active']
                            st.experimental_rerun()

    # --- TAB 2: Sortieren ---
    with tab_sort:
        st.subheader("Reihenfolge ändern")
        active_pages = [p for p in st.session_state.pdf_pages if p['is_active']]
        if not active_pages:
            st.warning("Keine aktiven Seiten zum Sortieren vorhanden.")
        else:
            items = [{'text': f"Seite {p['orig_index']+1} (Rotation: {p['rotation']}°)", 'id': p['id']} for p in active_pages]
            sorted_results = sort_items(items, key="page_sorter", multi_containers=True)
            if sorted_results:
                id_to_page = {p['id']: p for p in st.session_state.pdf_pages}
                new_order = [id_to_page[item['id']] for item in sorted_results]
                new_order += [p for p in st.session_state.pdf_pages if not p['is_active']]
                st.session_state.pdf_pages = new_order
                st.experimental_rerun()

    # --- TAB 3: Export ---
    with tab_export:
        st.subheader("PDF exportieren")
        active_count = sum(1 for p in st.session_state.pdf_pages if p['is_active'])
        st.write(f"**Seiten im neuen PDF:** {active_count}")
        st.markdown(f"**Originalgröße:** <span class='file-size'>{bytes_to_human_readable(st.session_state.original_size)}</span>", unsafe_allow_html=True)

        compression_level = st.slider("Verlustfreie Komprimierung (0-9)", 0, 9, 6)
        image_compression = st.checkbox("Verlustbehaftete Komprimierung (Bilder)", value=False)

        if st.button("🚀 PDF Generieren & Herunterladen"):
            if active_count == 0:
                st.error("Keine Seiten aktiv.")
            else:
                with st.spinner("PDF wird erstellt..."):
                    src_pdf = PdfReader(st.session_state.source_pdf_path)
                    writer = PdfWriter()
                    for page_data in st.session_state.pdf_pages:
                        if page_data['is_active']:
                            p = src_pdf.pages[page_data['orig_index']]
                            if page_data['rotation']:
                                p.rotate(page_data['rotation'])
                            writer.add_page(p)
                            if compression_level > 0:
                                writer.pages[-1].compress_content_streams(level=compression_level)
                            if image_compression:
                                writer.pages[-1].compress_images()
                    output = io.BytesIO()
                    writer.write(output)
                    pdf_bytes = output.getvalue()
                    st.success("PDF erstellt!")
                    st.markdown(f"**Neue Größe:** <span class='file-size'>{bytes_to_human_readable(len(pdf_bytes))}</span>", unsafe_allow_html=True)
                    st.download_button("📥 Herunterladen", pdf_bytes, "bearbeitet_pro.pdf", "application/pdf")
else:
    st.info("👆 Bitte laden Sie zuerst eine PDF-Datei hoch.")
