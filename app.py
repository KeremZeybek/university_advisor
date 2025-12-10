import streamlit as st
import pandas as pd
import json
import os
import re

from src.advisor import UniversityAdvisor
from src.personal_recommendation import check_smart_logic, calculate_score, sanitize_text

# ---------------------------------------------------------
# SAYFA AYARLARI
# ---------------------------------------------------------
st.set_page_config(
    page_title="Sabancı University Smart Advisor",
    page_icon="🎓",
    layout="wide"
)

# ---------------------------------------------------------
# VERİ YÜKLEME & ÖN İŞLEME
# ---------------------------------------------------------
@st.cache_data
def load_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    major_path = os.path.join(base_dir, 'data', 'json', 'undergrad_majors.json')
    minor_path = os.path.join(base_dir, 'data', 'json', 'undergrad_minors.json')
    csv_path = os.path.join(base_dir, 'data', 'csv', 'course_full_data_v2.csv')
    
    with open(major_path, 'r', encoding='utf-8') as f: majors = json.load(f)
    with open(minor_path, 'r', encoding='utf-8') as f: minors = json.load(f)
    
    courses_df = pd.read_csv(csv_path)
    
    # -----------------------------------------------------
    # CRITICAL FIX: Veri Setini Normalize Et (Büyük Harf)
    # -----------------------------------------------------
    courses_df['Course Code'] = courses_df['Course Code'].astype(str).str.strip().str.upper()

    # Level (Ders Seviyesi) Sütunu Oluştur (Örn: CS 412 -> 412)
    def extract_level(code):
        match = re.search(r"(\d+)", str(code))
        return int(match.group(1)) if match else 0
    
    courses_df['Level'] = courses_df['Course Code'].apply(extract_level)
    
    return majors, minors, courses_df

try:
    major_data, minor_data, courses_df = load_data()
    advisor = UniversityAdvisor(major_data, minor_data)
except Exception as e:
    st.error(f"Veri yüklenirken hata oluştu: {e}")
    st.stop()

# ---------------------------------------------------------
# SIDEBAR - KULLANICI AYARLARI
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Öğrenci Ayarları")
    
    st.subheader("1. Akademik Seviyeniz")
    # BUG FIX: Seçenek ismini değiştirmeden mantığı düzelttik
    level_choice = st.radio(
        "Hangi dersleri görmek istiyorsun?",
        ["Lisans (Undergrad)", "Yüksek Lisans / Doktora (Grad)"],
        index=0
    )
    
    # 2. Transkript Girişi
    st.subheader("2. Transkript")
    
    # Otomatik 1. Sınıf Dersleri (Sabancı Ortak Dersleri)
    default_transcript = (
        "MATH 101\nMATH 102\n"
        "NS 101\nNS 102\n"
        "SPS 101\nSPS 102\n"
        "TLL 101\nTLL 102\n"
        "HIST 191\nHIST 192\n"
        "IF 100\n"
        "AL 102\n"
        "CIP 101\n"
        "PROJ 201\n"
    )
    
    transcript_input = st.text_area(
        "Alınan Dersler (Düzenlenebilir):",
        value=default_transcript,
        height=250,
        help="Buraya eklediğin dersler önerilerden çıkarılır ve ön koşul kontrolünde kullanılır."
    )
    
    # Transkript İşleme (Case Insensitive Yapısı)
    taken_courses = set([code.strip().upper() for code in transcript_input.split('\n') if code.strip()])
    
    st.info(f"✅ {len(taken_courses)} ders tamamlanmış varsayılıyor.")

# ---------------------------------------------------------
# ANA EKRAN
# ---------------------------------------------------------
st.title("🎓 Sabancı Üniversitesi - Akıllı Akademik Danışman")

tab1, tab2, tab3 = st.tabs(["📚 Akıllı Ders Önerisi", "🔍 Bölüm/Yandal Bulucu", "🤝 Major-Minor Uyumu"])

# --- TAB 1: DERS ÖNERİ MOTORU ---
with tab1:
    st.header("Gelecek Dönem İçin Ders Önerileri")
    
    # --- YENİ ÖZELLİK: İLGİ ALANI SEÇİMİ ---
    st.subheader("🎯 Odak Alanı Seçin")
    
    # Tüm Major ve Minor programlarını tek listede toplayalım
    all_programs = {}
    for m in major_data['faculties']:
        for p in m['programs']:
            all_programs[f"{p['name']} (Major)"] = p['keywords']
            
    for m in minor_data['faculties']:
        for p in m['programs']:
            all_programs[f"{p['name']} (Minor)"] = p['keywords']
            
    # Kullanıcı buradan seçim yapacak (Varsayılan: CS veya senin bölümün)
    selected_focus = st.selectbox(
        "Hangi alana yönelik dersler önerilsin?",
        options=list(all_programs.keys()),
        index=0 # Listenin başındaki gelir
    )
    
    # Seçilen programın JSON'daki keywordlerini alıyoruz
    active_keywords = all_programs[selected_focus]
    st.caption(f"Aktif Filtreler: {', '.join(active_keywords)}")

    # -------------------------------------------------------

    if st.button("Analizi Başlat", type="primary"):
        with st.spinner('Dersler analiz ediliyor...'):
            df = courses_df.copy()
            
            # 1. Seviye Filtresi
            if level_choice.startswith("Lisans"):
                df = df[df['Level'] < 500]

            # 2. Temizlik
            cols_to_clean = ['Description', 'Restrictions', 'Prerequisites', 'Corequisites']
            for col in cols_to_clean:
                if col in df.columns:
                    df[col] = df[col].apply(sanitize_text)
            
            # 3. Alınanları Çıkar
            df = df[~df['Course Code'].isin(taken_courses)]
            
            # 4. Mantık Kontrolü
            df[['Status', 'Missing_Reqs']] = df.apply(
                lambda r: pd.Series(check_smart_logic(r, taken_courses)), axis=1
            )
            
            # 5. PUANLAMA (ARTIK DİNAMİK!)
            # calculate_score artık 2 değer döndürüyor: (Score, Matched Terms)
            score_results = df.apply(
                lambda r: pd.Series(calculate_score(r, active_keywords)), axis=1
            )
            df['Score'] = score_results[0]
            df['Why'] = score_results[1] # Neden önerildiğini tutan sütun
            
            # 6. Sonuç Gösterimi
            final_df = df[
                (df['Status'] == 'READY') & 
                (df['Score'] > 0)
            ].sort_values(by='Score', ascending=False)
            
            if final_df.empty:
                st.warning("Bu alanda uygun ders bulunamadı.")
            else:
                st.metric("Önerilen Ders Sayısı", len(final_df))
                
                # Tabloyu gösterirken 'Why' sütununu da ekliyoruz
                st.dataframe(
                    final_df[['Course Code', 'Course Name', 'Score', 'Why', 'Description']],
                    column_config={
                        "Score": st.column_config.ProgressColumn("Uygunluk", format="%d", min_value=0, max_value=100),
                        "Why": st.column_config.TextColumn("Eşleşen Konular", width="medium"),
                        "Description": st.column_config.TextColumn("İçerik", width="large")
                    },
                    hide_index=True
                )
        
# --- TAB 2: ARAMA MOTORU ---
with tab2:
    st.header("İlgi Alanına Göre Program Ara")
    keyword = st.text_input("Anahtar Kelime (Örn: Artificial Intelligence, Marketing)", "")
    if keyword:
        results = advisor.find_program_by_keyword(keyword)
        if results:
            for res in results:
                color = "green" if res['type'] == "Major" else "blue"
                with st.expander(f":{color}[{res['type']}] **{res['program']}**"):
                    st.write(f"Eşleşenler: {', '.join(res['matched_keywords'])}")
        else:
            st.warning("Sonuç bulunamadı.")

# --- TAB 3: UYUM ANALİZİ ---
with tab3:
    st.header("Major-Minor Uyumu")
    major_options = {m['name']: m['id'] for m in advisor.majors}
    selected = st.selectbox("Ana Dal Seç:", list(major_options.keys()))
    
    if selected:
        synergies = advisor.calculate_synergy(major_options[selected])
        col1, col2 = st.columns(2)
        for i, rec in enumerate(synergies[:4]):
            with (col1 if i % 2 == 0 else col2):
                st.success(f"**{rec['minor_name']}** (Skor: {rec['score']})")
                st.caption(f"Ortak Dersler: {', '.join(rec['shared_codes'])}")