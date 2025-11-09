import streamlit as st
from pypdf import PdfReader, PdfWriter
from pdf2image import convert_from_bytes
from streamlit_sortables import sort_items 
from PIL import Image
import io
import os # Für die Dateigrößenberechnung

# --- HELPER FUNKTIONEN ---

def bytes_to_human_readable(size_bytes):
    """Konvertiert Bytegröße in lesbare Form (KB, MB)."""
    if size_bytes == 0:
        return "0 Bytes"
    # Feste Einheitengrößen (1024)
    size_name = ("Bytes", "KB", "MB", "GB", "TB")
    i = 0
    while size_bytes >= 1024 and i < len(size_name) - 1:
        size_bytes /= 1024
        i += 1
    return f"{size_bytes:.2f} {size_name[i]}"

# --- SEITEN KONFIGURATION ---
st.set_page_config(page_title="PDF Pro Editor", page_icon="📎", layout="wide")

# Custom CSS für schönere Darstellung
st.markdown("""
<style>
    .page-card {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 10px;
        background-color: #f9f9f9;
        text-align: center;
    }
    .stButton > button {
        width: 100%;
        border-radius: 5px;
    }
    /* Visuelle Hervorhebung für Dateigrößen */
    .file-size {
        font-size: 1.1em;
        font-weight: bold;
        padding: 5px 10px;
        border-radius: 5px;
        background-color: #e6f7ff; /* Hellblau */
    }
</style>
""", unsafe_allow_html=True)

st.title("📎 PDF Pro Editor")
st.markdown("Laden Sie ein PDF hoch, um Seiten visuell anzuordnen, zu drehen, zu entfernen oder zu komprimieren.")

# --- STATE MANAGEMENT INITIALISIEREN ---
if 'pdf_pages' not in st.session_state:
    st.session_state.pdf_pages = []
if 'current_file_id' not in st.session_state:
    st.session_state.current_file_id = None
if 'file_uploaded' not in st.session_state:
    st.session_state.file_uploaded = False
if 'source_pdf_bytes' not in st.session_state:
    st.session_state.source_pdf_bytes = None

# --- DATEI UPLOAD ---
uploaded_file = st.file_uploader("PDF hier ablegen", type="pdf")

if uploaded_file:
    if uploaded_file.file_id != st.session_state.current_file_id:
        with st.spinner('PDF wird verarbeitet... Bitte warten.'):
            try:
                # 1. PDF lesen für spätere Extraktion
                pdf_reader = PdfReader(uploaded_file)
                
                # 2. Vorschau-Bilder generieren (benötigt Poppler!)
                images = convert_from_bytes(uploaded_file.getvalue(), dpi=100)
                
                # 3. State initialisieren
                st.session_state.pdf_pages = []
                for i, img in enumerate(images):
                    st.session_state.pdf_pages.append({
                        "orig_index": i,       
                        "thumb": img,
                        "rotation": 0,
                        "is_active": True,
                        "id": f"page_{i}"
                    })
                
                st.session_state.source_pdf_bytes = uploaded_file.getvalue()
                st.session_state.current_file_id = uploaded_file.file_id
                st.session_state.file_uploaded = True
                
                # NEU: Speichern der Originalgröße
                st.session_state.original_size = len(st.session_state.source_pdf_bytes)
                st.rerun()
            except Exception as e:
                st.error(f"Fehler beim Verarbeiten der PDF. Ist 'Poppler' installiert?\nDetails: {e}")
                st.session_state.file_uploaded = False

# --- HAUPTANSICHT (NUR WENN DATEI GELADEN) ---
if st.session_state.file_uploaded and st.session_state.pdf_pages:
    
    tab_edit, tab_sort, tab_export = st.tabs(["🛠️ Bearbeiten (Drehen/Löschen)", "🔃 Reihenfolge (Drag & Drop)", "📥 Exportieren"])

    # --- TAB 1: BEARBEITEN (GRID VIEW) ---
    with tab_edit:
        st.subheader("Seiten visuell bearbeiten")
        
        cols_per_row = 4
        all_pages = st.session_state.pdf_pages
        
        for i in range(0, len(all_pages), cols_per_row):
            cols = st.columns(cols_per_row)
            for j in range(cols_per_row):
                if i + j < len(all_pages):
                    page_data = all_pages[i+j]
                    with cols[j]:
                        with st.container(border=True):
                            status_icon = "✅" if page_data['is_active'] else "❌"
                            st.write(f"**Seite {page_data['orig_index'] + 1}** {status_icon}")
                            
                            preview_img = page_data['thumb'].rotate(-page_data['rotation'], expand=True)
                            
                            if not page_data['is_active']:
                                preview_img = preview_img.point(lambda p: p * 0.5)
                            
                            st.image(preview_img, use_container_width=True)
                            
                            c1, c2, c3 = st.columns(3)
                            if c1.button("↺", key=f"rotL_{page_data['orig_index']}", help="90° Links drehen"):
                                page_data['rotation'] = (page_data['rotation'] - 90) % 360
                                st.rerun()
                            if c2.button("↻", key=f"rotR_{page_data['orig_index']}", help="90° Rechts drehen"):
                                page_data['rotation'] = (page_data['rotation'] + 90) % 360
                                st.rerun()
                            
                            btn_label = "🗑️ Entfernen" if page_data['is_active'] else "Wiederherstellen"
                            btn_type = "secondary" if page_data['is_active'] else "primary"
                            if c3.button(btn_label, key=f"del_{page_data['orig_index']}", type=btn_type, help="Seite entfernen/wiederherstellen"):
                                page_data['is_active'] = not page_data['is_active']
                                st.rerun()

    # --- TAB 2: SORTIEREN (DRAG & DROP) ---
    with tab_sort:
        st.subheader("Reihenfolge ändern")
        st.info("Ziehen Sie die Elemente, um die Reihenfolge zu ändern. Änderungen werden automatisch übernommen. (Nur aktive Seiten werden hier angezeigt)")
        
        active_pages_for_sort = [p for p in st.session_state.pdf_pages if p['is_active']]
        
        # KORREKTUR: Sicherstellen, dass die Liste nicht leer ist, um den Component Error zu vermeiden
        if not active_pages_for_sort:
            st.warning("Keine aktiven Seiten zum Sortieren vorhanden. Bitte Seiten in 'Bearbeiten' aktivieren.")
            sorted_results = []
        else:
            sortable_items_list = [
                {'text': f"Seite {p['orig_index'] + 1} (Rotation: {p['rotation']}°)", 'id': p['id']}
                for p in active_pages_for_sort
            ]
            
            sorted_results = sort_items(sortable_items_list, key="page_sorter") 
            
            id_to_page = {p['id']: p for p in st.session_state.pdf_pages}
            new_ordered_pages = []
            
            # Die Sortier-Logik wurde beibehalten
            for item in sorted_results:
                new_ordered_pages.append(id_to_page[item['id']])

            for p in st.session_state.pdf_pages:
                if not p['is_active']:
                    new_ordered_pages.append(p)
                    
            current_ids = [p['id'] for p in st.session_state.pdf_pages if p['is_active']]
            new_sorted_ids = [item['id'] for item in sorted_results]
            
            if current_ids != new_sorted_ids:
                st.session_state.pdf_pages = new_ordered_pages
                st.toast("Reihenfolge aktualisiert!", icon="✅")
                st.rerun()

    # --- TAB 3: EXPORT ---
    with tab_export:
        st.subheader("PDF fertigstellen und komprimieren")
        
        active_count = sum(1 for p in st.session_state.pdf_pages if p['is_active'])
        st.write(f"Ihr neues PDF wird **{active_count}** Seiten enthalten.")
        
        # NEU: Anzeige der Originalgröße
        if st.session_state.get('original_size'):
            st.markdown(f"**Originalgröße:** <span class='file-size'>{bytes_to_human_readable(st.session_state.original_size)}</span>", unsafe_allow_html=True)
        
        st.divider()
        st.subheader("Komprimierungsoptionen")
        
        col_c1, col_c2 = st.columns(2)
        
        with col_c1:
            # 1. Verlustfreie Komprimierung (Zlib)
            compression_level = st.slider(
                "Verlustfreie Komprimierung",
                min_value=0, 
                max_value=9, 
                value=6,
                step=1,
                help="Level 0 deaktiviert die Komprimierung. Empfohlen für Vektorgrafiken und Text. Reduziert oft nur wenig."
            )
        
        with col_c2:
            # 2. Verlustbehaftete Komprimierung (Bilder)
            image_compression = st.checkbox(
                "Verlustbehaftete Komprimierung (Achtung: Bilder)", 
                value=False,
                help="Reduziert die Qualität eingebetteter Bilder drastisch, um die Dateigröße stark zu senken. Kann Bilder unscharf machen."
            )
        
        st.divider()
        
        if st.button("🚀 PDF Generieren & Herunterladen", type="primary", use_container_width=True):
            if active_count == 0:
                st.error("Sie haben alle Seiten entfernt. Es gibt nichts zu generieren.")
            else:
                with st.spinner("PDF wird erstellt..."):
                    
                    src_pdf = PdfReader(io.BytesIO(st.session_state.source_pdf_bytes))
                    writer = PdfWriter()
                    
                    for page_data in st.session_state.pdf_pages:
                        if page_data['is_active']:
                            original_page = src_pdf.pages[page_data['orig_index']]
                            
                            if page_data['rotation'] != 0:
                                original_page.rotate(page_data['rotation'])
                            
                            writer.add_page(original_page)
                            
                            # Verlustfreie Komprimierung (Level > 0)
                            if compression_level > 0:
                                writer.pages[-1].compress_content_streams(level=compression_level)
                            
                            # NEU: Verlustbehaftete Komprimierung (nur wenn Checkbox aktiv)
                            if image_compression:
                                writer.pages[-1].compress_images() 
                    
                    output_pdf = io.BytesIO()
                    writer.write(output_pdf)
                    pdf_bytes = output_pdf.getvalue()
                    
                    # NEU: Anzeige der neuen Größe
                    new_size = len(pdf_bytes)
                    
                    st.success("PDF erfolgreich erstellt!")
                    
                    col_dl_1, col_dl_2 = st.columns([1, 2])
                    with col_dl_1:
                        st.markdown(f"**Neue Größe:** <span class='file-size' style='background-color:#d4edda; color:#155724;'>{bytes_to_human_readable(new_size)}</span>", unsafe_allow_html=True)
                    with col_dl_2:
                        st.download_button(
                            label="📥 Fertiges PDF herunterladen",
                            data=pdf_bytes,
                            file_name="bearbeitet_pro.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                        
                    # NEU: Vorschau der ersten Seite
                    st.divider()
                    st.subheader("Vorschau (Erste Seite)")
                    
                    try:
                        # Konvertiere die neue PDF-Datei in ein Bild zur Vorschau
                        preview_images = convert_from_bytes(pdf_bytes, dpi=100, first_page=1, last_page=1)
                        if preview_images:
                            st.image(preview_images[0], caption="Vorschau der ersten Seite des neuen PDF", width=400)
                    except Exception as e:
                        st.warning(f"Konnte keine Vorschau der neuen Datei generieren: {e}")

else:
    st.info("👆 Bitte laden Sie zuerst eine PDF-Datei hoch.")
