import streamlit as st
from pypdf import PdfReader, PdfWriter
from io import BytesIO
import pikepdf
from pdf2image import convert_from_bytes
import traceback

st.set_page_config(page_title="PDF-Toolkit", layout="wide")

def get_pdf_size(pdf_bytes):
    return len(pdf_bytes) / 1024  # KB

def pdf_to_images(pdf_bytes):
    """Convert PDF to images for preview. Returns empty list if conversion fails."""
    try:
        images = convert_from_bytes(pdf_bytes, dpi=100)
        return images
    except Exception as e:
        # pdf2image might fail if poppler is not available
        # Return empty list silently - UI will handle it by showing page numbers
        return []

def compress_pdf_bytes(pdf_bytes):
    """Compress PDF using pikepdf."""
    buf = BytesIO()
    try:
        with pikepdf.open(BytesIO(pdf_bytes)) as pdf:
            # Remove metadata and compress streams
            pdf.save(
                buf,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
                normalize_content=True,
                recompress_flate=True
            )
            buf.seek(0)
            return buf.getvalue()
    except Exception as e:
        st.error(f"Compression failed: {str(e)}")
        return pdf_bytes

def create_pdf_reader(pdf_bytes):
    """Create a PdfReader from bytes."""
    try:
        return PdfReader(BytesIO(pdf_bytes))
    except Exception as e:
        st.error(f"Failed to read PDF: {str(e)}")
        return None

st.title("PDF-Toolkit")

uploaded_files = st.file_uploader("Upload PDFs", type="pdf", accept_multiple_files=True)

# Initialize session state
if 'pdfs' not in st.session_state:
    st.session_state.pdfs = []
if 'images_cache' not in st.session_state:
    st.session_state.images_cache = {}

# Handle file uploads
if uploaded_files:
    # Get current file names
    current_file_names = {f.name for f in uploaded_files}
    
    # Check if files have changed (different names or different count)
    stored_file_names = {p['name'] for p in st.session_state.pdfs} if st.session_state.pdfs else set()
    
    if current_file_names != stored_file_names:
        # Files changed, reset and reload
        st.session_state.pdfs = []
        st.session_state.images_cache = {}
        
        for f in uploaded_files:
            try:
                pdf_bytes = f.read()
                
                reader = create_pdf_reader(pdf_bytes)
                if reader is None:
                    st.error(f"Could not read PDF '{f.name}'. Please check if it's a valid PDF file.")
                    continue
                
                num_pages = len(reader.pages)
                if num_pages == 0:
                    st.warning(f"PDF '{f.name}' has no pages.")
                    continue
                
                page_order = list(range(num_pages))
                
                # Store PDF data (without reader object for serialization)
                st.session_state.pdfs.append({
                    'name': f.name,
                    'bytes': pdf_bytes,
                    'num_pages': num_pages,
                    'order': page_order
                })
                
                # Cache images for preview
                images = pdf_to_images(pdf_bytes)
                if images:
                    st.session_state.images_cache[f.name] = images
            except Exception as e:
                st.error(f"Error processing '{f.name}': {str(e)}")
                continue
else:
    # No files uploaded, clear session state
    if st.session_state.pdfs:
        st.session_state.pdfs = []
        st.session_state.images_cache = {}

if 'pdfs' in st.session_state and st.session_state.pdfs:
    pdfs = st.session_state.pdfs

    st.subheader("Page Overview & Reorder")
    
    # Check if any PDFs have preview images
    has_any_images = any(pdf['name'] in st.session_state.images_cache for pdf in pdfs)
    if not has_any_images:
        st.info("💡 Preview images are not available, but you can still reorder pages by page number.")
    
    # Reorder pages
    for pdf_index, pdf in enumerate(pdfs):
        st.markdown(f"**{pdf['name']}** ({pdf['num_pages']} pages)")
        images = st.session_state.images_cache.get(pdf['name'], [])
        order = pdf['order']

        # Display all pages with reorder buttons
        if images:
            # Show thumbnails if images are available
            for display_idx, page_idx in enumerate(order):
                cols = st.columns([1, 1, 6])
                with cols[0]:
                    if st.button("⬆", key=f"up_{pdf_index}_{display_idx}", disabled=(display_idx == 0)):
                        if display_idx > 0:
                            order[display_idx], order[display_idx-1] = order[display_idx-1], order[display_idx]
                            st.rerun()
                with cols[1]:
                    if st.button("⬇", key=f"down_{pdf_index}_{display_idx}", disabled=(display_idx == len(order)-1)):
                        if display_idx < len(order)-1:
                            order[display_idx], order[display_idx+1] = order[display_idx+1], order[display_idx]
                            st.rerun()
                with cols[2]:
                    if page_idx < len(images):
                        st.image(images[page_idx], width=150, caption=f"Page {page_idx+1}")
                    else:
                        st.write(f"Page {page_idx+1} (preview not available)")
        else:
            # Show page numbers if images are not available
            st.write("Page order (use buttons to reorder):")
            for display_idx, page_idx in enumerate(order):
                cols = st.columns([1, 1, 6])
                with cols[0]:
                    if st.button("⬆", key=f"up_{pdf_index}_{display_idx}", disabled=(display_idx == 0)):
                        if display_idx > 0:
                            order[display_idx], order[display_idx-1] = order[display_idx-1], order[display_idx]
                            st.rerun()
                with cols[1]:
                    if st.button("⬇", key=f"down_{pdf_index}_{display_idx}", disabled=(display_idx == len(order)-1)):
                        if display_idx < len(order)-1:
                            order[display_idx], order[display_idx+1] = order[display_idx+1], order[display_idx]
                            st.rerun()
                with cols[2]:
                    st.write(f"Page {page_idx + 1}")

    # Merge PDFs
    st.subheader("Merge PDFs")
    if st.button("Merge All PDFs"):
        try:
            writer = PdfWriter()
            for pdf in pdfs:
                reader = create_pdf_reader(pdf['bytes'])
                if reader is None:
                    continue
                for idx in pdf['order']:
                    if 0 <= idx < len(reader.pages):
                        writer.add_page(reader.pages[idx])
            
            out_bytes = BytesIO()
            writer.write(out_bytes)
            out_bytes.seek(0)  # Reset position to beginning
            
            st.success("PDFs merged successfully!")
            st.download_button(
                "Download Merged PDF",
                out_bytes.getvalue(),
                file_name="merged.pdf",
                mime="application/pdf"
            )
        except Exception as e:
            st.error(f"Failed to merge PDFs: {str(e)}")
            st.code(traceback.format_exc())

    # Split PDF
    st.subheader("Split PDF")
    if len(pdfs) > 0:
        split_pdf_names = [p['name'] for p in pdfs]
        split_pdf_index = st.selectbox("Select PDF to split", split_pdf_names, key="split_select")
        split_pdf = next(p for p in pdfs if p['name'] == split_pdf_index)
        
        st.write(f"PDF has {split_pdf['num_pages']} pages. Enter page range (e.g., 1-3,5,7-9)")
        split_range = st.text_input("Page range", "1-1", key="split_range")
        
        if st.button("Split PDF"):
            try:
                reader = create_pdf_reader(split_pdf['bytes'])
                if reader is None:
                    st.error("Could not read PDF for splitting.")
                else:
                    indices = []
                    parts = split_range.split(',')
                    for part in parts:
                        part = part.strip()
                        if '-' in part:
                            start_str, end_str = part.split('-', 1)
                            try:
                                start = int(start_str.strip())
                                end = int(end_str.strip())
                                # Convert to 0-based indexing and validate
                                start_idx = max(0, min(start - 1, len(reader.pages) - 1))
                                end_idx = max(0, min(end - 1, len(reader.pages) - 1))
                                # Include end page
                                if start_idx <= end_idx:
                                    indices.extend(range(start_idx, end_idx + 1))
                                else:
                                    st.warning(f"Invalid range: {part} (start > end)")
                            except ValueError:
                                st.error(f"Invalid range format: {part}")
                        else:
                            try:
                                page_num = int(part.strip())
                                idx = page_num - 1
                                if 0 <= idx < len(reader.pages):
                                    indices.append(idx)
                                else:
                                    st.warning(f"Page {page_num} is out of range (1-{len(reader.pages)})")
                            except ValueError:
                                st.error(f"Invalid page number: {part}")
                    
                    if indices:
                        # Remove duplicates while preserving order
                        seen = set()
                        unique_indices = []
                        for idx in indices:
                            if idx not in seen:
                                seen.add(idx)
                                unique_indices.append(idx)
                        
                        writer = PdfWriter()
                        for idx in unique_indices:
                            writer.add_page(reader.pages[idx])
                        
                        out_bytes = BytesIO()
                        writer.write(out_bytes)
                        out_bytes.seek(0)  # Reset position to beginning
                        
                        st.success(f"PDF split successfully! Extracted {len(unique_indices)} page(s).")
                        st.download_button(
                            "Download Split PDF",
                            out_bytes.getvalue(),
                            file_name="split.pdf",
                            mime="application/pdf"
                        )
                    else:
                        st.error("No valid pages selected for splitting.")
            except Exception as e:
                st.error(f"Failed to split PDF: {str(e)}")
                st.code(traceback.format_exc())

    # Compress PDF
    st.subheader("Compress PDF")
    if len(pdfs) > 0:
        compress_pdf_names = [p['name'] for p in pdfs]
        compress_index = st.selectbox("Select PDF to compress", compress_pdf_names, key="compress_select")
        compress_pdf = next(p for p in pdfs if p['name'] == compress_index)
        compress_pdf_bytes_data = compress_pdf['bytes']
        
        compression_info = st.info("Compression reduces file size by optimizing the PDF structure. Quality is preserved.")
        
        if st.button("Compress PDF"):
            try:
                original_size = get_pdf_size(compress_pdf_bytes_data)
                compressed_bytes = compress_pdf_bytes(compress_pdf_bytes_data)
                compressed_size = get_pdf_size(compressed_bytes)
                
                reduction = ((original_size - compressed_size) / original_size) * 100 if original_size > 0 else 0
                
                st.write(f"**Original size:** {original_size:.2f} KB")
                st.write(f"**Compressed size:** {compressed_size:.2f} KB")
                st.write(f"**Reduction:** {reduction:.1f}%")
                
                # Show preview
                images = pdf_to_images(compressed_bytes)
                if images:
                    st.image(images[0], caption="Preview of first page", width=300)
                
                st.download_button(
                    "Download Compressed PDF",
                    compressed_bytes,
                    file_name="compressed.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Failed to compress PDF: {str(e)}")
                st.code(traceback.format_exc())

else:
    st.info("Please upload one or more PDF files to get started.")
