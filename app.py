"""
=============================================================================
PROJE: SABANCI UNIVERSITY SMART ADVISOR
DOSYA: app.py
TANIM: Streamlit tabanlı ana web arayüzü.

YOL HARİTASI (ROADMAP):
1. IMPORTS & CONFIG ....... Kütüphaneler ve Sayfa Ayarları
2. DATA LOADING ........... JSON ve CSV dosyalarının yüklenmesi ve birleştirilmesi
3. SIDEBAR (INPUTS) ....... Kullanıcıdan veri alma (Sınıf, Transkript vb.)
4. MAIN TABS .............. Ana Arayüz Sekmeleri
   |__ Tab 1: Recommendation Engine (Ders Öneri Motoru - EN KARMAŞIK KISIM)
   |__ Tab 2: Program Search (Bölüm Arama)
   |__ Tab 3: Synergy Analysis (Major-Minor Uyumu)
=============================================================================
"""

import streamlit as st
import pandas as pd
import json
import os
import re
from src.ml_engine import calculate_ml_scores 

# Özel Modüller (src klasöründen)
from src.advisor import UniversityAdvisor
from src.personal_recommendation import check_smart_logic, calculate_score, sanitize_text

# =============================================================================
# 1. IMPORTS & CONFIGURATION
# =============================================================================
st.set_page_config(
    page_title="Sabancı University Smart Advisor",
    page_icon="🎓",
    layout="wide"
)

# =============================================================================
# 2. DATA LOADING & PRE-PROCESSING
# =============================================================================
@st.cache_data
def load_data():
    """
    Tüm veri setlerini yükler, temizler ve birleştirir.
    Cache mekanizması sayesinde sayfa yenilendiğinde tekrar çalışmaz, hız kazandırır.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # --- A. Dosya Yolları ---
    major_path = os.path.join(base_dir, 'data', 'json', 'undergrad_majors.json')
    minor_path = os.path.join(base_dir, 'data', 'json', 'undergrad_minors.json')
    catalog_path = os.path.join(base_dir, 'data', 'csv', 'course_full_data_v2.csv')    # Statik Veri (Açıklama, Ön Koşul)
    schedule_path = os.path.join(base_dir, 'data', 'csv', 'active_schedule_master.csv') # Dinamik Veri (Dönem, Şube)
    
    # --- B. JSON Yükleme (Major/Minor) ---
    if not os.path.exists(major_path) or not os.path.exists(minor_path):
        st.error("❌ Kritik Hata: JSON dosyaları eksik! 'data/json' klasörünü kontrol edin.")
        st.stop()
        
    with open(major_path, 'r', encoding='utf-8') as f: majors = json.load(f)
    with open(minor_path, 'r', encoding='utf-8') as f: minors = json.load(f)
    
    # --- C. Katalog Yükleme ---
    if not os.path.exists(catalog_path):
        st.error(f"❌ Katalog verisi bulunamadı: {catalog_path}")
        st.stop()
        
    catalog_df = pd.read_csv(catalog_path)
    
    # Normalizasyon: Kodları BÜYÜK HARF ve boşluksuz yap (Örn: " cs 201 " -> "CS 201")
    catalog_df['Course Code'] = catalog_df['Course Code'].astype(str).str.strip().str.upper()
    
    # Temizlik: Katalogdaki güvenilmez 'Term' sütununu at
    catalog_df.columns = [c.strip() for c in catalog_df.columns]
    if 'Term' in catalog_df.columns:
        catalog_df = catalog_df.drop(columns=['Term'])
        
    # --- D. Schedule (Tarife) Yükleme ve Birleştirme ---
    if os.path.exists(schedule_path):
        schedule_df = pd.read_csv(schedule_path)
        schedule_df.columns = [c.strip() for c in schedule_df.columns]
        
        if 'Course Code' in schedule_df.columns and 'Term' in schedule_df.columns:
            schedule_df['Course Code'] = schedule_df['Course Code'].astype(str).str.strip().str.upper()
            
            # AGGREGATION: Bir dersin tüm şubelerini (A1, B1) tek satıra indir -> "Fall, Spring"
            term_info = schedule_df.groupby('Course Code')['Term'].apply(
                lambda x: ', '.join(sorted(x.unique()))
            ).reset_index()
            
            # MERGE: Katalog ile Dönem bilgisini birleştir
            # how='right' -> Sadece bu yıl açılan (Schedule'da olan) dersleri al, eskileri at.
            merged_df = pd.merge(catalog_df, term_info, on='Course Code', how='right')
            
            # Eksik verileri doldur
            merged_df['Description'] = merged_df['Description'].fillna("Açıklama bulunamadı.")
            merged_df['Prerequisites'] = merged_df['Prerequisites'].fillna("")
            
        else:
            st.error("⚠️ Schedule dosya formatı hatalı (Sütunlar eksik).")
            merged_df = catalog_df
            merged_df['Term'] = 'Unknown'
    else:
        st.warning("⚠️ Schedule dosyası bulunamadı. Filtreleme çalışmayacak.")
        merged_df = catalog_df
        merged_df['Term'] = 'Unknown'

    # --- E. Seviye (Level) Çıkarma ---
    # CS 412 -> 412 sayısını çıkarır.
    def extract_level(code):
        try:
            match = re.search(r"(\d+)", str(code))
            return int(match.group(1)) if match else 0
        except:
            return 0
    
    merged_df['Level'] = merged_df['Course Code'].apply(extract_level)
    
    return majors, minors, merged_df

# Veriyi Başlat
try:
    major_data, minor_data, courses_df = load_data()
    advisor = UniversityAdvisor(major_data, minor_data)
except Exception as e:
    st.error(f"Sistem başlatılırken hata oluştu: {e}")
    st.stop()

# =============================================================================
# 3. SIDEBAR (USER INPUTS)
# =============================================================================
with st.sidebar:
    st.header("⚙️ Öğrenci Profili")
    
    # --- A. Akademik Seviye ---
    st.subheader("1. Akademik Durum")
    level_choice = st.radio(
        "Hedef Ders Seviyesi:",
        ["Lisans", "Yüksek Lisans"],
        index=0
    )
    
    # --- B. Dönem Seçimi ---
    st.subheader("2. Dönem")
    term_choice = st.radio(
        "Hangi dönem için plan yapıyorsun?",
        ["Güz", "Bahar", "Her ikisi de"],
        index=0
    )
    
    # --- C. Sınıf Bilgisi ---
    st.subheader("3. Sınıf")
    student_year = st.selectbox(
        "Kaçıncı sınıfsın?",
        options=[1, 2, 3, 4],
        index=1, # Varsayılan 2. Sınıf
        format_func=lambda x: f"{x}. Sınıf"
    )

    # --- D. Transkript (Otomatik Doldurma) ---
    st.subheader("4. Transkript")
    
    # 2. sınıf ve üstü için ortak dersleri otomatik ekle
    if student_year >= 2:
        default_transcript = (
            "MATH 101\nMATH 102\n"
            "NS 101\nNS 102\n"
            "SPS 101\nSPS 102\n"
            "TLL 101\nTLL 102\n"
            "HIST 191\nHIST 192\n"
            "IF 100\nAL 102\nCIP 101\nPROJ 201\n"
        )
    else:
        default_transcript = ""
        
    transcript_input = st.text_area(
        "Alınan Dersler (Kodu yazıp Enter'a bas):",
        value=default_transcript,
        height=200,
        help="Buraya girilen dersler 'Tamamlanmış' sayılır ve önerilerden çıkarılır."
    )
    
    # Listeye Çevir
    taken_courses = set([code.strip().upper() for code in transcript_input.split('\n') if code.strip()])
    st.info(f"✅ {len(taken_courses)} ders tamamlandı.")

# =============================================================================
# 4. MAIN INTERFACE (TABS)
# =============================================================================
st.title("🎓 Sabancı Üniversitesi - Akıllı Akademik Danışman")

tab1, tab2, tab3 = st.tabs([
    "📚 Akıllı Ders Önerisi", 
    "🔍 Bölüm/Yandal Bulucu", 
    "🤝 Major-Minor Uyumu"
])

# -----------------------------------------------------------------------------
# TAB 1: RECOMMENDATION ENGINE (ÖNERİ MOTORU)
# -----------------------------------------------------------------------------
with tab1:
    st.header("Gelecek Dönem İçin Ders Önerileri")
    
    # --- A. Odak Alanı Seçimi (Subject Focus) ---
    st.subheader("🎯 Odak Alanı")
    
    # Tüm programları (Major+Minor) tek listede topla
    all_programs = {}
    
    # Major Döngüsü
    for m in major_data['faculties']:
        for p in m['programs']:
            all_programs[f"{p['name']} (Major)"] = {
                'keywords': p.get('keywords', []),
                'codes': p.get('subject_codes', []) 
            }
            
    # Minor Döngüsü
    for m in minor_data['faculties']:
        for p in m['programs']:
            all_programs[f"{p['name']} (Minor)"] = {
                'keywords': p.get('keywords', []),
                'codes': p.get('subject_codes', [])
            }
            
    selected_focus = st.selectbox(
        "Hangi alana yönelik dersler önerilsin?",
        options=list(all_programs.keys()),
        index=0 
    )
    
    # Seçilen programın verilerini çek
    program_data = all_programs[selected_focus]
    active_keywords = program_data['keywords']
    allowed_codes = program_data['codes']
    
    # Bilgi Çubuğu
    st.caption(f"Filtreler: {', '.join(active_keywords[:5])}...")
    st.caption(f"İzin Verilen Kodlar: {', '.join(allowed_codes)}")

    if st.button("Analizi Başlat", type="primary"):
        with st.spinner('Yapay Zeka dersleri analiz ediyor...'):
            df = courses_df.copy()

            # ---------------------------------------------------------
            # 1. TEMEL FİLTRELER (Gürültü Temizliği)
            # ---------------------------------------------------------
            
            # Recit & Lab Filtresi (Regex: Sonu R veya L ile biten 3 haneli kodlar)
            df = df[~df['Course Code'].str.contains(r"\d{3}[RL]$", regex=True, na=False)]
            
            # İsim Filtresi (Adında Recitation/Lab geçenleri at)
            exclude_keywords = ["Recitation", "Laboratory", " Lab ", "Discussion"]
            pattern = '|'.join(exclude_keywords)
            df = df[~df['Course Name'].str.contains(pattern, case=False, na=False)]
            
            # Seviye Filtresi
            if level_choice.startswith("Lisans"):
                df = df[df['Level'] < 500]
            else:
                df = df[df['Level'] >= 400]

            # Dönem Filtresi
            if "Güz" in term_choice or "Fall" in term_choice:
                df = df[df['Term'].str.contains("Fall", case=False, na=False)]
            elif "Bahar" in term_choice or "Spring" in term_choice:
                df = df[df['Term'].str.contains("Spring", case=False, na=False)]
            
            # ---------------------------------------------------------
            # 2. VERİ HAZIRLIĞI
            # ---------------------------------------------------------
            
            # Metin Temizliği
            cols_to_clean = ['Description', 'Restrictions', 'Prerequisites', 'Corequisites']
            for col in cols_to_clean:
                if col in df.columns:
                    df[col] = df[col].apply(sanitize_text)
            
            # Transkript Kontrolü (Alınanları Çıkar)
            df = df[~df['Course Code'].isin(taken_courses)]
            
            # Ön Koşul (Logic) Kontrolü
            df[['Status', 'Missing_Reqs']] = df.apply(
                lambda r: pd.Series(check_smart_logic(r, taken_courses)), axis=1
            )
            
            # ---------------------------------------------------------
            # 3. AI MOTORU & HİBRİT PUANLAMA
            # ---------------------------------------------------------
            
            # A. ML ile İçerik Benzerliği Hesapla
            user_query = " ".join(active_keywords)
            ml_scores = calculate_ml_scores(df, user_query)
            df['ML_Score'] = ml_scores
            
            # B. Hibrit Skorlama Fonksiyonu
            def calculate_hybrid_score(row, current_year):
                # Başlangıç puanı Yapay Zeka'dan gelir
                score = row['ML_Score']
                reasons = []
                
                # Eğer ML skoru yüksekse açıklama ekle
                if score > 15:
                    reasons.append(f"İçerik Uyumu (%{int(score)})")
                
                # Zincirleme Bonusu (Prerequisite varsa ve sağlanmışsa)
                prereq_text = str(row['Prerequisites']).lower()
                # Basit kontrol: İçinde ders kodu formatı (CS 201 gibi) var mı?
                if re.search(r"[a-z]{2,5}\s*\d{3,4}", prereq_text):
                    score += 20
                    reasons.append("Zincir Ders (+20)")
                
                # Sınıf Uyumu (Year Relevance)
                try:
                    code_num = int(re.search(r"(\d+)", str(row['Course Code'])).group(1))
                    level = code_num // 100
                    
                    if current_year == 1 and level >= 4: score -= 30  # 1. sınıfa 4. sınıf dersi önerme
                    if level == current_year or level == current_year + 1:
                        score += 10
                        # reasons.append("Sınıfına Uygun")
                except:
                    pass

                # Bölüm Kodu Kontrolü (Allowed Codes)
                # Dersin kodu izin verilenler listesinde değilse puan kır
                course_subject = row['Course Code'].split()[0]
                if course_subject not in allowed_codes:
                    score -= 50

                return pd.Series([score, " + ".join(reasons)])

            # Fonksiyonu Uygula
            score_results = df.apply(
                lambda r: calculate_hybrid_score(r, student_year), axis=1
            )
            df['Score'] = score_results[0]
            df['Why'] = score_results[1]
            
            # ---------------------------------------------------------
            # 4. SONUÇ GÖSTERİMİ
            # ---------------------------------------------------------
            
            MIN_SCORE_THRESHOLD = 20 # ML skorları üzerine bonuslar eklendiği için barajı ayarladık
            
            final_df = df[
                (df['Status'] == 'READY') & 
                (df['Score'] >= MIN_SCORE_THRESHOLD) 
            ].sort_values(by='Score', ascending=False)
  
            final_df = final_df.head(20)

            if final_df.empty:
                st.warning(f"Kriterlere uygun ders bulunamadı (Min Puan: {MIN_SCORE_THRESHOLD}). İlgi alanını veya dönemi değiştirmeyi dene.")
            else:
                st.success(f"Yapay Zeka senin için en uygun **{len(final_df)}** dersi buldu.")
                
                st.dataframe(
                    final_df[['Course Code', 'Course Name', 'Score', 'Why', 'Description']],
                    column_config={
                        "Score": st.column_config.ProgressColumn("Uygunluk", format="%d", min_value=0, max_value=100),
                        "Why": st.column_config.TextColumn("Eşleşme Nedeni", width="medium"),
                        "Description": st.column_config.TextColumn("Ders İçeriği", width="large")
                    },
                    hide_index=True
                )

# -----------------------------------------------------------------------------
# TAB 2: SEARCH ENGINE (ARAMA)
# -----------------------------------------------------------------------------
with tab2:
    st.header("İlgi Alanına Göre Program Ara")
    keyword = st.text_input("Anahtar Kelime (Örn: Artificial Intelligence, Marketing)", "")
    
    if keyword:
        results = advisor.find_program_by_keyword(keyword)
        if results:
            for res in results:
                color = "green" if res['type'] == "Major" else "blue"
                with st.expander(f":{color}[{res['type']}] **{res['program']}**"):
                    st.write(f"Eşleşen Konular: {', '.join(res['matched_keywords'])}")
        else:
            st.warning("Sonuç bulunamadı.")

# -----------------------------------------------------------------------------
# TAB 3: SYNERGY ANALYSIS (UYUM)
# -----------------------------------------------------------------------------
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