# 🎓 Sabancı University Smart Advisor

Bu proje, Sabancı Üniversitesi öğrencileri için yapay zeka destekli bir **Akademik Danışman ve Ders Öneri Sistemi**dir.

Öğrencilerin transkriptlerini, ilgi alanlarını ve akademik durumlarını analiz ederek onlara en uygun **Dersleri**, **Yandal (Minor)** programlarını ve **Akademik Yolları** önerir.

---

## 📂 Proje Mimarisi

```text
university_advisor/
│
├── data/                       # TÜM VERİLERİN DEPOSU
│   ├── csv/                    # İşlenmiş ve temizlenmiş veriler
│   │   ├── course_full_data_v2.csv    # (Ham) Ders kataloğu
│   │   ├── active_schedule_master.csv # (İşlenmiş) Dönemlik ders programı
│   │   └── course_links_master.csv    # (Eski) Link veritabanı
│   │
│   ├── json/                   # Program yapıları (Major/Minor)
│   │   ├── undergrad_majors.json
│   │   └── undergrad_minors.json
│   │
│   ├── raw_html/               # BannerWeb'den indirilen ham sayfalar
│   │   ├── 2025-2026_fall_schedule.html
│   │   └── 2025-2026_spring_schedule.html
│   │
│   └── user/                   # (Git'e atılmaz) Kişisel kullanıcı verileri
│       └── transcript.txt
│
├── src/                        # UYGULAMA MANTIĞI (BACKEND)
│   ├── advisor.py              # Bölüm/Yandal arama ve uyum motoru
│   ├── personal_recommendation.py  # Ders puanlama ve ön koşul algoritması
│   ├── parse_schedule.py       # HTML -> CSV dönüştürücü (Parser)
│   └── clean_data.py           # Veri temizleme scripti
│
├── app.py                      # KULLANICI ARAYÜZÜ (STREAMLIT)
├── main.py                     # (Opsiyonel) Terminal test dosyası
└── README.md                   # Proje dokümantasyonu