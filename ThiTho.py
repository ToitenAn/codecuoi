import streamlit as st
from docx import Document
import pdfplumber
import random
import re
import time

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
for key in ["data_thi", "user_answers", "current_idx", "next_trigger"]:
    if key not in st.session_state:
        st.session_state[key] = None if key == "data_thi" else ({} if key == "user_answers" else (0 if key == "current_idx" else False))

# ================= DOCX =================
def read_docx(file):
    doc = Document(file)
    data = []
    current_q = None

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # CÂU HỎI
        if text.lower().startswith("câu"):
            current_q = {
                "question": text,
                "options": [],
                "correct": None
            }
            data.append(current_q)
            continue

        # ĐÁP ÁN
        if current_q is not None:
            m = re.match(r'^([A-D])\.\s*(.+)$', text)
            if m:
                letter = m.group(1)
                content = m.group(2).strip().rstrip(".")

                answer = f"{letter}. {content}"

                current_q["options"].append(answer)

                # ✅ FIX: detect correct bằng ký tự *
                is_correct = "*" in text or text.startswith("*")

                if is_correct:
                    current_q["correct"] = answer

    return [q for q in data if len(q["options"]) >= 2]


# ================= PDF =================
def read_pdf(file):
    data = []

    with pdfplumber.open(file) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    blocks = re.split(r'(?=Câu)', text)

    for block in blocks:
        lines = [x.strip() for x in block.split("\n") if x.strip()]
        if not lines:
            continue

        question = lines[0]
        block_text = " ".join(lines[1:])

        matches = re.findall(r'([A-D]\.\s*.*?)(?=\s*[A-D]\.|$)', block_text)

        options = []
        correct = None

        for m in matches:
            m = m.strip()

            is_correct = "*" in m or m.startswith("*")

            clean = m.replace("*", "").strip().rstrip(".")

            options.append(clean)

            if is_correct:
                correct = clean

        if len(options) >= 2:
            data.append({
                "question": question,
                "options": options,
                "correct": correct
            })

    return data


# ================= SIDEBAR =================
with st.sidebar:
    st.header("⚙️ CÀI ĐẶT")

    uploaded_file = st.file_uploader("Tải đề", type=["docx", "pdf"])
    shuffle_q = st.checkbox("Đảo câu hỏi")
    shuffle_a = st.checkbox("Đảo đáp án")

    if st.button("🚀 BẮT ĐẦU", use_container_width=True):

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

        if st.button("🎯 Làm lại"):
            st.session_state.user_answers = {}
            st.session_state.current_idx = 0
            st.rerun()

        if st.button("🔄 Đổi đề"):
            st.session_state.data_thi = None
            st.session_state.user_answers = {}
            st.session_state.current_idx = 0
            st.rerun()


# ================= MAIN =================
if st.session_state.data_thi:

    data = st.session_state.data_thi
    idx = st.session_state.current_idx
    total = len(data)

    done = len(st.session_state.user_answers)

    correct_count = sum(
        1 for i, ans in st.session_state.user_answers.items()
        if ans == data[i].get("correct")
    )

    col1, col2, col3 = st.columns([1, 2.5, 1.2])

    # ===== LEFT =====
    with col1:
        st.write("### 📊 Thống kê")
        st.write(f"Đã làm: {done}/{total}")
        st.write(f"Đúng: {correct_count}")
        st.write(f"Sai: {done - correct_count}")
        st.progress(done / total if total else 0)

    # ===== CENTER =====
    with col2:
        item = data[idx]

        st.markdown(f"""
        <div class="question-box">
            <div class="question-text">Câu {idx+1}</div>
            <div>{item['question']}</div>
        </div>
        """, unsafe_allow_html=True)

        answered = idx in st.session_state.user_answers

        choice = st.radio(
            "Đáp án:",
            item["options"],
            key=f"q_{idx}",
            index=item["options"].index(st.session_state.user_answers[idx]) if answered else 0,
            disabled=answered
        )

        if choice and not answered:
            st.session_state.user_answers[idx] = choice
            st.session_state.next_trigger = True
            st.rerun()

        # ===== RESULT =====
        if answered:
            user_ans = st.session_state.user_answers[idx]
            correct_ans = item.get("correct")

            if correct_ans is None:
                st.warning("⚠️ Chưa detect được đáp án đúng")
            elif user_ans == correct_ans:
                st.success("ĐÚNG ✅")
            else:
                st.error(f"SAI ❌ | Đáp án đúng: {correct_ans}")

        c1, c2 = st.columns(2)
        if c1.button("⬅ Trước"):
            st.session_state.current_idx = max(0, idx - 1)
            st.rerun()

        if c2.button("Sau ➡"):
            st.session_state.current_idx = min(total - 1, idx + 1)
            st.rerun()

    # ===== RIGHT =====
    with col3:
        st.write("### 📑 Mục lục")

        for i in range(0, total, 4):
            cols = st.columns(4)

            for j in range(4):
                k = i + j
                if k < total:

                    label = str(k + 1)

                    if k in st.session_state.user_answers:
                        if st.session_state.user_answers[k] == data[k].get("correct"):
                            label += " ✅"
                        else:
                            label += " ❌"

                    if cols[j].button(label, key=f"m_{k}"):
                        st.session_state.current_idx = k
                        st.rerun()

    # ===== AUTO NEXT =====
    if st.session_state.next_trigger:
        time.sleep(0.3)
        st.session_state.next_trigger = False

        if st.session_state.current_idx < total - 1:
            st.session_state.current_idx += 1
            st.rerun()

else:
    st.info("👈 Upload file DOCX / PDF để bắt đầu")
