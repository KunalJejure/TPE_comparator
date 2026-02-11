import streamlit as st
from PIL import Image
import tempfile
import os
import fitz  # PyMuPDF
import cv2
import numpy as np
import base64
from services.pdf_report import generate_diff_pdf

# ---------------- CONFIG ----------------
st.set_page_config(
    page_title="PDF Diff Visualizer",
    layout="centered",
    initial_sidebar_state="collapsed",
    page_icon="📄",
)

# ---------------- PALETTE & STYLES (Soft & Readable) ----------------
BG_COLOR = "#F3F5F9"        # Softer cool gray background
CARD_BG = "#FFFFFF"
TEXT_PRIMARY = "#2C3E50"    # Dark blue-gray (easier on eyes than black)
TEXT_SECONDARY = "#7F8C8D"  # Medium gray
ACCENT = "#5D9CEC"          # Soft Blue
ACCENT_LIGHT = "#EAF2FA"    # Very light blue for tags
SUCCESS = "#2ECC71"         # Soft Green
ERROR = "#E74C3C"           # Soft Red
BORDER = "#E0E6ED"          

st.markdown(f"""
<style>
/* Font */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

* {{
    font-family: 'Inter', sans-serif;
    color: {TEXT_PRIMARY};
}}

.stApp {{
    background-color: {BG_COLOR};
}}

/* Hide default elements */
#MainMenu {{visibility: hidden;}}
footer {{visibility: hidden;}}
header {{visibility: hidden;}}

/* Hero Section */
.hero-container {{
    text-align: center;
    padding: 60px 0 40px 0;
}}

.hero-title {{
    font-size: 42px;
    font-weight: 800;
    margin-bottom: 12px;
    color: {TEXT_PRIMARY}; /* Removed gradient for better readability */
}}

.hero-subtitle {{
    font-size: 18px;
    color: {TEXT_SECONDARY};
    max-width: 600px;
    margin: 0 auto;
    line-height: 1.6;
}}

/* Upload Area */
.upload-container {{
    background-color: {CARD_BG};
    border-radius: 20px;
    padding: 40px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.03); /* Softer shadow */
    border: 1px solid {BORDER};
    text-align: center;
    margin-bottom: 40px;
}}

/* Stats Banner */
.stats-banner {{
    display: flex;
    justify-content: space-around;
    background-color: {CARD_BG};
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 30px;
    border: 1px solid {BORDER};
    box-shadow: 0 2px 10px rgba(0,0,0,0.02);
}}

.stat-item {{
    text-align: center;
}}

.stat-val {{
    font-size: 28px;
    font-weight: 700;
    color: {TEXT_PRIMARY}; /* Unified color for stats values, less jarring */
}}

.stat-lbl {{
    font-size: 13px;
    color: {TEXT_SECONDARY};
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 4px;
}}

/* Visual Diff Card */
.diff-card {{
    background-color: {CARD_BG};
    border-radius: 16px;
    border: 1px solid {BORDER};
    padding: 24px;
    margin-bottom: 24px;
    transition: transform 0.2s;
    box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}}

.diff-card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 8px 16px rgba(0,0,0,0.04);
}}

.diff-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid {BORDER};
}}

.page-tag {{
    background-color: {ACCENT_LIGHT};
    color: {ACCENT};
    padding: 6px 14px;
    border-radius: 20px;
    font-weight: 600;
    font-size: 14px;
}}

.score-good {{ color: {SUCCESS}; font-weight: 700; }}
.score-bad {{ color: {ERROR}; font-weight: 700; }}

/* Button Styling */
.stButton button {{
    background-color: {ACCENT} !important;
    color: white !important;
    border-radius: 12px !important;
    padding: 14px 32px !important;
    font-weight: 500 !important; /* Slightly lighter weight */
    border: none !important;
    width: 100%;
    transition: all 0.2s;
    box-shadow: 0 4px 6px rgba(93, 156, 236, 0.2) !important;
}}

.stButton button:hover {{
    background-color: #4A89DC !important;
    box-shadow: 0 6px 12px rgba(93, 156, 236, 0.3) !important;
    transform: translateY(-1px);
}}

</style>
""", unsafe_allow_html=True)

# ---------------- HELPER FUNCTIONS ----------------
def pdf_to_images(pdf_path: str, dpi: int = 200) -> list[Image.Image]:
    """Convert PDF to images."""
    if not os.path.exists(pdf_path): return []
    doc = fitz.open(pdf_path)
    images = []
    for i in range(doc.page_count):
        page = doc.load_page(i)
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    doc.close()
    return images

# ---------------- UI LAYOUT ----------------

# 1. Hero Section
st.markdown("""
<div class="hero-container">
    <div class="hero-title">PDF Diff Visualizer</div>
    <div class="hero-subtitle">Compare documents side-by-side. Automatically highlight differences. Simple, fast, and visual.</div>
</div>
""", unsafe_allow_html=True)

# 2. Upload Section
st.markdown('<div class="upload-container">', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    pdf1 = st.file_uploader("Original Document", type=["pdf"], key="f1")
with c2:
    pdf2 = st.file_uploader("Modified Document", type=["pdf"], key="f2")
st.markdown('</div>', unsafe_allow_html=True)

# 3. Processing & Results
if pdf1 and pdf2:
    # Save & Process
    def save(upl):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            f.write(upl.getvalue())
            return f.name
            
    p1, p2 = save(pdf1), save(pdf2)
    
    with st.spinner("Analyzing differences..."):
        try:
            imgs1 = pdf_to_images(p1)
            imgs2 = pdf_to_images(p2)
            # Use smaller set for speed if unmatched length, though real app should handle it
            min_len = min(len(imgs1), len(imgs2))
            imgs1 = imgs1[:min_len]
            imgs2 = imgs2[:min_len]
            
            pdf_bytes, results = generate_diff_pdf(imgs1, imgs2)
        finally:
            if os.path.exists(p1): os.remove(p1)
            if os.path.exists(p2): os.remove(p2)

    # 4. Summary Banner
    total = len(results)
    passed = sum(1 for r in results if r["similarity"] > 99.0) # Strict check for "perfect"
    failed = total - passed
    avg = sum(r["similarity"] for r in results)/total if total else 0
    
    st.markdown(f"""
    <div class="stats-banner">
        <div class="stat-item">
            <div class="stat-val">{total}</div>
            <div class="stat-lbl">Total Pages</div>
        </div>
        <div class="stat-item">
            <div class="stat-val" style="color: {SUCCESS}">{passed}</div>
            <div class="stat-lbl">Matches</div>
        </div>
        <div class="stat-item">
            <div class="stat-val" style="color: {ERROR}">{failed}</div>
            <div class="stat-lbl">Differences</div>
        </div>
        <div class="stat-item">
            <div class="stat-val">{avg:.1f}%</div>
            <div class="stat-lbl">Avg Similarity</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 5. Visual Inspector (Only showing differences or all if requested)
    show_all = st.checkbox("Show all pages (including matches)", value=False)
    
    cnt = 0
    for r in results:
        # Show if it's a mismatch OR if user wants to see all
        # We define mismatch as < 99.9% logic for simplicity in this view
        is_diff = r["similarity"] < 99.0
        
        if is_diff or show_all:
            cnt += 1
            idx = r["page"] - 1
            
            # Prepare diff image on the fly
            # (In production, cache this or return from service)
            from services.visual_diff import generate_visual_diff
            i1 = cv2.cvtColor(np.array(imgs1[idx]), cv2.COLOR_RGB2BGR)
            i2 = cv2.cvtColor(np.array(imgs2[idx]), cv2.COLOR_RGB2BGR)
            if i1.shape != i2.shape:
                 i2 = cv2.resize(i2, (i1.shape[1], i1.shape[0]))
            diff_bgr, _ = generate_visual_diff(i1, i2)
            diff_rgb = cv2.cvtColor(diff_bgr, cv2.COLOR_BGR2RGB)
            
            # Render Card
            st.markdown(f"""
            <div class="diff-card">
                <div class="diff-header">
                    <span class="page-tag">Page {r['page']}</span>
                    <span class="{'score-bad' if is_diff else 'score-good'}">
                        {r['similarity']:.2f}% Match
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Grid for visuals
            c_ref, c_diff, c_new = st.columns(3)
            with c_ref: 
                st.image(imgs1[idx], caption="Original", use_container_width=True)
            with c_diff:
                st.image(diff_rgb, caption="Difference Highlight", use_container_width=True)
            with c_new:
                st.image(imgs2[idx], caption="Modified", use_container_width=True)
            
            st.divider()

    if cnt == 0 and not show_all:
         st.success("🎉 No differences found! Documents are identical.")

    # 6. Download
    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
    st.download_button(
        label="Download Detailed PDF Report",
        data=pdf_bytes,
        file_name="comparison_report.pdf",
        mime="application/pdf",
        use_container_width=True
    )
