import os
from bs4 import BeautifulSoup
import json
import re

# ---------------------------------------------------------
# AYARLAR VE YOL HARİTASI
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_DIR = os.path.join(BASE_DIR, 'data', 'raw_html', 'dsa_html')
OUTPUT_JSON = os.path.join(BASE_DIR, 'data', 'json', 'dsa_requirements_full.json')

def parse_course_table(soup_or_html):
    """
    Verilen HTML içeriğindeki (soup veya file path) ders tablolarını tarar.
    Hem SU hem de ECTS kredilerini çeker.
    
    Dönüş Formatı: 
    [
      {'code': 'CS 210', 'name': 'Intro to Data Science', 'su': 3, 'ects': 6}, 
      ...
    ]
    """
    soup = None
    
    # Gelen veri dosya yolu mu yoksa Soup objesi mi?
    if isinstance(soup_or_html, str):
        if os.path.exists(soup_or_html):
            print(f"📂 Okunuyor: {os.path.basename(soup_or_html)}...")
            with open(soup_or_html, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
        else:
            print(f"⚠️ Dosya bulunamadı: {soup_or_html}")
            return []
    else:
        soup = soup_or_html

    courses = []
    seen_codes = set() # Tekrarı önlemek için

    # Tüm satırları (tr) bul
    rows = soup.find_all('tr')
    
    for row in rows:
        cols = row.find_all('td')
        
        # BannerWeb Tablo Yapısı (Görsele Göre):
        # [0]: Spacer (Boş)
        # [1]: Course Code (Linkli) -> CS 210
        # [2]: Name -> Introduction to Data Science
        # [3]: ECTS Credits -> 6
        # [4]: SU Credits -> 3
        # [5]: Faculty -> FENS
        
        if len(cols) >= 5:
            # Kolon 1'de Link var mı? (Ders Kodu Orada)
            code_link = cols[1].find('a')
            if code_link:
                code_text = code_link.text.strip()
                
                # Regex ile kod formatı kontrolü (CS 210, AL 102 vb.)
                if re.match(r"^[A-Z]{2,5}\s\d{3,4}[A-Z]?$", code_text):
                    
                    # Eğer aynı ders tabloda iki kere varsa (Lecture/Lab vb.) atla
                    if code_text in seen_codes:
                        continue
                        
                    try:
                        course_name = cols[2].text.strip()
                        ects_val = int(cols[3].text.strip()) # ECTS (Kolon 3)
                        su_val = int(cols[4].text.strip())   # SU (Kolon 4)
                        
                        course_obj = {
                            "code": code_text,
                            "name": course_name,
                            "su_credit": su_val,
                            "ects_credit": ects_val
                        }
                        courses.append(course_obj)
                        seen_codes.add(code_text)
                    except (ValueError, IndexError):
                        # Bazen başlık satırları araya karışabilir, onları atla
                        continue
    
    return courses

def parse_degree_full():
    print("🔄 DSA Detaylı Müfredat Analizi Başlıyor (SU + ECTS)...")
    
    # 1. Ana Dosya Analizi
    main_file = os.path.join(HTML_DIR, 'dsa_degree_detail.html')
    
    if not os.path.exists(main_file):
        print(f"❌ Ana dosya eksik: {main_file}")
        print(f"   Lütfen dosyayı şuraya koyun: {HTML_DIR}")
        return

    with open(main_file, 'r', encoding='utf-8') as f:
        main_soup = BeautifulSoup(f.read(), 'html.parser')

    # Dönem Bilgisi
    term_header = main_soup.find('h3', string=re.compile("Admit Term"))
    admit_term = term_header.text.strip() if term_header else "Unknown Term"
    print(f"📅 Müfredat Dönemi: {admit_term}")

    # Özet Tablosundan Gereksinimleri Çek (Toplam kaç kredi lazım?)
    summary_table = main_soup.find('table', {'class': 't_mezuniyet'})
    req_summary = {}
    if summary_table:
        rows = summary_table.find_all('tr')
        for r in rows:
            cols = r.find_all('td')
            if len(cols) >= 3:
                cat_name = cols[0].text.strip() # Örn: Area Electives
                try:
                    su_credit = int(cols[2].text.strip())
                    req_summary[cat_name] = su_credit
                except:
                    pass

    # Ana Dosyadaki Bölümleri (University & Required) Ayrıştır
    def get_section_courses(anchor_name):
        anchor = main_soup.find('a', {'name': anchor_name})
        if anchor:
            current_table = anchor.find_parent('table')
            found_courses = []
            # Altındaki 4 tabloyu tara (Bazen tablolar bölünmüş olabilir)
            for _ in range(4): 
                if current_table:
                    current_table = current_table.find_next('table')
                    if current_table:
                        # Tabloyu ayrıştırıp listeye ekle
                        extracted = parse_course_table(current_table)
                        if extracted:
                            found_courses.extend(extracted)
        return found_courses

    # Zorunlu Dersleri Çek (Artık Kredili Nesne Olarak Geliyor)
    uni_courses = get_section_courses('UC_DSA')
    req_courses = get_section_courses('BSDSA_REQ')

    # 2. Seçmeli Ders Dosyalarını Oku (Electives)
    # Core ve Area sayfalarını HTML olarak indirip dsa_html içine attığını varsayıyoruz
    core_courses = parse_course_table(os.path.join(HTML_DIR, 'dsa_core.html'))
    area_courses = parse_course_table(os.path.join(HTML_DIR, 'dsa_area.html'))
    free_courses = parse_course_table(os.path.join(HTML_DIR, 'dsa_free.html'))

    print("-" * 50)
    print(f"✅ University Courses : {len(uni_courses)} ders")
    print(f"✅ Major Required     : {len(req_courses)} ders")
    print(f"✅ Core Electives     : {len(core_courses)} ders (Havuz)")
    print(f"✅ Area Electives     : {len(area_courses)} ders (Havuz)")
    print("-" * 50)

    # 3. Final JSON Yapısı
    full_json = {
        "program_code": "DSA",
        "program_name": "Data Science and Analytics",
        "version": admit_term,
        "requirements": {
            "university_courses": {
                "name": "University Courses",
                "type": "MANDATORY",
                "credits_su": req_summary.get('University Courses', 41),
                "course_objects": uni_courses 
            },
            "major_required": {
                "name": "Required Courses",
                "type": "MANDATORY",
                "credits_su": req_summary.get('Required Courses', 30),
                "course_objects": req_courses
            },
            "core_electives": {
                "name": "Core Electives",
                "type": "ELECTIVE_POOL",
                "credits_su": req_summary.get('Core Electives', 27),
                "pool_objects": core_courses
            },
            "area_electives": {
                "name": "Area Electives",
                "type": "ELECTIVE_POOL",
                "credits_su": req_summary.get('Area Electives', 12),
                "pool_objects": area_courses
            },
            "free_electives": {
                "name": "Free Electives",
                "type": "FREE_POOL",
                "credits_su": req_summary.get('Free Electives', 15),
                "pool_objects": free_courses, 
                "note": "Courses not in University Courses or Language Courses."
            }
        }
    }

    # Kaydet
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(full_json, f, indent=4, ensure_ascii=False)

    print(f"🚀 Başarılı! ECTS verileriyle birlikte JSON oluşturuldu:\n{OUTPUT_JSON}")

if __name__ == "__main__":
    parse_degree_full()