# app.py
import streamlit as st
from pypdf import PdfReader, PdfWriter
from pdf2image import convert_from_bytes
from PIL import Image
import io
import tempfile
import os
import subprocess
import base64

# Optional: drag reorder
try:
    from streamlit_sortables import sort_items
    HAS_SORTABLES = True
except Exception:
    HAS_SORTABLES = False

# -----------------------
# Hilfsfunktionen
# -----------------------
def bytes_to_human(num_bytes: int) -> str:
    for unit in ['B','KB','MB','GB']:
        if num_bytes < 1024:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.2f} TB"

def read_pdf_pages(pdf_bytes: bytes):
    """Gibt Anzahl Seiten und Reader zurück."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return reader, len(reader.pages)

@st.cache_data
def generate_thumbnails(pdf_bytes: bytes, pages=None, dpi=100):
    """Erzeuge Thumbnails als PIL.Images; pages = list of 1-based pages oder None für alle."""
    images = []
    if pages is None:
        pil_pages = convert_from_bytes(pdf_bytes, dpi=dpi)
        images = pil_pages
    else:
        # pdf2image kann page Auswahl über first_page/last_page, für einzelne Seiten mehrere Aufrufe
        for p in pages:
            imgs = convert_from_bytes(pdf_bytes, first_page=p, last_page=p, dpi=dpi)
            images.append(imgs[0])
    return images

def merge_pdfs_bytes(list_of_bytes):
    writer = PdfWriter()
    for b in list_of_bytes:
        r = PdfReader(io.BytesIO(b))
        for p in r.pages:
            writer.add_page(p)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()

def reorder_pdf_bytes(pdf_bytes: bytes, new_order: list):
    """new_order ist Liste mit 0-basierten Seitenindizes in gewünschter Reihenfolge."""
    r = PdfReader(io.BytesIO(pdf_bytes))
    w = PdfWriter()
    for idx in new_order:
        w.add_page(r.pages[idx])
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()

def extract_pages(pdf_bytes: bytes, page_indices: list):
    r = PdfReader(io.BytesIO(pdf_bytes))
    w = PdfWriter()
    for i in page_indices:
        w.add_page(r.pages[i])
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()

def compress_with_ghostscript(input_bytes: bytes, quality: str = "ebook"):
    """Benötigt ghostscript (gs) auf dem System. quality: screen, ebook, printer, prepress"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as in_f:
        in_f.write(input_bytes)
        in_path = in_f.name
    out_path = in_path.replace(".pdf", f".compressed.pdf")
    # Ghostscript command
    gs_cmd = [
        "gs", "-sDEVICE=pdfwrite", f"-dPDFSETTINGS=/{quality}",
        "-dNOPAUSE", "-dQUIET", "-dBATCH",
        f"-sOutputFile={out_path}", in_path
    ]
    try:
        subprocess.run(gs_cmd, check=True)
        with open(out_path, "rb") as f:
            out = f.read()
    except Exception as e:
        st.error(f"Ghostscript Fehler: {e}")
        out = input_bytes
    finally:
        try:
            os.remove(in_path)
            if os.path.exists(out_path):
                os.remove(out_path)
        except Exception:
            pass
    return out

def make_pdf_download_button(pdf_bytes: bytes, filename: str = "result.pdf"):
    st.download_button("Download PDF", data=pdf_bytes, file_name=filename, mime="application/pdf")

# -----------------------
# Session State initialisieren
# -----------------------
if 'files' not in st.session_state:
    # files: list of dicts {name, bytes, size, pages}
    st.session_state['files'] = []

if 'current' not in st.session_state:
    st.session_state['current'] = None  # index in files

# -----------------------
# UI
# -----------------------
st.title("PDF Toolbox (Streamlit)")

st.sidebar.header("Upload / Cloud")
uploaded = st.sidebar.file_uploader("PDF(s) hochladen (Drag & Drop möglich)", accept_multiple_files=True, type=['pdf'])
if uploaded:
    for up in uploaded:
        data = up.read()
        reader, n_pages = read_pdf_pages(data)
        st.session_state['files'].append({
            'name': up.name,
            'bytes': data,
            'size': len(data),
            'pages': n_pages
        })
    st.sidebar.success(f"{len(uploaded)} Datei(en) hinzugefügt")

# Dateiliste
st.sidebar.header("Dateien")
for i, f in enumerate(st.session_state['files']):
    cols = st.sidebar.columns([1,2,1])
    cols[0].write(f"{i+1}.")
    if cols[1].button(f"{f['name']}", key=f"open_{i}"):
        st.session_state['current'] = i
    cols[2].write(bytes_to_human(f['size']))
if st.sidebar.button("Alle löschen"):
    st.session_state['files'] = []
    st.session_state['current'] = None

# Hauptbereich: Datei bearbeiten
if st.session_state['current'] is None:
    st.info("Wähle links eine Datei aus oder lade eine hoch.")
    st.stop()

file_obj = st.session_state['files'][st.session_state['current']]
st.header(file_obj['name'])
st.write(f"Seiten: {file_obj['pages']} — Grösse: {bytes_to_human(file_obj['size'])}")

# Thumbnails anzeigen
with st.expander("Thumbnails / Seiten"):
    thumbs = generate_thumbnails(file_obj['bytes'], dpi=100)
    # Prepare simple list of images for ordering
    img_cols = st.columns(len(thumbs) if len(thumbs) <= 6 else 6)
    # Simple grid display (for full drag & drop use streamlit_sortables)
    for idx, img in enumerate(thumbs):
        c = img_cols[idx % len(img_cols)]
        c.image(img, caption=f"Seite {idx+1}", use_column_width=True)
        # Selection checkbox
        if c.checkbox("Auswählen", key=f"sel_{idx}"):
            pass
    st.write("Nutze Drag & Drop (wenn verfügbar) oder Buttons unten, um die Reihenfolge zu ändern.")

# Reihenfolge ändern (Fallback Buttons)
st.subheader("Reihenfolge ändern")
if HAS_SORTABLES:
    # Beispiel minimal: IDs als strings
    items = [f"Seite {i+1}" for i in range(file_obj['pages'])]
    order = sort_items(items, key="reorder")
    st.write("Neue Reihenfolge:", order)
    # map order back to indices omitted here (implement mapping)
else:
    col1, col2 = st.columns(2)
    if col1.button("Seite 1 nach unten") or col2.button("Seite 2 nach oben"):
        st.info("Nutze streamlit_sortables für echtes Drag & Drop. Fallback: Implementiere Up/Down per Buttons.")

# Split / Extract
st.subheader("Seiten extrahieren / teilen")
page_range = st.text_input("Seiten (z.B. 1,3-5)", value="")
if st.button("Extrahieren"):
    try:
        indices = []
        for part in page_range.split(','):
            if '-' in part:
                a,b = map(int, part.split('-'))
                indices.extend(list(range(a-1, b)))
            elif part.strip():
                indices.append(int(part)-1)
        out_bytes = extract_pages(file_obj['bytes'], indices)
        st.download_button("Download extrahierte PDF", data=out_bytes, file_name="extract.pdf", mime="application/pdf")
    except Exception as e:
        st.error(f"Fehler beim Extrahieren: {e}")

# Merge (einfaches Beispiel)
st.subheader("Zusammenführen")
if len(st.session_state['files']) > 1:
    to_merge = st.multiselect("Dateien auswählen zum Zusammenführen", options=[(i, f['name']) for i,f in enumerate(st.session_state['files'])], format_func=lambda x: x[1])
    if st.button("Merge"):
        bytes_list = [st.session_state['files'][i]['bytes'] for i,_name in to_merge]
        merged = merge_pdfs_bytes(bytes_list)
        st.success("Zusammengeführt")
        st.download_button("Download merged PDF", merged, "merged.pdf", "application/pdf")
else:
    st.info("Mehrere Dateien zum Zusammenführen nötig.")

# Kompression
st.subheader("Kompression")
quality = st.selectbox("Qualität (Ghostscript PDFSETTINGS)", options=["screen","ebook","printer","prepress"], index=1)
if st.button("Komprimieren & Vorschau"):
    before = len(file_obj['bytes'])
    compressed = compress_with_ghostscript(file_obj['bytes'], quality=quality)
    after = len(compressed)
    st.write(f"Original: {bytes_to_human(before)} → Komprimiert: {bytes_to_human(after)} ({(after/before)*100:.1f}%)")
    # Vorschau erste Seite
    try:
        img = generate_thumbnails(compressed, pages=[1], dpi=120)[0]
        st.image(img, caption="Vorschau (erste Seite) nach Kompression")
        st.download_button("Download komprimierte PDF", compressed, "compressed.pdf", "application/pdf")
    except Exception as e:
        st.error(f"Vorschau nicht möglich: {e}")

# Download final
st.subheader("Resultat")
if st.button("Download aktuelle Datei"):
    make_pdf_download_button(file_obj['bytes'], filename=file_obj['name'])
