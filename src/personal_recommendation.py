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


def calculate_score(row, interest_keywords):
    """
    Dersin içeriğini (Description + Name), kullanıcının ilgi alanlarına (interest_keywords)
    göre puanlar.
    """
    text = (str(row['Course Name']) + " " + str(row['Description'])).lower()
    
    score = 0
    matched_terms = []
    
    # 1. Keyword Eşleşmesi (Ana Puanlama)
    for w in interest_keywords:
        if w.lower() in text:
            score += 10 
            matched_terms.append(w)
            
    try:
        match = re.search(r"(\d+)", str(row['Course Code']))
        if match:
            level = int(match.group(1))
            if 400 <= level < 500: 
                score += 5
    except: 
        pass
        
    return score, ", ".join(list(set(matched_terms)))

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