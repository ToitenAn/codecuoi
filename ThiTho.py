import streamlit as st
from docx2python import docx2python
import random
import time
import base64
import re

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="ThiTho Pro", layout="wide")

# Link ảnh nền bạn đã gửi
BG_IMAGE_URL = "https://i.ibb.co/Q32JcTYJ/image.png" 

st.markdown(f"""
    <style>
    .stApp {{
        background-image: url("{BG_IMAGE_URL}");
        background-attachment: fixed;
        background-size: cover;
    }}
    .question-box {{ 
        background: rgba(255, 255, 255, 0.85) !important;
        backdrop-filter: blur(10px);
        padding: 25px; border-radius: 15px; 
        border: 1px solid rgba(255, 255, 255, 0.3); margin-bottom: 20px;
    }}
    .question-text {{ font-size: 20px !important; font-weight: 700; color: #000; }}
    h3, p, span, label {{ color: #000 !important; font-weight: 600; }}
    </style>
    """, unsafe_allow_html=True)

# --- QUẢN LÝ TRẠNG THÁI ---
for key in ['data_thi', 'user_answers', 'current_idx', 'next_trigger']:
    if key not in st.session_state:
        st.session_state[key] = None if key == 'data_thi' else ({} if key == 'user_answers' else (0 if key == 'current_idx' else False))

# --- HÀM ĐỌC FILE WORD CÓ ẢNH ---
def process_word_with_images(uploaded_file):
    # Lưu file tạm để docx2python đọc
    with open("temp.docx", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    # Trích xuất dữ liệu bao gồm cả ảnh (lưu vào thư mục tạm)
    with docx2python("temp.docx", html=True) as doc:
        # doc.body là danh sách: [phần][bảng][dòng][ô]
        # Chúng ta gộp lại thành danh sách các dòng văn bản đơn giản
        rows = []
        for part in doc.body:
            for table in part:
                for row in table:
                    for cell in row:
                        for line in cell:
                            if line.strip(): rows.append(line)
        
        data = []
        current_q = None
        
        for line in rows:
            # Nhận diện Đề bài (In đậm trong docx2python thường nằm trong thẻ <b>)
            is_bold = "<b>" in line
            text_clean = re.sub('<[^<]+?>', '', line).strip() # Xóa thẻ HTML
            
            # Kiểm tra xem dòng có chứa ảnh không (docx2python đánh dấu là ----image1.png----)
            img_match = re.search(r'----image(\d+)\.(png|jpg|jpeg)----', line)
            
            if is_bold or text_clean.lower().startswith("câu") or (text_clean and text_clean[0].isdigit() and "." in text_clean[:5]):
                current_q = {"question": text_clean, "options": [], "correct": None, "image_key": None}
                if img_match:
                    img_name = f"image{img_match.group(1)}.{img_match.group(2)}"
                    if img_name in doc.images:
                        current_q["image_key"] = doc.images[img_name]
                data.append(current_q)
            
            elif current_q is not None:
                # Nhận diện đáp án đúng (Dấu * hoặc bôi màu/đỏ thường xuất hiện dưới dạng ký tự đặc biệt)
                # Lưu ý: docx2python khó nhận diện màu sắc hơn, ta dùng dấu * và text
                is_correct = "*" in line or '<span style="background-color:yellow">' in line.lower()
                
                # Nếu dòng có ảnh nhưng không phải đề bài, gán ảnh vào đề bài của câu hiện tại
                if img_match and not current_q["image_key"]:
                    img_name = f"image{img_match.group(1)}.{img_match.group(2)}"
                    current_q["image_key"] = doc.images.get(img_name)

                clean_ans = text_clean.replace("*", "").strip()
                if clean_ans and clean_ans not in current_q["options"] and "phần bổ sung" not in clean_ans.lower():
                    current_q["options"].append(clean_ans)
                    if is_correct: current_q["correct"] = clean_ans
                    
        return [q for q in data if len(q['options']) >= 2]

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ CÀI ĐẶT")
    file = st.file_uploader("Tải đề (.docx)", type=["docx"])
    if file and st.button("🚀 BẮT ĐẦU", use_container_width=True, type="primary"):
        st.session_state.data_thi = process_word_with_images(file)
        st.session_state.user_answers = {}
        st.session_state.current_idx = 0
        st.rerun()

# --- HIỂN THỊ ---
if st.session_state.data_thi:
    data = st.session_state.data_thi
    idx = st.session_state.current_idx
    item = data[idx]
    
    col_l, col_m, col_r = st.columns([1, 2.5, 1.2])
    
    with col_m:
        st.markdown(f'<div class="question-box"><div class="question-text">Câu {idx + 1}: {item["question"]}</div></div>', unsafe_allow_html=True)
        
        # HIỂN THỊ ẢNH NẾU CÓ
        if item.get("image_key"):
            st.image(item["image_key"], caption="Hình ảnh minh họa", use_container_width=True)
        
        # Radio chọn đáp án
        ans = idx in st.session_state.user_answers
        choice = st.radio("Chọn:", item['options'], key=f"q_{idx}", index=item['options'].index(st.session_state.user_answers[idx]) if ans else None, disabled=ans)
        
        if choice and not ans:
            st.session_state.user_answers[idx] = choice
            st.rerun()
            
        if ans:
            if st.session_state.user_answers[idx] == item['correct']: st.success("Chính xác! ✅")
            else: st.error(f"Sai rồi! ❌ Đáp án: {item['correct']}")
        
        # Điều hướng
        c1, c2 = st.columns(2)
        if c1.button("⬅ Trước"): st.session_state.current_idx = max(0, idx-1); st.rerun()
        if c2.button("Sau ➡"): st.session_state.current_idx = min(len(data)-1, idx+1); st.rerun()

    # (Phần Thống kê col_l và Mục lục col_r giữ nguyên logic cũ)
