import streamlit as st
from docx import Document
import pdfplumber
import random
import re

# ================= UI =================
st.set_page_config(page_title="ThiTho Pro", layout="wide")

st.markdown("""
<style>
.main .block-container {
    max-width: 95% !important;
}
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
</style>
""", unsafe_allow_html=True)

# ================= STATE =================
if "data" not in st.session_state:
    st.session_state.data = None
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "idx" not in st.session_state:
    st.session_state.idx = 0

# ================= DOCX =================
def read_docx(file):
    doc = Document(file)
    data = []
    q = None

    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue

        if text.lower().startswith("câu"):
            q = {"question": text, "options": [], "correct": None}
            data.append(q)
            continue

        if q is not None:
            m = re.match(r'^([A-D])\.\s*(.+)$', text)
            if m:
                ans = f"{m.group(1)}. {m.group(2).strip().rstrip('.')}"
                q["options"].append(ans)

                # detect đáp án đúng bằng *
                if "*" in text:
                    q["correct"] = ans

    return [x for x in data if len(x["options"]) >= 2]

# ================= PDF =================
def read_pdf(file):
    data = []

    with pdfplumber.open(file) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    blocks = re.split(r'(?=Câu)', text)

    for b in blocks:
        lines = [x.strip() for x in b.split("\n") if x.strip()]
        if not lines:
            continue

        q_text = lines[0]
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

        if options:
            data.append({
                "question": q_text,
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

    if st.button("🚀 BẮT ĐẦU"):
        if file:
            if file.name.endswith(".pdf"):
                st.session_state.data = read_pdf(file)
            else:
                st.session_state.data = read_docx(file)

            if shuffle_q:
                random.shuffle(st.session_state.data)

            if shuffle_a:
                for q in st.session_state.data:
                    random.shuffle(q["options"])

            st.session_state.answers = {}
            st.session_state.idx = 0

            st.rerun()

    if st.session_state.data:
        st.divider()

        if st.button("🔄 Làm lại"):
            st.session_state.answers = {}
            st.session_state.idx = 0
            st.rerun()

        if st.button("❌ Reset đề"):
            st.session_state.data = None
            st.session_state.answers = {}
            st.session_state.idx = 0
            st.rerun()

# ================= MAIN =================
if st.session_state.data:

    data = st.session_state.data
    i = st.session_state.idx
    total = len(data)

    done = len(st.session_state.answers)

    correct = sum(
        1 for k, v in st.session_state.answers.items()
        if v == data[k].get("correct")
    )

    col1, col2, col3 = st.columns([1, 2.5, 1.2])

    # ===== LEFT =====
    with col1:
        st.write("### 📊 Thống kê")
        st.write(f"Đã chấm: {done}/{total}")
        st.write(f"Đúng: {correct}")
        st.write(f"Sai: {done - correct}")
        st.progress(done / total if total else 0)

    # ===== CENTER =====
    with col2:
        q = data[i]

        st.markdown(f"""
        <div class="question-box">
            <div class="question-text">Câu {i+1}</div>
            <div>{q['question']}</div>
        </div>
        """, unsafe_allow_html=True)

        # ===== CHỌN ĐÁP ÁN =====
        choice = st.radio(
            "Chọn đáp án:",
            q["options"],
            key=f"q_{i}",
            index=q["options"].index(st.session_state.answers[i]) if i in st.session_state.answers else 0
        )

        # ===== NÚT CHẤM =====
        if st.button("🎯 CHẤM CÂU NÀY"):
            st.session_state.answers[i] = choice
            st.rerun()

        # ===== KẾT QUẢ =====
        if i in st.session_state.answers:
            user = st.session_state.answers[i]
            correct_ans = q.get("correct")

            if correct_ans is None:
                st.warning("⚠️ Chưa detect đáp án đúng")
            elif user == correct_ans:
                st.success("ĐÚNG ✅")
            else:
                st.error(f"SAI ❌ | Đáp án đúng: {correct_ans}")

        # ===== NAV =====
        c1, c2 = st.columns(2)

        if c1.button("⬅ Trước"):
            st.session_state.idx = max(0, i - 1)
            st.rerun()

        if c2.button("Sau ➡"):
            st.session_state.idx = min(total - 1, i + 1)
            st.rerun()

    # ===== RIGHT =====
    with col3:
        st.write("### 📑 Mục lục")

        for k in range(total):
            label = str(k + 1)

            if k in st.session_state.answers:
                if st.session_state.answers[k] == data[k].get("correct"):
                    label += " ✅"
                else:
                    label += " ❌"

            if st.button(label, key=f"m_{k}"):
                st.session_state.idx = k
                st.rerun()

else:
    st.info("👈 Upload DOCX / PDF để bắt đầu")
