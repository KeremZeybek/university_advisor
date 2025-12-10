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
    
    # --- 1. DOSYA YOLLARI ---
    major_path = os.path.join(base_dir, 'data', 'json', 'undergrad_majors.json')
    minor_path = os.path.join(base_dir, 'data', 'json', 'undergrad_minors.json')
    catalog_path = os.path.join(base_dir, 'data', 'csv', 'course_full_data_v2.csv')      # Statik Katalog
    schedule_path = os.path.join(base_dir, 'data', 'csv', 'active_schedule_master.csv')   # Dinamik Tarife (YENİ)
    
    # --- 2. DOSYA KONTROLLERİ ---
    if not os.path.exists(major_path) or not os.path.exists(minor_path):
        st.error("❌ JSON dosyaları eksik! 'data/json' klasörünü kontrol et.")
        st.stop()
        
    with open(major_path, 'r', encoding='utf-8') as f: majors = json.load(f)
    with open(minor_path, 'r', encoding='utf-8') as f: minors = json.load(f)
    
    if not os.path.exists(catalog_path):
        st.error(f"❌ Katalog verisi bulunamadı: {catalog_path}")
        st.stop()
        
    # --- 3. KATALOG VERİSİNİ YÜKLE & TEMİZLE ---
    catalog_df = pd.read_csv(catalog_path)
    
    # Kodları standartlaştır (Büyük Harf & Boşluksuz)
    catalog_df['Course Code'] = catalog_df['Course Code'].astype(str).str.strip().str.upper()
    
    # Katalogdaki hatalı 'Term' sütununu at (Artık gerçeği var)
    catalog_df.columns = [c.strip() for c in catalog_df.columns]
    if 'Term' in catalog_df.columns:
        catalog_df = catalog_df.drop(columns=['Term'])
        
    # --- 4. TARİFE (SCHEDULE) VERİSİNİ YÜKLE & ÖZETLE ---
    if os.path.exists(schedule_path):
        schedule_df = pd.read_csv(schedule_path)
        
        # Sütunları standartlaştır
        schedule_df.columns = [c.strip() for c in schedule_df.columns]
        
        if 'Course Code' in schedule_df.columns and 'Term' in schedule_df.columns:
            schedule_df['Course Code'] = schedule_df['Course Code'].astype(str).str.strip().str.upper()
            
            # --- KRİTİK ADIM: AGGREGATION (ÖZETLEME) ---
            # Schedule dosyasında bir dersin 10 tane şubesi olabilir (A1, A2, B1...).
            # Bize sadece "Bu ders hangi dönemlerde var?" bilgisi lazım.
            # Örn: CS 201 -> "Fall, Spring"
            
            term_info = schedule_df.groupby('Course Code')['Term'].apply(
                lambda x: ', '.join(sorted(x.unique()))
            ).reset_index()
            
            # --- 5. BİRLEŞTİRME (MERGE) ---
            # Katalog verisine 'Term' bilgisini ekle
            # how='right' diyerek SADECE bu sene açılan (Schedule'da olan) dersleri alıyoruz.
            # Böylece 10 yıl önce açılmış ama artık olmayan "Ölü Dersler" eleniyor.
            merged_df = pd.merge(
                catalog_df, 
                term_info, 
                on='Course Code', 
                how='right' 
            )
            
            # Merge sonrası boş gelen Description/Prereq alanlarını doldur
            # (Bazı yeni dersler katalogda olmayabilir)
            merged_df['Description'] = merged_df['Description'].fillna("Açıklama bulunamadı.")
            merged_df['Prerequisites'] = merged_df['Prerequisites'].fillna("")
            
        else:
            st.error("⚠️ Schedule dosyasında 'Course Code' veya 'Term' sütunu eksik.")
            merged_df = catalog_df
            merged_df['Term'] = 'Unknown'
    else:
        st.warning("⚠️ Schedule dosyası bulunamadı. Tüm dersler gösteriliyor (Filtre çalışmaz).")
        merged_df = catalog_df
        merged_df['Term'] = 'Unknown'

    # --- 6. SEVİYE (LEVEL) HESAPLAMA ---
    def extract_level(code):
        try:
            match = re.search(r"(\d+)", str(code))
            return int(match.group(1)) if match else 0
        except:
            return 0
    
    merged_df['Level'] = merged_df['Course Code'].apply(extract_level)
    
    return majors, minors, merged_df


    
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
    st.subheader("2. Dönem Seçimi")
    term_choice = st.radio(
        "Hangi dönem için plan yapıyorsun?",
        ["Fall (Güz)", "Spring (Bahar)", "Her İkisi"],
        index=0 # Varsayılan Fall olsun
    )
    # ... Dönem Seçimi kodunun altına ...
    
    st.subheader("3. Sınıfınız")
    student_year = st.selectbox(
        "Kaçıncı sınıfsın?",
        options=[1, 2, 3, 4],
        index=0,
        format_func=lambda x: f"{x}. Sınıf"
    )

    
    # 2. Transkript Girişi
    st.subheader("4. Transkript")
    
    # Otomatik 1. Sınıf Dersleri (Sabancı Ortak Dersleri)
    if student_year >= 2:
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
    else:
        default_transcript = ""
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
    st.subheader("🎯 Odak Alanı Seçin")
    
    all_programs = {}
    
    # Majorları ekle
    for m in major_data['faculties']:
        for p in m['programs']:
            all_programs[f"{p['name']} (Major)"] = {
                'keywords': p.get('keywords', []),
                'codes': p.get('subject_codes', []) 
            }
            
    # Minorları ekle
    for m in minor_data['faculties']:
        for p in m['programs']:
            all_programs[f"{p['name']} (Minor)"] = {
                'keywords': p.get('keywords', []),
                'codes': p.get('subject_codes', [])
            }
            
    # Döngü dışına alınan selectbox
    selected_focus = st.selectbox(
        "Hangi alana yönelik dersler önerilsin?",
        options=list(all_programs.keys()),
        index=0 
    )
    
    program_data = all_programs[selected_focus]
    active_keywords = program_data['keywords']
    allowed_codes = program_data['codes']
    
    st.caption(f"Aktif Filtreler: {', '.join(active_keywords)}")
    st.caption(f"İzin Verilen Kodlar: {', '.join(allowed_codes)}")

    # -------------------------------------------------------

    if st.button("Analizi Başlat", type="primary"):
        with st.spinner('Dersler analiz ediliyor...'):
            df = courses_df.copy()

            # --- YENİ EKLENEN KISIM: RECIT & LAB FİLTRESİ ---
            # 1. Kod Kontrolü: Sonu R veya L ile bitenleri at (Örn: DSA 201R, NS 101L)
            # Regex Mantığı: \d{3} (3 rakam) + [RL] (R veya L harfi) + $ (Son)
            df = df[~df['Course Code'].str.contains(r"\d{3}[RL]$", regex=True, na=False)]

            # 2. İsim Kontrolü: Adında 'Recitation', 'Laboratory' veya 'Discussion' geçenleri at
            exclude_keywords = ["Recitation", "Laboratory", " Lab ", "Discussion"]
            pattern = '|'.join(exclude_keywords)
            df = df[~df['Course Name'].str.contains(pattern, case=False, na=False)]
            # ------------------------------------------------
            
            # --- 1. SEVİYE FİLTRESİ ---
            if level_choice.startswith("Lisans"):
                df = df[df['Level'] < 500]
            else:
                df = df[df['Level'] >= 400]

            # --- 2. DÖNEM FİLTRESİ ---
            if "Fall" in term_choice:
                df = df[df['Term'].str.contains("Fall", case=False, na=False)]
            elif "Spring" in term_choice:
                df = df[df['Term'].str.contains("Spring", case=False, na=False)]
            
            # 3. Temizlik
            cols_to_clean = ['Description', 'Restrictions', 'Prerequisites', 'Corequisites']
            for col in cols_to_clean:
                if col in df.columns:
                    df[col] = df[col].apply(sanitize_text)
            
            # 4. Alınanları Çıkar
            df = df[~df['Course Code'].isin(taken_courses)]
            
            # 5. Mantık Kontrolü
            df[['Status', 'Missing_Reqs']] = df.apply(
                lambda r: pd.Series(check_smart_logic(r, taken_courses)), axis=1
            )
            
            # 6. PUANLAMA
            score_results = df.apply(
                lambda r: pd.Series(calculate_score(r, active_keywords, student_year, allowed_codes)), axis=1
            )
            df['Score'] = score_results[0]
            df['Why'] = score_results[1]
            
            # 7. Sonuç Gösterimi
            MIN_SCORE_THRESHOLD = 40
            
            final_df = df[
                (df['Status'] == 'READY') & 
                (df['Score'] >= MIN_SCORE_THRESHOLD) 
            ].sort_values(by='Score', ascending=False)

            final_df = final_df.head(20)

            if final_df.empty:
                st.warning(f"Kriterlere uygun ders bulunamadı (Minimum Puan: {MIN_SCORE_THRESHOLD}).")
            else:
                st.success(f"En uygun **{len(final_df)}** ders listeleniyor (İlk 20).")
                
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