from bs4 import BeautifulSoup
import pandas as pd
import os

# ---------------------------------------------------------
# 1. FILE PATHS & CONFIGURATION 
# ---------------------------------------------------------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)

HTML_DIR = os.path.join(BASE_DIR, 'data', 'raw_html')

OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'csv')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "course_links_master.csv")

BASE_URL = "https://suis.sabanciuniv.edu"

FILE_FALL = os.path.join(HTML_DIR, "fall.html")
FILE_SPRING = os.path.join(HTML_DIR, "spring.html")

def parse_course_links():
    print("🚀 Link Extraction Process Started...")

    # Mapping terms to FULL file paths
    files_map = {
        'Fall': FILE_FALL,
        'Spring': FILE_SPRING
    }

    course_data = []

    # ---------------------------------------------------------
    # 2. MAIN PARSING LOOP
    # ---------------------------------------------------------
    for term, file_path in files_map.items():
        # Dosya var mı kontrol et
        if not os.path.exists(file_path):
            print(f"⚠️ UYARI: '{term}' dönemi için dosya bulunamadı: {file_path}")
            print("   -> Lütfen HTML dosyasını 'data/raw_html' klasörüne ekleyin.")
            continue
            
        print(f"📄 Processing {term} term data from source...")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f, 'html.parser')
                
            # STRATEGY: Locate all 'td' elements with class 'nttitle'
            course_cells = soup.find_all("td", class_="nttitle")
            
            for cell in course_cells:
                link_tag = cell.find("a")
                
                if link_tag:
                    full_text = link_tag.get_text().strip()
                    href = link_tag.get('href')
                    
                    # Construct the absolute URL
                    if href and href.startswith("/"):
                        full_link = BASE_URL + href
                    else:
                        full_link = href
                    
                    # Parse Course Code and Course Name
                    if " - " in full_text:
                        parts = full_text.split(" - ", 1)
                        course_code = parts[0].strip()
                        course_name = parts[1].strip()
                    else:
                        course_code = full_text
                        course_name = full_text 

                    course_data.append({
                        "Course Code": course_code,
                        "Course Name": course_name,
                        "URL": full_link,
                        "Term": term
                    })
        except Exception as e:
            print(f"❌ HATA: {file_path} okunurken bir sorun oluştu: {e}")

    # ---------------------------------------------------------
    # 3. DATAFRAME CREATION & AGGREGATION
    # ---------------------------------------------------------
    if not course_data:
        print("❌ HATA: Hiçbir ders bulunamadı. HTML dosyalarının içeriğini kontrol edin.")
        return

    df = pd.DataFrame(course_data)

    # AGGREGATION LOGIC: Merge Fall/Spring duplicates
    master_df = df.groupby(['Course Code', 'Course Name']).agg({
        'URL': 'first', 
        'Term': lambda x: ", ".join(sorted(set(x)))
    }).reset_index()

    print(f"\n✅ SUCCESS! Extracted {len(master_df)} unique courses.")
    
    # ---------------------------------------------------------
    # 4. SAVE TO CSV
    # ---------------------------------------------------------
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    master_df.to_csv(OUTPUT_FILE, index=False)
    print(f"💾 Data saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    parse_course_links()