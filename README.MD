# 🎓 Sabancı University Smart Advisor & Degree Auditor

**Sabancı Üniversitesi** öğrencileri için geliştirilmiş; Yapay Zeka destekli ders önerme, akademik yol haritası çizme ve mezuniyet denetim (audit) sistemidir.

Bu proje, öğrencilerin transkriptlerini analiz eder, ilgi alanlarına (NLP) göre ders önerir ve bölüm yükümlülüklerini (DSA, CS vb.) otomatik kontrol eder.

---

## 🚀 Öne Çıkan Özellikler

### 1. 🧠 Yapay Zeka Destekli Ders Önerisi (AI Powered)
* **Sentence-BERT (HuggingFace):** Kullanıcının ilgi alanlarını ("I want to learn about finance and money") anlar ve ders açıklamalarıyla anlamsal eşleştirme yapar.
* **Hibrit Puanlama:** AI skorunu; dersin ön koşulları (Zincirleme Bonusu) ve öğrencinin sınıf seviyesiyle birleştirir.

### 2. 🕵️‍♂️ Mezuniyet Denetçisi (Degree Audit) - *YENİ*
* **Otomatik Müfredat Analizi:** Bölüm web sayfalarındaki (HTML) tabloları okuyarak zorunlu dersleri, kredi yükümlülüklerini (SU & ECTS) ve seçmeli havuzlarını otomatik çıkarır.
* **İlerleme Takibi:** Transkriptinizdeki dersleri müfredatla kıyaslayıp "Ne kadar yolum kaldı?" sorusunu cevaplar.

### 3. 📅 Dinamik Ders Programı (Live Schedule)
* BannerWeb üzerinden güncel ders programını çeker.
* Dersin hangi dönem, hangi saatte ve hangi hoca tarafından verildiğini analiz eder.

---

## 📂 Proje Mimarisi

```text
university_advisor/
│
├── app.py                      # 🖥️ Ana Arayüz (Streamlit Dashboard)
├── main.py                     # ⚙️ Terminal Test Modülü
│
├── data/                       # 💾 VERİ DEPOSU
│   ├── csv/                    # İşlenmiş veriler (Schedule, Catalog)
│   │   ├── active_schedule_master.csv
│   │   ├── course_data_clean.csv
│   │   ├── course_full_data_v2.csv
│   │   └── course_links_master.csv
|   |   
│   ├── json/                   # Müfredat ve Bölüm Yapıları
│   │   ├── undergrad_majors.json
│   │   ├── undergrad_minors.json
│   │   └── dsa_requirements_full.json
│   │
│   └── raw_html/               # Ham HTML Kaynakları
│       ├── dsa_html/           # DSA Bölümü Kaynak Dosyaları
│       │   ├── dsa_degree_detail.html
│       │   ├── dsa_core.html
│       │   └── ...
│       ├── 2025.2026_spring_schedule.html
│       └── 2025-2026_fall_schedule.html
│
└── src/                        # 🧠 UYGULAMA MOTORU
    ├── advisor.py              # Bölüm/Yandal Arama Motoru
    ├── ml_engine.py            # AI (Sentence-BERT) Katmanı
    ├── parse_degree.py         # Müfredat Ayrıştırıcı (HTML -> JSON)
    ├── parse_schedule.py       # Ders Programı Ayrıştırıcı
    ├── personal_recommendation.py # Puanlama ve Mantık Kontrolü
    └── clean_data.py           # Veri Temizleme Araçları