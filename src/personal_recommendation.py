import pandas as pd
import re
import os
import csv

# ---------------------------------------------------------
# 1. FILE PATHS & CONFIGURATION 
# ---------------------------------------------------------

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)

INPUT_FILE = os.path.join(BASE_DIR, "data", "csv", "course_full_data_v2.csv")
TRANSCRIPT_FILE = os.path.join(BASE_DIR, "data", "user", "transcript.txt")
OUTPUT_FILE = os.path.join(BASE_DIR, "data", "user", "kerem_final_clean_plan.csv")

# ---------------------------------------------------------
# 2. CLEANING FUNCTION
# ---------------------------------------------------------
def sanitize_text(text):
    if pd.isna(text) or text == "None":
        return ""
    
    text = str(text)
    
    # STEP 1: Cleanup using specific garbage marker
    garbage_marker = "Select the desired Level or Schedule Type to find available classes for the course."
    
    if garbage_marker in text:
        text = text.split(garbage_marker)[-1]
    
    # STEP 2: Other Navigation Cleanup
    if "Return to Previous New Search" in text:
        text = re.sub(r'.*Release: \d+\.\d+\.\d+', '', text, flags=re.DOTALL)

    # STEP 3: Standard Cleanup
    text = re.sub(r'[\r\n\t]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

# ---------------------------------------------------------
# 3. OTHER FUNCTIONS
# ---------------------------------------------------------
def load_transcript(filename):
    if not os.path.exists(filename): 
        print(f"UYARI: Transkript dosyası bulunamadı: {filename}")
        return set()
    with open(filename, "r", encoding="utf-8") as f:
        return {line.strip().upper() for line in f if line.strip()}

def extract_codes(text):
    return re.findall(r"([A-Z]{2,5}\s+\d{3,4})", str(text))

def check_smart_logic(row, taken_courses):
    raw_text = str(row['Prerequisites']).lower()
    if pd.isna(row['Prerequisites']) or row['Prerequisites'] == "None" or raw_text == "" or raw_text == "nan":
        return "READY", ""

    raw_text = re.sub(r'minimum grade of [a-z]', '', raw_text)
    raw_text = re.sub(r'undergraduate level', '', raw_text)
    
    req_blocks = raw_text.split(' and ')
    missing_requirements = []
    
    for block in req_blocks:
        options = block.split(' or ')
        block_codes = []
        block_satisfied = False
        
        for option in options:
            codes_in_option = extract_codes(option.upper())
            if not codes_in_option: continue
            block_codes.extend(codes_in_option)
            
            if all(code in taken_courses for code in codes_in_option):
                block_satisfied = True
                break 
        
        if not block_satisfied and block_codes:
            missing_text = " OR ".join(sorted(list(set(block_codes))))
            missing_requirements.append(f"({missing_text})")

    if not missing_requirements: return "READY", ""
    else: return "LOCKED", " AND ".join(missing_requirements)


def calculate_score(row, interest_keywords, student_year=1, allowed_codes=None):
    """
    Dersin puanını hesaplar:
    1. Progression Score (Zincirleme Bonusu): Ön koşulu varsa ve sağlanmışsa.
    2. Keyword Score: İlgi alanı eşleşmesi.
    3. Year Relevance (Sınıf Uyumu): Öğrencinin sınıfına uygun dersler (N ve N+1).
    """
    # Metinleri hazırla
    text = (str(row['Course Name']) + " " + str(row['Description'])).lower()
    prereq_text = str(row['Prerequisites']).lower()
    course_code_str = str(row['Course Code']).strip().upper()
    score = 0
    reasons = []

    # ---------------------------------------------------------
    # 1. ZİNCİRLEME BONUSU (PROGRESSION BOOST)
    # ---------------------------------------------------------
    has_prerequisite = False
    if pd.notna(row['Prerequisites']) and row['Prerequisites'] != "nan":
        # Harf + Sayı formatında ders kodu var mı?
        if re.search(r"[a-z]{2,5}\s*\d{3,4}", prereq_text):
            has_prerequisite = True

    if has_prerequisite:
        score += 50
        reasons.append("Zincir Ders")

    # ---------------------------------------------------------
    # 2. İLGİ ALANI (KEYWORD MATCHING)
    # ---------------------------------------------------------
    keyword_hits = 0
    matched_terms = []
    for w in interest_keywords:
        if w.lower() in text:
            keyword_hits += 1
            matched_terms.append(w)
    
    if keyword_hits > 0:
        score += (keyword_hits * 20)
        reasons.append(f"İlgi: {', '.join(matched_terms[:2])}")

    # ---------------------------------------------------------
    # 3. SINIF UYUMU (YEAR RELEVANCE) - YENİ ÖZELLİK
    # ---------------------------------------------------------
    
    try:
        match = re.search(r"(\d+)", str(row['Course Code']))
        if match:
            course_num = int(match.group(1))
            course_level = course_num // 100 # 201 -> 2, 412 -> 4
            
            # Hedef seviyeleri belirle
            # 4. sınıflar için 4 ve üstü (Master dersleri dahil olabilir)
            if student_year >= 4:
                target_levels = [4, 5, 6]
            else:
                target_levels = [student_year, student_year + 1]
            
            if course_level in target_levels:
                score += 20
                # reasons.append(f"{course_level}. Seviye Uyumu") # Ekranda kalabalık etmesin diye kapalı
            
            if student_year == 1 and course_level >= 4: score -= 40
            if student_year == 3 and course_level == 2: score -= 10
            if student_year == 3 and course_level == 1: score -= 20
            if student_year == 4 and course_level == 1: score -= 40
            if student_year == 4 and course_level == 2: score -= 20
            

    except: 
        pass

    if allowed_codes:
    # Ders kodunun başındaki harfleri al (CS 201 -> CS)
        subject_match = re.match(r"([A-Z]+)", course_code_str)
        
        if subject_match:
            subject = subject_match.group(1)
            
            # Eğer dersin konusu izin verilen listede YOKSA -> CEZA KES
            if subject not in allowed_codes:
                score -= 50

    score = min(100, score)
    
    why_string = " + ".join(reasons) if reasons else "Genel"
    
    return score, why_string


# ---------------------------------------------------------
# 4. MAIN PROCESSING BLOCK
# ---------------------------------------------------------
def run_analysis():
    print(f"📂 Veri Kaynağı: {INPUT_FILE}")
    print("🔄 Data Cleaning and Filtering Starting...")

    try:
        df = pd.read_csv(INPUT_FILE)
        taken_courses = load_transcript(TRANSCRIPT_FILE)
        print(f"✅ Transkript okundu ({len(taken_courses)} ders).")
    except FileNotFoundError as e:
        print(f"❌ ERROR: Dosya bulunamadı!\n{e}")
        return

    # 1. Clean Text Columns
    cols_to_clean = ['Description', 'Restrictions', 'Prerequisites', 'Corequisites']
    for col in cols_to_clean:
        if col in df.columns:
            df[col] = df[col].apply(sanitize_text)

    # 2. Remove Taken Courses
    df = df[~df['Course Code'].isin(taken_courses)].copy()

    # 3. Logic Check
    df[['Status', 'Missing_Reqs']] = df.apply(lambda r: pd.Series(check_smart_logic(r, taken_courses)), axis=1)

    # 4. Scoring
    df['Score'] = df.apply(calculate_score, axis=1)

    # 5. Filtering
    df['Level'] = df['Course Code'].apply(lambda x: int(re.search(r"(\d+)", str(x)).group(1)) if re.search(r"(\d+)", str(x)) else 0)
    target_deps = ['ECON', 'MGMT', 'FIN', 'BAN', 'OPIM', 'IE', 'CS', 'ENS', 'DA']
    mask = df['Course Code'].str.contains('|'.join(target_deps), na=False)

    final_df = df[mask & (df['Level'] < 500) & (df['Score'] > 0)].copy()
    final_df = final_df.sort_values(by=['Status', 'Score'], ascending=[False, False])

    # 6. Save Final Output
    save_cols = ['Course Code', 'Course Name', 'Status', 'Score', 'Missing_Reqs', 'Description']
    
    # Klasörün var olup olmadığını kontrol et, yoksa oluştur
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    final_df[save_cols].to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig', quoting=csv.QUOTE_ALL)

    print("\n" + "="*60)
    print("✅ PROCESS COMPLETED!")
    print(f"📝 Dosya kaydedildi: {OUTPUT_FILE}")
    print("-" * 60)

if __name__ == "__main__":
    run_analysis()