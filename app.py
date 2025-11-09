import streamlit as st
from pypdf import PdfReader, PdfWriter
from pdf2image import convert_from_bytes
from io import BytesIO
from PIL import Image
import tempfile
import os

st.set_page_config(page_title="PDF-Toolkit", layout="wide")

# --- Helper Funktionen ---

def get_pdf_size(pdf_bytes):
    return len(pdf_bytes) / 1024  # in KB

def pdf_to_images(pdf_bytes):
    images = convert_from_bytes(pdf_bytes, dpi=100)
    return images

def compress_pdf(input_pdf_bytes, quality=75):
    images = convert_from_bytes(input_pdf_bytes, dpi=100)
    output = PdfWriter()
    for img in images:
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        buf.seek(0)
        temp_img = Image.open(buf)
        output.add_page(PdfReader(BytesIO(buf.getvalue())).pages[0])
    out_bytes = BytesIO()
    output.write(out_bytes)
    return out_bytes.getvalue()

def save_temp_file(pdf_bytes, filename="temp.pdf"):
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_file.write(pdf_bytes)
    tmp_file.close()
    return tmp_file.name

# --- UI: Upload ---
st.title("PDF-Toolkit")
uploaded_files = st.file_uploader("PDFs hochladen", type="pdf", accept_multiple_files=True)

pdf_bytes = f.read()
pdfs.append({
    'name': f.name,
    'bytes': pdf_bytes,
    'reader': PdfReader(BytesIO(pdf_bytes))  # aus Bytes erstellen, nicht f
})
    
    # --- Seiten-Vorschau & Reihenfolge ändern ---
    st.subheader("Seitenübersicht und Reihenfolge")
    for pdf_index, pdf in enumerate(pdfs):
        st.markdown(f"**{pdf['name']}**")
        images = pdf_to_images(pdf['bytes'])
        page_order = list(range(len(images)))
        # Drag & Drop oder Auf/Ab Buttons
        for idx, img in enumerate(images):
            st.image(img, width=150, caption=f"Seite {idx+1}")
            move_up = st.button(f"⬆ Seite {idx+1}", key=f"up_{pdf_index}_{idx}")
            move_down = st.button(f"⬇ Seite {idx+1}", key=f"down_{pdf_index}_{idx}")
            if move_up and idx > 0:
                page_order[idx], page_order[idx-1] = page_order[idx-1], page_order[idx]
            if move_down and idx < len(images)-1:
                page_order[idx], page_order[idx+1] = page_order[idx+1], page_order[idx]
        pdf['order'] = page_order

    # --- PDF Zusammenführen ---
    st.subheader("PDF zusammenführen")
    if st.button("Alle PDFs zusammenführen"):
        writer = PdfWriter()
        for pdf in pdfs:
            for idx in pdf['order']:
                writer.add_page(pdf['reader'].pages[idx])
        out_bytes = BytesIO()
        writer.write(out_bytes)
        st.success("PDFs zusammengeführt!")
        st.download_button("Download Zusammengeführt", out_bytes.getvalue(), file_name="merged.pdf")

    # --- PDF Teilen ---
    st.subheader("PDF teilen")
    split_pdf_index = st.selectbox("PDF wählen zum Teilen", [p['name'] for p in pdfs])
    split_pdf = next(p for p in pdfs if p['name'] == split_pdf_index)
    split_range = st.text_input("Seitenbereich (z.B. 1-3,5,7)", "1-1")
    if st.button("Teilen"):
        indices = []
        for part in split_range.split(','):
            if '-' in part:
                start, end = map(int, part.split('-'))
                indices.extend(list(range(start-1, end)))
            else:
                indices.append(int(part)-1)
        writer = PdfWriter()
        for idx in indices:
            writer.add_page(split_pdf['reader'].pages[idx])
        out_bytes = BytesIO()
        writer.write(out_bytes)
        st.success("PDF geteilt!")
        st.download_button("Download geteilte PDF", out_bytes.getvalue(), file_name="split.pdf")

    # --- PDF Komprimieren ---
    st.subheader("PDF komprimieren")
    compress_index = st.selectbox("PDF wählen zum Komprimieren", [p['name'] for p in pdfs], key="compress_pdf")
    compress_pdf_bytes = next(p['bytes'] for p in pdfs if p['name'] == compress_index)
    quality = st.slider("Qualität (JPEG)", 10, 100, 75)
    if st.button("Komprimieren"):
        original_size = get_pdf_size(compress_pdf_bytes)
        compressed_bytes = compress_pdf(compress_pdf_bytes, quality)
        compressed_size = get_pdf_size(compressed_bytes)
        st.write(f"Original: {original_size:.2f} KB | Komprimiert: {compressed_size:.2f} KB")
        images = pdf_to_images(compressed_bytes)
        st.image(images[0], caption="Vorschau erste Seite", width=300)
        st.download_button("Download komprimierte PDF", compressed_bytes, file_name="compressed.pdf")
