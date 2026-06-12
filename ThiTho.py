import streamlit as st
from docx import Document
from docx.shared import RGBColor
from docx.enum.text import WD_COLOR_INDEX
import pdfplumber
import random
import re
import io
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
/* CSS hỗ trợ bôi màu đáp án hiển thị */
.correct-highlight {
    background-color: #FFFF00; /* Bôi vàng */
    color: #FF0000; /* Chữ đỏ */
    font-weight: bold;
    padding: 2px 5px;
    border-radius: 4px;
}
</style>
""", unsafe_allow_html=True)

# ================= STATE =================
for key in ["data_thi", "user_answers", "current_idx", "next_trigger"]:
    if key not in st.session_state:
        st.session_state[key] = None if key == "data_thi" else ({} if key == "user_answers" else (0 if key == "current_idx" else False))

# ================= HÀM BỔ TRỢ NHẬN DIỆN NỀN XANH LÁ =================
def is_explanation_green(text):
    """
    Nhận diện dòng giải thích dựa trên từ khóa nội dung (để bọc lót cho phần nền xanh)
    """
    txt = text.lower().strip()
    keywords = [
        "trong excel", "giải thích", "để di chuyển", "cấu trúc của", 
        "đại chỉ tuyệt đối", "hướng dẫn", "trong thiết kế", "công cụ số",
        "khi thiết kế", "địa chỉ ô", "mặc định", "hàm count", "hàm sum", 
        "phần page", "phần report", "về côn", "đáp án đúng"
    ]
    return any(kw in txt for kw in keywords) or txt in ['z', 'd', '[image']

# ================= DOCX =================
def read_docx(file):
    doc = Document(file)
    data = []
    current_q = None

    # CHIẾN THUẬT 1: python-docx mặc định khi duyệt `doc.paragraphs` sẽ 
    # TỰ ĐỘNG BỎ QUA toàn bộ chữ nằm trong Khung (Text Box/Shapes) và Bảng (Tables).
    # Do đó ta chỉ xử lý text thô chính quy xuất hiện ở ngoài.
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # Cập nhật yêu cầu 2: Bỏ qua chữ nền xanh (dòng giải thích)
        if is_explanation_green(text):
            continue

        # NHẬN DIỆN CÂU HỎI
        if text.lower().startswith("câu"):
            current_q = {
                "question": text,
                "options": [],
                "correct": None
            }
            data.append(current_q)
            continue

        # NHẬN DIỆN ĐÁP ÁN (Ép bẻ dọc các đáp án dính chung một hàng)
        if current_q is not None:
            # Thuật toán xé nhỏ dòng: Tìm các cụm A. B. C. D. độc lập
            # Sửa đổi Regex để bẻ gãy dấu Tab hoặc khoảng trắng lớn ngăn cách giữa các đáp án nằm ngang
            text_split = re.sub(r'\s+(\*?\s*[A-D]\s*[\.\:])', r'\n\1', text)
            lines = text_split.split('\n')
            
            for line in lines:
                line_clean = line.strip()
                if not line_clean: continue
                
                matches = re.findall(r'(\*?\s*[A-D]\.\s*.*?)(?=\s*\*?\s*[A-D]\.|$)', line_clean)
                
                if matches:
                    for m in matches:
                        m_clean = m.strip()
                        is_correct = m_clean.startswith("*")
                        opt_text = m_clean.replace("*", "").strip()
                        
                        # Kiểm tra chữ đỏ hoặc bôi vàng từ các Runs trong đoạn
                        for run in para.runs:
                            if run.font.color and run.font.color.rgb == RGBColor(255, 0, 0):
                                if opt_text[3:] in run.text: 
                                    is_correct = True
                            if run.font.highlight_color == WD_COLOR_INDEX.YELLOW:
                                if opt_text[3:] in run.text:
                                    is_correct = True

                        if len(current_q["options"]) < 4: 
                            current_q["options"].append(opt_text)
                            if is_correct:
                                current_q["correct"] = opt_text
                else:
                    # Nếu không phải đáp án mà là văn bản thường kéo dài của câu hỏi
                    if not current_q["options"] and not line_clean.lower().startswith("câu"):
                        current_q["question"] += " " + line_clean

    return [q for q in data if len(q["options"]) >= 2]

# ================= PDF =================
def read_pdf(file):
    data = []

    with pdfplumber.open(file) as pdf:
        full_text = ""
        for page in pdf.pages:
            page_chars = page.chars
            if not page_chars: continue
            
            # Cập nhật yêu cầu 1 (PDF): Chữ in chìm watermark EduQuiz nằm trong khung 
            # thường có size chữ khổng lồ (> 15). Ta lọc bỏ ngay từ tầng ký tự.
            lines_dict = {}
            for c in page_chars:
                if c["size"] > 15: 
                    continue # Loại bỏ hoàn toàn chữ trong khung ẩn dưới nền
                
                top = round(c["top"], 1)
                found_line = False
                for t in lines_dict:
                    if abs(t - top) < 3:
                        lines_dict[t].append(c)
                        found_line = True
                        break
                if not found_line:
                    lines_dict[top] = [c]
            
            for t in sorted(lines_dict.keys()):
                line_chars = sorted(lines_dict[t], key=lambda x: x["x0"])
                full_text += "".join([c["text"] for c in line_chars]) + "\n"

    # Tách các khối bắt đầu bằng chữ "Câu"
    blocks = re.split(r'(?=Câu\s*\d+[:\.])', full_text)

    for block in blocks:
        lines = [x.strip() for x in block.split("\n") if x.strip()]
        if not lines:
            continue

        question = lines[0]
        if not question.lower().startswith("câu"): continue
        
        # Cập nhật yêu cầu 2 (PDF): Lọc bỏ triệt để dòng giải thích nền xanh
        filtered_lines = []
        for line in lines[1:]:
            if is_explanation_green(line):
                continue
            filtered_lines.append(line)
            
        # Ép buộc bẻ dọc toàn bộ các đáp án nằm ngang ra thành các dòng riêng biệt
        block_text = " ".join(filtered_lines)
        block_text = re.sub(r'\s+(\*?\s*[A-D]\s*[\.\:])', r'\n\1', block_text)
        
        sub_lines = block_text.split('\n')
        options = []
        correct = None

        for sub_line in sub_lines:
            matches = re.findall(r'(\*?\s*[A-D]\.\s*.*?)(?=\s*\*?\s*[A-D]\.|$)', sub_line.strip())
            for m in matches:
                m = m.strip()
                is_correct = m.startswith("*")
                clean = m.replace("*", "").strip()

                if len(options) < 4: 
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

            if shuffle_q and st.session_state.data_thi:
                random.shuffle(st.session_state.data_thi)

            if shuffle_a and st.session_state.data_thi:
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
        correct_ans = item.get("correct")

        # Đồng bộ index chính xác khi hiển thị đáp án radio button
        selected_index = None
        if answered:
            user_ans = st.session_state.user_answers[idx]
            if user_ans in item["options"]:
                selected_index = item["options"].index(user_ans)

        choice = st.radio(
            "Đáp án:",
            item["options"],
            key=f"q_{idx}",
            index=selected_index,
            disabled=answered
        )

        if choice and not answered:
            st.session_state.user_answers[idx] = choice
            st.session_state.next_trigger = True
            st.rerun()

        # ===== RESULT =====
        if answered:
            user_ans = st.session_state.user_answers[idx]

            if correct_ans is None:
                st.warning("⚠️ Chưa detect được đáp án đúng từ file gốc")
            elif user_ans == correct_ans:
                st.success("ĐÚNG ✅")
            else:
                st.error("SAI ❌")
            
            # Hiển thị đáp án đúng bao gồm cả 3 định dạng: Dấu *, bôi vàng và chữ đỏ bằng HTML
            st.markdown(f"**Đáp án đúng hệ thống tìm thấy:** <span class='correct-highlight'>⭐ {correct_ans}</span>", unsafe_allow_html=True)

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
        time.sleep(0.5)
        st.session_state.next_trigger = False
        if st.session_state.current_idx < total - 1:
            st.session_state.current_idx += 1
            st.rerun()
else:
    st.info("👈 Upload file DOCX / PDF để bắt đầu")
