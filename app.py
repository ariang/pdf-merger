import streamlit as st
from pypdf import PdfReader, PdfWriter
from pdf2image import convert_from_bytes
from io import BytesIO
from PIL import Image
import tempfile

st.set_page_config(page_title="PDF-Toolkit", layout="wide")

def get_pdf_size(pdf_bytes):
    return len(pdf_bytes) / 1024  # KB

def pdf_to_images(pdf_bytes):
    images = convert_from_bytes(pdf_bytes, dpi=100)
    return images

def compress_pdf(input_pdf_bytes, quality=75):
    images = convert_from_bytes(input_pdf_bytes, dpi=100)
    writer = PdfWriter()
    for img in images:
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        buf.seek(0)
        writer.add_page(PdfReader(BytesIO(buf.getvalue())).pages[0])
    out_bytes = BytesIO()
    writer.write(out_bytes)
    return out_bytes.getvalue()

st.title("PDF-Toolkit")
uploaded_files = st.file_uploader("PDFs hochladen", type="pdf", accept_multiple_files=True)

if uploaded_files:
    pdfs = []
    for f in uploaded_files:
        pdf_bytes = f.read()
        pdfs.append({
            'name': f.name,
            'bytes': pdf_bytes,
            'reader': PdfReader(BytesIO(pdf_bytes))
        })

    st.subheader("Seitenübersicht und Reihenfolge")
    for pdf_index, pdf in enumerate(pdfs):
        st.markdown(f"**{pdf['name']}**")
        images = pdf_to_images(pdf['bytes'])
        page_order = list(range(len(images)))
        for idx, img in enumerate(images):
            st.image(img, width=150, caption=f"Seite {idx+1}")
            move_up = st.button(f"⬆ Seite {idx+1}", key=f"up_{pdf_index}_{idx}")
            move_down = st.button(f"⬇ Seite {idx+1}", key=f"down_{pdf_index}_{idx}")
            if move_up and idx > 0:
                page_order[idx], page_order[idx-1] = page_order[idx-1], page_order[idx]
            if move_down and idx < len(images)-1:
                page_order[idx], page_order[idx+1] = page_order[idx+1], page_order[idx]
        pdf['order'] = page_order

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

st.set_page_config(page_title="PDF-Toolkit", layout="wide")

def get_pdf_size(pdf_bytes):
    return len(pdf_bytes) / 1024  # KB

def compress_pdf_bytes(pdf_bytes, compression_level=6):
    # pikepdf komprimiert PDF ohne Konvertierung zu Bildern
    buf = BytesIO()
    try:
        with pikepdf.open(BytesIO(pdf_bytes)) as pdf:
            pdf.save(buf, compression=pikepdf.CompressionLevel(compression_level))
    except Exception:
        return pdf_bytes  # fallback, falls fehlerhaft
    return buf.getvalue()

uploaded_files = st.file_uploader("PDFs hochladen", type="pdf", accept_multiple_files=True)

if uploaded_files:
    pdfs = []
    for f in uploaded_files:
        pdf_bytes = f.read()
        try:
            reader = PdfReader(BytesIO(pdf_bytes))
            pdfs.append({'name': f.name, 'bytes': pdf_bytes, 'reader': reader})
        except Exception:
            st.error(f"Die PDF '{f.name}' konnte nicht gelesen werden.")

    if pdfs:
        # Zusammenführen
        if st.button("Alle PDFs zusammenführen"):
            writer = PdfWriter()
            for pdf in pdfs:
                for page in pdf['reader'].pages:
                    writer.add_page(page)
            out_bytes = BytesIO()
            writer.write(out_bytes)
            st.download_button("Download Zusammengeführt", out_bytes.getvalue(), file_name="merged.pdf")

        # Kompression
        compress_index = st.selectbox("PDF wählen zum Komprimieren", [p['name'] for p in pdfs])
        compress_pdf_bytes_data = next(p['bytes'] for p in pdfs if p['name'] == compress_index)
        compression_level = st.slider("Kompressionsstufe", 1, 9, 6)
        if st.button("Komprimieren"):
            original_size = get_pdf_size(compress_pdf_bytes_data)
            compressed_bytes = compress_pdf_bytes(compress_pdf_bytes_data, compression_level)
            compressed_size = get_pdf_size(compressed_bytes)
            st.write(f"Original: {original_size:.2f} KB | Komprimiert: {compressed_size:.2f} KB")
            st.download_button("Download komprimierte PDF", compressed_bytes, file_name="compressed.pdf")
