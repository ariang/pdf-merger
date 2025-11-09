import streamlit as st
from pypdf import PdfReader, PdfWriter
from pdf2image import convert_from_bytes
# Die korrekte Funktion für das Sortieren ist 'sort_items'
from streamlit_sortables import sort_items 
from PIL import Image
import io

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
</style>
""", unsafe_allow_html=True)

st.title("📎 PDF Pro Editor")
st.markdown("Laden Sie ein PDF hoch, um Seiten visuell anzuordnen, zu drehen, zu entfernen oder zu komprimieren.")

# --- STATE MANAGEMENT INITIALISIEREN ---
if 'pdf_pages' not in st.session_state:
    # Speichert die Metadaten jeder Seite: Original-Index, Drehung, Aktiv-Status, Bild
    st.session_state.pdf_pages = []
if 'current_file_id' not in st.session_state:
    st.session_state.current_file_id = None
if 'file_uploaded' not in st.session_state:
    st.session_state.file_uploaded = False

# --- DATEI UPLOAD ---
uploaded_file = st.file_uploader("PDF hier ablegen", type="pdf")

if uploaded_file:
    # Prüfen, ob eine neue Datei hochgeladen wurde
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
                        "orig_index": i,       # Verweis auf die Originalseite im PDF
                        "thumb": img,          # Vorschaubild
                        "rotation": 0,         # Aktuelle Drehung (0, 90, 180, 270)
                        "is_active": True,     # Soll die Seite im End-PDF sein?
                        "id": f"page_{i}"      # Eindeutige ID für Sortables
                    })
                
                # Speichern der Rohdaten für den finalen Build
                st.session_state.source_pdf_bytes = uploaded_file.getvalue()
                st.session_state.current_file_id = uploaded_file.file_id
                st.session_state.file_uploaded = True
                st.rerun() # UI neu laden mit Daten
            except Exception as e:
                st.error(f"Fehler beim Verarbeiten der PDF. Ist 'Poppler' installiert?\nDetails: {e}")
                st.session_state.file_uploaded = False

# --- HAUPTANSICHT (NUR WENN DATEI GELADEN) ---
if st.session_state.file_uploaded and st.session_state.pdf_pages:
    
    # Tabs für bessere Übersicht
    tab_edit, tab_sort, tab_export = st.tabs(["🛠️ Bearbeiten (Drehen/Löschen)", "🔃 Reihenfolge (Drag & Drop)", "📥 Exportieren"])

    # --- TAB 1: BEARBEITEN (GRID VIEW) ---
    with tab_edit:
        st.subheader("Seiten visuell bearbeiten")
        
        # Grid-Layout erstellen (z.B. 4 Spalten)
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
                            
                            # Aktions-Buttons
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
        
        sortable_items_list = [
            {'text': f"Seite {p['orig_index'] + 1} (Rotation: {p['rotation']}°)", 'id': p['id']}
            for p in active_pages_for_sort
        ]
        
        # KORRIGIERTER AUFRUF: sort_items
        sorted_results = sort_items(sortable_items_list, key="page_sorter", multi_containers=True) 
        
        id_to_page = {p['id']: p for p in st.session_state.pdf_pages}
        new_ordered_pages = []
        
        if sorted_results:
            for item in sorted_results:
                new_ordered_pages.append(id_to_page[item['id']])
        else:
            new_ordered_pages = active_pages_for_sort

        for p in st.session_state.pdf_pages:
            if not p['is_active']:
                 new_ordered_pages.append(p)
                 
        current_ids = [p['id'] for p in st.session_state.pdf_pages if p['is_active']]
        new_sorted_ids = [item['id'] for item in sorted_results] if sorted_results else []
        
        if current_ids != new_sorted_ids and sorted_results:
             st.session_state.pdf_pages = new_ordered_pages
             st.toast("Reihenfolge aktualisiert!", icon="✅")
             st.rerun()

    # --- TAB 3: EXPORT ---
    with tab_export:
        st.subheader("PDF fertigstellen")
        
        active_count = sum(1 for p in st.session_state.pdf_pages if p['is_active'])
        st.write(f"Ihr neues PDF wird **{active_count}** Seiten enthalten.")
        
        st.divider()
        st.subheader("Optionen")
        
        compress_pdf = st.checkbox(
            "PDF verlustfrei komprimieren", 
            value=True, 
            help="Entfernt überflüssige Daten aus den Seitenströmen. Reduziert die Dateigröße, ohne die Qualität zu beeinträchtigen."
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
                            
                            # KORRIGIERTE LOGIK: Seite zuerst hinzufügen, dann komprimieren
                            writer.add_page(original_page)
                            
                            if compress_pdf:
                                # Komprimierung auf die Seite im Writer aufrufen
                                writer.pages[-1].compress_content_streams() 
                    
                    output_pdf = io.BytesIO()
                    writer.write(output_pdf)
                    pdf_bytes = output_pdf.getvalue()
                    
                    st.success("PDF erfolgreich erstellt!")
                    st.download_button(
                        label="📥 Fertiges PDF herunterladen",
                        data=pdf_bytes,
                        file_name="bearbeitet_pro.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )

else:
    st.info("👆 Bitte laden Sie zuerst eine PDF-Datei hoch.")
