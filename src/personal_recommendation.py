"""
=============================================================================
PROJE: SABANCI UNIVERSITY SMART ADVISOR
DOSYA: src/personal_recommendation.py
TANIM: Ders önerme mantığı, puanlama algoritması ve transkript analizi.

YOL HARİTASI (ROADMAP):
1. CONFIG & PATHS ......... Dosya yolları ve ayarlar
2. TEXT CLEANING .......... HTML ve metin temizleme fonksiyonları
3. LOGIC & SCORING ........ En kritik bölüm: Puanlama ve Ön koşul kontrolü
   |__ check_smart_logic(): Transkripte göre dersi kilitler/açar
   |__ calculate_score():   Dersin uygunluk puanını hesaplar
4. EXECUTION .............. Dosya doğrudan çalıştırılırsa (Test Modu)
=============================================================================
"""

import pandas as pd
import re
import os
import csv

# =============================================================================
# 1. FILE PATHS & CONFIGURATION
# =============================================================================
# Bu dosyanın bulunduğu klasörden yola çıkarak ana dizini buluyoruz
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)

# Varsayılan dosya yolları (Standalone çalışırsa kullanılır)
INPUT_FILE = os.path.join(BASE_DIR, "data", "csv", "course_full_data_v2.csv")
TRANSCRIPT_FILE = os.path.join(BASE_DIR, "data", "user", "transcript.txt")
OUTPUT_FILE = os.path.join(BASE_DIR, "data", "user", "kerem_final_clean_plan.csv")

# =============================================================================
# 2. CLEANING FUNCTIONS
# =============================================================================
def sanitize_text(text):
    """
    HTML artıklarını, gereksiz boşlukları ve navigasyon metinlerini temizler.
    """
    if pd.isna(text) or text == "None":
        return ""
    
    text = str(text)
    
    # 1. Belirli BannerWeb cümlelerini at
    garbage_marker = "Select the desired Level or Schedule Type to find available classes for the course."
    if garbage_marker in text:
        text = text.split(garbage_marker)[-1]
    
    # 2. Navigasyon linklerini temizle
    if "Return to Previous New Search" in text:
        text = re.sub(r'.*Release: \d+\.\d+\.\d+', '', text, flags=re.DOTALL)

    # 3. Standart temizlik (Satır sonları, tablar)
    text = re.sub(r'[\r\n\t]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def load_transcript(filename):
    """
    Kullanıcının transkript dosyasını okur ve ders kodlarını küme (set) olarak döner.
    """
    if not os.path.exists(filename): 
        print(f"UYARI: Transkript dosyası bulunamadı: {filename}")
        return set()
    
    with open(filename, "r", encoding="utf-8") as f:
        # Her satırı temizle ve BÜYÜK HARFE çevir
        return {line.strip().upper() for line in f if line.strip()}

def extract_codes(text):
    """Metin içindeki ders kodlarını (Örn: CS 201) regex ile bulur."""
    return re.findall(r"([A-Z]{2,5}\s+\d{3,4})", str(text))

# =============================================================================
# 3. CORE LOGIC & SCORING ALGORITHMS
# =============================================================================

def check_smart_logic(row, taken_courses):
    """
    Dersin ön koşullarını (Prerequisites) kontrol eder.
    
    Dönüş:
    - Status: 'READY' (Alınabilir) veya 'LOCKED' (Ön koşul eksik)
    - Missing: Eksik olan derslerin listesi
    """
    raw_text = str(row['Prerequisites']).lower()
    
    # Ön koşul yoksa direkt hazırdır
    if pd.isna(row['Prerequisites']) or row['Prerequisites'] == "None" or raw_text == "" or raw_text == "nan":
        return "READY", ""

    # Metin temizliği (Minimum grade vb. ifadeleri at)
    raw_text = re.sub(r'minimum grade of [a-z]', '', raw_text)
    raw_text = re.sub(r'undergraduate level', '', raw_text)
    
    # Mantıksal Blokları Ayır (AND ile ayrılmış bloklar)
    req_blocks = raw_text.split(' and ')
    missing_requirements = []
    
    for block in req_blocks:
        # Her blok içindeki alternatifler (OR ile ayrılmış)
        options = block.split(' or ')
        block_codes = []
        block_satisfied = False
        
        for option in options:
            codes_in_option = extract_codes(option.upper())
            if not codes_in_option: continue
            block_codes.extend(codes_in_option)
            
            # Eğer bu opsiyondaki TÜM kodlar alınmışsa blok tamamdır
            if all(code in taken_courses for code in codes_in_option):
                block_satisfied = True
                break 
        
        # Blok sağlanmadıysa eksikleri listeye ekle
        if not block_satisfied and block_codes:
            missing_text = " OR ".join(sorted(list(set(block_codes))))
            missing_requirements.append(f"({missing_text})")

    if not missing_requirements: 
        return "READY", ""
    else: 
        return "LOCKED", " AND ".join(missing_requirements)


def calculate_score(row, interest_keywords, student_year=1, allowed_codes=None):
    """
    GELİŞMİŞ PUANLAMA MOTORU:
    
    1. Progression Score (+50): Zincirleme ders bonusu (Ön koşulu varsa ve sağlanmışsa).
    2. Keyword Score (+20/kelime): İlgi alanı eşleşmesi.
    3. Year Relevance (+/- Puan): Öğrencinin sınıfına uygunluk ve seviye cezaları.
    4. Subject Penalty (-50): İzin verilmeyen bölüm kodları için ceza.
    """
    # Analiz edilecek metinleri birleştir
    text = (str(row['Course Name']) + " " + str(row['Description'])).lower()
    prereq_text = str(row['Prerequisites']).lower()
    course_code_str = str(row['Course Code']).strip().upper()
    
    score = 0
    reasons = []

    # --- 1. ZİNCİRLEME BONUSU (CHAIN) ---
    has_prerequisite = False
    if pd.notna(row['Prerequisites']) and row['Prerequisites'] != "nan":
        if re.search(r"[a-z]{2,5}\s*\d{3,4}", prereq_text):
            has_prerequisite = True

    if has_prerequisite:
        score += 50
        reasons.append("Zincir Ders")

    # --- 2. İLGİ ALANI (KEYWORDS) ---
    keyword_hits = 0
    matched_terms = []
    for w in interest_keywords:
        if w.lower() in text:
            keyword_hits += 1
            matched_terms.append(w)
    
    if keyword_hits > 0:
        score += (keyword_hits * 20)
        reasons.append(f"İlgi: {', '.join(matched_terms[:2])}")

    # --- 3. SINIF UYUMU (YEAR RELEVANCE) ---
    try:
        match = re.search(r"(\d+)", str(row['Course Code']))
        if match:
            course_num = int(match.group(1))
            course_level = course_num // 100 # Örn: 201 -> 2
            
            # Hedef seviyeler (N ve N+1)
            if student_year >= 4:
                target_levels = [4, 5, 6]
            else:
                target_levels = [student_year, student_year + 1]
            
            if course_level in target_levels:
                score += 20
            
            # Sınıf uyumsuzluk cezaları
            if student_year == 1 and course_level >= 4: score -= 40
            if student_year == 3 and course_level == 2: score -= 10
            if student_year == 3 and course_level == 1: score -= 20
            if student_year == 4 and course_level == 1: score -= 40
            if student_year == 4 and course_level == 2: score -= 20

    except: 
        pass

    # --- 4. BÖLÜM KODU FİLTRESİ (SUBJECT PENALTY) ---
    if allowed_codes:
        subject_match = re.match(r"([A-Z]+)", course_code_str)
        if subject_match:
            subject = subject_match.group(1)
            
            # İzin verilen listede yoksa ceza kes
            if subject not in allowed_codes:
                score -= 50

    # Skoru 100'e sabitle (Maksimum)
    score = min(100, score)
    
    why_string = " + ".join(reasons) if reasons else "Genel"
    
    return score, why_string

# =============================================================================
# 4. MAIN EXECUTION (STANDALONE TEST MODE)
# =============================================================================
def run_analysis():
    """
    Bu dosya doğrudan çalıştırılırsa (python personal_recommendation.py),
    varsayılan ayarlarla bir test analizi yapar.
    """
    print(f"📂 Veri Kaynağı: {INPUT_FILE}")
    print("🔄 Standalone Analiz Başlatılıyor...")

    try:
        df = pd.read_csv(INPUT_FILE)
        taken_courses = load_transcript(TRANSCRIPT_FILE)
        print(f"✅ Transkript okundu ({len(taken_courses)} ders).")
    except FileNotFoundError as e:
        print(f"❌ ERROR: Dosya bulunamadı!\n{e}")
        return

    # 1. Temizlik
    cols_to_clean = ['Description', 'Restrictions', 'Prerequisites', 'Corequisites']
    for col in cols_to_clean:
        if col in df.columns:
            df[col] = df[col].apply(sanitize_text)

    # 2. Alınanları Çıkar
    df = df[~df['Course Code'].isin(taken_courses)].copy()

    # 3. Mantık Kontrolü
    df[['Status', 'Missing_Reqs']] = df.apply(lambda r: pd.Series(check_smart_logic(r, taken_courses)), axis=1)

    # 4. Puanlama (TEST İÇİN VARSAYILAN DEĞERLER)
    # Standalone çalışırken hata vermemesi için dummy veriler kullanıyoruz
    test_keywords = ['DATA', 'PYTHON', 'ANALYSIS'] 
    test_year = 2
    
    print(f"ℹ️ Test Modu Parametreleri: Yıl={test_year}, Keywords={test_keywords}")
    
    # calculate_score artık tuple döndürüyor (score, why), bunları ayırıyoruz
    score_results = df.apply(
        lambda r: pd.Series(calculate_score(r, test_keywords, student_year=test_year)), axis=1
    )
    df['Score'] = score_results[0]
    
    # 5. Filtreleme ve Kaydetme
    df['Level'] = df['Course Code'].apply(lambda x: int(re.search(r"(\d+)", str(x)).group(1)) if re.search(r"(\d+)", str(x)) else 0)
    
    final_df = df[(df['Level'] < 500) & (df['Score'] > 0)].copy()
    final_df = final_df.sort_values(by=['Status', 'Score'], ascending=[False, False])

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    final_df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig', quoting=csv.QUOTE_ALL)

    print("\n" + "="*60)
    print("✅ TEST ANALİZİ TAMAMLANDI!")
    print(f"📝 Sonuç: {OUTPUT_FILE}")
    print("-" * 60)

if __name__ == "__main__":
    run_analysis()