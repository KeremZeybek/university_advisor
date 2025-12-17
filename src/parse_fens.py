import os
import re
import json
from bs4 import BeautifulSoup

# --- AYARLAR ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_HTML_DIR = os.path.join(BASE_DIR, 'data', 'raw_html')
OUTPUT_FILE = os.path.join(BASE_DIR, 'data', 'json', 'fens_data_raw.json')

def clean_text(text):
    if not text: return ""
    return " ".join(text.replace('\xa0', ' ').split()).strip()

def is_course_code(text):
    # Regex: 2-5 harf, boşluk, 3-4 rakam
    return bool(re.match(r"^[A-Z]{2,5}\s+\d{3,4}[A-Z]*$", text))

def parse_course_row(tr):
    cols = tr.find_all('td')
    if not cols: return None
    
    course_code = None
    course_name = ""
    ects = 0.0
    su_credit = 0.0
    
    # 1. Ders Kodunu Bul
    for idx, col in enumerate(cols):
        txt = clean_text(col.get_text())
        if is_course_code(txt):
            course_code = txt
            if idx + 1 < len(cols):
                course_name = clean_text(cols[idx+1].get_text())
            break
            
    if not course_code: return None

    # 2. Kredileri Bul
    nums = []
    for col in cols:
        txt = clean_text(col.get_text())
        if re.match(r"^\d+(\.\d+)?$", txt):
            nums.append(float(txt))
            
    if len(nums) >= 2:
        ects = nums[0]
        su_credit = nums[1]
    elif len(nums) == 1:
        su_credit = nums[0]

    return {
        "code": course_code,
        "name": course_name,
        "ects": ects,
        "su_credit": su_credit
    }

def find_courses_in_html(soup, section_keywords=None, forbidden_codes=None):
    """
    Tabloları tarar. 
    forbidden_codes: Eğer tabloda bu kodlardan biri varsa, o tabloyu atla (Yanlış tabloyu almamak için).
    """
    courses = []
    
    # Sayfadaki tüm tabloları al
    all_tables = soup.find_all('table')
    
    target_table = None
    
    # Eğer keyword varsa, o keyword'e en yakın tabloyu bulmaya çalış
    if section_keywords:
        # Önce keywordleri içeren elementi bul
        header_node = None
        for kw in section_keywords:
            header_node = soup.find(string=re.compile(kw, re.IGNORECASE))
            if header_node: break
        
        if header_node:
            # O başlıktan sonra gelen tabloları incele
            current = header_node.find_parent()
            if current:
                next_tables = current.find_all_next('table')
                for tbl in next_tables:
                    # Tabloyu geçici parse et
                    temp_courses = []
                    rows = tbl.find_all('tr')
                    for tr in rows:
                        c = parse_course_row(tr)
                        if c: temp_courses.append(c['code'])
                    
                    # KONTROL: Bu tablo yasaklı kod içeriyor mu?
                    # (Örn: Required ararken AL 102 bulursan, bu Üniversite tablosudur, ATLA)
                    if forbidden_codes and any(fc in temp_courses for fc in forbidden_codes):
                        continue # Pas geç, sonraki tabloya bak
                    
                    if temp_courses: # Eğer geçerli ve yasaksız ders varsa
                        target_table = tbl
                        break # Bulduk!
    
    # Eğer spesifik hedef tablo yoksa veya bulunamadıysa (Pool dosyaları için)
    tables_to_scan = [target_table] if target_table else all_tables
    
    for tbl in tables_to_scan:
        rows = tbl.find_all('tr')
        for tr in rows:
            course = parse_course_row(tr)
            if course:
                if not any(c['code'] == course['code'] for c in courses):
                    courses.append(course)
                    
    return courses

def main():
    print(f"🏭 FENS Veri Fabrikası (v4 - Anti-Overlap) Çalışıyor...\n")
    
    if not os.path.exists(RAW_HTML_DIR):
        print("❌ HATA: raw_html klasörü bulunamadı.")
        return

    all_majors = {}
    subdirs = [d for d in os.listdir(RAW_HTML_DIR) if os.path.isdir(os.path.join(RAW_HTML_DIR, d)) and d.endswith('_html')]
    
    for subdir in subdirs:
        major_code = subdir.replace('_html', '').upper()
        folder_path = os.path.join(RAW_HTML_DIR, subdir)
        print(f"   ⚙️  İşleniyor: {major_code}...")
        
        prefix = subdir.replace('_html', '')
        files = {
            "main": os.path.join(folder_path, f"{prefix}_degree_detail.html"),
            "core": os.path.join(folder_path, f"{prefix}_core.html"),
            "area": os.path.join(folder_path, f"{prefix}_area.html"),
            "free": os.path.join(folder_path, f"{prefix}_free.html")
        }
        
        major_data = {
            "code": major_code,
            "requirements": {
                "university_courses": [],
                "required_courses": [],
                "core_electives": [],
                "area_electives": [],
                "free_electives": []
            }
        }
        
        if os.path.exists(files["main"]):
            with open(files["main"], "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
                
            # 1. Önce Üniversite Derslerini Çek
            uni_keys = ["University Courses", "Üniversite Dersleri"]
            major_data["requirements"]["university_courses"] = find_courses_in_html(soup, uni_keys)
            
            # Üniversite ders kodlarını bir listeye al (Yasaklı Liste)
            # Örn: AL 102, CIP 101N, HIST 191...
            uni_codes = [c['code'] for c in major_data["requirements"]["university_courses"]]
            
            # 2. Şimdi Zorunlu Dersleri Çek (Ama Yasaklıları Hariç Tut!)
            req_keys = ["Required Courses", "Major Required", "Zorunlu Dersler", "Program Requirements"]
            
            # Eğer "Required" diye ararken bulduğu tabloda "AL 102" varsa, o tabloyu alma!
            major_data["requirements"]["required_courses"] = find_courses_in_html(
                soup, 
                req_keys, 
                forbidden_codes=["AL 102", "CIP 101N"] # Bu dersler varsa o tablo University tablosudur.
            )
            
        else:
            print(f"      ⚠️ Ana dosya yok: {files['main']}")

        if os.path.exists(files["core"]):
            with open(files["core"], "r", encoding="utf-8") as f:
                major_data["requirements"]["core_electives"] = find_courses_in_html(BeautifulSoup(f.read(), "html.parser"))
        
        if os.path.exists(files["area"]):
            with open(files["area"], "r", encoding="utf-8") as f:
                major_data["requirements"]["area_electives"] = find_courses_in_html(BeautifulSoup(f.read(), "html.parser"))
                
        if os.path.exists(files["free"]):
            with open(files["free"], "r", encoding="utf-8") as f:
                major_data["requirements"]["free_electives"] = find_courses_in_html(BeautifulSoup(f.read(), "html.parser"))

        # Özet
        c_req = len(major_data['requirements']['required_courses'])
        c_uni = len(major_data['requirements']['university_courses'])
        
        print(f"      📊 Uni: {c_uni} | Req: {c_req}")
        all_majors[major_code] = major_data

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_majors, f, ensure_ascii=False, indent=4)
        
    print(f"\n🎉 JSON DÜZELTİLDİ: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()