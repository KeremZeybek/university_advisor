# 🎓 Sabancı University Smart Advisor & Degree Auditor

**Sabancı Üniversitesi** öğrencileri için geliştirilmiş; ders önerme, akademik yol haritası çizme ve mezuniyet denetim (audit) sistemidir.

Bu proje, öğrencilerin transkriptlerini ve geçmişlerini analiz eder, **Sentence-BERT** ile ilgi alanlarını anlar ve bölüm yükümlülüklerini (Major/Minor) otomatik kontrol ederek kişiselleştirilmiş tavsiyeler sunar.
Bu bir öğrenci projesidir, kar amacı gütmemektedir. AI kullanımı mevcuttur. Daha tamamlanmamış olup yapım aşamasındadır. Bazı hatalar meydana gelebilir.
---

## 🚀 Öne Çıkan Özellikler

### 1. 🧠 İlgi Alanı / Bölüm Bazlı Ders Önerisi
* **Semantik Arama:** Kullanıcının ilgi alanlarını ("I want to work on fintech") vektör uzayında analiz eder ve ders kataloglarıyla eşleştirir.
* **Hibrit Puanlama:** Ders skorunu; dersin ön koşul derinliği (Zincir Etkisi), mezuniyet aciliyeti ve öğrenci seviyesi ile harmanlar.

### 2. 🕵️‍♂️ Akıllı Mezuniyet Denetçisi (Audit Engine)
* **Dinamik Müfredat Analizi:** Bölüm gereksinimlerini (Required, Core, Area, University Electives) statik bir liste yerine dinamik kurallarla denetler.
* **Eksik Hesaplama:** Transkriptinizdeki dersleri müfredatla kıyaslar, kredi (SU/ECTS) açıklarını ve zorunlu ders eksiklerini raporlar.

### 3. 🕸️ Zincir Analizi ve Görselleştirme
* **Ön Koşul Ağaçları:** Bir dersin hangi derslere ön koşul olduğunu grafiksel olarak çizer.
* **Stratejik Öneri:** "Bu dersi alırsan gelecekte 4 dersin kilidini açarsın" gibi stratejik içgörüler sunar.

### 4. 📅 Canlı Ders Programı Entegrasyonu
* Güncel dönem (Fall/Spring) programını analiz eder.
* Çakışma kontrolü seçilen dönemde açılan dersleri önerir.

---
### 5. Yapım Aşamasında Olan Özellikler
* **Öğrenci Profil Analizi:** Öğrencinin geçmişte aldığı derslere bakarak hangi alanlara (örn. "Computer Vision" veya "Macroeconomics") yatkın olduğunu tespit eder.
* **Çift Anadal Uyumlu Analiz** Öğrencinin çiftanadalıan göre mezuniyet takibi ve disiplinler arasu ders önerisinde bulunur.
* **Ders Programı Hazırlayıcı** Canlı ders programına bakarak öğrenciye çakışmayacak ve isteklerine uyacak şekilde otomatik ders programı hazırlar.


## 📂 Proje Mimarisi

Proje, iş mantığını (business logic) ve arayüzü (UI) birbirinden ayıran modüler bir yapıya sahiptir:
---
```text
university_advisor/
│
├── app.py                      # 🖥️ Ana Arayüz (Streamlit Dashboard)
│
├── data/                       # 💾 VERİ KATMANI
│   ├── csv/                    # İşlenmiş Katalog ve Schedule Verileri
│   │   ├── active_schedule_master.csv
│   │   ├── course_data_clean.csv
│   │   └── ...
│   │   
│   └── json/                   # Müfredat Kuralları (FENS/FMAN vb.)
│       ├── fens_data_raw.json
│       └── ...
│
└── src/                        # 🧠 UYGULAMA MOTORU
    ├── audit_engine.py         # Mezuniyet ve kural denetimi (Audit)
    ├── recommender.py          # Ana öneri orkestratörü
    ├── ml_engine.py            # AI (Sentence-BERT) Vektör işlemleri
    ├── utils.py                # Grafik çizimi ve yardımcı araçlar
    ├── major_rules.py          # Mezuniyet yükümlülükleri