import streamlit as st
from docx import Document
from docx.shared import RGBColor
from docx.enum.text import WD_COLOR_INDEX
import pdfplumber
import random
import re

# ================= UI & STYLE =================
st.set_page_config(page_title="ThiTho Pro X", layout="wide", page_icon="🎯")

# Tối ưu giao diện: Thêm hiệu ứng hover, bôi màu đáp án trực quan hơn
st.markdown("""
<style>
    .main .block-container { max-width: 90% !important; padding-top: 2rem; }
    .question-box {
        background: #f8f9fa;
        padding: 24px;
        border-radius: 12px;
        border-left: 5px solid #4CAF50;
        margin-bottom: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .question-text { font-size: 22px; font-weight: 700; color: #1e293b; margin-bottom: 10px; }
    
    /* Highlight đáp án đúng kiểu chuyên nghiệp */
    .correct-ans-box {
        background-color: #fef08a !important; /* Vàng dịu */
        color: #b91c1c !important; /* Chữ đỏ đậm dễ nhìn */
        font-weight: bold;
        padding: 12px;
        border-radius: 8px;
        border: 1px dashed #f59e0b;
        margin-top: 15px;
    }
</style>
""", unsafe_allow_html=True)

# ================= SESSION STATE =================
# Gom trạng thái vào một chỗ cho sạch code
defaults = {
    "data_thi": None,
    "user_answers": {},  # Lưu theo dạng { index_cau_hoi: text_dap_an_da_chon }
    "current_idx": 0,
    "show_result": False # Chỉ xem kết quả khi người dùng bấm "Nộp bài" hoặc "Check"
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ================= LOGIC ĐỌC FILE (ĐÃ SỬA LỖI ĐẢO ĐÁP ÁN) =================
def process_docx(file):
    doc = Document(file)
    data = []
    current_q = None

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text: continue

        if text.lower().startswith("câu"):
            current_q = {"question": text, "options": [], "correct": None}
            data.append(current_q)
            continue

        if current_q is not None:
            m = re.match(r'^([A-D])\.\s*(.+)$', text)
            if m:
                clean_text = m.group(2).strip()
                is_correct = False
                
                # Check 3 điều kiện bôi đỏ / bôi vàng / dấu *
                if text.startswith("*"): is_correct = True
                for run in para.runs:
                    if run.font.color and run.font.color.rgb == RGBColor(255, 0, 0): is_correct = True
                    if run.font.highlight_color == WD_COLOR_INDEX.YELLOW: is_correct = True
                
                current_q["options"].append(clean_text)
                if is_correct:
                    current_q["correct"] = clean_text # Lưu text gốc làm đáp án đúng

    return [q for q in data if len(q["options"]) >= 2]

def process_pdf(file):
    data = []
    with pdfplumber.open(file) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    blocks = re.split(r'(?=Câu\s?\d+)', text)
    for block in blocks:
        lines = [x.strip() for x in block.split("\n") if x.strip()]
        if not lines: continue
        
        question = lines[0]
        block_text = " ".join(lines[1:])
        matches = re.findall(r'([A-D]\.\s*.*?)(?=\s*[A-D]\.|$)', block_text)
        
        options = []
        correct = None
        for m in matches:
            m = m.strip()
            # Xử lý lấy text sạch không chứa ký tự định dạng của đáp án mẫu
            is_correct = m.startswith("*")
            clean_opt = re.sub(r'^[A-D]\.\s*\*?', '', m).strip()
            options.append(clean_opt)
            if is_correct: correct = clean_opt

        if len(options) >= 2:
            data.append({"question": question, "options": options, "correct": correct})
    return data

# ================= SIDEBAR CÀI ĐẶT =================
with st.sidebar:
    st.header("⚙️ CẤU HÌNH ĐỀ THI")
    uploaded_file = st.file_uploader("Tải lên bộ đề (DOCX/PDF)", type=["docx", "pdf"])
    shuffle_q = st.checkbox("Xáo trộn thứ tự CÂU HỎI")
    shuffle_a = st.checkbox("Xáo trộn thứ tự ĐÁP ÁN")
    
    if st.button("🚀 KHỞI TẠO ĐỀ THI", use_container_width=True, type="primary"):
        if uploaded_file:
            with st.spinner("Đang xử lý dữ liệu..."):
                raw_data = process_pdf(uploaded_file) if uploaded_file.name.endswith(".pdf") else process_docx(uploaded_file)
                
                if shuffle_q:
                    random.shuffle(raw_data)
                if shuffle_a:
                    for item in raw_data:
                        random.shuffle(item["options"]) # Đảo thoải mái vì ta check theo text chính xác
                
                st.session_state.data_thi = raw_data
                st.session_state.user_answers = {}
                st.session_state.current_idx = 0
                st.session_state.show_result = False
                st.rerun()
        else:
            st.error("Vui lòng chọn file trước!")

    if st.session_state.data_thi:
        st.markdown("---")
        if st.button("🔄 Đổi bộ đề khác", use_container_width=True):
            st.session_state.data_thi = None
            st.rerun()

# ================= GIAO DIỆN CHÍNH =================
if st.session_state.data_thi:
    data = st.session_state.data_thi
    idx = st.session_state.current_idx
    item = data[idx]
    
    # Tính toán thống kê nhanh
    total = len(data)
    done = len(st.session_state.user_answers)
    correct_count = sum(1 for i, ans in st.session_state.user_answers.items() if ans == data[i].get("correct"))

    # Bố cục 3 cột: Thống kê | Nội dung câu hỏi | Danh sách câu
    col_stats, col_main, col_nav = st.columns([1, 2.5, 1.2])

    # 1. CỘT TRÁI: THỐNG KÊ
    with col_stats:
        st.markdown("### 📊 TIẾN ĐỘ")
        st.metric("Đã trả lời", f"{done} / {total}")
        st.metric("Làm đúng", f"{correct_count} câu")
        st.progress(done / total if total else 0)
        
        if st.button("🔔 NỘP BÀI / XEM ĐÁP ÁN", type="secondary", use_container_width=True):
            st.session_state.show_result = True
            st.rerun()

    # 2. CỘT GIỮA: NỘI DUNG CÂU HỎI
    with col_main:
        st.markdown(f"""
        <div class="question-box">
            <div class="question-text">Câu hỏi {idx + 1} / {total}</div>
            <div>{item['question']}</div>
        </div>
        """, unsafe_allow_html=True)

        # Xử lý lấy index đáp án đã chọn trước đó (nếu có) để giữ trạng thái giao diện
        previously_selected = st.session_state.user_answers.get(idx)
        try:
            default_sel_idx = item["options"].index(previously_selected)
        except ValueError:
            default_sel_idx = None

        # Hiển thị các phương án lựa chọn (A, B, C, D tự động điền bằng code)
        choice = st.radio(
            "Chọn phương án trả lời:",
            item["options"],
            index=default_sel_idx,
            format_func=lambda x: f"{chr(65 + item['options'].index(x))}. {x}",
            key=f"radio_q_{idx}"
        )

        # Lưu đáp án ngay khi chọn (Không dùng auto-next gây ức chế UX)
        if choice != previously_selected:
            st.session_state.user_answers[idx] = choice
            st.rerun()

        # Hiển thị đáp án đúng (Nếu bấm nộp bài hoặc câu này đã chọn xong)
        if st.session_state.show_result or idx in st.session_state.user_answers:
            st.markdown("---")
            if item["correct"] == st.session_state.user_answers.get(idx):
                st.success("🎉 Bạn đã trả lời CHÍNH XÁC!")
            else:
                st.error("❌ Câu trả lời chưa chính xác hoặc chưa chọn.")
                
            # Đạt yêu cầu: Hiện dấu *, bôi vàng, chữ đỏ cho đáp án đúng bằng HTML cực sạch
            st.markdown(f"""
            <div class="correct-ans-box">
                ⭐ ĐÁP ÁN ĐÚNG: {item['correct']}
            </div>
            """, unsafe_allow_html=True)

        # Thanh điều hướng Trước / Sau
        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        if c1.button("⬅️ Câu Trước", use_container_width=True) and idx > 0:
            st.session_state.current_idx -= 1
            st.rerun()
        if c2.button("Câu Tiếp Theo ➡️", use_container_width=True) and idx < total - 1:
            st.session_state.current_idx += 1
            st.rerun()

    # 3. CỘT PHẢI: MỤC LỤC ĐIỀU HƯỚNG NHANH
    with col_nav:
        st.markdown("### 📑 DANH SÁCH")
        # Chia lưới nút bấm thông minh
        for i in range(0, total, 4):
            btn_cols = st.columns(4)
            for j in range(4):
                k = i + j
                if k < total:
                    # Đổi trạng thái hiển thị icon dựa trên việc làm đúng/sai/chưa làm
                    if k in st.session_state.user_answers:
                        icon = "✅" if st.session_state.user_answers[k] == data[k].get("correct") else "❌"
                    else:
                        icon = "📄"
                    
                    # Highlight nút của câu hiện tại bằng kiểu dáng riêng
                    btn_type = "primary" if k == idx else "secondary"
                    if btn_cols[j].button(f"{k+1}\n{icon}", key=f"nav_{k}", type=btn_type):
                        st.session_state.current_idx = k
                        st.rerun()
else:
    st.info("👈 Vui lòng tải file câu hỏi lên ở thanh bên trái để bắt đầu học và thi thử!")
