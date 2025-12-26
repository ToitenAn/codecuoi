import streamlit as st
from docx2python import docx2python
import random
import time
import re
import os

# --- CẤU HÌNH GIAO DIỆN (BỎ BACKGROUND) ---
st.set_page_config(page_title="ThiTho Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .main .block-container {
        max-width: 95% !important;
        padding-top: 2rem !important;
    }
    /* Khung câu hỏi đơn giản */
    .question-box { 
        background-color: #f8f9fa;
        padding: 25px; 
        border-radius: 10px; 
        border-left: 5px solid #007bff;
        margin-bottom: 20px;
    }
    .question-text { 
        font-size: 20px !important; 
        font-weight: 700; 
        color: #1f1f1f; 
    }
    /* Màu nút bấm mục lục */
    div[data-testid="stHorizontalBlock"] button:has(span:contains("✅")) { background-color: #28a745 !important; color: white !important; }
    div[data-testid="stHorizontalBlock"] button:has(span:contains("❌")) { background-color: #ff4b4b !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- QUẢN LÝ TRẠNG THÁI ---
for key in ['data_thi', 'user_answers', 'current_idx', 'next_trigger']:
    if key not in st.session_state:
        st.session_state[key] = None if key == 'data_thi' else ({} if key == 'user_answers' else (0 if key == 'current_idx' else False))

# --- HÀM ĐỌC FILE WORD CÓ ẢNH & NHẬN DIỆN CHỮ ĐẬM ---
def process_word_with_images(uploaded_file):
    with open("temp.docx", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    with docx2python("temp.docx") as doc:
        # Lấy tất cả các dòng văn bản từ body
        all_lines = []
        for part in doc.body:
            for table in part:
                for row in table:
                    for cell in row:
                        for line in cell:
                            if line.strip(): all_lines.append(line)
        
        data = []
        current_q = None
        
        for line in all_lines:
            # Nhận diện Đề bài: Có thẻ <b> (in đậm) HOẶC bắt đầu bằng "Câu"
            is_bold = "<b>" in line
            text_clean = re.sub('<[^<]+?>', '', line).strip() 
            
            # Tìm ảnh trong dòng (docx2python format: ----image1.png----)
            img_match = re.search(r'----image(\d+)\.(png|jpg|jpeg)----', line)
            
            if is_bold or text_clean.lower().startswith("câu") or (text_clean and text_clean[0].isdigit() and "." in text_clean[:5]):
                current_q = {"question": text_clean, "options": [], "correct": None, "image_data": None}
                if img_match:
                    img_name = f"image{img_match.group(1)}.{img_match.group(2)}"
                    current_q["image_data"] = doc.images.get(img_name)
                data.append(current_q)
            
            elif current_q is not None:
                # Đáp án đúng: Có dấu * hoặc thẻ bôi màu (tùy định dạng docx2python)
                is_correct = "*" in line or '<span style="background-color:yellow">' in line.lower()
                
                # Nếu dòng có ảnh mà chưa gán cho đề bài
                if img_match and not current_q["image_data"]:
                    img_name = f"image{img_match.group(1)}.{img_match.group(2)}"
                    current_q["image_data"] = doc.images.get(img_name)

                clean_ans = text_clean.replace("*", "").strip()
                if clean_ans and "phần bổ sung" not in clean_ans.lower():
                    if clean_ans not in current_q["options"]:
                        current_q["options"].append(clean_ans)
                        if is_correct: current_q["correct"] = clean_ans
                    
        return [q for q in data if len(q['options']) >= 2]

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ CÀI ĐẶT")
    file = st.file_uploader("Tải đề Word (.docx)", type=["docx"])
    t1 = st.checkbox("Đảo câu hỏi")
    t2 = st.checkbox("Đảo đáp án")
    
    if file and st.button("🚀 BẮT ĐẦU", use_container_width=True, type="primary"):
        st.session_state.data_thi = process_word_with_images(file)
        if t1: random.shuffle(st.session_state.data_thi)
        if t2: 
            for it in st.session_state.data_thi: random.shuffle(it['options'])
        st.session_state.user_answers = {}
        st.session_state.current_idx = 0
        st.rerun()

    if st.session_state.data_thi:
        st.markdown("---")
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
        st.write("### 📊 Thống kê")
        st.metric("🎯 Điểm", f"{(dung/tong)*10:.2f}" if tong > 0 else "0.00")
        st.write(f"✅ Đúng: **{dung}** | ❌ Sai: **{da_lam - dung}**")
        st.progress(da_lam / tong if tong > 0 else 0)

    with col_m:
        item = data[idx]
        st.markdown(f'<div class="question-box"><div class="question-text">Câu {idx + 1}: {item["question"]}</div></div>', unsafe_allow_html=True)
        
        if item.get("image_data"):
            st.image(item["image_data"], use_container_width=True)
        
        answered = idx in st.session_state.user_answers
        choice = st.radio("Chọn đáp án:", item['options'], key=f"q_{idx}", 
                          index=item['options'].index(st.session_state.user_answers[idx]) if answered else None,
                          disabled=answered)
        
        if choice and not answered:
            st.session_state.user_answers[idx] = choice
            st.session_state.next_trigger = True
            st.rerun()
            
        if answered:
            if st.session_state.user_answers[idx] == item['correct']: st.success("Đúng rồi! ✅")
            else: st.error(f"Sai rồi! ❌ Đáp án đúng: {item['correct']}")
        
        c1, c2 = st.columns(2)
        if c1.button("⬅ Câu trước", use_container_width=True): st.session_state.current_idx = max(0, idx-1); st.rerun()
        if c2.button("Câu sau ➡", use_container_width=True): st.session_state.current_idx = min(tong-1, idx+1); st.rerun()

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
        time.sleep(1)
        st.session_state.next_trigger = False
        if st.session_state.current_idx < tong - 1:
            st.session_state.current_idx += 1; st.rerun()
else:
    st.info("👈 Hãy tải file Word lên để bắt đầu.")
