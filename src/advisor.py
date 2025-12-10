"""
=============================================================================
PROJE: SABANCI UNIVERSITY SMART ADVISOR
DOSYA: src/advisor.py
TANIM: Bölüm/Yandal arama motoru ve uyumluluk (Synergy) hesaplama mantığı.

YOL HARİTASI (ROADMAP):
1. INIT ................... Verilerin yüklenmesi ve düzleştirilmesi (Flatten)
2. SEARCH ENGINE .......... Keyword tabanlı program arama
3. SYNERGY ENGINE ......... Major ve Minor arasındaki akademik uyum hesabı
4. MAIN EXECUTION ......... Standalone test bloğu
=============================================================================
"""

import json
import os

class UniversityAdvisor:
    def __init__(self, major_data, minor_data):
        """
        Sınıf başlatılırken hiyerarşik JSON verisini alır ve analiz için düzleştirir.
        
        Args:
            major_data (dict): Major programlarını içeren ham JSON verisi.
            minor_data (dict): Minor programlarını içeren ham JSON verisi.
        """
        self.majors = self._flatten_programs(major_data)
        self.minors = self._flatten_programs(minor_data)

    def _flatten_programs(self, data):
        """
        Hiyerarşik (Fakülte -> Program) JSON yapısını analiz için düz (flat) listeye çevirir.
        Her programa 'faculty_code' bilgisini ekler.
        """
        flat_list = []
        # Veri yapısının doğruluğunu kontrol et
        if not data or 'faculties' not in data:
            return flat_list

        for faculty in data['faculties']:
            for program in faculty['programs']:
                # Analiz kolaylığı için her programa fakülte bilgisini inject ediyoruz
                program['faculty_code'] = faculty.get('short_code', 'UNKNOWN')
                flat_list.append(program)
        return flat_list

    def find_program_by_keyword(self, query, search_type="all"):
        """
        Kullanıcının girdiği kelimeye göre (örn: 'AI', 'Money') program önerir.
        
        Puanlama Mantığı:
        - İsim Eşleşmesi: 5 Puan (Örn: "Finance" aranınca Finance bölümü)
        - Keyword Eşleşmesi: 2 Puan (Örn: "Money" aranınca Finance bölümü)
        """
        if not query:
            return []

        query_tokens = set(query.lower().split())
        results = []

        # Hangi havuzda arama yapılacak?
        target_list = []
        if search_type == "major": 
            target_list = self.majors
        elif search_type == "minor": 
            target_list = self.minors
        else: 
            target_list = self.majors + self.minors

        for prog in target_list:
            # Programın keywordlerini ve ismini sete çevir
            prog_keywords = set([k.lower() for k in prog.get('keywords', [])])
            prog_name_tokens = set(prog.get('name', '').lower().split())
            
            # Kesişimleri bul
            keyword_match = len(query_tokens.intersection(prog_keywords))
            name_match = len(query_tokens.intersection(prog_name_tokens))
            
            # Skorlama
            score = (name_match * 5) + (keyword_match * 2) 

            if score > 0:
                results.append({
                    "program": prog['name'],
                    "type": "Major" if prog in self.majors else "Minor",
                    "score": score,
                    "matched_keywords": list(query_tokens.intersection(prog_keywords))
                })

        # Skora göre sırala (En yüksek puan en üstte)
        return sorted(results, key=lambda x: x['score'], reverse=True)

    def calculate_synergy(self, major_id):
        """
        Seçilen bir Major için en uyumlu Minor programlarını hesaplar.
        
        Uyumluluk Kriterleri:
        1. Ortak Ders Kodları (Subject Codes): x3 Puan (Akademik kolaylık)
        2. Ortak Anahtar Kelimeler (Keywords): x1 Puan (Tematik uyum)
        """
        # Seçilen Major'ı ID'ye göre bul
        selected_major = next((m for m in self.majors if m['id'] == major_id), None)
        
        if not selected_major:
            # Hata durumunda boş liste dönmek, uygulamanın çökmesini engeller
            return []

        recommendations = []
        
        # Major'ın özelliklerini çıkar (Set kullanarak hızlı işlem)
        major_codes = set(selected_major.get('subject_codes', []))
        major_keywords = set(selected_major.get('keywords', []))

        for minor in self.minors:
            # Minor'ın özelliklerini çıkar
            minor_codes = set(minor.get('subject_codes', []))
            minor_keywords = set(minor.get('keywords', []))

            # Kesişimleri bul
            code_intersection = major_codes.intersection(minor_codes)
            keyword_intersection = major_keywords.intersection(minor_keywords)

            # Sinerji Puanı Hesapla
            # Ders kodu uyumu (Örn: CS okurken MATH yandalı yapmak) daha değerlidir (x3)
            synergy_score = (len(code_intersection) * 3) + (len(keyword_intersection) * 1)

            if synergy_score > 0:
                recommendations.append({
                    "minor_name": minor['name'],
                    "faculty": minor['faculty_code'],
                    "score": synergy_score,
                    "shared_codes": list(code_intersection),
                    "shared_topics": list(keyword_intersection)
                })

        return sorted(recommendations, key=lambda x: x['score'], reverse=True)

# =============================================================================
# 4. MAIN EXECUTION (STANDALONE TEST MODE)
# =============================================================================
if __name__ == "__main__":
    # Bu blok sadece dosya doğrudan çalıştırılırsa çalışır.
    # Streamlit üzerinden import edilirse çalışmaz.
    
    # Dosya yollarını dinamik bul
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(current_dir)
    major_path = os.path.join(base_dir, 'data', 'json', 'undergrad_majors.json')
    minor_path = os.path.join(base_dir, 'data', 'json', 'undergrad_minors.json')
    
    print("--- University Advisor Test Modu ---")
    
    try:
        with open(major_path, 'r', encoding='utf-8') as f: majors_json = json.load(f)
        with open(minor_path, 'r', encoding='utf-8') as f: minors_json = json.load(f)
        
        advisor = UniversityAdvisor(majors_json, minors_json)
        print("✅ Veriler başarıyla yüklendi.")
        
        # TEST 1: Arama
        test_query = "Artificial Intelligence"
        print(f"\n🔍 Arama Testi: '{test_query}'")
        results = advisor.find_program_by_keyword(test_query)
        for res in results[:3]:
            print(f"   - {res['program']} ({res['type']}) | Skor: {res['score']}")
            
        # TEST 2: Uyumluluk
        test_major_id = "computer-science-engineering"
        print(f"\n🤝 Uyumluluk Testi: '{test_major_id}'")
        synergies = advisor.calculate_synergy(test_major_id)
        for syn in synergies[:3]:
            print(f"   - {syn['minor_name']} | Skor: {syn['score']}")
            print(f"     Ortak Dersler: {syn['shared_codes']}")
            
    except FileNotFoundError:
        print("❌ HATA: JSON dosyaları bulunamadı. Lütfen 'data/json' klasörünü kontrol et.")
    except Exception as e:
        print(f"❌ Beklenmeyen Hata: {e}")