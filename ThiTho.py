import streamlit as st
from docx import Document
from docx.shared import RGBColor
from docx.enum.text import WD_COLOR_INDEX
import pdfplumber
import random
import re

# ================= UI =================
st.set_page_config(page_title="ThiTho Pro", layout="wide")

st.markdown("""
<style>
.main .block-container {max-width: 95% !important;}

.question-box {
    background: #fff;
    padding: 18px;
    border-radius: 10px;
    border: 1px solid #ddd;
    margin-bottom: 15px;
}

.question-text {
    font-size: 20px;
    font-weight: 700;
}

.option {
    padding: 10px;
    border-radius: 8px;
    border: 1px solid #ddd;
    margin-bottom: 6px;
}

.correct {
    background: #fff3cd;
    border: 2px solid #ffc107;
}

.wrong {
    background: #f8d7da;
    border: 2px solid #dc3545;
}
</style>
""", unsafe_allow_html=True)

# ================= STATE =================
for k in ["data", "answers", "idx", "checked"]:
    if k not in st.session_state:
        st.session_state[k] = None if k == "data" else ({} if k == "answers" else (0 if k == "idx" else -1))

# ================= CHECK ĐÁP ÁN ĐÚNG =================
def is_correct_para(para):
    text = para.text.strip()

    # * = chắc chắn đúng
    if "*" in text:
        return True

    # chữ đỏ
    for run in para.runs:
        if run.font.color and run.font.color.rgb == RGBColor(255, 0, 0):
            return True

    # highlight vàng
    for run in para.runs:
        if run.font.highlight_color == WD_COLOR_INDEX.YELLOW:
            return True

    return False

# ================= DOCX =================
def read_docx(file):
    doc = Document(file)
    data = []
    q = None

    for p in doc.paragraphs:
        t = p.text.strip()
        if not t:
            continue

        # câu hỏi
        if t.lower().startswith("câu"):
            q = {"question": t, "options": [], "correct": None}
            data.append(q)
            continue

        if q is not None:
            m = re.match(r'^([A-D])\.\s*(.+)$', t)
            if m:
                ans = f"{m.group(1)}. {m.group(2).strip().rstrip('.')}"
                q["options"].append(ans)

                if is_correct_para(p):
                    q["correct"] = ans

    return data

# ================= PDF =================
def read_pdf(file):
    data = []

    with pdfplumber.open(file) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    blocks = re.split(r'(?=Câu)', text)

    for b in blocks:
        lines = [x.strip() for x in b.split("\n") if x.strip()]
        if not lines:
            continue

        q = lines[0]
        rest = " ".join(lines[1:])

        matches = re.findall(r'([A-D]\.\s*.*?)(?=\s*[A-D]\.|$)', rest)

        options = []
        correct = None

        for m in matches:
            is_correct = "*" in m
            clean = m.replace("*", "").strip().rstrip(".")

            options.append(clean)

            if is_correct:
                correct = clean

        data.append({
            "question": q,
            "options": options,
            "correct": correct
        })

    return data

# ================= SIDEBAR =================
with st.sidebar:
    st.header("⚙️ CÀI ĐẶT")

    file = st.file_uploader("Upload đề", type=["docx", "pdf"])

    shuffle_q = st.checkbox("Đảo câu hỏi")
    shuffle_a = st.checkbox("Đảo đáp án")

    if st.button("🚀 START"):
        if file:
            if file.name.endswith("pdf"):
                st.session_state.data = read_pdf(file)
            else:
                st.session_state.data = read_docx(file)

            # ===== GIỮ SHUFFLE =====
            if shuffle_q:
                random.shuffle(st.session_state.data)

            if shuffle_a:
                for q in st.session_state.data:
                    random.shuffle(q["options"])

            st.session_state.answers = {}
            st.session_state.idx = 0
            st.session_state.checked = -1

            st.rerun()

# ================= MAIN =================
if st.session_state.data:

    data = st.session_state.data
    i = st.session_state.idx
    q = data[i]

    st.title(f"Câu {i+1}")

    st.markdown(f"""
    <div class="question-box">{q['question']}</div>
    """, unsafe_allow_html=True)

    # ================= CHỌN =================
    choice = st.radio(
        "Chọn đáp án:",
        q["options"],
        key=f"q_{i}",
        index=q["options"].index(st.session_state.answers[i]) if i in st.session_state.answers else 0
    )

    st.session_state.answers[i] = choice

    # ================= CHẤM =================
    if st.button("🎯 CHẤM"):
        st.session_state.checked = i
        st.rerun()

    # ================= RESULT =================
    if st.session_state.checked == i:
        user = st.session_state.answers[i]
        correct = q.get("correct")

        if correct is None:
            st.warning("⚠️ Không detect được đáp án đúng")
        elif user == correct:
            st.success("ĐÚNG ✅")
        else:
            st.error(f"SAI ❌ | Đáp án đúng: {correct}")

    # ================= NAV =================
    c1, c2 = st.columns(2)

    if c1.button("⬅"):
        st.session_state.idx = max(0, i - 1)
        st.rerun()

    if c2.button("➡"):
        st.session_state.idx = min(len(data) - 1, i + 1)
        st.rerun()

    # ================= HIGHLIGHT =================
    st.divider()
    st.write("### Đáp án")

    for opt in q["options"]:

        cls = ""

        if st.session_state.checked == i:
            if opt == q.get("correct"):
                cls = "correct"
            elif opt == st.session_state.answers[i]:
                cls = "wrong"

        st.markdown(f"<div class='option {cls}'>{opt}</div>", unsafe_allow_html=True)

else:
    st.info("Upload DOCX / PDF để bắt đầu")
