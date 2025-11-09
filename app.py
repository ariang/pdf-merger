# app.py
import streamlit as st
from PyPDF2 import PdfReader, PdfWriter, PdfMerger
import io
import tempfile
import os
from pathlib import Path
from typing import List
from PIL import Image
import math

# optional imports
try:
    from pdf2image import convert_from_bytes
    HAS_PDF2IMAGE = True
except Exception:
    HAS_PDF2IMAGE = False

try:
    from streamlit_sortables import sort_items
    HAS_SORTABLES = True
except Exception:
    HAS_SORTABLES = False

# ---------------------------
# Helpers
# ---------------------------
def human_size(n: int) -> str:
    if n < 1024: return f"{n} B"
    for unit in ["KB","MB","GB","TB"]:
        n /= 1024.0
        if n < 1024:
            return f"{n:.2f} {unit}"
    return f"{n:.2f} PB"

def pdf_to_thumbs(pdf_bytes: bytes, dpi=100, fmt="PNG"):
    if not HAS_PDF2IMAGE:
        return None
    try:
        images = convert_from_bytes(pdf_bytes, dpi=dpi)
        thumbs = []
        for img in images:
            img.thumbnail((260, 360))
            buf = io.BytesIO()
            img.save(buf, format=fmt)
            buf.seek(0)
            thumbs.append(buf.read())
        return thumbs
    except Exception:
        return None

def pages_from_reader(reader: PdfReader) -> int:
    return len(reader.pages)

def download_bytes_button(data: bytes, filename: str, label: str):
    st.download_button(label, data, file_name=filename, mime="application/pdf")

def render_pdf_from_writer(writer: PdfWriter) -> bytes:
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf.read()

def rasterize_and_make_pdf(pdf_bytes: bytes, dpi: int=150) -> bytes:
    # lossy compression: rasterize each page at given dpi then combine
    if not HAS_PDF2IMAGE:
        raise RuntimeError("pdf2image (poppler) fehlt. Installiere pdf2image und Poppler.")
    images = convert_from_bytes(pdf_bytes, dpi=dpi)
    image_bufs = []
    for img in images:
        rgb = img.convert("RGB")
        b = io.BytesIO()
        rgb.save(b, format="PDF", quality=85)
        b.seek(0)
        image_bufs.append(Image.open(b))
    out_buf = io.BytesIO()
    if image_bufs:
        image_bufs[0].save(out_buf, format="PDF", save_all=True, append_images=image_bufs[1:])
    out_buf.seek(0)
    return out_buf.read()

# ---------------------------
# UI / Session init
# ---------------------------
st.set_page_config(page_title="PDF Pro Tool", layout="wide")
if "uploads" not in st.session_state:
    st.session_state.uploads = []  # list of dict {name, data (bytes)}

lang = st.selectbox("Sprache / Language", ["Deutsch","English"])
DE = (lang == "Deutsch")

def t(d, e=None):
    return d if DE else (e or d)

st.title(t("PDF Pro Tool — Pro Funktionen","PDF Pro Tool — Pro features"))
st.caption(t(
    "Hinweis: Thumbnails brauchen pdf2image + Poppler. Reihenfolge Drag&Drop nur mit streamlit-sortables.",
    "Note: Thumbnails need pdf2image + Poppler. Drag&Drop ordering needs streamlit-sortables."
))

# Upload area
with st.expander(t("PDFs hochladen / Upload PDFs","Upload PDFs")):
    uploaded = st.file_uploader(t("Wähle mehrere PDFs","Select multiple PDFs"), accept_multiple_files=True, type="pdf")
    if uploaded:
        for f in uploaded:
            data = f.read()
            # avoid duplicates by name+size
            exists = any((u["name"]==f.name and u["size"]==len(data)) for u in st.session_state.uploads)
            if not exists:
                st.session_state.uploads.append({"name": f.name, "data": data, "size": len(data)})

# show uploaded files
st.sidebar.header(t("Hochgeladene Dateien","Uploaded files"))
if not st.session_state.uploads:
    st.sidebar.info(t("Keine Dateien hochgeladen.","No files uploaded."))
else:
    for i,u in enumerate(st.session_state.uploads):
        st.sidebar.write(f"{i+1}. {u['name']} — {human_size(u['size'])}")
    if st.sidebar.button(t("Alle entfernen","Remove all")):
        st.session_state.uploads.clear()
        st.experimental_rerun()

# Mode selection
mode = st.radio(
    t("Funktion wählen","Choose function"),
    [t("Zusammenführen","Merge"), t("PDF bearbeiten (Split/Reorder/Delete/Rotate)","Edit PDF (Split/Reorder/Delete/Rotate)"), t("Komprimieren (Raster)","Compress (raster)"), t("Passwort setzen/entfernen","Password set/remove")]
)

# ---------------------------
# Merge mode
# ---------------------------
if mode == t("Zusammenführen","Merge"):
    st.header(t("PDFs zusammenführen","Merge PDFs"))
    if not st.session_state.uploads:
        st.info(t("Lade zuerst PDFs hoch.","Upload PDFs first."))
    else:
        # ordering UI
        names = [u["name"] for u in st.session_state.uploads]
        st.subheader(t("Reihenfolge wählen","Choose order"))
        if HAS_SORTABLES:
            order = sort_items(names, key="order")
        else:
            st.write(t("Drag&Drop nicht verfügbar. Benutze Auswahl unten.","Drag&Drop not available. Use selection below."))
            order = st.multiselect(t("Reihenfolge","Order"), options=names, default=names)
        if st.button(t("Zusammenführen und herunterladen","Merge and download")):
            merger = PdfMerger()
            for name in order:
                u = next(x for x in st.session_state.uploads if x["name"]==name)
                merger.append(io.BytesIO(u["data"]))
            out_buf = io.BytesIO()
            merger.write(out_buf)
            merger.close()
            out_buf.seek(0)
            download_bytes_button(out_buf.read(), "merged.pdf", t("Download merged.pdf","Download merged.pdf"))

# ---------------------------
# Edit single PDF: split, reorder, delete, rotate, export pages
# ---------------------------
elif mode == t("PDF bearbeiten (Split/Reorder/Delete/Rotate)","Edit PDF (Split/Reorder/Delete/Rotate)"):
    st.header(t("PDF bearbeiten","Edit single PDF"))
    if not st.session_state.uploads:
        st.info(t("Lade zuerst wenigstens eine PDF hoch.","Upload at least one PDF first."))
    else:
        sel_name = st.selectbox(t("Wähle eine Datei","Select a file"), [u["name"] for u in st.session_state.uploads])
        u = next(x for x in st.session_state.uploads if x["name"]==sel_name)
        reader = None
        try:
            reader = PdfReader(io.BytesIO(u["data"]))
        except Exception as e:
            st.error(t("Fehler beim Lesen der PDF:","Error reading PDF:") + str(e))

        if reader:
            total = pages_from_reader(reader)
            st.info(t(f"Seiten: {total}","Pages: ") + str(total))
            # thumbnails (if available)
            thumbs = None
            if HAS_PDF2IMAGE:
                with st.spinner(t("Generiere Thumbnails...","Generating thumbnails...")):
                    thumbs = pdf_to_thumbs(u["data"], dpi=100)
            # Page list and operations
            st.subheader(t("Seitenverwaltung","Page management"))

            page_indices = list(range(1, total+1))
            # show thumbnails + checkboxes
            cols = st.columns(3)
            selected_pages = []
            for idx in page_indices:
                col = cols[(idx-1)%3]
                key = f"p_{sel_name}_{idx}"
                if thumbs and idx-1 < len(thumbs):
                    col.image(thumbs[idx-1], caption=str(idx), use_column_width=True)
                else:
                    col.write(t("Seite","Page") + f" {idx}")
                checked = col.checkbox(t("Behalten","Keep"), value=True, key=key)
                if checked:
                    selected_pages.append(idx-1)

            # reorder selected pages
            st.write(t("Gewählte Seiten reihenfolge festlegen","Set order of chosen pages"))
            selected_names = [f"Seite {i+1}" for i in selected_pages]
            if not selected_pages:
                st.warning(t("Keine Seiten ausgewählt.","No pages selected."))
            else:
                if HAS_SORTABLES:
                    new_order_labels = sort_items(selected_names, key="page_order")
                    # map labels back to indices
                    new_order = [int(lbl.split()[1]) - 1 for lbl in new_order_labels]
                else:
                    new_order = st.multiselect(t("Reihenfolge","Order"), options=selected_names, default=selected_names)
                    new_order = [int(lbl.split()[1]) - 1 for lbl in new_order]
                # rotate option
                rotate_deg = st.selectbox(t("Drehen","Rotate"), [0, 90, 180, 270], index=0)
                # Export options
                col1, col2, col3 = st.columns(3)
                if col1.button(t("Extrahieren & herunterladen","Extract & download")):
                    writer = PdfWriter()
                    for p in new_order:
                        page = reader.pages[p]
                        if rotate_deg:
                            page.rotate(rotate_deg)
                        writer.add_page(page)
                    data = render_pdf_from_writer(writer)
                    download_bytes_button(data, "extracted.pdf", t("Download extrahierte Seiten","Download extracted pages"))
                if col2.button(t("Seiten als Bilder herunterladen (JPG)","Download pages as JPG")):
                    if not HAS_PDF2IMAGE:
                        st.error(t("pdf2image/Poppler fehlt. Kann nicht exportieren.","pdf2image/Poppler missing. Cannot export."))
                    else:
                        imgs = convert_from_bytes(u["data"], dpi=150)
                        # filter pages
                        chosen_imgs = [imgs[p] for p in new_order]
                        # make a zip in memory
                        import zipfile
                        zbuf = io.BytesIO()
                        with zipfile.ZipFile(zbuf, "w") as z:
                            for i,img in enumerate(chosen_imgs, start=1):
                                b = io.BytesIO()
                                img.convert("RGB").save(b, format="JPEG", quality=85)
                                b.seek(0)
                                z.writestr(f"page_{i}.jpg", b.read())
                        zbuf.seek(0)
                        st.download_button(t("Download JPG ZIP","Download JPG ZIP"), zbuf.read(), file_name="pages.zip", mime="application/zip")
                if col3.button(t("Seiten löschen & neues PDF herunterladen","Delete pages & download new PDF")):
                    # create writer with only pages not selected
                    writer = PdfWriter()
                    keep_set = set(new_order)  # careful: here new_order are kept pages
                    for i in range(total):
                        if i in keep_set:
                            page = reader.pages[i]
                            if rotate_deg:
                                page.rotate(rotate_deg)
                            writer.add_page(page)
                    data = render_pdf_from_writer(writer)
                    download_bytes_button(data, f"edited_{sel_name}", t("Download neues PDF","Download new PDF"))

# ---------------------------
# Compression mode (raster)
# ---------------------------
elif mode == t("Komprimieren (Raster)","Compress (raster)"):
    st.header(t("Komprimieren durch Rasterisierung (verlustbehaftet)","Compress by rasterizing (lossy)"))
    st.warning(t(
        "Das Komprimieren rendert Seiten als Bilder. Resultat ist verlustbehaftet, aber oft deutlich kleiner.",
        "Compression rasterizes pages to images. Output is lossy but can be much smaller."
    ))
    if not st.session_state.uploads:
        st.info(t("Lade zuerst eine Datei hoch.","Upload a file first."))
    else:
        sel_name = st.selectbox(t("Wähle eine Datei zum komprimieren","Select a file to compress"), [u["name"] for u in st.session_state.uploads])
        u = next(x for x in st.session_state.uploads if x["name"]==sel_name)
        dpi = st.slider(t("DPI (niedriger = kleinere Datei)","DPI (lower = smaller file)"), 50, 300, 150)
        if st.button(t("Komprimiere und herunterladen","Compress and download")):
            try:
                out = rasterize_and_make_pdf(u["data"], dpi=dpi)
            except Exception as e:
                st.error(str(e))
            else:
                st.write(t("Originalgröße:", "Original size:"), human_size(len(u["data"])))
                st.write(t("Komprimierte Größe:", "Compressed size:"), human_size(len(out)))
                download_bytes_button(out, f"compressed_{sel_name}", t("Download komprimierte PDF","Download compressed PDF"))

# ---------------------------
# Password set / remove
# ---------------------------
elif mode == t("Passwort setzen/entfernen","Password set/remove"):
    st.header(t("Passwort setzen oder entfernen","Set or remove PDF password"))
    if not st.session_state.uploads:
        st.info(t("Lade zuerst eine Datei hoch.","Upload a file first."))
    else:
        sel_name = st.selectbox(t("Wähle Datei","Select file"), [u["name"] for u in st.session_state.uploads])
        u = next(x for x in st.session_state.uploads if x["name"]==sel_name)
        action = st.radio(t("Aktion","Action"), [t("Passwort setzen","Set password"), t("Passwort entfernen (falls bekannt)","Remove password (if known)")])
        if action == t("Passwort setzen","Set password"):
            pwd = st.text_input(t("Neues Passwort","New password"), type="password")
            if st.button(t("Setzen & herunterladen","Set & download")):
                writer = PdfWriter()
                reader = PdfReader(io.BytesIO(u["data"]))
                for p in reader.pages:
                    writer.add_page(p)
                if not pwd:
                    st.error(t("Gib ein Passwort ein.","Enter a password."))
                else:
                    try:
                        writer.encrypt(pwd)
                        data = render_pdf_from_writer(writer)
                        download_bytes_button(data, f"pwd_{sel_name}", t("Download passwortgeschützte PDF","Download password protected PDF"))
                    except Exception as e:
                        st.error(str(e))
        else:
            # remove
            pwd = st.text_input(t("Momentanes Passwort","Current password"), type="password")
            if st.button(t("Entfernen & herunterladen","Remove & download")):
                try:
                    reader = PdfReader(io.BytesIO(u["data"]))
                    # try without password first
                    if reader.is_encrypted:
                        if not pwd:
                            st.error(t("PDF ist verschlüsselt. Gib das Passwort ein.","PDF is encrypted. Provide password."))
                        else:
                            reader = PdfReader(io.BytesIO(u["data"]), password=pwd)
                    writer = PdfWriter()
                    for p in reader.pages:
                        writer.add_page(p)
                    data = render_pdf_from_writer(writer)
                    download_bytes_button(data, f"unlocked_{sel_name}", t("Download entschlüsselte PDF","Download unlocked PDF"))
                except Exception as e:
                    st.error(t("Fehler beim Entfernen des Passworts: ","Error removing password: ") + str(e))

# Footer / Cleanup
st.markdown("---")
st.caption(t(
    "Privacy: Dateien werden nur temporär in der Session gehalten. Für Thumbnails wird pdf2image + Poppler benötigt.",
    "Privacy: Files are kept only in session. Thumbnails require pdf2image + Poppler."
))
