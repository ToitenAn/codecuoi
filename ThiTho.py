import streamlit as st
from docx import Document
from docx.shared import Pt, RGBColor
import pdfplumber
import random
import re
import io
import time

# ================= GIAO DIỆN UI =================
st.set_page_config(page_title="ThiTho Pro X", layout="wide", page_icon="🎯")

st.markdown("""
<style>
.main .block-container { max-width: 95% !important; }
.question-box {
    background: #f8f9fa;
    padding: 18px;
    border-radius: 10px;
    border-left: 5px solid #0066cc;
    margin-bottom: 15px;
}
.question-text { font-size: 20px; font-weight: 700; color: #1e293b; }
.correct-highlight {
    background-color: #FFFF00; /* Bôi vàng */
    color: #FF0000; /* Chữ đỏ */
    font-weight: bold;
    padding: 2px 5px;
    border-radius: 4px;
}
</style>
""", unsafe_allow_html=True)

# ================= KHỞI TẠO STATE =================
for key in ["data_thi", "user_answers", "current_idx", "file_docx_clean", "next_trigger"]:
    if key not in st.session_state:
        st.session_state[key] = None if key in ["data_thi", "file_docx_clean"] else ({} if key == "user_answers" else (0 if key == "current_idx" else False))

# ================= HÀM LỌC WATERMARK VÀ GIẢI THÍCH =================
def clean_text_core(text):
    """Xóa sạch chữ EduQuiz in chìm lọt vào văn bản (kể cả khi bị giãn cách chữ hoặc dính ký tự rác)"""
    return re.sub(r'(?i)e\s*d\s*u\s*q\s*u\s*i\s*z', '', text)

def check_is_explanation(line_text):
    """Nhận diện các dòng giải thích để loại bỏ hoàn toàn khỏi câu hỏi/đáp án"""
    txt = line_text.lower()
    keywords = [
        "trong excel", "giải thích", "để di chuyển", "cấu trúc của", 
        "đáp án đúng", "hướng dẫn", "trong thiết kế", "công cụ số",
        "khi thiết kế", "địa chỉ tuyệt đối"
    ]
    return any(txt.startswith(kw) or kw in txt[:20] for kw in keywords)

# ================= XỬ LÝ ĐỌC FILE PDF SẠCH =================
def process_pdf_clean(file_bytes):
    data = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        raw_text = ""
        for page in pdf.pages:
            p_text = page.extract_text() or ""
            # Xóa các dòng header/footer số trang cố định của file PDF
            p_text = re.sub(r'(?i)--- PAGE \d+ ---', '', p_text)
            raw_text += p_text + "\n"
    
    # Làm sạch triệt để watermark EduQuiz trước khi bóc tách khối
    clean_text = clean_text_core(raw_text)
    
    # Tách khối văn bản dựa theo cấu trúc "Câu [số]:" hoặc "Câu [số]."
    blocks = re.split(r'(?=Câu\s*\d+[:\.])', clean_text)

    for block in blocks:
        lines = [x.strip() for x in block.split("\n") if x.strip()]
        if not lines: 
            continue

        question = lines[0]
        if not question.lower().startswith("câu"): 
            continue

        # Loại bỏ các dòng giải thích và dòng chứa ảnh dạng [Image ...]
        filtered_lines = []
        for line in lines[1:]:
            if check_is_explanation(line) or line.startswith("[Image"):
                continue
            filtered_lines.append(line)
            
        block_text = " ".join(filtered_lines)

        # Trích xuất chính xác hệ 4 đáp án dạng A., B., C., D. (có hoặc không có dấu * định dạng đáp án đúng)
        matches = re.findall(r'(\*?\s*[A-D]\.\s*.*?)(?=\s*\*?\s*[A-D]\.|$)', block_text)

        options = []
        correct = None

        for m in matches:
            m_clean = m.strip()
            is_correct = m_clean.startswith("*")
            clean_opt = m_clean.replace("*", "").strip()

            if len(options) < 4:
                options.append(clean_opt)
                if is_correct:
                    correct = clean_opt

        if len(options) >= 2:
            data.append({"question": question, "options": options, "correct": correct})
    return data

# ================= HÀM XUẤT FILE WORD (.DOCX) SẠCH =================
def export_to_docx(data_list):
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(12)

    for idx, item in enumerate(data_list, 1):
        p_q = doc.add_paragraph()
        p_q.paragraph_format.space_before = Pt(12)
        p_q.add_run(f"Câu {idx}: {item['question'].split(':', 1)[-1].strip() if ':' in item['question'] else item['question']}").bold = True

        for opt in item["options"]:
            p_o = doc.add_paragraph()
            p_o.paragraph_format.left_indent = Pt(20)
            is_correct = (opt == item["correct"])

            if is_correct:
                run_star = p_o.add_run("* ")
                run_star.font.color.rgb = RGBColor(255, 0, 0)
                run_star.bold = True
                
                run_txt = p_o.add_run(opt)
                run_txt.font.color.rgb = RGBColor(255, 0, 0)
                run_txt.bold = True
            else:
                p_o.add_run(opt)
                
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

# ================= THANH SIDEBAR =================
with st.sidebar:
    st.header("⚙️ THIẾT LẬP BỘ ĐỀ")
    uploaded_file = st.file_uploader("Tải lên đề thi (PDF)", type=["pdf"])
    shuffle_q = st.checkbox("Đảo thứ tự câu hỏi")
    shuffle_a = st.checkbox("Đảo thứ tự đáp án")

    if st.button("🚀 BẮT ĐẦU TRẮC NGHIỆM", use_container_width=True, type="primary"):
        if uploaded_file is not None:
            with st.spinner("Hệ thống đang quét Layer lọc Watermark..."):
                file_bytes = uploaded_file.read()
                parsed_data = process_pdf_clean(file_bytes)
                
                if parsed_data:
                    # Tạo sẵn file Word sạch nguyên bản trước khi đảo để người dùng tải về
                    st.session_state.file_docx_clean = export_to_docx(parsed_data)
                    
                    if shuffle_q: 
                        random.shuffle(parsed_data)
                    if shuffle_a:
                        for q in parsed_data: 
                            random.shuffle(q["options"])
                        
                    st.session_state.data_thi = parsed_data
                    st.session_state.user_answers = {}
                    st.session_state.current_idx = 0
                    st.session_state.next_trigger = False
                    st.rerun()
                else:
                    st.error("❌ Không thể bóc tách câu hỏi, kiểm tra lại cấu trúc file!")

    if st.session_state.data_thi:
        st.markdown("---")
        st.download_button(
            label="📥 TẢI FILE WORD SẠCH (.DOCX)",
            data=st.session_state.file_docx_clean,
            file_name="De_Thi_Da_Loc_Sach.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True
        )
        if st.button("🔄 Đổi bộ đề khác", use_container_width=True):
            st.session_state.data_thi = None
            st.session_state.file_docx_clean = None
            st.session_state.user_answers = {}
            st.session_state.current_idx = 0
            st.session_state.next_trigger = False
            st.rerun()

# ================= KHÔNG GIAN HIỂN THỊ CHÍNH =================
if st.session_state.data_thi:
    data = st.session_state.data_thi
    idx = st.session_state.current_idx
    item = data[idx]
    total = len(data)

    col1, col2, col3 = st.columns([1, 2.5, 1.2])

    # ===== CỘT TRÁI: THỐNG KÊ =====
    with col1:
        st.write("### 📊 Tiến độ")
        done = len(st.session_state.user_answers)
        correct_count = sum(1 for i, ans in st.session_state.user_answers.items() if ans == data[i].get("correct"))
        st.write(f"Đã làm: {done}/{total}")
        st.write(f"Đúng: {correct_count} | Sai: {done - correct_count}")
        st.progress(done / total if total else 0)

    # ===== CỘT GIỮA: NỘI DUNG CÂU HỎI =====
    with col2:
        st.markdown(f"""
        <div class="question-box">
            <div class="question-text">Câu {idx+1}</div>
            <div>{item['question']}</div>
        </div>
        """, unsafe_allow_html=True)

        answered = idx in st.session_state.user_answers
        correct_ans = item.get("correct")

        selected_index = item["options"].index(st.session_state.user_answers[idx]) if answered else None

        choice = st.radio("Chọn đáp án:", item["options"], key=f"q_{idx}", index=selected_index, disabled=answered)

        if choice and not answered:
            st.session_state.user_answers[idx] = choice
            st.session_state.next_trigger = True
            st.rerun()

        if answered:
            if correct_ans == st.session_state.user_answers[idx]:
                st.success("ĐÚNG ✅")
            else:
                st.error("SAI ❌")
            st.markdown(f"**Đáp án đúng:** <span class='correct-highlight'>⭐ {correct_ans}</span>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        if c1.button("⬅ Câu Trước") and idx > 0:
            st.session_state.current_idx -= 1
            st.rerun()
        if c2.button("Câu Tiếp ➡") and idx < total - 1:
            st.session_state.current_idx += 1
            st.rerun()

    # ===== CỘT PHẢI: MỤC LỤC =====
    with col3:
        st.write("### 📑 Mục lục")
        for i in range(0, total, 4):
            cols = st.columns(4)
            for j in range(4):
                k = i + j
                if k < total:
                    label = str(k + 1)
                    if k in st.session_state.user_answers:
                        label += " ✅" if st.session_state.user_answers[k] == data[k].get("correct") else " ❌"
                    btn_type = "primary" if k == idx else "secondary"
                    if cols[j].button(label, key=f"m_{k}", type=btn_type):
                        st.session_state.current_idx = k
                        st.rerun()

    # ===== TỰ ĐỘNG CHUYỂN CÂU HỎI (AUTO NEXT) =====
    if st.session_state.next_trigger:
        time.sleep(0.5)
        st.session_state.next_trigger = False
        if st.session_state.current_idx < total - 1:
            st.session_state.current_idx += 1
            st.rerun()
else:
    st.info("👈 Vui lòng kéo thả file PDF bộ đề bị dính hình mờ vào thanh bên để xử lý tự động!")
