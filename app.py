import streamlit as st
from pypdf import PdfReader, PdfWriter
from pdf2image import convert_from_bytes
from streamlit_sortables import sort_items
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import io

# --- HELPER FUNKTIONEN ---
def bytes_to_human_readable(size_bytes):
    if size_bytes == 0:
        return "0 Bytes"
    size_name = ("Bytes", "KB", "MB", "GB", "TB")
    i = 0
    while size_bytes >= 1024 and i < len(size_name) - 1:
        size_bytes /= 1024
        i += 1
    return f"{size_bytes:.2f} {size_name[i]}"

def make_placeholder_image(page_number, size=(420, 595)):
    img = Image.new("RGB", size, (245, 245, 245))
    draw = ImageDraw.Draw(img)
    text = f"Seite {page_number}"
    try:
        # Versuche eine Systemschrift, falls verfügbar
        font = ImageFont.truetype("DejaVuSans.ttf", 28)
    except Exception:
        font = ImageFont.load_default()
    w, h = draw.textsize(text, font=font)
    draw.text(((size[0]-w)/2, (size[1]-h)/2), text, fill=(80,80,80), font=font)
    return img

# --- SEITEN KONFIGURATION ---
st.set_page_config(page_title="PDF Pro Editor", page_icon="📎", layout="wide")

st.markdown("""
<style>
    .file-size { font-size: 1.05em; font-weight:600; padding:4px 8px; border-radius:6px; background:#e6f7ff; }
</style>
""", unsafe_allow_html=True)

st.title("📎 PDF Pro Editor")
st.markdown("PDF hochladen. Vorschau, Seiten drehen, entfernen, Reihenfolge ändern und exportieren.")

# --- STATE MANAGEMENT ---
if 'pdf_pages' not in st.session_state:
    st.session_state.pdf_pages = []
if 'current_file_id' not in st.session_state:
    st.session_state.current_file_id = None
if 'file_uploaded' not in st.session_state:
    st.session_state.file_uploaded = False
if 'source_pdf_bytes' not in st.session_state:
    st.session_state.source_pdf_bytes = None
if 'original_size' not in st.session_state:
    st.session_state.original_size = 0

# --- DATEI UPLOAD ---
uploaded_file = st.file_uploader("PDF hier ablegen", type="pdf")

if uploaded_file:
    # Wenn dieselbe Datei erneut hochgeladen wurde, nichts neu initialisieren
    if uploaded_file.name != st.session_state.current_file_id:
        with st.spinner("PDF wird verarbeitet..."):
            try:
                # Einmalige Bytes-Leseoperation (sicher)
                pdf_bytes = uploaded_file.getvalue()
                if not pdf_bytes:
                    raise ValueError("Keine Bytes gefunden in der hochgeladenen Datei.")

                # PdfReader mit eigener BytesIO-Kopie
                pdf_reader = PdfReader(io.BytesIO(pdf_bytes), strict=False)
                page_count = len(pdf_reader.pages)
                if page_count == 0:
                    raise ValueError("PDF enthält keine Seiten.")

                images = None
                # Vorschaubilder generieren (Poppler erforderlich). Falls Fehlschlag -> Platzhalter
                try:
                    images = convert_from_bytes(pdf_bytes, dpi=100)
                    # convert_from_bytes kann weniger/more Seiten liefern in seltenen Fällen
                    if len(images) != page_count:
                        # immer noch akzeptieren, aber wenn mismatch -> fallback to placeholders to keep indices consistent
                        images = None
                except Exception as e_img:
                    images = None

                # Wenn keine Vorschaubilder möglich, Platzhalterbilder erstellen
                if images is None:
                    images = [make_placeholder_image(i + 1) for i in range(page_count)]
                    st.warning("Vorschau konnte nicht als Bild erzeugt werden. Es werden Platzhalter angezeigt. (Poppler möglicherweise nicht installiert oder PDF ungewöhnlich.)")

                # State initialisieren (original_index bleibt stabil)
                st.session_state.pdf_pages = []
                for i, img in enumerate(images):
                    st.session_state.pdf_pages.append({
                        "orig_index": i,
                        "thumb": img,
                        "rotation": 0,
                        "is_active": True,
                        "id": f"page_{i}"
                    })

                st.session_state.source_pdf_bytes = pdf_bytes
                st.session_state.current_file_id = uploaded_file.name
                st.session_state.file_uploaded = True
                st.session_state.original_size = len(pdf_bytes)

                st.experimental_rerun()
            except Exception as e:
                st.error(f"Fehler beim Verarbeiten der PDF. Details: {e}")
                st.session_state.file_uploaded = False

# --- HAUPTANSICHT ---
if st.session_state.file_uploaded and st.session_state.pdf_pages:
    tab_edit, tab_sort, tab_export = st.tabs(["🛠️ Bearbeiten", "🔃 Reihenfolge", "📥 Exportieren"])

    # --- TAB 1: BEARBEITEN (GRID) ---
    with tab_edit:
        st.subheader("Seiten bearbeiten")
        cols_per_row = 4
        pages = st.session_state.pdf_pages
        for i in range(0, len(pages), cols_per_row):
            cols = st.columns(cols_per_row)
            for j in range(cols_per_row):
                idx = i + j
                if idx < len(pages):
                    p = pages[idx]
                    with cols[j]:
                        status_icon = "✅" if p['is_active'] else "❌"
                        st.markdown(f"**Seite {p['orig_index'] + 1}** {status_icon}")
                        # Vorschau rotieren (PIL)
                        preview = p['thumb'].rotate(-p['rotation'], expand=True)
                        if not p['is_active']:
                            try:
                                enhancer = ImageEnhance.Brightness(preview)
                                preview = enhancer.enhance(0.6)
                            except Exception:
                                # Fallback dim
                                preview = preview.point(lambda px: px//2)
                        st.image(preview, use_container_width=True)

                        c1, c2, c3 = st.columns([1,1,1])
                        if c1.button("↺", key=f"rotL_{p['id']}"):
                            p['rotation'] = (p['rotation'] - 90) % 360
                            st.experimental_rerun()
                        if c2.button("↻", key=f"rotR_{p['id']}"):
                            p['rotation'] = (p['rotation'] + 90) % 360
                            st.experimental_rerun()
                        btn_label = "🗑️ Entfernen" if p['is_active'] else "Wiederherstellen"
                        if c3.button(btn_label, key=f"toggle_{p['id']}"):
                            p['is_active'] = not p['is_active']
                            st.experimental_rerun()

    # --- TAB 2: SORTIEREN (Drag & Drop) ---
    with tab_sort:
        st.subheader("Reihenfolge ändern")
        st.info("Nur aktive Seiten werden gezogen. Inaktive Seiten bleiben am Ende.")
        active_pages = [p for p in st.session_state.pdf_pages if p['is_active']]
        if not active_pages:
            st.warning("Keine aktiven Seiten zum Sortieren vorhanden.")
        else:
            items = [{'text': f"Seite {p['orig_index']+1} (Rot:{p['rotation']}°)", 'id': p['id']} for p in active_pages]
            try:
                sorted_results = sort_items(items, key="page_sorter", multi_containers=True)
            except Exception as e:
                st.error(f"Sortier-Widget Fehler: {e}")
                sorted_results = None

            if sorted_results:
                # sort_items liefert Liste von dicts [{'id':...}, ...] oder ev. nur ids; handle beide Fälle
                if isinstance(sorted_results[0], dict) and 'id' in sorted_results[0]:
                    new_active_ids = [it['id'] for it in sorted_results]
                else:
                    new_active_ids = list(sorted_results)

                id_to_page = {p['id']: p for p in st.session_state.pdf_pages}
                new_order = []
                for aid in new_active_ids:
                    if aid in id_to_page:
                        new_order.append(id_to_page[aid])
                # append inactive pages unchanged (preserve their relative order)
                new_order += [p for p in st.session_state.pdf_pages if not p['is_active']]
                # Only update if changed
                old_ids = [p['id'] for p in st.session_state.pdf_pages]
                new_ids = [p['id'] for p in new_order]
                if old_ids != new_ids:
                    st.session_state.pdf_pages = new_order
                    st.success("Reihenfolge aktualisiert.")
                    st.experimental_rerun()

    # --- TAB 3: EXPORT / DOWNLOAD ---
    with tab_export:
        st.subheader("PDF exportieren")
        active_count = sum(1 for p in st.session_state.pdf_pages if p['is_active'])
        st.write(f"**Seiten im neuen PDF:** {active_count}")
        st.markdown(f"**Originalgröße:** <span class='file-size'>{bytes_to_human_readable(st.session_state.original_size)}</span>", unsafe_allow_html=True)

        compression_note = st.checkbox("Versuche einfache Bild-Kompression (nur bei eingebetteten Bildern wirksam)", value=False)
        st.divider()

        if st.button("🚀 PDF Generieren & Herunterladen"):
            if active_count == 0:
                st.error("Keine aktive Seite zum Exportieren.")
            else:
                with st.spinner("PDF wird erstellt..."):
                    try:
                        src_pdf = PdfReader(io.BytesIO(st.session_state.source_pdf_bytes), strict=False)
                        writer = PdfWriter()
                        for p in st.session_state.pdf_pages:
                            if not p['is_active']:
                                continue
                            page_obj = src_pdf.pages[p['orig_index']]
                            # Rotation anwenden (pypdf)
                            rot = p.get('rotation', 0) % 360
                            if rot != 0:
                                # rotate_clockwise ist in pypdf verfügbar
                                try:
                                    page_obj.rotate_clockwise(rot)
                                except Exception:
                                    # fallback: rotate in 90° steps with counterclockwise if needed
                                    try:
                                        page_obj.rotate(rot)
                                    except Exception:
                                        pass
                            writer.add_page(page_obj)

                        out = io.BytesIO()
                        writer.write(out)
                        pdf_bytes_new = out.getvalue()
                        st.success("PDF erfolgreich erstellt.")
                        st.markdown(f"**Neue Größe:** <span class='file-size'>{bytes_to_human_readable(len(pdf_bytes_new))}</span>", unsafe_allow_html=True)
                        st.download_button("📥 Fertiges PDF herunterladen", data=pdf_bytes_new, file_name="bearbeitet_pro.pdf", mime="application/pdf", use_container_width=True)

                        # Vorschau der ersten Seite (falls möglich)
                        try:
                            preview_imgs = convert_from_bytes(pdf_bytes_new, dpi=100, first_page=1, last_page=1)
                            if preview_imgs:
                                st.image(preview_imgs[0], caption="Vorschau (erste Seite)", width=400)
                        except Exception:
                            # kein Preview möglich, kein Problem
                            pass

                    except Exception as e_export:
                        st.error(f"Fehler beim Erstellen des PDFs: {e_export}")

else:
    st.info("👆 Bitte laden Sie zuerst eine PDF-Datei hoch.")
