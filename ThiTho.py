import streamlit as st
from docx import Document
from docx.shared import RGBColor
from docx.enum.text import WD_COLOR_INDEX
import pdfplumber
import random
import time
import re

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="ThiTho Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    /* Ép rộng màn hình để không bị cụt */
    .main .block-container {
        max-width: 95% !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
        padding-top: 1.5rem !important;
    }
    .stApp { color: #1f1f1f; }
    .question-box { 
        background: #ffffff; 
        padding: 20px; 
        border-radius: 12px; 
        border: 1px solid #dee2e6; 
        margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        min-height: 150px;
    }
    .question-text { font-size: 18px !important; font-weight: 500; color: #1f1f1f; margin-bottom: 10px; }
    div[data-testid="stHorizontalBlock"] button:has(span:contains("✅")) { background-color: #28a745 !important; color: white !important; }
    div[data-testid="stHorizontalBlock"] button:has(span:contains("❌")) { background-color: #ff4b4b !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- QUẢN LÝ TRẠNG THÁI ---
for key in ['data_thi', 'user_answers', 'current_idx', 'next_trigger']:
    if key not in st.session_state:
        st.session_state[key] = None if key == 'data_thi' else ({} if key == 'user_answers' else (0 if key == 'current_idx' else False))

# --- HÀM ĐỌC FILE ---
def read_docx(file):
    doc = Document(file)
    data = []
    current_q = None
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text: continue
        if text.lower().startswith("câu") or (text[0].isdigit() and "." in text[:5]):
            current_q = {"question": text, "options": [], "correct": None}
            data.append(current_q)
        elif current_q is not None:
            is_correct = False
            if "*" in text or "--" in text: is_correct = True
            for run in para.runs:
                if (run.font.color and run.font.color.rgb == RGBColor(255, 0, 0)) or (run.font.highlight_color == WD_COLOR_INDEX.YELLOW) or (run.bold):
                    is_correct = True; break
            clean_text = text.replace("*", "").replace("--", "").strip()
            if clean_text and clean_text not in current_q["options"]:
                current_q["options"].append(clean_text)
                if is_correct: current_q["correct"] = clean_text
    return [q for q in data if len(q['options']) >= 2]

def read_pdf(file):
    data = []
    current_q = None
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            for line in text.split('\n'):
                line = line.strip()
                if not line or "PAGE" in line: continue
                if re.match(r'^(Câu hỏi|Câu)\s*\d+[:.]', line, re.I):
                    parts = re.split(r'Câu\s*\d+[:.]', line, flags=re.I)
                    current_q = {"question": parts[-1].strip() if len(parts) > 1 else line, "options": [], "correct": None}
                    data.append(current_q)
                elif current_q is not None:
                    is_c = "*" in line or "--" in line
                    t = line.replace("*", "").replace("--", "").replace("•", "").strip()
                    if t and t not in current_q["options"]:
                        current_q["options"].append(t)
                        if is_c: current_q["correct"] = t
    return [q for q in data if len(q['options']) >= 2]

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ CÀI ĐẶT")
    uploaded_file = st.file_uploader("Tải đề (Word/PDF)", type=["docx", "pdf"])
    t1 = st.checkbox("Đảo câu hỏi")
    t2 = st.checkbox("Đảo đáp án")
    if uploaded_file and st.button("🚀 BẮT ĐẦU", use_container_width=True, type="primary"):
        st.session_state.user_answers = {}; st.session_state.current_idx = 0
        st.session_state.data_thi = read_docx(uploaded_file) if uploaded_file.name.endswith('.docx') else read_pdf(uploaded_file)
        if t1: random.shuffle(st.session_state.data_thi)
        if t2: [random.shuffle(it['options']) for it in st.session_state.data_thi]
        st.rerun()

    if st.session_state.data_thi:
        st.markdown("---")
        if st.button("🎯 Làm lại câu sai", use_container_width=True):
            sai_idx = [i for i, ans in st.session_state.user_answers.items() if ans != st.session_state.data_thi[i]['correct']]
            if sai_idx:
                st.session_state.data_thi = [st.session_state.data_thi[i] for i in sai_idx]
                st.session_state.user_answers = {}; st.session_state.current_idx = 0; st.rerun()
            else:
                st.toast("Bạn chưa có câu nào sai!")
        if st.button("🔄 Đổi đề khác", use_container_width=True):
            st.session_state.data_thi = None; st.rerun()

# --- GIAO DIỆN CHÍNH ---
if st.session_state.data_thi:
    data = st.session_state.data_thi; idx = st.session_state.current_idx
    tong = len(data); da_lam = len(st.session_state.user_answers)
    dung = sum(1 for i, ans in st.session_state.user_answers.items() if ans == data[i]['correct'])
    sai = da_lam - dung
    
    col_l, col_m, col_r = st.columns([1, 2.5, 1.2])
    with col_l:
        with st.container(border=True):
            st.write("### 📊 Thống kê")
            st.write(f"📝 Đã làm: **{da_lam}/{tong}**")
            st.write(f"✅ Đúng: **{dung}** | ❌ Sai: **{sai}**")
            st.progress(da_lam / tong if tong > 0 else 0)
            st.metric("🎯 Điểm hiện tại", f"{(dung/tong)*10:.2f}" if tong > 0 else "0.00")

    with col_m:
        item = data[idx]
        st.markdown(f'<div class="question-box"><div class="question-text">Câu {idx + 1}:</div><div>{item["question"]}</div></div>', unsafe_allow_html=True)
        answered = idx in st.session_state.user_answers
        choice = st.radio("Đáp án:", item['options'], key=f"r_{idx}", index=item['options'].index(st.session_state.user_answers[idx]) if answered else None, disabled=answered, label_visibility="collapsed")
        
        if choice and not answered:
            st.session_state.user_answers[idx] = choice; st.session_state.next_trigger = True; st.rerun()
        
        if answered:
            if st.session_state.user_answers[idx] == item['correct']: st.success("ĐÚNG! ✅")
            else: st.error(f"SAI! ❌ Đáp án đúng là: **{item['correct']}**")
        
        c1, c2 = st.columns(2)
        if c1.button("⬅ Câu trước", use_container_width=True): st.session_state.current_idx = max(0, idx - 1); st.rerun()
        if c2.button("Câu sau ➡", use_container_width=True): st.session_state.current_idx = min(tong-1, idx + 1); st.rerun()

    with col_r:
        st.write("### 📑 Mục lục câu hỏi")
        grid = 4
        for i in range(0, tong, grid):
            cols = st.columns(grid)
            for j in range(grid):
                curr = i + j
                if curr < tong:
                    lbl = f"{curr+1}"
                    if curr in st.session_state.user_answers:
                        lbl += " ✅" if st.session_state.user_answers[curr] == data[curr]['correct'] else " ❌"
                    if cols[j].button(lbl, key=f"m_{curr}", use_container_width=True):
                        st.session_state.current_idx = curr; st.rerun()
    
    if st.session_state.next_trigger:
        time.sleep(1.0)
        st.session_state.next_trigger = False
        if st.session_state.current_idx < tong - 1: st.session_state.current_idx += 1; st.rerun()
else:
    st.info("👈 Mở thanh bên trái để tải lên file đề và bắt đầu luyện tập.")
