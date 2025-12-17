# 🗺️ Sabancı Smart Advisor - Proje Yol Haritası (Revize: v2.0)

## 🎯 Hedef
Öğrencinin mezuniyet durumunu **JSON Kuralları** ile denetleyen, ders önerilerini ise **Gerçek Ders Programı (Schedule)** ve **Akademik İlgi Alanları (Keywords)** ile yapan hibrit bir sistem.

---

## 📂 Veri Envanteri ve Sorumluluklar

Bu proje 4 kritik veri kaynağının **Füzyonu** ile çalışır. Her dosyanın görevi kesindir:

| Dosya | Tür | Kritik Veri | Görevi (Rolü) |
| :--- | :--- | :--- | :--- |
| **`fens_data_raw.json`** | JSON | Mezuniyet Kuralları, Havuzlar | **Tab 1 (Audit)**: Eksik dersleri bulur. |
| **`active_schedule_master.csv`** | CSV | **Term**, Time, Instructor | **Tab 2 (Filtre)**: "Bu ders bu dönem açılıyor mu?" kontrolü. (Eski CSV'deki yanlış Term bilgisi yerine bu kullanılacak). |
| **`course_data_clean.csv`** | CSV | **Prerequisites**, Corequisites | **Tab 2 (Logic)**: "Bu dersi alabilir miyim?" kontrolü. (Buradaki Term bilgisi YOK sayılacak). |
| **`undergrad_majors.json`** | JSON | **Keywords**, Subject Codes | **Tab 2 (Scoring)**: İlgi alanına göre puanlama (Örn: CS öğrencisine AI dersi önerme). |

---

## 🧠 Algoritma Mimarisi

### 1. Tab 1: Mezuniyet Denetimi (The Auditor)
* **Motor:** `src/audit_engine.py`
* **Girdi:** `fens_data_raw.json` + Öğrenci Transkripti.
* **Çıktı:** `missing_courses` (Örn: `['CS 300', 'ENS 208']`).

### 2. Tab 2: Akıllı Öneri (The Recommender - Revize)
Eski sistemdeki statik katalog yerine, **Dinamik Birleştirme** yapılacak:

1.  **Adım 1 (Schedule Filter):** `active_schedule_master.csv` okunur. Seçilen dönemde (Örn: 202402 - Spring) açılmayan dersler elenir.
2.  **Adım 2 (Prereq Merge):** Kalan derslerin yanına `course_data_clean.csv` dosyasından **Prerequisite** bilgisi eklenir (Merge işlemi).
3.  **Adım 3 (Logic Check):** Öğrenci bu dersin ön koşulunu sağlıyor mu? (Eski `recommender.py` mantığı).
4.  **Adım 4 (Keyword Scoring):** `undergrad_majors.json` dosyasından seçilen alanın keyword'leri ile ML puanlaması yapılır.

### 3. Tab 3: Arama (The Search)
* **Veri:** `active_schedule_master.csv`
* **İşlev:** Dersin hocasını, yerini ve saatini gösterir.

---

## ✅ Tamamlananlar
- [x] JSON verisinin çekilmesi ve Audit Engine entegrasyonu.
- [x] Audit Engine'deki mantık hatalarının (HUM 3xx, Overlap) giderilmesi.
- [x] Tab 1 Arayüzü.

## 🚧 Sırada Yapılacaklar (Action Plan)
1.  **Data Loader Güncellemesi:** `app.py` içinde 4 dosyayı da okuyan yapı kurulacak.
2.  **Keyword Parser:** `undergrad_majors.json` ve `minors.json` dosyalarını okuyup Dropdown listesi (Örn: "CS - Artificial Intelligence") üreten fonksiyon yazılacak.
3.  **Recommender Füzyonu:** Recommender'a tek bir CSV değil, **Schedule + Metadata** birleşimi gönderilecek.

## ⚠️ Kritik Kurallar
* **KURAL 1:** Asla `course_data_clean.csv` içindeki TERM bilgisini kullanma. Yanlış.
* **KURAL 2:** Recommender sadece `active_schedule_master.csv` içinde o dönem aktif olan dersleri önermeli.
* **KURAL 3:** Puanlama yaparken; Alttan dersler (+85), Dönem dersleri (+45), Zincir dersler (+20) puan alır.