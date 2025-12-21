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
    .main .block-container {
        max-width: 95% !important;
        padding: 1.5rem !important;
    }
    .question-box { 
        background: #ffffff; padding: 20px; border-radius: 12px; 
        border: 1px solid #dee2e6; margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    .question-text { font-size: 18px !important; font-weight: 500; color: #1f1f1f; }
    /* Màu nút bấm mục lục */
    div[data-testid="stHorizontalBlock"] button:has(span:contains("✅")) { background-color: #28a745 !important; color: white !important; }
    div[data-testid="stHorizontalBlock"] button:has(span:contains("❌")) { background-color: #ff4b4b !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- QUẢN LÝ TRẠNG THÁI ---
for key in ['data_thi', 'user_answers', 'current_idx', 'next_trigger']:
    if key not in st.session_state:
        st.session_state[key] = None if key == 'data_thi' else ({} if key == 'user_answers' else (0 if key == 'current_idx' else False))

# --- HÀM ĐỌC FILE WORD (CHỈ QUÉT 3 TRƯỜNG HỢP) ---
def read_docx(file):
    doc = Document(file)
    data = []
    current_q = None
    
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text: continue
        
        # Nhận diện câu hỏi (Bắt đầu bằng chữ "Câu" hoặc số kèm dấu chấm)
        if text.lower().startswith("câu") or (text[0].isdigit() and "." in text[:5]):
            current_q = {"question": text, "options": [], "correct": None}
            data.append(current_q)
        elif current_q is not None:
            is_correct = False
            
            # Quét từng Run (cụm chữ có định dạng riêng) trong dòng
            for run in para.runs:
                # 1. Chữ màu đỏ (RGB: 255, 0, 0)
                if run.font.color and run.font.color.rgb == RGBColor(255, 0, 0):
                    is_correct = True
                # 2. Bôi nền màu vàng (Highlight)
                if run.font.highlight_color == WD_COLOR_INDEX.YELLOW:
                    is_correct = True
                # 3. Dấu * màu đỏ (Đã bao hàm ở điều kiện chữ đỏ, nhưng thêm kiểm tra text)
                if "*" in run.text and run.font.color and run.font.color.rgb == RGBColor(255, 0, 0):
                    is_correct = True
            
            # Xử lý text sạch
            clean_text = text.replace("*", "").strip()
            
            # Loại bỏ các dòng ghi chú rác (không phải đáp án)
            if clean_text and "phần bổ sung" not in clean_text.lower():
                if clean_text not in current_q["options"]:
                    current_q["options"].append(clean_text)
                    if is_correct:
                        current_q["correct"] = clean_text

    return [q for q in data if len(q['options']) >= 2]

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ CÀI ĐẶT")
    uploaded_file = st.file_uploader("Tải đề (Word)", type=["docx"])
    t1 = st.checkbox("Đảo câu hỏi")
    t2 = st.checkbox("Đảo đáp án")
    
    if uploaded_file and st.button("🚀 BẮT ĐẦU", use_container_width=True, type="primary"):
        st.session_state.user_answers = {}
        st.session_state.current_idx = 0
        st.session_state.data_thi = read_docx(uploaded_file)
        if t1: random.shuffle(st.session_state.data_thi)
        if t2: 
            for it in st.session_state.data_thi: random.shuffle(it['options'])
        st.rerun()

    if st.session_state.data_thi:
        st.markdown("---")
        if st.button("🎯 Làm lại câu chưa đúng", use_container_width=True):
            sai_hoac_chua = [i for i in range(len(st.session_state.data_thi)) 
                             if st.session_state.user_answers.get(i) != st.session_state.data_thi[i]['correct']]
            if sai_hoac_chua:
                st.session_state.data_thi = [st.session_state.data_thi[i] for i in sai_hoac_chua]
                st.session_state.user_answers = {}; st.session_state.current_idx = 0; st.rerun()
        
        if st.button("🔄 Đổi đề khác", use_container_width=True):
            st.session_state.data_thi = None; st.rerun()

# --- GIAO DIỆN CHÍNH ---
if st.session_state.data_thi:
    data = st.session_state.data_thi
    idx = st.session_state.current_idx
    tong = len(data)
    da_lam = len(st.session_state.user_answers)
    dung = sum(1 for i, ans in st.session_state.user_answers.items() if ans == data[i]['correct'])
    
    col_l, col_m, col_r = st.columns([1, 2.5, 1.2])
    
    with col_l:
        with st.container(border=True):
            st.write("### 📊 Thống kê")
            st.write(f"📝 Đã làm: **{da_lam}/{tong}**")
            st.write(f"✅ Đúng: **{dung}** | ❌ Sai: **{da_lam - dung}**")
            st.write(f"⏳ Chưa làm: **{tong - da_lam}**")
            st.progress(da_lam / tong if tong > 0 else 0)
            st.metric("🎯 Điểm", f"{(dung/tong)*10:.2f}" if tong > 0 else "0.00")

    with col_m:
        item = data[idx]
        st.markdown(f'<div class="question-box"><div class="question-text">Câu {idx + 1}:</div><div>{item["question"]}</div></div>', unsafe_allow_html=True)
        
        answered = idx in st.session_state.user_answers
        choice = st.radio("Đáp án:", item['options'], key=f"r_{idx}", 
                          index=item['options'].index(st.session_state.user_answers[idx]) if answered else None,
                          disabled=answered, label_visibility="collapsed")
        
        if choice and not answered:
            st.session_state.user_answers[idx] = choice
            st.session_state.next_trigger = True
            st.rerun()
            
        if answered:
            if st.session_state.user_answers[idx] == item['correct']: st.success("ĐÚNG! ✅")
            else: st.error(f"SAI! ❌ Đáp án đúng: **{item['correct']}**")
        
        c1, c2 = st.columns(2)
        if c1.button("⬅ Câu trước", use_container_width=True):
            st.session_state.current_idx = max(0, idx - 1); st.rerun()
        if c2.button("Câu sau ➡", use_container_width=True):
            st.session_state.current_idx = min(tong-1, idx + 1); st.rerun()

    with col_r:
        st.write("### 📑 Mục lục")
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
        if st.session_state.current_idx < tong - 1:
            st.session_state.current_idx += 1; st.rerun()
else:
    st.info("👈 Mở thanh bên trái để nạp file Word (.docx) và bắt đầu.")
