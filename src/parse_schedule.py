from bs4 import BeautifulSoup
import pandas as pd
import os
import re

# ---------------------------------------------------------
# AYARLAR VE DOSYA İSİMLERİ
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_DIR = os.path.join(BASE_DIR, 'data', 'raw_html')
OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'csv')

# İşlenecek dosyalar haritası
# (Dosya Adı, Dönem Etiketi)
FILES_TO_PROCESS = [
    ("2025-2026_fall_schedule.html", "Fall"),
    ("2025-2026_spring_schedule.html", "Spring")
]

OUTPUT_FILENAME = "active_schedule_master.csv"
OUTPUT_PATH = os.path.join(OUTPUT_DIR, OUTPUT_FILENAME)

def parse_html_file(file_path, term_label):
    """
    Tek bir HTML dosyasını okur ve ders listesini döndürür.
    """
    if not os.path.exists(file_path):
        print(f"⚠️ UYARI: Dosya bulunamadı, atlanıyor -> {file_path}")
        return []

    print(f"📂 İşleniyor ({term_label}): {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, 'html.parser')

    schedule_data = []
    
    # BannerWeb yapısında başlıklar: <th class="ddlabel">
    headers = soup.find_all("th", class_="ddlabel")
    
    for th in headers:
        try:
            # 1. Başlıktan Ders Bilgisi Çek (AL 102 - A1 vb.)
            link = th.find("a")
            if not link: continue
            
            full_title = link.get_text().strip()
            # Beklenen format: "Course Name - CRN - Code - Section"
            # Örn: "Academic Literacies - 10263 - AL 102 - A1"
            parts = full_title.split(" - ")
            
            if len(parts) >= 4:
                # Sondan başa doğru almak daha güvenlidir (İsimde tire varsa bozulmasın diye)
                section = parts[-1].strip()
                course_code = parts[-2].strip() # AL 102
                crn = parts[-3].strip()
                # Geri kalan her şey isimdir
                course_name = " - ".join(parts[:-3]).strip()
            else:
                continue

            # 2. Detay Tablosunu Bul
            parent_tr = th.find_parent("tr")
            if not parent_tr: continue
            
            details_tr = parent_tr.find_next_sibling("tr")
            if not details_tr: continue
            
            schedule_table = details_tr.find("table", summary="This table lists the scheduled meeting times and assigned instructors for this class..")
            
            if schedule_table:
                # İlk satır başlıktır, atla
                rows = schedule_table.find_all("tr")[1:]
                
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) < 7: continue
                    
                    # Verileri çek
                    class_time = cols[1].get_text().strip()
                    days = cols[2].get_text().strip()
                    location = cols[3].get_text().strip()
                    instructor_raw = cols[6].get_text().strip()
                    
                    # Hoca ismini temizle: "Ali Nihat Eken (<ABBR...>P</ABBR>)..." -> "Ali Nihat Eken"
                    instructor = re.sub(r'\s*\(.*?\)', '', instructor_raw) # Parantez içini sil
                    instructor = instructor.split('(')[0].strip() # Kalan parantez varsa sil

                    schedule_data.append({
                        "Term": term_label,  # Fall veya Spring
                        "Course Code": course_code,
                        "Section": section,
                        "CRN": crn,
                        "Course Name": course_name,
                        "Time": class_time,
                        "Days": days,
                        "Location": location,
                        "Instructor": instructor
                    })
            else:
                # Ders var ama saat bilgisi yok (TBA)
                schedule_data.append({
                    "Term": term_label,
                    "Course Code": course_code,
                    "Section": section,
                    "CRN": crn,
                    "Course Name": course_name,
                    "Time": "TBA",
                    "Days": "TBA",
                    "Location": "TBA",
                    "Instructor": "TBA"
                })

        except Exception as e:
            # Tekil bir satır hatası tüm işlemi durdurmasın
            continue

    return schedule_data

def main():
    print("🚀 Schedule Parsing Başlıyor (Master)...")
    
    all_data = []
    
    # Listemideki her dosyayı sırayla işle
    for filename, term in FILES_TO_PROCESS:
        file_path = os.path.join(HTML_DIR, filename)
        term_data = parse_html_file(file_path, term)
        
        if term_data:
            print(f"   ✅ {term}: {len(term_data)} section bulundu.")
            all_data.extend(term_data)
        else:
            print(f"   ❌ {term}: Veri bulunamadı veya dosya yok.")

    # Sonuçları Kaydet
    if all_data:
        df = pd.DataFrame(all_data)
        
        # Kodları standartlaştır
        df['Course Code'] = df['Course Code'].str.strip().str.upper()
        
        # Klasör yoksa oluştur
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        df.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')
        
        print("\n" + "="*40)
        print(f"🎉 İŞLEM TAMAMLANDI!")
        print(f"📊 Toplam Kayıt: {len(df)}")
        print(f"💾 Dosya: {OUTPUT_PATH}")
        print("="*40)
        print(df.head())
    else:
        print("\n❌ Hiçbir dosyadan veri çekilemedi.")

if __name__ == "__main__":
    main()