import streamlit as st
from docx import Document
from docx.shared import RGBColor
from docx.enum.text import WD_COLOR_INDEX
import random
import time
import pdfplumber
import re

# --- CONFIG ---
st.set_page_config(page_title="ThiTho Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.main .block-container {
    max-width: 95% !important;
    padding-top: 2rem !important;
}
.question-box {
    background: #ffffff;
    padding: 20px;
    border-radius: 10px;
    border: 1px solid #dee2e6;
    margin-bottom: 20px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}
.question-text {
    font-size: 20px !important;
    font-weight: 700;
    color: #1f1f1f;
}
</style>
""", unsafe_allow_html=True)

# --- STATE ---
for key in ['data_thi', 'user_answers', 'current_idx', 'next_trigger']:
    if key not in st.session_state:
        st.session_state[key] = None if key == 'data_thi' else ({} if key == 'user_answers' else (0 if key == 'current_idx' else False))

# --- DOCX ---
def read_docx(file):
    doc = Document(file)
    data = []
    current_q = None

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        is_bold = any(run.bold for run in para.runs)
        is_q = is_bold or text.lower().startswith("câu") or (text[0].isdigit() and "." in text[:5])

        if is_q:
            current_q = {"question": text, "options": [], "correct": None}
            data.append(current_q)
        elif current_q is not None and not is_bold:
            is_correct = False
            for run in para.runs:
                if (run.font.color and run.font.color.rgb == RGBColor(255, 0, 0)) or \
                   (run.font.highlight_color == WD_COLOR_INDEX.YELLOW):
                    is_correct = True

            clean = text.replace("*", "").strip()
            if clean and clean not in current_q["options"]:
                current_q["options"].append(clean)
                if is_correct:
                    current_q["correct"] = clean

    return [q for q in data if len(q["options"]) >= 2]

# --- PDF ---
def read_pdf(file):
    data = []
    with pdfplumber.open(file) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    blocks = re.split(r'(?=Câu\s+\d+:)', text)

    for block in blocks:
        if not block.strip().startswith("Câu"):
            continue

        lines = [x.strip() for x in block.split("\n") if x.strip()]
        question = lines[0]

        options = []
        correct = None

        for line in lines:
            m = re.match(r'^\*\s*([A-D])[\.\)]\s*(.+)', line)
            if m:
                ans = f"{m.group(1)}. {m.group(2)}"
                options.append(ans)
                correct = ans
                continue

            m = re.match(r'^([A-D])[\.\)]\s*(.+)', line)
            if m:
                options.append(f"{m.group(1)}. {m.group(2)}")

        if len(options) >= 2:
            data.append({"question": question, "options": options, "correct": correct})

    return data

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ CÀI ĐẶT")

    uploaded_file = st.file_uploader("Tải đề", type=["docx", "pdf"])
    shuffle_q = st.checkbox("Đảo câu hỏi")
    shuffle_a = st.checkbox("Đảo đáp án")

    if st.button("🚀 BẮT ĐẦU", use_container_width=True, type="primary"):
        if uploaded_file is not None:
            if uploaded_file.name.lower().endswith(".pdf"):
                st.session_state.data_thi = read_pdf(uploaded_file)
            else:
                st.session_state.data_thi = read_docx(uploaded_file)

            if shuffle_q:
                random.shuffle(st.session_state.data_thi)

            if shuffle_a:
                for q in st.session_state.data_thi:
                    random.shuffle(q["options"])

            st.session_state.user_answers = {}
            st.session_state.current_idx = 0
            st.rerun()

    if st.session_state.data_thi:

        st.markdown("---")

        if st.button("🎯 Làm lại câu sai"):
            wrong = [
                i for i in range(len(st.session_state.data_thi))
                if st.session_state.user_answers.get(i) != st.session_state.data_thi[i]["correct"]
            ]
            if wrong:
                st.session_state.data_thi = [st.session_state.data_thi[i] for i in wrong]
                st.session_state.user_answers = {}
                st.session_state.current_idx = 0
                st.rerun()

        if st.button("🔄 Đổi đề khác"):
            st.session_state.data_thi = None
            st.session_state.user_answers = {}
            st.session_state.current_idx = 0
            st.rerun()

# --- MAIN ---
if st.session_state.data_thi:

    data = st.session_state.data_thi
    idx = st.session_state.current_idx
    tong = len(data)

    da_lam = len(st.session_state.user_answers)
    dung = sum(1 for i, ans in st.session_state.user_answers.items() if ans == data[i]["correct"])

    col_l, col_m, col_r = st.columns([1, 2.5, 1.2])

    with col_l:
        st.write("### 📊 Thống kê")
        st.write(f"Đã làm: {da_lam}/{tong}")
        st.write(f"Đúng: {dung} | Sai: {da_lam - dung}")
        st.progress(da_lam / tong if tong else 0)

    with col_m:
        item = data[idx]

        st.markdown(f"""
        <div class="question-box">
            <div class="question-text">Câu {idx+1}:</div>
            <div>{item["question"]}</div>
        </div>
        """, unsafe_allow_html=True)

        answered = idx in st.session_state.user_answers

        choice = st.radio(
            "Đáp án:",
            item["options"],
            key=f"q_{idx}",
            index=item["options"].index(st.session_state.user_answers[idx]) if answered else None,
            disabled=answered
        )

        if choice and not answered:
            st.session_state.user_answers[idx] = choice
            st.session_state.next_trigger = True
            st.rerun()

        if answered:
            if st.session_state.user_answers[idx] == item["correct"]:
                st.success("ĐÚNG ✅")
            else:
                st.error(f"SAI ❌ | Đáp án đúng: {item['correct']}")

        c1, c2 = st.columns(2)
        if c1.button("⬅ Trước"):
            st.session_state.current_idx = max(0, idx - 1)
            st.rerun()

        if c2.button("Sau ➡"):
            st.session_state.current_idx = min(tong - 1, idx + 1)
            st.rerun()

    with col_r:
        st.write("### 📑 Mục lục")

        for i in range(0, tong, 4):
            cols = st.columns(4)
            for j in range(4):
                k = i + j
                if k < tong:
                    label = str(k + 1)
                    if k in st.session_state.user_answers:
                        label += " ✅" if st.session_state.user_answers[k] == data[k]["correct"] else " ❌"

                    if cols[j].button(label, key=f"m_{k}"):
                        st.session_state.current_idx = k
                        st.rerun()

    if st.session_state.next_trigger:
        time.sleep(0.8)
        st.session_state.next_trigger = False
        if st.session_state.current_idx < tong - 1:
            st.session_state.current_idx += 1
            st.rerun()

else:
    st.info("👈 Upload file DOCX/PDF để bắt đầu")
