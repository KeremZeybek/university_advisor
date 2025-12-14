"""
=============================================================================
MODÜL: Recommendation Engine (Business Logic)
DOSYA: src/recommender.py
TANIM: Öğrenci profiline ve mezuniyet durumuna göre dersleri filtreler, puanlar ve sıralar.
MEVCUT FONKSİYONLAR:
1. check_prerequisites(...) ........ Regex ile ön koşul metnini analiz eder.
2. get_recommendations(...) ........ Ana öneri fonksiyonu.
GÜNCELLEME V3: 'Zorunluysa Alttan Al, Seçmeliyse İleri Bak' kuralı eklendi.
=============================================================================
"""

import pandas as pd
import re
from src.ml_engine import calculate_ml_scores

def extract_codes(text):
    """Metin içindeki ders kodlarını (Örn: CS 201) regex ile bulur."""
    if not isinstance(text, str): return []
    return re.findall(r"([A-Z]{2,5}\s+\d{3,4})", text)

def check_prerequisites(prereq_text, taken_courses):
    """
    Dersin ön koşullarını kontrol eder.
    Returns: (bool: Alınabilir mi, list: Eksikler)
    """
    if pd.isna(prereq_text) or str(prereq_text).lower() in ["nan", "none", ""]:
        return True, [] 

    text = str(prereq_text).upper()
    text = re.sub(r'MINIMUM GRADE OF [A-Z]', '', text)
    
    req_blocks = text.split(' AND ')
    missing = []
    
    for block in req_blocks:
        options = block.split(' OR ')
        codes = []
        satisfied = False
        for option in options:
            found = extract_codes(option)
            if not found: continue
            codes.extend(found)
            if all(c in taken_courses for c in found):
                satisfied = True
                break
        
        if not satisfied and codes:
            missing.append(f"({' OR '.join(sorted(set(codes)))})")
            
    return (len(missing) == 0), missing

def get_recommendations(catalog_df, student_params, audit_data, keywords):
    """
    Mantıksal Filtreleme + AI Puanlama + Akademik Önceliklendirme + Açıklama
    """
    df = catalog_df.copy()
    
    # ---------------------------------------------------------
    # ADIM 1: TEKNİK FİLTRELER
    # ---------------------------------------------------------
    term = student_params['term']
    df = df[df['Term'].str.contains(term, case=False, na=False) | (df['Term'] == "Unknown")]
    df = df[~df['Course Code'].isin(student_params['taken'])]
    df = df[~df['Course Code'].str.contains(r"\d{3}[RL]$", regex=True)] # Lab/Recit temizliği
    
    if student_params['level'] == "Lisans": df = df[df['Level'] < 500]
    else: df = df[df['Level'] >= 400]

    # ---------------------------------------------------------
    # ADIM 2: ÖN KOŞUL KONTROLÜ (SMART LOGIC)
    # ---------------------------------------------------------
    taken = student_params['taken']
    df = df[df.apply(lambda r: check_prerequisites(r.get('Prerequisites', ''), taken)[0], axis=1)]

    # ---------------------------------------------------------
    # ADIM 3: AI SKORLAMA (İÇERİK)
    # ---------------------------------------------------------
    if keywords:
        # AI Puanını hesapla ama biraz yumuşat (Katsayı: 0.7)
        raw_ai_scores = calculate_ml_scores(df, keywords)
        df['AI_Score'] = [round(s * 0.7, 1) for s in raw_ai_scores]
    else:
        df['AI_Score'] = 0

    # ---------------------------------------------------------
    # ADIM 4: HİBRİT PUANLAMA & AÇIKLAMA (REPORTING)
    # ---------------------------------------------------------
    year = student_params['year']
    critical = audit_data.get('critical', set())
    pool = audit_data.get('pool', set())

    def score_logic(row):
        code = row['Course Code']
        base_ai = row['AI_Score']
        
        total_score = base_ai
        reasons = [] 
        category = "⚪ Diğer"
        
        if base_ai > 15:
            reasons.append(f"İlgi Alanı (+{int(base_ai)})")

        try: lvl = int(re.search(r"(\d+)", str(code)).group(1)) // 100
        except: lvl = 0

        # --- A. ZİNCİRLEME BONUSU ---
        has_prereq = pd.notna(row.get('Prerequisites')) and str(row.get('Prerequisites')).lower() not in ["nan", "none", ""]
        if has_prereq:
            total_score += 20
            reasons.append("Zincir Ders (+20)")

        # --- B. MEZUNİYET DURUMU (ÖNEMLİ KISIM) ---
        
        # 1. ZORUNLU DERSLER (Critical)
        if code in critical:
            if lvl < year:
                # Alttan kalan zorunlu ders: EN YÜKSEK PUAN
                total_score += 85
                category = "🔴 Kritik (Alttan)"
                reasons.insert(0, "⚠️ Alttan Kalan Zorunlu (+85)")
            elif lvl <= year + 1:
                total_score += 45
                category = "🟠 Zorunlu"
                reasons.insert(0, "🎓 Dönem Zorunlusu (+45)")
            else:
                total_score += 10
                category = "⚪ Zorunlu (Erken)"
                reasons.append("Gelecek Zorunlu (+10)")
                
        # 2. SEÇMELİ DERSLER (Pool)
        elif code in pool:
            # KURAL: Seçmeli ders, öğrencinin sınıfından düşükse ÖNERME!
            if lvl < year:
                total_score -= 50 # Cezalandır
                category = "⚪ Alt Dönem Seçmeli"
                reasons.append("⛔ Seviye Düşük (-50)")
            else:
                # Seviye uygunsa bonus ver
                total_score += 25
                category = "🔵 Core Seçmeli"
                reasons.append("Havuz Seçmeli (+25)")
            
        elif base_ai > 30:
            category = "🟢 Tavsiye"
            
        explanation = " | ".join(reasons) if reasons else "Genel Seçmeli"
        return pd.Series([total_score, category, explanation])

    df[['Final_Score', 'Category', 'Explanation']] = df.apply(score_logic, axis=1)
    
    # ---------------------------------------------------------
    # ADIM 5: SIRALAMA
    # ---------------------------------------------------------
    # Filtreden geçmesi için 15 puan barajı koyuyoruz (Cezalılar elensin diye)
    return df[df['Final_Score'] > 15].sort_values(by='Final_Score', ascending=False).head(20)