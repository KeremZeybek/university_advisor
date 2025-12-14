import os
from bs4 import BeautifulSoup
import json
import re

# ---------------------------------------------------------
# AYARLAR
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_DIR = os.path.join(BASE_DIR, 'data', 'raw_html', 'dsa_html')
OUTPUT_JSON = os.path.join(BASE_DIR, 'data', 'json', 'dsa_requirements_full.json')

def parse_course_table(soup_or_html):
    """
    Ders tablolarını tarar: Code, Name, SU Credit bilgilerini çeker.
    """
    soup = None
    if isinstance(soup_or_html, str):
        if os.path.exists(soup_or_html):
            print(f"📂 Okunuyor: {os.path.basename(soup_or_html)}...")
            with open(soup_or_html, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
        else:
            return []
    else:
        soup = soup_or_html

    courses = []
    seen_codes = set() 
    rows = soup.find_all('tr')
    
    for row in rows:
        cols = row.find_all('td')
        # Tablo Yapısı: [Spacer, Code, Name, ECTS, SU, Faculty]
        if len(cols) >= 5: 
            code_link = cols[1].find('a')
            if code_link:
                code_text = code_link.text.strip()
                if re.match(r"^[A-Z]{2,5}\s\d{3,4}[A-Z]?$", code_text):
                    if code_text in seen_codes: continue
                    try:
                        # Kredileri çek
                        su_val = int(cols[4].text.strip())
                        
                        course_obj = {
                            "code": code_text,
                            "name": cols[2].text.strip(),
                            "su_credit": su_val
                        }
                        courses.append(course_obj)
                        seen_codes.add(code_text)
                    except (ValueError, IndexError):
                        continue
    return courses

def parse_degree_full():
    print("🔄 DSA Temel Müfredat Analizi (125 Kredi)...")
    
    main_file = os.path.join(HTML_DIR, 'dsa_degree_detail.html')
    if not os.path.exists(main_file):
        print(f"❌ Dosya yok: {main_file}")
        return

    with open(main_file, 'r', encoding='utf-8') as f:
        main_soup = BeautifulSoup(f.read(), 'html.parser')

    term_header = main_soup.find('h3', string=re.compile("Admit Term"))
    admit_term = term_header.text.strip() if term_header else "Unknown"

    # Bölümleri Çek
    def get_section_courses(anchor_name):
        anchor = main_soup.find('a', {'name': anchor_name})
        found = []
        if anchor:
            tbl = anchor.find_parent('table')
            for _ in range(4):
                if tbl:
                    tbl = tbl.find_next('table')
                    if tbl: found.extend(parse_course_table(tbl))
        return found

    uni_courses = get_section_courses('UC_DSA')
    req_courses = get_section_courses('BSDSA_REQ')
    
    # Seçmeli Havuzları
    core_courses = parse_course_table(os.path.join(HTML_DIR, 'dsa_core.html'))
    area_courses = parse_course_table(os.path.join(HTML_DIR, 'dsa_area.html'))
    free_courses = parse_course_table(os.path.join(HTML_DIR, 'dsa_free.html'))

    # JSON Yapısı (Kuralları netleştirdik)
    full_json = {
        "program_code": "DSA",
        "program_name": "Data Science and Analytics",
        "version": admit_term,
        "total_su_credits_required": 125,  # NET HEDEF
        "requirements": {
            "university_courses": {
                "name": "University Courses",
                "type": "MANDATORY",
                "credits_su": 41,
                "course_objects": uni_courses,
                "rule": "1XX courses + SPS 303 + HUM 2XX required."
            },
            "major_required": {
                "name": "Required Courses",
                "type": "MANDATORY",
                "credits_su": 30,
                "course_objects": req_courses,
                "rule": "DSA 210/CS 210 equivalent. MATH 201/212 equivalent."
            },
            "core_electives": {
                "name": "Core Electives",
                "type": "ELECTIVE_POOL",
                "credits_su": 27,
                "pool_objects": core_courses
            },
            "area_electives": {
                "name": "Area Electives",
                "type": "ELECTIVE_POOL",
                "credits_su": 12,
                "pool_objects": area_courses
            },
            "free_electives": {
                "name": "Free Electives",
                "type": "FREE_POOL",
                "credits_su": 15,
                "pool_objects": free_courses
            }
        }
    }

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(full_json, f, indent=4, ensure_ascii=False)
    print(f"🚀 JSON Güncellendi: {OUTPUT_JSON}")

if __name__ == "__main__":
    parse_degree_full()