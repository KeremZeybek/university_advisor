"""
=============================================================================
MODÜL: Recommendation Engine (HIGH PERFORMANCE VECTORIZED)
DOSYA: src/recommender.py
TANIM: Yüksek performanslı, vektörize edilmiş öneri motoru.
       - Numpy/Pandas Vectorization (10x-20x Hız Artışı)
       - Lazy Text Generation (Sadece sonuçlar için metin üretimi)
       - Dinamik Ağırlıklandırma Desteği
=============================================================================
"""

import pandas as pd
import numpy as np
import re
import logging
from typing import Dict, List, Set, Tuple, Optional, Any

# Logging Setup
logger = logging.getLogger(__name__)

# ML Engine Import
try:
    from src.ml_engine import calculate_ml_scores
except ImportError:
    try:
        from ml_engine import calculate_ml_scores
    except:
        def calculate_ml_scores(df, kw): 
            logger.warning("ML Engine bulunamadı, 0 score döndürülüyor")
            return np.zeros(len(df))

# --- KONFİGÜRASYON ---
SCORING_WEIGHTS = {
    'graduation_urgency': 1.3,
    'readiness': 1.0,
    'chain_impact': 1.1,
    'scarcity_bonus': 1.0,
    'interest_fit': 0.8,
    'overlap_risk': 0.7,
    'subject_penalty': 1.0,
}

MIN_FINAL_SCORE = 15
MAX_RECOMMENDATIONS = 20

# --- YARDIMCI FONKSİYONLAR ---

def get_adaptive_weights(year: int) -> Dict[str, float]:
    """
    Öğrencinin sınıfına göre ağırlıkları dinamik olarak ayarlar.
    
    Mantık:
    - 1. Sınıf: Zincir açmak ve keşfetmek önemlidir.
    - 4. Sınıf: Mezuniyet her şeyden önemlidir, zincir açmanın anlamı yoktur.
    """
    weights = SCORING_WEIGHTS.copy()
    
    if year >= 4:
        # Son Sınıf Modu (Panic Mode): Sadece mezun olmaya odaklan
        weights['graduation_urgency'] = 2.5  # Çok büyük öncelik
        weights['chain_impact'] = 0.1        # Zincir açmanın artık faydası yok
        weights['interest_fit'] = 0.5        # Seçicilik lüksü azalır
        weights['scarcity_bonus'] = 1.5      # Kaçırırsan okul uzar
        logger.info("Adaptive Weights: 4. Sınıf (Mezuniyet Odaklı) profili uygulandı.")
        
    elif year == 3:
        # 3. Sınıf Modu: Denge
        weights['graduation_urgency'] = 1.5
        # Standart ağırlıklar korunur
        logger.info("Adaptive Weights: 3. Sınıf (Dengeli) profili uygulandı.")
        
    elif year <= 2:
        # 1. ve 2. Sınıf Modu (Exploration Mode): Geleceği planla
        weights['graduation_urgency'] = 1.0  # Henüz panik yok
        weights['chain_impact'] = 1.6        # Gelecek kilitleri açmak çok önemli
        weights['interest_fit'] = 1.2        # İlgi alanını keşfet
        logger.info("Adaptive Weights: Alt Sınıf (Keşif ve Zincir) profili uygulandı.")
        
    return weights

def extract_codes(text: str) -> List[str]:
    if not isinstance(text, str): return []
    return re.findall(r"([A-Z]{2,5}\s+\d{3,4})", text)

def normalize_keywords(keywords: Any) -> Set[str]:
    if isinstance(keywords, dict):
        return set(kw.lower() for kw in keywords.keys())
    elif isinstance(keywords, (list, tuple)):
        return set(str(kw).lower() for kw in keywords)
    elif isinstance(keywords, str):
        return set(keywords.lower().split())
    else:
        return set()

def extract_course_level(code: str) -> int:
    try:
        # Hızlı split
        return (int(code.split()[1]) // 100) * 100
    except:
        return 0

def check_prerequisites(prereq_text: str, taken_courses: Set[str]) -> bool:
    """
    Satır bazlı çalışmak zorunda olan nadir fonksiyonlardan.
    Ancak sonucu boolean döner, hızdan tasarruf için apply içinde sadece bunu çağırırız.
    """
    if pd.isna(prereq_text) or str(prereq_text).lower() in ["nan", "none", "", " "]:
        return True

    text = str(prereq_text).upper()
    text = re.sub(r'MINIMUM GRADE OF [A-Z]', '', text)
    text = re.sub(r'LEVEL \d+', '', text)
    
    req_blocks = text.split(' AND ')
    
    for block in req_blocks:
        options = block.split(' OR ')
        satisfied = False
        for option in options:
            found = extract_codes(option)
            if not found: continue
            # Eğer opsiyondaki herhangi bir ders alındıysa bu blok tamamdır
            if any(c in taken_courses for c in found):
                satisfied = True
                break
        
        if not satisfied:
            # Hiçbir opsiyon sağlanmadıysa ön koşul tutmuyor
            # (found boşsa yani ders kodu yoksa text açıklamadır, pass geçiyoruz)
            if any(extract_codes(block)):
                return False
            
    return True

def analyze_student_profile(transcript_set, catalog_df):
    """
    Öğrencinin aldığı derslere bakarak ilgi alanlarını (Keyword) çıkarır.
    Örn: 'Machine Learning', 'Computer Vision' aldıysa -> ['LEARNING', 'VISION', 'COMPUTER'] çıkarır.
    """
    if not transcript_set or catalog_df.empty:
        return []

    # Analiz edilmeyecek gereksiz kelimeler (Stopwords)
    STOPWORDS = {
        'INTRODUCTION', 'TO', 'OF', 'THE', 'AND', 'IN', 'FOR', 'WITH', 
        'I', 'II', 'III', 'IV', 'V', 'PROJECT', 'DESIGN', 'ANALYSIS', 
        'APPLICATION', 'APPLICATIONS', 'BASIC', 'GENERAL', 'PRINCIPLES',
        'FUNDAMENTALS', 'TOPICS', 'ADVANCED', 'SYSTEMS', 'THEORY', 'PRACTICE',
        'ENGINEERING', 'SCIENCE', 'SOCIAL', 'TERM', 'GRADUATION', 'SUMMER',
        'STUDIES', 'CONTEMPORARY', 'ISSUES', 'METHODS'
    }

    # Transkriptteki derslerin satırlarını bul
    taken_courses = catalog_df[catalog_df['Course Code'].isin(transcript_set)]
    
    word_counter = {}
    
    for _, row in taken_courses.iterrows():
        # Ders adını kelimelere böl
        course_name = str(row['Course Name']).upper()
        # Sadece harflerden oluşan en az 3 harfli kelimeleri al
        words = re.findall(r'\b[A-Z]{3,}\b', course_name)
        
        for w in words:
            if w not in STOPWORDS:
                word_counter[w] = word_counter.get(w, 0) + 1

    # En çok tekrar eden kelimeleri sırala
    sorted_words = sorted(word_counter.items(), key=lambda x: x[1], reverse=True)
    
    # En güçlü 5 ilgi alanını al
    profile_keywords = [w[0] for w in sorted_words[:5]]
    
    logger.info(f"Profil Analizi Sonucu: {profile_keywords}")
    return profile_keywords

def build_chain_map(df: pd.DataFrame) -> Dict[str, int]:
    chain_map = {code: 0 for code in df['Course Code']}
    for prereq_text in df.get('Prerequisites', []):
        if pd.isna(prereq_text): continue
        found = extract_codes(str(prereq_text).upper())
        for code in found:
            if code in chain_map:
                chain_map[code] += 1
    return chain_map

def calculate_subject_penalty_map(prefixes: np.ndarray, keywords: Any) -> Dict[str, int]:
    """Her benzersiz prefix için cezayı bir kez hesapla"""
    kw_tokens = normalize_keywords(keywords)
    penalty_map = {}
    
    if not kw_tokens:
        return {p: 0 for p in prefixes}

    for p in prefixes:
        p_lower = p.lower()
        if p_lower in kw_tokens:
            penalty_map[p] = 0
        else:
            # Kısmi uyum kontrolü
            match = False
            for kw in kw_tokens:
                if p_lower.startswith(kw[:2]) or kw.startswith(p_lower[:2]):
                    penalty_map[p] = 5
                    match = True
                    break
            if not match:
                penalty_map[p] = 25
                
    return penalty_map

# --- STRING GENERATORS (SADECE SONUÇLAR İÇİN ÇALIŞIR) ---

def generate_explanation(row) -> str:
    reasons = []
    
    # Skorlar DataFrame'den gelir
    gus = row.get('GUS', 0)
    cis = row.get('CIS', 0)
    csb = row.get('CSB', 0)
    ifs = row.get('IFS', 0)
    srp = row.get('SRP', 0)
    base_ai = row.get('AI_Score', 0)
    
    if gus >= 40: reasons.append("🔴 Mezuniyet Şartı")
    elif gus >= 35: reasons.append("🟠 Üniversite Şartı")
    elif gus >= 25: reasons.append("🔵 Çekirdek Ders")
    elif gus >= 15: reasons.append("🟡 Alan Dersi")
    
    if cis > 0: reasons.append(f"🔗 {int(row.get('Chain_Size', 0))} dersin önünü açıyor")
    if csb > 0: reasons.append("⏰ Sadece bu dönem açılıyor")
    if ifs > 5: reasons.append(f"❤️ İlgi alanı uyumu (%{int(base_ai)})")
    if srp > 0: reasons.append("⚠️ Alan Dışı")
    
    # Level kontrolü
    lvl = row.get('Level_Num', 0)
    year = row.get('Student_Year', 1)
    if lvl < year * 100: reasons.append("📉 Alttan Ders")
    
    return " | ".join(reasons) if reasons else "Serbest Seçmeli"

def generate_category(row) -> str:
    srp = row.get('SRP', 0)
    if srp > 100: return "🚫 Alan Dışı"
    
    gus = row.get('GUS', 0)
    ifs = row.get('IFS', 0)
    cis = row.get('CIS', 0)
    
    # GUS Puanlarına göre kategori (graduation_urgency_score fonksiyonundaki mantıkla eşleşmeli)
    if gus >= 40: return "🔴 Kritik Zorunlu"     # Required
    if gus >= 35: return "🟠 Üniversite Şartı"   # University
    if gus >= 25:                                # Core
        return "🟢 Çekirdek & İlgi Alanı" if ifs >= 5 else "🔵 Çekirdek (Core)"
    if gus >= 15:                                # Area
        return "🟢 Alan & İlgi Alanı" if ifs >= 5 else "🟡 Alan (Area)"
        
    if cis >= 5: return "🟣 Stratejik (Zincir)"
    if ifs >= 5: return "🟢 İlgi Alanı"
    
    return "⚪ Genel Seçmeli"


# --- ANA MOTOR (VEKTÖRİZE) ---

def get_recommendations(
    catalog_df: pd.DataFrame,
    student_params: Dict[str, Any],
    audit_data: Dict[str, Any],
    keywords: Any,
    weights: Optional[Dict[str, float]] = None,
    min_score: int = MIN_FINAL_SCORE,
    max_recs: int = MAX_RECOMMENDATIONS
) -> pd.DataFrame:
    
    year = student_params.get('year', 1)
    if weights is None:
        weights = get_adaptive_weights(year)
    
    # --- 1. HIZLI FİLTRELEME ---
    df = catalog_df.copy().reset_index(drop=True)
    taken_set = set(student_params.get('taken', []))
    year = student_params.get('year', 1)
    
    # Alınanları çıkar
    df = df[~df['Course Code'].isin(taken_set)]
    # Lab/Recit/Discussion çıkar (Regex yerine str methodları daha hızlı olabilir ama regex esnektir)
    df = df[~df['Course Code'].str.contains(r"\d{3}[RLD]$", regex=True)]
    
    # Lisans / YL Filtresi
    # Level sütunu yoksa oluştur, varsa kullan
    if 'Level' not in df.columns:
        df['Level'] = df['Course Code'].apply(extract_course_level)
    
    if student_params.get('level') == "Lisans":
        df = df[df['Level'] < 500]
    else:
        df = df[df['Level'] >= 400]
        
    df = df.reset_index(drop=True)
    
    # --- 2. ÖN KOŞUL (Tek Yavaş Kısım - Apply Mecbur) ---
    if 'Prerequisites' in df.columns:
        # Sadece dolu olanları kontrol et
        mask_has_prereq = df['Prerequisites'].notna() & (df['Prerequisites'] != "")
        # Vektörize edilemediği için apply kullanıyoruz ama sadece gerekli satırlara
        valid_prereqs = df.loc[mask_has_prereq, 'Prerequisites'].apply(
            lambda x: check_prerequisites(x, taken_set)
        )
        # Ön koşulu olmayanlar (True) + Ön koşulu sağlayanlar
        df = df[~mask_has_prereq | valid_prereqs].reset_index(drop=True)
    
    if df.empty: return pd.DataFrame()

    # --- 3. VERİ HAZIRLIĞI (SÜTUN BAZLI) ---
    
    # Level Num (Hesaplama için int hali)
    # df['Level'] zaten var ama emin olalım
    df['Level_Num'] = (df['Level'] // 100) * 100
    
    # AI Score
    if keywords:
        df['AI_Score'] = calculate_ml_scores(df, keywords)
    else:
        df['AI_Score'] = 0.0
        
    # Prereq Count (Metinden sayma)
    def fast_count_prereqs(x):
        if pd.isna(x): return 0
        return len(extract_codes(str(x)))
    df['Prereq_Count'] = df['Prerequisites'].apply(fast_count_prereqs)
    
    # Chain Map
    chain_map = build_chain_map(df)
    df['Chain_Size'] = df['Course Code'].map(chain_map).fillna(0).astype(int)
    
    # Prefix Counts
    df['Prefix'] = df['Course Code'].str.split().str[0]
    prefix_counts = df['Prefix'].value_counts()
    df['Prefix_Count'] = df['Prefix'].map(prefix_counts).fillna(1).astype(int)
    
    # Opening Terms (Varsayılan 2)
    if 'Opening_Terms' not in df.columns:
        df['Opening_Terms'] = 2
    
    # Set Kümeleri (Boolean Maskeler)
    required = audit_data.get('required', set())
    university = audit_data.get('university', set())
    core = audit_data.get('core', set())
    area = audit_data.get('area', set())
    
    is_required = df['Course Code'].isin(required)
    is_university = df['Course Code'].isin(university)
    is_core = df['Course Code'].isin(core)
    is_area = df['Course Code'].isin(area)
    is_critical = is_required | is_university
    is_elective = is_core | is_area

    # --- 4. VEKTÖRİZE PUANLAMA (NUMPY/PANDAS ILE HIZLI HESAP) ---
    
    # 1. Graduation Urgency Score (GUS)
    # np.select condlist sırasıyla kontrol edilir, ilk True olanın değerini alır
    df['GUS'] = np.select(
        [is_required, is_university, is_core, is_area],
        [40, 35, 25, 15],
        default=0
    )
    
    # 2. Readiness Score (RES)
    # Level farkı
    level_diff = (df['Level_Num'] // 100) - year
    base_res = 20
    
    level_adj = np.select(
        [level_diff == 0, level_diff == 1, level_diff >= 2, level_diff < 0],
        [10, 5, -15, -5],
        default=0
    )
    
    prereq_adj = np.select(
        [df['Prereq_Count'] == 0, df['Prereq_Count'] >= 3],
        [5, -10],
        default=0
    )
    
    df['RES'] = np.maximum(base_res + level_adj + prereq_adj, 0)
    
    # 3. Chain Impact Score (CIS)
    df['CIS'] = np.select(
        [df['Chain_Size'] >= 3, df['Chain_Size'] == 2, df['Chain_Size'] == 1],
        [20, 12, 5],
        default=0
    )
    
    # 4. Scarcity Bonus (CSB)
    # Sadece 1 dönem açılanlara bonus
    scarcity_mask = (df['Opening_Terms'] == 1)
    base_bonus = 5
    critical_bonus = np.where(is_critical, 10, 0)
    chain_bonus = np.where(df['Chain_Size'] > 0, 5, 0)
    
    df['CSB'] = np.where(scarcity_mask, base_bonus + critical_bonus + chain_bonus, 0)
    
    # 5. Interest Fit Score (IFS)
    # Elective ise %40, değilse %20. Max 20 veya 10.
    # AI_Score genelde 0-100 arasıdır.
    elective_score = np.minimum(df['AI_Score'] * 0.4, 20)
    mandatory_score = np.minimum(df['AI_Score'] * 0.2, 10)
    df['IFS'] = np.where(is_elective, elective_score, mandatory_score).astype(int)
    
    # 6. Overlap Risk Score (ORS)
    df['ORS'] = np.select(
        [df['Prefix_Count'] >= 4, df['Prefix_Count'] == 3],
        [15, 8],
        default=0
    )
    
    # 7. Subject Relevance Penalty (SRP)
    # Kritik derslerde (GUS > 0) ceza uygulanmaz
    unique_prefixes = df['Prefix'].unique()
    penalty_map = calculate_subject_penalty_map(unique_prefixes, keywords)
    raw_srp = df['Prefix'].map(penalty_map).fillna(0)
    df['SRP'] = np.where(df['GUS'] > 0, 0, raw_srp)
    
    # --- 5. FİNAL SKOR VE SIRALAMA ---
    
    df['Final_Score'] = (
        (df['GUS'] * weights['graduation_urgency']) +
        (df['RES'] * weights['readiness']) +
        (df['CIS'] * weights['chain_impact']) +
        (df['CSB'] * weights['scarcity_bonus']) +
        (df['IFS'] * weights['interest_fit']) -
        (df['ORS'] * weights['overlap_risk']) -
        (df['SRP'] * weights['subject_penalty'])
    )
    
    # Negatifleri sıfırla
    df['Final_Score'] = df['Final_Score'].clip(lower=0)
    
    # Filtrele ve Sırala (EN ÖNEMLİ PERFORMANS ADIMI)
    # Tüm tabloya metin üretmek yerine, önce eliyoruz.
    result_df = df[df['Final_Score'] > min_score].sort_values(
        by='Final_Score', ascending=False
    ).head(max_recs).copy()
    
    if result_df.empty:
        return pd.DataFrame(columns=['Course Code', 'Course Name', 'Final_Score', 'Category', 'Explanation'])

    # --- 6. METİN ÜRETİMİ (LAZY GENERATION) ---
    # Sadece seçilen az sayıdaki ders için çalışır
    result_df['Student_Year'] = year
    result_df['Category'] = result_df.apply(generate_category, axis=1)
    result_df['Explanation'] = result_df.apply(generate_explanation, axis=1)
    
    return result_df


def get_recommendations_with_stats(
    catalog_df: pd.DataFrame,
    student_params: Dict[str, Any],
    audit_data: Dict[str, Any],
    keywords: Any
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    
    result = get_recommendations(catalog_df, student_params, audit_data, keywords)
    
    stats = {
        'total_recommended': len(result),
        'by_category': result['Category'].value_counts().to_dict() if not result.empty else {},
        'avg_score': float(result['Final_Score'].mean()) if not result.empty else 0,
        'max_score': float(result['Final_Score'].max()) if not result.empty else 0,
        'min_score': float(result['Final_Score'].min()) if not result.empty else 0,
        'top_5_courses': result[['Course Code', 'Course Name', 'Final_Score']].head(5).to_dict('records') if not result.empty else [],
    }
    
    return result, stats