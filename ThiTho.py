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
    background-color: #FFFF00; 
    color: #FF0000; 
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

# ================= HÀM LỌC BỎ CÁC DÒNG GIẢI THÍCH =================
def check_is_explanation(line_text):
    """Nhận diện các dòng giải thích để loại bỏ hoàn toàn"""
    txt = line_text.lower().strip()
    keywords = [
        "trong excel", "giải thích", "để di chuyển", "cấu trúc của", 
        "đáp án đúng", "hướng dẫn", "trong thiết kế", "công cụ số",
        "khi thiết kế", "địa chỉ tuyệt đối", "phần mềm access", 
        "địa chỉ ô", "mặc định", "hàm count", "hàm sum", "phần page", "phần report"
    ]
    return any(kw in txt for kw in keywords)

# ================= THUẬT TOÁN ÉP ĐÁP ÁN XUỐNG DÒNG TUYỆT ĐỐI =================
def parse_raw_text_to_data(raw_text):
    """
    Thuật toán cắt chuỗi thông minh bằng cách ép các ký tự đáp án A, B, C, D 
    phải tách rời hoàn toàn và đứng ở các dòng riêng biệt.
    """
    # 1. Dọn sạch rác watermark và tiêu đề lặp lại
    raw_text = re.sub(r'(?i)e\s*d\s*u\s*q\s*u\s*i\s*z', '', raw_text)
    raw_text = re.sub(r'\b(E|DU|IZ|QUIZ|EDUQUIZ|UQ|ED)\b', '', raw_text)
    raw_text = re.sub(r'(?i)--- PAGE \d+ ---|TIN\s*3\s*-\s*HUBT\s*2026', '', raw_text)
    raw_text = re.sub(r'Số trang:\s*\d+\s*Số câu hỏi:\s*\d+', '', raw_text)
    raw_text = re.sub(r'PHẦN\s*\d+:\s*[A-Z\s\(\)0-9\-]+', '', raw_text)
    
    # 2. Thay thế tất cả khoảng trống lớn (như phím Tab) thành dấu xuống dòng trước chữ A. B. C. D.
    # Nhờ vậy các đáp án nằm ngang sẽ tự động bị bẻ dọc xuống thành từng dòng đơn lẻ
    raw_text = re.sub(r'\s+(\*?\s*A\s*[\.\:])', r'\n\1', raw_text)
    raw_text = re.sub(r'\s+(\*?\s*B\s*[\.\:])', r'\n\1', raw_text)
    raw_text = re.sub(r'\s+(\*?\s*C\s*[\.\:])', r'\n\1', raw_text)
    raw_text = re.sub(r'\s+(\*?\s*D\s*[\.\:])', r'\n\1', raw_text)

    lines = raw_text.split('\n')
    final_data = []
    current_q = None

    for line in lines:
        line_clean = line.strip()
        if not line_clean or line_clean in ['Z', 'z', 'D', '[Image']: 
            continue
        if check_is_explanation(line_clean): 
            continue

        # Phát hiện Bắt đầu một câu hỏi mới
        if line_clean.lower().startswith("câu"):
            current_q = {"question": line_clean, "options": [], "correct": None}
            final_data.append(current_q)
            continue

        # Kiểm tra xem dòng này có phải là một đáp án đơn lẻ hay không
        opt_match = re.match(r'^(\*?)\s*([A-D])\s*[\.\:]\s*(.*)$', line_clean)
        if opt_match and current_q is not None:
            is_correct = bool(opt_match.group(1))
            opt_letter = opt_match.group(2)
            opt_text = opt_match.group(3).strip()
            
            full_opt_str = f"{opt_letter}. {opt_text}"
            
            if len(current_q["options"]) < 4:
                current_q["options"].append(full_opt_str)
                if is_correct:
                    current_q["correct"] = full_opt_str
        else:
            # Nếu không phải đáp án mà là văn bản thường, bổ sung vào phần nội dung câu hỏi
            if current_q is not None and not current_q["options"]:
                current_q["question"] += " " + line_clean

    # Trả về bộ đề sạch đã lọc
    return [q for q in final_data if len(q["options"]) >= 2]

# ================= ĐỌC FILE WORD (.DOCX) SẠCH KHÔNG KHUNG =================
def process_docx_clean(file_bytes):
    doc = Document(io.BytesIO(file_bytes))
    # Gom toàn bộ paragraph chính quy (loại bỏ chữ trong Khung/Bảng ẩn)
    paragraphs_text = []
    for para in doc.paragraphs:
        if para.text.strip():
            paragraphs_text.append(para.text.strip())
            
    full_raw_text = "\n".join(paragraphs_text)
    return parse_raw_text_to_data(full_raw_text)

# ================= ĐỌC FILE PDF NÂNG CAO =================
def process_pdf_clean(file_bytes):
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        full_raw = ""
        for page in pdf.pages:
            page_chars = page.chars
            if not page_chars: continue
            
            lines_dict = {}
            for c in page_chars:
                if c["size"] > 15: continue
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
                full_raw += "".join([c["text"] for c in line_chars]) + "\n"
                
    return parse_raw_text_to_data(full_raw)

# ================= HÀM XUẤT FILE WORD CHUẨN ĐẸP TUYỆT ĐỐI =================
def export_to_docx(data_list):
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(12)

    for idx, item in enumerate(data_list, 1):
        p_q = doc.add_paragraph()
        p_q.paragraph_format.space_before = Pt(12)
        q_clean = item['question'].split(':', 1)[-1].strip() if ':' in item['question'] else item['question']
        p_q.add_run(f"Câu {idx}: {q_clean}").bold = True

        # Bảo đảm ghi mỗi đáp án trên một paragraph độc lập (bắt buộc xuống dòng)
        for opt in item["options"]:
            p_o = doc.add_paragraph()
            p_o.paragraph_format.left_indent = Pt(20)
            
            if opt == item["correct"]:
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

# ================= THANH SIDEBAR TÙY CHỌN =================
with st.sidebar:
    st.header("⚙️ THIẾT LẬP BỘ ĐỀ")
    uploaded_file = st.file_uploader("Tải lên đề thi (DOCX hoặc PDF)", type=["docx", "pdf"])
    shuffle_q = st.checkbox("Đảo thứ tự câu hỏi")
    shuffle_a = st.checkbox("Đảo thứ tự đáp án")

    if st.button("🚀 BẮT ĐẦU TRẮC NGHIỆM", use_container_width=True, type="primary"):
        if uploaded_file is not None:
            with st.spinner("Đang xé nhỏ dòng, bẻ dọc đáp án sang từng dòng độc lập..."):
                file_bytes = uploaded_file.read()
                
                if uploaded_file.name.lower().endswith(".pdf"):
                    parsed_data = process_pdf_clean(file_bytes)
                else:
                    parsed_data = process_docx_clean(file_bytes)
                
                if parsed_data:
                    st.session_state.file_docx_clean = export_to_docx(parsed_data)
                    if shuffle_q: random.shuffle(parsed_data)
                    if shuffle_a:
                        for q in parsed_data: random.shuffle(q["options"])
                        
                    st.session_state.data_thi = parsed_data
                    st.session_state.user_answers = {}
                    st.session_state.current_idx = 0
                    st.session_state.next_trigger = False
                    st.rerun()
                else:
                    st.error("❌ Không tìm thấy dữ liệu trắc nghiệm hợp lệ!")

    if st.session_state.data_thi:
        st.markdown("---")
        st.download_button(
            label="📥 TẢI FILE WORD ĐÁP ÁN XUỐNG DÒNG (.DOCX)",
            data=st.session_state.file_docx_clean,
            file_name="De_Thi_HUBT_Chuan_Dong.docx",
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

# ================= GIAO DIỆN CHÍNH HIỂN THỊ THI THỬ =================
if st.session_state.data_thi:
    data = st.session_state.data_thi
    idx = st.session_state.current_idx
    item = data[idx]
    total = len(data)

    col1, col2, col3 = st.columns([1, 2.5, 1.2])

    with col1:
        st.write("### 📊 Tiến độ")
        done = len(st.session_state.user_answers)
        correct_count = sum(1 for i, ans in st.session_state.user_answers.items() if ans == data[i].get("correct"))
        st.write(f"Đã làm: {done}/{total}")
        st.write(f"Đúng: {correct_count} | Sai: {done - correct_count}")
        st.progress(done / total if total else 0)

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

        # Hiển thị đáp án trên giao diện Streamlit (Mỗi cái một dòng chuẩn chỉ)
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

    if st.session_state.next_trigger:
        time.sleep(0.5)
        st.session_state.next_trigger = False
        if st.session_state.current_idx < total - 1:
            st.session_state.current_idx += 1
            st.rerun()
else:
    st.info("👈 Nạp lại file word lên thanh bên để tận hưởng giao diện mỗi đáp án một dòng đi ông ơi!")
