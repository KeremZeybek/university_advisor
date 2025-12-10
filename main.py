import json
import os
from src.advisor import UniversityAdvisor 

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MAJOR_PATH = os.path.join(BASE_DIR, 'data', 'json', 'undergrad_majors.json')
MINOR_PATH = os.path.join(BASE_DIR, 'data', 'json', 'undergrad_minors.json')

def load_data():
    try:
        with open(MAJOR_PATH, 'r', encoding='utf-8') as f:
            major_data = json.load(f)
        with open(MINOR_PATH, 'r', encoding='utf-8') as f:
            minor_data = json.load(f)
        return major_data, minor_data
    except FileNotFoundError as e:
        print(f"Hata: Dosya bulunamadı! Yolları kontrol et.\n{e}")
        exit()


def main():
    print("--- Sabancı Üniversitesi Program Danışmanı Başlatılıyor ---")
    
    majors, minors = load_data()
    
    advisor = UniversityAdvisor(majors, minors)
    print("✅ Veriler yüklendi ve sistem hazır.\n")

    # --- TEST SENARYOLARI ---
    
    # Senaryo 1: Arama Testi
    query = "artificial intelligence"
    print(f"🔍 '{query}' için arama yapılıyor...")
    results = advisor.find_program_by_keyword(query)
    
    for res in results[:3]: # İlk 3 sonuç
        print(f"   • {res['program']} ({res['type']}) - Skor: {res['score']}")

    print("\n" + "-"*30 + "\n")

    # Senaryo 2: Uyum (Synergy) Testi
    # Örnek: Data Science okuyan biri için öneriler
    my_major_id = "data-science-analytics" 
    print(f"🤝 '{my_major_id}' için Minor önerileri hesaplanıyor...")
    
    recommendations = advisor.calculate_synergy(my_major_id)
    
    for rec in recommendations[:3]:
        print(f"   • {rec['minor_name']} (Skor: {rec['score']})")
        print(f"     Ortak Konular: {', '.join(rec['shared_topics'])}")


if __name__ == "__main__":
    main()