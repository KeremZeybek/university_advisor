import pandas as pd
import os
import re

# ---------------------------------------------------------
# 1. AYARLAR VE DOSYA YOLLARI
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Proje ana dizini
RAW_CSV_PATH = os.path.join(BASE_DIR, 'data', 'csv', 'course_full_data_v2.csv')      # Kirli veri
LINKS_CSV_PATH = os.path.join(BASE_DIR, 'data', 'csv', 'course_links_master.csv')    # Güvenilir dönem verisi
OUTPUT_PATH = os.path.join(BASE_DIR, 'data', 'csv', 'course_data_clean.csv')         # ÇIKTI (Temiz)

def clean_html_garbage(text):
    """
    HTML'den kalan 'Detailed Course Information', 'Return to Previous' gibi
    çöp metinleri temizler.
    """
    if pd.isna(text) or text == "":
        return ""
    
    text = str(text)
    
    # 1. Üst Kısımdaki Çöpü Temizle
    # Genelde "...find available classes for the course." cümlesinden sonra asıl metin başlar.
    garbage_start_pattern = r".*?find available classes for the course\.\s*"
    text = re.sub(garbage_start_pattern, "", text, flags=re.DOTALL)
    
    # 2. Alt Kısımdaki Çöpü Temizle
    # "Must be enrolled...", "Return to Previous", "Release: 8.x" gibi teknik yazılar.
    garbage_end_pattern = r"(Must be enrolled in one of the following Levels:|Return to Previous|Skip to top of page|Release: \d+\.\d+).*"
    text = re.sub(garbage_end_pattern, "", text, flags=re.DOTALL)
    
    # 3. HTML Entity ve Fazla Boşluk Temizliği
    text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def main():
    print("🧹 Veri Temizleme İşlemi Başlıyor...")
    
    # -----------------------------------------------------
    # 2. DOSYALARI YÜKLE
    # -----------------------------------------------------
    if not os.path.exists(RAW_CSV_PATH):
        print(f"HATA: {RAW_CSV_PATH} bulunamadı!")
        return

    df = pd.read_csv(RAW_CSV_PATH)
    print(f"📥 Ham veri yüklendi: {len(df)} satır")

    # -----------------------------------------------------
    # 3. METİN TEMİZLİĞİ (TEXT CLEANING)
    # -----------------------------------------------------
    print("🧼 Metin sütunları (Description, Restrictions vb.) temizleniyor...")
    
    # Temizlenecek sütunlar
    text_cols = ['Description', 'Restrictions', 'Prerequisites', 'Corequisites']
    
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_html_garbage)

    # -----------------------------------------------------
    # 4. 'TERM' VERİSİNİ DÜZELTME (DATA MERGING)
    # -----------------------------------------------------
    print("🔗 Dönem (Term) bilgisi 'course_links_master.csv' dosyasından güncelleniyor...")
    
    # Ana dosyadaki hatalı Term sütununu sil
    if 'Term' in df.columns:
        df = df.drop(columns=['Term'])
    
    # Link dosyasını yükle
    if os.path.exists(LINKS_CSV_PATH):
        links_df = pd.read_csv(LINKS_CSV_PATH)
        
        # Sütun isimlerini standartlaştır (Büyük Harf)
        links_df.columns = [c.strip().upper() for c in links_df.columns]
        
        if 'COURSE CODE' in links_df.columns and 'TERM' in links_df.columns:
            # Eşleşme anahtarlarını standartlaştır (Strip + Upper)
            df['Course Code'] = df['Course Code'].astype(str).str.strip().str.upper()
            links_df['COURSE CODE'] = links_df['COURSE CODE'].astype(str).str.strip().str.upper()
            
            # Birleştirme (Merge)
            df = pd.merge(
                df,
                links_df[['COURSE CODE', 'TERM']],
                left_on='Course Code',
                right_on='COURSE CODE',
                how='left'
            )
            
            # Sütun ismini düzelt ve temizle
            df = df.rename(columns={'TERM': 'Term'})
            df['Term'] = df['Term'].fillna("Unknown")
            
            # Gereksiz çift anahtarı sil
            if 'COURSE CODE' in df.columns:
                df = df.drop(columns=['COURSE CODE'])
        else:
            print("UYARI: Link dosyasında beklenen sütunlar (COURSE CODE, TERM) yok.")
            df['Term'] = "Unknown"
    else:
        print("UYARI: Link dosyası bulunamadı, Term sütunu 'Unknown' olarak ayarlanıyor.")
        df['Term'] = "Unknown"

    # -----------------------------------------------------
    # 5. EKSTRA ÖZELLİK ÇIKARIMI (FEATURE EXTRACTION)
    # -----------------------------------------------------
    print("u2699 Seviye (Level) bilgisi çıkarılıyor...")
    
    def extract_level(code):
        import re
        try:
            match = re.search(r"(\d+)", str(code))
            return int(match.group(1)) if match else 0
        except:
            return 0

    df['Level'] = df['Course Code'].apply(extract_level)

    # -----------------------------------------------------
    # 6. KAYDET
    # -----------------------------------------------------
    desired_order = ['Course Code', 'Course Name', 'Level', 'Term', 'Description', 'Prerequisites', 'Restrictions', 'Corequisites']
    final_cols = [c for c in desired_order if c in df.columns]
    final_cols += [c for c in df.columns if c not in final_cols]
    
    df = df[final_cols]
    
    df.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')
    print(f"\n✅ BAŞARILI! Temizlenmiş dosya kaydedildi: {OUTPUT_PATH}")
    print(f"📊 Toplam Ders Sayısı: {len(df)}")
    print("-" * 50)

if __name__ == "__main__":
    main()