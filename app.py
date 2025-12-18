"""
=============================================================================
PROJE: SABANCI UNIVERSITY SMART ADVISOR
DOSYA: app.py
TANIM: Ana Streamlit Arayüzü. 
       - Yardımcı Fonskiyonlar ve Veri Yükleme
       - Sidebar: Transkript Yönetimi / Test Senaryoları
       - Tab 1: Mezuniyet Durumu
       - Tab 2: Hibrit Recommender + Detaylı Debug
       - Tab 3: Ders / Hoca Arama + Detaylı Bilgi / Görsel Ağaç
       - Yeni recommender.py ile tam uyumlu
=============================================================================
"""

import streamlit as st
import pandas as pd
import json
import os
import sys
import logging
import time
import hashlib
import re

# Loglama ayarları
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# --- YARDIMCI FONKSİYONLAR ---

def clean_instructor_name(name_str):
    """
    Hoca isimlerini Regex ile temizler.
    Her türlü boşluğu (tab, non-breaking space) tek boşluğa indirir.
    """
    if pd.isna(name_str) or str(name_str).strip() == "": 
        return "Unknown"
    
    text = str(name_str).replace('"', '').replace("'", "")
    
    parts = text.split(',')
    
    cleaned_parts = []
    for p in parts:
        clean_name = re.sub(r'\s+', ' ', p).strip()
        
        if clean_name:
            cleaned_parts.append(clean_name)
            
    return ", ".join(cleaned_parts)

def extract_program_keywords(data):
    """
    JSON verisinden program anahtar kelimelerini (keywords) çıkarır.
    Hiyerarşik (Faculties -> Programs) yapıyı destekler.
    """
    keywords = {}
    
    # 1. Durum: Eski Düz Format (Backup)
    # { "Program Adı": { "keywords": [...] } }
    if isinstance(data, dict) and "faculties" not in data:
        for prog, info in data.items():
            if isinstance(info, dict) and "keywords" in info:
                keywords[prog] = info["keywords"]
                
    # 2. Durum: Yeni Hiyerarşik Format (undergrad_majors.json)
    # { "faculties": [ { "programs": [ ... ] } ] }
    elif isinstance(data, dict) and "faculties" in data:
        for faculty in data["faculties"]:
            for program in faculty.get("programs", []):
                p_name = program.get("name")
                p_kws = program.get("keywords")
                
                if p_name and p_kws:
                    keywords[p_name] = p_kws

    return keywords

def merge_keywords(*maps):
    """Birden fazla keyword sözlüğünü (Major + Minor) birleştirir."""
    final_map = {}
    for m in maps:
        final_map.update(m)
    return final_map

def normalize_keywords(keywords):
    """
    Kullanıcının verdiği keywordleri set formatına çevirir.
    (Recommender'dan alındı, arayüz için buraya eklendi)
    """
    if isinstance(keywords, dict):
        return set(kw.lower() for kw in keywords.keys())
    elif isinstance(keywords, (list, tuple)):
        return set(str(kw).lower() for kw in keywords)
    elif isinstance(keywords, str):
        return set(keywords.lower().split())
    else:
        return set()

# -----------------------------------------------------------------------------
# 1. PATH VE IMPORT AYARLARI
# -----------------------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT_DIR, 'src')
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

try:
    from src.audit_engine import run_fens_audit
    from src.recommender import get_recommendations_with_stats
    
    logger.info("Tüm modüller başarıyla yüklendi.")

except ImportError as e:
    st.error("🚨 Kritik Hata: Modüller yüklenemedi!")
    st.code(str(e))
    logger.error(f"Import hatası: {e}")
    st.stop()
try:
    from src.utils import generate_prereq_graph 
except ImportError:
    def generate_prereq_graph(*args): return None

# -----------------------------------------------------------------------------
# 2. VERİ YÜKLEME
# -----------------------------------------------------------------------------
st.set_page_config(page_title="FENS Smart Advisor", page_icon="🎓", layout="wide")

JSON_PATH = os.path.join(ROOT_DIR, 'data', 'json', 'fens_data_raw.json')


def get_file_hash(filepath):
    """Dosyanın hash değerini al (değişip değişmediğini kontrol etmek için)"""
    try:
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        logger.warning(f"Hash hesaplanırken hata: {e}")
        return None

    
@st.cache_data(ttl=3600)
def load_data():
    """JSON dosyasından veri yükle ve DataFrame'e çevir"""
    logger.info("JSON verisi yükleniyor...")
    current_hash = get_file_hash(JSON_PATH)
    
    if not os.path.exists(JSON_PATH):
        logger.error(f"JSON dosyası bulunamadı: {JSON_PATH}")
        return None, None

    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"JSON verisi başarıyla yüklendi (Hash: {current_hash[:8] if current_hash else 'N/A'})")
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse hatası: {e}")
        return None, None
    
    # DataFrame Dönüşümü (Recommender için)
    courses_list = []
    for major, info in data.items():
        reqs = info.get("requirements", {})
        for cat, clist in reqs.items():
            for c in clist:
                try: 
                    lvl = int(c['code'].split()[1][0]) * 100
                except: 
                    lvl = 0
                
                courses_list.append({
                    "Course Code": c.get("code"),
                    "Course Name": c.get("name", ""),
                    "ECTS": c.get("ects", 0),
                    "Term": "Unknown",
                    "Level": lvl,
                    "Description": c.get("name", ""), 
                    "Prerequisites": ""
                })

    df = pd.DataFrame(courses_list).drop_duplicates(subset=["Course Code"])
    logger.info(f"DataFrame oluşturuldu: {len(df)} benzersiz ders")
    return data, df

@st.cache_data(ttl=3600)
def load_tab2_resources():
    logger.info("Tab 2 kaynakları yükleniyor ve optimize ediliyor...")
    
    # 1. SCHEDULE (DERS PROGRAMI)
    sched_path = os.path.join(ROOT_DIR, 'data', 'csv', 'active_schedule_master.csv')
    sched_df = pd.DataFrame()
    
    if os.path.exists(sched_path):
        try: 
            sched_df = pd.read_csv(sched_path)
            sched_df.columns = [c.strip() for c in sched_df.columns]
            
            # --- OPTİMİZASYON 1: Hoca Temizliği ---
            if 'Instructor' in sched_df.columns:
                sched_df['Instructor'] = sched_df['Instructor'].apply(clean_instructor_name)
                
            # --- OPTİMİZASYON 2: Gün Düzeltme ve Türkçeleştirme ---
            if 'Days' in sched_df.columns: 
                sched_df = sched_df.rename(columns={'Days': 'Day'})
            
            # [ESKİ KODDAN KORUNAN KISIM]: Günleri Türkçeleştir
            day_map = {'M': 'Pazartesi', 'T': 'Salı', 'W': 'Çarşamba', 'R': 'Perşembe', 'F': 'Cuma'}
            if 'Day' in sched_df.columns:
                for code, name in day_map.items():
                    sched_df['Day'] = sched_df['Day'].astype(str).str.replace(code, name, regex=False)

            # --- OPTİMİZASYON 3: Ana Ders İşareti ---
            if 'Course Code' in sched_df.columns:
                sched_df['Is_Main'] = ~sched_df['Course Code'].astype(str).str.endswith(('R', 'L', 'D'))

            logger.info(f"Schedule yüklendi: {len(sched_df)} satır")
        except Exception as e:
            logger.warning(f"Schedule yükleme hatası: {e}")

    # 2. PREREQUISITES (ÖN KOŞULLAR)
    prereq_path = os.path.join(ROOT_DIR, 'data', 'csv', 'course_data_clean.csv')
    prereq_df = pd.DataFrame()
    
    if os.path.exists(prereq_path):
        try: 
            prereq_df = pd.read_csv(prereq_path)
            prereq_df.columns = [c.strip() for c in prereq_df.columns]
            
            # Level hesaplama (Lambda hatasını önlemek için güvenli yöntem)
            if 'Level' not in prereq_df.columns and 'Course Code' in prereq_df.columns:
                def fast_extract_level(code):
                    try: return (int(code.split()[1]) // 100) * 100
                    except: return 0
                prereq_df['Level'] = prereq_df['Course Code'].apply(fast_extract_level)
                
            logger.info(f"Prerequisite yüklendi: {len(prereq_df)} satır")
        except Exception as e:
            logger.warning(f"Prerequisite yükleme hatası: {e}")

    # 3. KEYWORDS (YENİLENEN GÜVENLİ KISIM)
    kws = {}
    m_path = os.path.join(ROOT_DIR, 'data', 'json', 'undergrad_majors.json')
    mi_path = os.path.join(ROOT_DIR, 'data', 'json', 'undergrad_minors.json')
    
    try:
        if os.path.exists(m_path):
            with open(m_path, 'r', encoding='utf-8') as f: 
                kws.update(extract_program_keywords(json.load(f)))
                
        if os.path.exists(mi_path):
            with open(mi_path, 'r', encoding='utf-8') as f: 
                kws.update(extract_program_keywords(json.load(f)))
    except Exception as e:
        logger.warning(f"Keyword dosyası okuma hatası: {e}")

    # [YENİ EKLENEN KISIM]: Eğer dosya yoksa/boşsa uygulama çökmesin diye varsayılanlar
    if not kws:
        logger.info("⚠️ JSON verisi bulunamadı, varsayılan keyword listesi devreye giriyor.")
        kws = {
            "Computer Science & Eng": ["software", "algorithm", "data", "ai", "network", "security"],
            "Electronics Engineering": ["circuit", "signal", "electronics", "communication", "fpga"],
            "Industrial Engineering": ["optimization", "supply chain", "production", "system", "stochastic"],
            "Mechatronics Engineering": ["robotics", "control", "mechanical", "automation"],
            "Molecular Biology": ["genetics", "cell", "protein", "bioinformatics"],
            "Economics": ["macroeconomics", "microeconomics", "finance", "policy", "econometrics"],
            "Psychology": ["cognitive", "behavioral", "social", "clinical", "developmental"],
            "General Engineering": ["science", "engineering", "math", "physics"]
        }

    return sched_df, prereq_df, kws
          

# Verileri Yükle
logger.info("="*70)
logger.info("UYGULAMANIN BAŞLANGIÇ AŞAMASI")
logger.info("="*70)

raw_data, catalog_df = load_data()
sched_df, prereq_df, keyword_map = load_tab2_resources()

if raw_data is None or catalog_df is None:
    st.error("❌ Kritik Veri Hatası: JSON yüklenemedi!")
    logger.error("JSON verisi yüklenemedi, uygulama durduruluyor.")
    st.stop()
else:
    logger.info("Veriler başarıyla hazırlandı.")

# Dropdown için liste
all_options = sorted(catalog_df["Course Code"] + " - " + catalog_df["Course Name"])

# Session State için varsayılan dersler
DEFAULT_COURSES = {
    "MATH 101", "MATH 102", 
    "NS 101", "NS 102", 
    "SPS 101", "SPS 102",
    "TLL 101", "TLL 102",
    "HIST 191", "HIST 192",
    "IF 100", "AL 102",
    "CIP 101N", "PROJ 201"
}


# -----------------------------------------------------------------------------
# 3. SIDEBAR (TRANSKRİPT YÖNETİMİ)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/6/61/Sabancı_University_logo.svg/500px-Sabancı_University_logo.svg.png", width=150)
    st.title("FENS Advisor")
    
    # Bölüm Seç
    major_list = list(raw_data.keys())
    selected_major = st.selectbox("Bölümünüz:", major_list, index=0)
    logger.info(f"Seçilen bölüm: {selected_major}")
    
    c1, c2 = st.columns(2)
    with c1: year = st.selectbox("Sınıf:", [1, 2, 3, 4], index=1)
    with c2: term = st.selectbox("Dönem:", ["Fall", "Spring"])
    
    logger.info(f"Öğrenci profili - Sınıf: {year}, Dönem: {term}")
    
    st.divider()
    
    st.subheader("📝 Transkript")

        # Session State Başlatma
    if 'transcript' not in st.session_state:
        if year > 1:
            st.session_state.transcript = DEFAULT_COURSES
            logger.info(f"Session state başlatıldı (Sınıf {year}): {len(st.session_state.transcript)} ders")
        else:
            st.session_state.transcript = set()
            logger.info("Session state başlatıldı (Sınıf 1): boş")
    
    # Ekleme
    with st.expander("➕ Ders Ekle", expanded=True):
        # Arama metni
        search_text = st.text_input(
            "Ders Ara:", 
            placeholder="Örn: CS 201, Calculus",
            label_visibility="collapsed"
        ).lower()
        
        # Filtreleme ve sorting
        available = [
            o for o in all_options 
            if o.split(" - ")[0] not in st.session_state.transcript
        ]
        
        # Arama kriterine göre filtrele
        if search_text:
            filtered = sorted([
                o for o in available 
                if search_text in o.lower()
            ])
            logger.info(f"Arama: '{search_text}' - {len(filtered)} sonuç")
        else:
            filtered = sorted(available)
        
        # Selectbox
        sel_add = st.selectbox(
            "Seç:", 
            filtered,
            index=None,
            label_visibility="collapsed"
        )
        
        if st.button("Ekle", use_container_width=True):
            if sel_add:
                course_code = sel_add.split(" - ")[0]
                st.session_state.transcript.add(course_code)
                logger.info(f"Ders eklendi: {course_code}")
                st.rerun()
            else:
                st.warning("Lütfen bir ders seçin.")
                
        # Manuel Ekle
        man_add = st.text_input("Kod Gir (Örn: XYZ 101)").upper()
        if st.button("Manuel Ekle"):
            if man_add:
                st.session_state.transcript.add(man_add)
                logger.info(f"Ders manuel olarak eklendi: {man_add}")
                st.rerun()
            else:
                st.warning("Lütfen bir ders kodu girin.")

    # Çıkarma
    if st.session_state.transcript:
        with st.expander("➖ Ders Çıkar"):
            sel_rm = st.selectbox("Sil:", sorted(list(st.session_state.transcript)))
            if st.button("Sil", type="primary", use_container_width=True):
                st.session_state.transcript.discard(sel_rm)
                logger.info(f"Ders çıkarıldı: {sel_rm}")
                st.rerun()

    st.caption(f"Toplam: {len(st.session_state.transcript)} Ders")
    st.dataframe(
        pd.DataFrame({"Alınanlar": sorted(list(st.session_state.transcript))}), 
        hide_index=True, 
        height=200
    )
    
    # ========== TEST TRANSKRİPT SENARYOLARI ==========
    st.divider()
    st.subheader("🧪 Test Senaryoları")
    st.caption("Hızlı test için farklı transkript yükle")
    
    # Test Senaryoları Tanımı
    TEST_SCENARIOS = {
        "ŞEF": {
            "year": 3,
            "courses": DEFAULT_COURSES.union({
                "CS 201", "MATH 201", "MATH 203", "HUM 202", "ECON 201",
                "CS 204", "MATH 204", "MATH 306", "DSA 210", "ECON 202",
                "CS 303"
            })
        },
        "Sınıf 3 - Kerem": {
            "year": 3,
            "courses": DEFAULT_COURSES.union({
                "CS 201", "DSA 201", "DSA 210", "HUM 202",
                "MATH 201", "MATH 203", "MATH 204", "MATH 306",
                "PSY 202", "MKTG 301", "ENS 205", "ENS 208"
            })
        },
        "Sınıf 3 - Kerem Gelecek Dönem": {
            "year": 3,
            "courses": DEFAULT_COURSES.union({
                "CS 201", "DSA 201", "DSA 210", "HUM 202",
                "MATH 201", "MATH 203", "MATH 204", "MATH 306",
                "PSY 202", "MKTG 301", "ENS 205", "ENS 208",
                "DSA 301", "ECON 301", "OPIM 390", "MKTG 414",
                "IE 445", "FIN 301"
            })
        },
        "Orhun Yavuz": {
            "year": 3,
            "courses": DEFAULT_COURSES.union({
                "CS 201", "CS 204", "CS 300", "CS 303", "CS 307",
                "MATH 201", "MATH 203", "MATH 204",
                "ECON 201", "HUM 201", "DSA 210"
            })
        },
        "Ahmet Ekiz": {
            "year": 3,
            "courses": DEFAULT_COURSES.union({
                "CS 201", "CS 204", "CS 300", "CS 303",
                "MATH 201", "MATH 203", "MATH 204",
                "ENS 205", "ENS 202", "MAT 314",
                "HUM 202", "ENS 203"
            })
        },
        "Finance Odaklı": {
            "year": 3,
            "courses": DEFAULT_COURSES.union({
                "MATH 201", "MATH 203", "MATH 306",
                "ECON 202", "ECON 204", "ECON 201",
                "ACC 201", "FIN 301", "FIN 401", "FIN 402",
                "MKTG 301", "HUM 202"
            })
        },
        "Duru Özsaygı": {
            "year": 2,
            "courses": DEFAULT_COURSES.union({
                "MATH 201", "MATH 203", "HUM 202",
                "ENS 205", "ENS 208"

            })
        },
        "Emir Vargör": {
            "year": 3,
            "courses": DEFAULT_COURSES.union({
                "MATH 201", "MATH 203", "HUM 202",
                "ENS 205", "ENS 203", "ENS 211",
                "CS 201", "DSA 210", "MATH 204",
                "NS 206"
            })
        }
    }
    
    selected_scenario = st.selectbox(
        "Senaryo Seç:",
        list(TEST_SCENARIOS.keys()),
        key="scenario_select",
        help="Test için önceden tanımlanmış transkript yükle"
    )
    
    if st.button("📥 Senaryoyu Yükle", use_container_width=True, key="load_scenario_btn"):
        scenario = TEST_SCENARIOS[selected_scenario]
        st.session_state.transcript = scenario["courses"].copy()
        
        # Year seçimini de güncelle
        if scenario["year"] != year:
            st.info(f"⚠️ Not: Sınıf otomatik olarak **{scenario['year']}** olarak değiştirildi.")
        
        logger.info(f"Test senaryosu yüklendi: {selected_scenario}")
        logger.info(f"Transkript: {len(st.session_state.transcript)} ders")
        st.success(f"✅ **{selected_scenario}** senaryosu yüklendi! ({len(scenario['courses'])} ders)")
        time.sleep(0.5)
        st.rerun()
    
    # Senaryo bilgisi
    with st.expander("ℹ️ Senaryo Açıklaması", expanded=False):
        scenario = TEST_SCENARIOS[selected_scenario]
        st.write(f"**Sınıf:** {scenario['year']}")
        st.write(f"**Ders Sayısı:** {len(scenario['courses'])}")
        st.write("**Dersler:**")
        st.code(", ".join(sorted(scenario['courses'])))
    
    # ========== TEST SENARYOLARI SONU ==========
    
    analyze_btn = st.button("Analiz Et 🚀", type="primary", use_container_width=True)
    
    if analyze_btn:
        logger.info("Analiz butonu tıklandı")
       

# -----------------------------------------------------------------------------
# 4. ANA EKRAN (SEKMELER)
# -----------------------------------------------------------------------------
st.header(f"🎓 {selected_major} Mezuniyet Analizi")

tab1, tab2, tab3 = st.tabs(["📊 Durum Raporu", "🤖 Akıllı Öneri", "🔍 Arama"])

# --- TAB 1: MEZUNİYET DURUMU ---
with tab1:
    if analyze_btn or st.session_state.transcript:
        logger.info("TAB 1: Mezuniyet Durumu Analizi Başlatıldı")
        
        taken_list = list(st.session_state.transcript)
        logger.info(f"Alınan dersler ({len(taken_list)}): {taken_list}")
        
        report = run_fens_audit(selected_major, taken_list, raw_data)
        
        if "Error" in report:
            logger.error(f"Audit hatası: {report['Error']}")
            st.error(report["Error"])
        else:
            logger.info("Audit başarıyla tamamlandı")
            
            # Yol Haritası
            st.subheader("🗺️ Yol Haritası")
            for step in report["Roadmap"]:
                if "🎉" in step: 
                    st.success(step, icon="🎉")
                elif "🚨" in step: 
                    st.error(step, icon="🚨")
                elif "Dikkat" in step: 
                    st.warning(step, icon="⚠️")
                else: 
                    st.info(step, icon="👉")
            
            st.divider()

            # İlerleme Kartları - DÜZELTILMIŞ VERSİYON
            def show_progress(title, data):
                """İyileştirilmiş ilerleme gösterimi (Nesting hatası çözüldü)"""
                taken = data.get("credits", 0)
                target = data.get("target", 1)
                pct = min(taken/target, 1.0) if target > 0 else 0
                icon = "✅" if pct >= 1.0 else "⏳"
                
                with st.expander(f"{icon} {title} (%{int(pct*100)})", expanded=pct<1.0):
                    st.progress(pct)
                    
                    # Metric gösterimi (expander içinde columns yerine direkt metric kullan)
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Alınan", f"{int(taken)} Kredi")
                    with col2:
                        st.metric("Hedef", f"{int(target)} Kredi")
                    with col3:
                        st.metric("Kalan", f"{int(max(0, target-taken))} Kredi")
                    
                    st.divider()
                    
                    # Alınanlar ve Eksikler - Columns KULLANMA (DİREKT CONTAINER KULLAN)
                    left_col, right_col = st.columns(2)
                    
                    with left_col:
                        st.markdown("**✅ Alınanlar:**")
                        if data["taken"]:
                            # Columns yerine direkt caption kullan
                            for course in sorted(data["taken"]):
                                st.caption(f"📌 {course}")
                        else:
                            st.caption("-")
                    
                    with right_col:
                        st.markdown("**❌ Eksikler/Notlar:**")
                        if "missing" in data and data["missing"]:
                            for m in data["missing"]:
                                st.error(f"Eksik: {m}")
                        elif taken < target:
                            st.warning(f"{int(target - taken)} kredi eksiğin var.")
                        if "note" in data and data["note"]:
                            st.info(data["note"])
                    
                    logger.debug(f"{title}: %{int(pct*100)} (Alınan: {int(taken)}/{int(target)})")

            # Kategorileri 2 sütunla göster (Expander DIŞINDAKi Columns)
            c1, c2 = st.columns(2)
            with c1:
                show_progress("Zorunlu Dersler", report["Required"])
                show_progress("Çekirdek (Core)", report["Core"])
            with c2:
                show_progress("Alan (Area)", report["Area"])
                show_progress("Üniversite & Serbest", report["University"]) 
            
            # Serbest Seçmeliler - tam genişlik
            show_progress("Serbest Seçmeliler (Free)", report["Free"])

            # Fakülte Kontrolü
            if "FacultyCheck" in report:
                fc = report["FacultyCheck"]
                if fc["status"] != "OK":
                    st.error(f"Fakülte Kuralı: {fc['message']}")
                    logger.warning(f"Fakülte kuralı uyarısı: {fc['message']}")
                else:
                    st.success("Fakülte Dağılımı: Uygun")
                    logger.info("Fakülte dağılımı uygun")

# --- TAB 2: AKILLI ÖNERİ ---
with tab2:
    st.subheader(f"📅 {term} Dönemi Tavsiyeleri")
    
    logger.info("TAB 2: Akıllı Öneri Sayfası Açıldı")
    
    # Keyword Seçimi
    if keyword_map:
        target_focus = st.selectbox(
            "İlgi Alanı / Odak:", 
            list(keyword_map.keys()),
            help="Önerileri belirlemek için ilgi alanınızı seçin"
        )
        active_keys = keyword_map[target_focus]
        logger.info(f"Seçilen ilgi alanı: {target_focus}")
    else:
        st.warning("Keyword verisi bulunamadı, varsayılan liste kullanılıyor.")
        logger.warning("Keyword map boş, fallback kullanılıyor")
        
        fallback_kws = {
            "Genel": "Engineering Science", 
            "CS": "Software AI"
        }
        target_focus = st.selectbox("İlgi Alanı:", list(fallback_kws.keys()))
        active_keys = fallback_kws[target_focus]
    
    if st.button("Önerileri Getir", type="primary"):
        if prereq_df.empty:
            st.error("⚠️ CSV Dosyaları Eksik! (Course Data)")
            logger.error("prereq_df boş - Recommender çalıştırılamıyor")
        else:
            with st.spinner("Öneriler hesaplanıyor..."):
                logger.info("="*70)
                logger.info("ÖNERİ MOTORU BAŞLATILDI")
                logger.info("="*70)
                
                # ADIM 1: SCHEDULE FİLTRESİ
                active_codes = []
                schedule_available = False
                
                logger.info(f"\nADIM 1: Schedule filtreleme ({term} dönemi)")

                if not sched_df.empty and 'Term' in sched_df.columns:
                    # Case-insensitive filtreleme
                    active_courses = sched_df[
                        sched_df['Term'].astype(str).str.contains(term, case=False, na=False)
                    ]
                    if not active_courses.empty:
                        active_codes = active_courses['Course Code'].unique()
                        schedule_available = True
                        logger.info(f"Schedule'de {len(active_codes)} aktif ders bulundu")
                    else:
                        logger.warning(f"Schedule'de '{term}' dönemine ait ders bulunamadı")
                else:
                    logger.warning("Schedule verisi boş veya 'Term' sütunu yok")

                # ADIM 2: PREREQ MERGE & FALLBACK
                filtered_catalog = pd.DataFrame()
                
                logger.info("\nADIM 2: Katalog filtreleme")
                
                if schedule_available:
                    filtered_catalog = prereq_df[
                        prereq_df['Course Code'].isin(active_codes)
                    ].copy()
                    logger.info(f"Schedule ile eşlenen dersler: {len(filtered_catalog)}")

                # Fallback durumu
                if filtered_catalog.empty:
                    if schedule_available:
                        st.warning(
                            f"⚠️ Schedule'de {term} dersleri bulundu ama Katalogda eşleşmedi. "
                            "Genel katalog kullanılıyor."
                        )
                        logger.warning("Schedule ile Katalog eşleşmedi, fallback aktif")
                    else:
                        st.info(
                            f"📌 {term} dönemi için program verisi bulunamadı. "
                            "Genel katalogdan öneri yapılıyor."
                        )
                        logger.info("Schedule bulunamadı, fallback aktif")
                    
                    filtered_catalog = prereq_df.copy()
                    logger.info(f"Fallback aktivasyon - katalog boyutu: {len(filtered_catalog)}")

                # --- AÇILMA SIKLIĞI (NADİR DERS) HESABI ---
                logger.info("\nADIM 3: Açılma sıklığı hesabı")
                
                if not sched_df.empty and 'Term' in sched_df.columns:
                    counts = sched_df.groupby('Course Code')['Term'].nunique()
                    filtered_catalog['Opening_Terms'] = filtered_catalog['Course Code'].map(counts).fillna(2)
                    logger.info("Opening_Terms hesaplandı")
                else:
                    filtered_catalog['Opening_Terms'] = 2
                    logger.info("Opening_Terms varsayılan değere (2) ayarlandı")

                # ADIM 4: AUDIT & 5 KATEGORİYİ AYIRMA (GÜNCELLENMIŞ)
                logger.info("\nADIM 4: Audit çalıştırma ve 5 kategoriyi ayırma")
                
                curr_audit = run_fens_audit(selected_major, list(st.session_state.transcript), raw_data)
                
                # 5 kategoriyi ayır
                audit_data = {
                    'required': set(),      # Zorunlu dersler
                    'university': set(),    # Üniversite şartı dersler
                    'core': set(),          # Çekirdek (Core) dersler
                    'area': set(),          # Alan (Area) dersler
                }
                
                if "Error" not in curr_audit:
                    # Required (Zorunlu) - eksik zorunlu dersler
                    audit_data['required'].update(curr_audit['Required'].get('missing', []))
                    logger.info(f"Required dersler: {len(audit_data['required'])}")
                    
                    # University (Üniversite şartı) - üniversite şartı dersler
                    audit_data['university'].update(curr_audit['University'].get('missing', []))
                    logger.info(f"University dersler: {len(audit_data['university'])}")
                    
                    # Core (Çekirdek) - çekirdek/core electives
                    core_list = raw_data[selected_major].get('requirements', {}).get('core_electives', [])
                    audit_data['core'].update([c['code'] for c in core_list])
                    logger.info(f"Core dersler: {len(audit_data['core'])}")
                    
                    # Area (Alan) - alan seçmelileri
                    area_list = raw_data[selected_major].get('requirements', {}).get('area_electives', [])
                    audit_data['area'].update([c['code'] for c in area_list])
                    logger.info(f"Area dersler: {len(audit_data['area'])}")
                    
                else:
                    logger.warning(f"Audit hatası: {curr_audit['Error']}")
                    logger.info("Audit başarısız, dersler Free kategorisine atandı")

                # ADIM 5: RECOMMENDER
                logger.info("\nADIM 5: Recommender çağrısı")
                
                try:
                    # Normalize keywords
                    normalized_kw = active_keys if isinstance(active_keys, str) else normalize_keywords(active_keys)
                    logger.info(f"Keywords normalize edildi: {normalized_kw}")
                    
                    recs, stats = get_recommendations_with_stats(
                        catalog_df=filtered_catalog, 
                        student_params={
                            'year': year, 
                            'term': term, 
                            'level': "Lisans", 
                            'taken': list(st.session_state.transcript)
                        },
                        audit_data=audit_data,  # ✅ Yeni yapı
                        keywords=normalized_kw
                    )
                    
                    logger.info(f"{len(recs)} adet ders önerisi üretildi")
                    logger.info(f"Kategoriye göre dağılım: {stats['by_category']}")
                    
                    if not recs.empty:
                        st.success(f"✅ {stats['total_recommended']} ders önerildi!")
                        
                        # İstatistikler
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Toplam Öneri", stats['total_recommended'])
                        with col2:
                            st.metric("Ortalama Skor", f"{stats['avg_score']:.1f}")
                        with col3:
                            st.metric("En Yüksek Skor", f"{stats['max_score']:.0f}")
                        with col4:
                            st.metric("En Düşük Skor", f"{stats['min_score']:.0f}")
                        
                        st.divider()
                        
                        # Kategoriye göre grup gösterimi
                        if stats['by_category']:
                            st.subheader("📚 Önerilen Dersler")
                            
                            # ÖNCELIK SIRASI: Zorunlu > Üniversite > Core İlgili > Core > Area İlgili > Area > Stratejik > İlgi Alanı > Genel > Alan Dışı
                            category_priority = {
                                "🔴 Kritik Zorunlu": 1,
                                "🟠 Üniversite Şartı": 2,
                                "🟢 Çekirdek & İlgi Alanı": 3,
                                "🔵 Çekirdek (Core)": 4,
                                "🟢 Alan & İlgi Alanı": 5,
                                "🟡 Alan (Area)": 6,
                                "🟣 Stratejik (Zincir)": 7,
                                "🟢 İlgi Alanı": 8,
                                "⚪ Genel Seçmeli": 9,
                                "🚫 Alan Dışı": 10,
                            }
                            
                            categories = sorted(
                                recs['Category'].unique(),
                                key=lambda x: category_priority.get(x, 99)
                            )
                            
                            # Kategori açıklamaları
                            category_descriptions = {
                                "🔴 Kritik Zorunlu": "Mezuniyet için mutlak şart olan dersler",
                                "🟠 Üniversite Şartı": "Üniversite genelinde zorunlu olan dersler",
                                "🟢 Çekirdek & İlgi Alanı": "Çekirdek ders + Seçili odak alanına uygun",
                                "🔵 Çekirdek (Core)": "Bölümün temel/çekirdek eğitim dersleri",
                                "🟢 Alan & İlgi Alanı": "Alan dersi + Seçili odak alanına uygun",
                                "🟡 Alan (Area)": "Seçili alan içinde önemli olan dersler",
                                "🟣 Stratejik (Zincir)": "Diğer derslerin ön koşulu olan dersler",
                                "🟢 İlgi Alanı": "Seçili odak alanına uygun serbest dersler",
                                "⚪ Genel Seçmeli": "Genel seçmeli dersler",
                                "🚫 Alan Dışı": "Önerilen alan dışındaki dersler",
                            }
                            
                            for category in categories:
                                category_recs = recs[recs['Category'] == category]
                                
                                # Önceliğine göre expanded durumu (1-6: açık, 7-10: kapalı)
                                is_high_priority = category_priority.get(category, 99) <= 6
                                
                                with st.expander(
                                    f"{category} ({len(category_recs)} ders)", 
                                    expanded=is_high_priority
                                ):
                                    # Kategori açıklaması
                                    st.caption(category_descriptions.get(category, ""))
                                    
                                    st.divider()
                                    
                                    # Tablo gösterimi
                                    display_df = category_recs[[
                                        'Course Code', 
                                        'Course Name', 
                                        'Final_Score', 
                                        'Explanation'
                                    ]].reset_index(drop=True).copy()
                                    
                                    st.dataframe(
                                        display_df,
                                        column_config={
                                            "Final_Score": st.column_config.ProgressColumn(
                                                "Puan", 
                                                format="%d", 
                                                min_value=0, 
                                                max_value=100
                                            ),
                                            "Course Code": st.column_config.TextColumn(
                                                "Ders Kodu",
                                                width="small"
                                            ),
                                            "Course Name": st.column_config.TextColumn(
                                                "Ders Adı",
                                                width="medium"
                                            ),
                                            "Explanation": st.column_config.TextColumn(
                                                "Neden?",
                                                width="large"
                                            ),
                                        },
                                        hide_index=True,
                                        use_container_width=True
                                    )
                                    
                                    st.divider()
                                    
                                    # Hızlı ekleme butonları
                                    st.write("**➕ Dersleri Ekle:**")
                                    
                                    # Ders sayısına göre dinamik sütun sayısı
                                    num_courses = len(category_recs)
                                    if num_courses == 1:
                                        cols_count = 1
                                    elif num_courses <= 3:
                                        cols_count = num_courses
                                    else:
                                        cols_count = 3
                                    
                                    cols = st.columns(cols_count)
                                    for idx, (_, row) in enumerate(category_recs.iterrows()):
                                        with cols[idx % cols_count]:
                                            if st.button(
                                                f"➕ {row['Course Code']}", 
                                                key=f"add_{row['Course Code']}_{category}_{idx}",
                                                use_container_width=True
                                            ):
                                                st.session_state.transcript.add(row['Course Code'])
                                                logger.info(f"Ders öneri ile eklendi: {row['Course Code']}")
                                                st.success(f"✅ {row['Course Code']} eklendi!")
                                                time.sleep(0.3)
                                                st.rerun()
                        
                        # --- EN İYİ 5 DERS (Top Recommendations) ---
                        if stats['top_5_courses']:
                            st.divider()
                            st.subheader("🏆 En İyi 5 Ders Önerisi")
                            st.caption("Puanlandırma ve uygunluk açısından en iyi seçenekler")
                            
                            for i, course in enumerate(stats['top_5_courses'], 1):
                                # Renk kodlaması
                                if i == 1:
                                    badge = "🥇"
                                elif i == 2:
                                    badge = "🥈"
                                elif i == 3:
                                    badge = "🥉"
                                else:
                                    badge = f"#{i}"
                                
                                col1, col2, col3, col4 = st.columns([0.5, 1.5, 3, 1.5])
                                
                                with col1:
                                    st.metric(badge, f"{course['Final_Score']:.0f}", label_visibility="collapsed")
                                
                                with col2:
                                    st.write(f"**{course['Course Code']}**")
                                
                                with col3:
                                    st.write(course['Course Name'])
                                
                                with col4:
                                    if st.button(
                                        "➕ Ekle", 
                                        key=f"top_add_{course['Course Code']}_{i}",
                                        use_container_width=True
                                    ):
                                        st.session_state.transcript.add(course['Course Code'])
                                        logger.info(f"En iyi 5'ten ders eklendi: {course['Course Code']}")
                                        st.success(f"✅ {course['Course Code']} eklendi!")
                                        time.sleep(0.3)
                                        st.rerun()

                    else:
                        st.warning("⚠️ Kriterlere uygun ders bulunamadı.")
                        logger.warning("Recommender hiç ders öneremedi")
                        
                except Exception as e:
                    logger.error(f"Recommender hatası: {e}", exc_info=True)
                    st.error(f"❌ Recommender Hatası: {str(e)}")
                    
                    # Debug bilgisi
                    with st.expander("🔧 Debug Bilgisi"):
                        st.write(f"**Hata Türü:** {type(e).__name__}")
                        st.write(f"**Hata Mesajı:** {str(e)}")
                        st.code(f"filtered_catalog boyutu: {len(filtered_catalog)}")
                        st.code(f"audit_data: {audit_data}")
                
                logger.info("="*70)
                    
    # DETAYLI DEBUG KUTUSU
    with st.expander("🛠️ Geliştirici Bilgisi (Veri & Filtre Kontrolü)", expanded=False):
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("**📂 Veri Setleri**")
            st.write(f"Schedule Satır: `{len(sched_df) if not sched_df.empty else 0}`")
            st.write(f"Prereq Satır: `{len(prereq_df) if not prereq_df.empty else 0}`")
            st.write(f"Katalog Satır: `{len(catalog_df)}`")
            st.write(f"Audit Major: `{selected_major}`")
        
        with c2:
            st.markdown("**🗓️ Dönem Bilgisi**")
            st.write(f"Seçilen: `{term}`")
            if not sched_df.empty and 'Term' in sched_df.columns:
                unique_terms = sched_df['Term'].unique()
                st.write(f"Benzersiz Dönemler: `{list(unique_terms)[:5]}`...")
        
        st.divider()
        
        st.markdown("**🔍 Filtre Testi**")
        if not sched_df.empty and 'Term' in sched_df.columns:
            match_count = len(
                sched_df[sched_df['Term'].astype(str).str.contains(term, case=False, na=False)]
            )
            st.write(f"Schedule içinde **{term}** geçen kayıt sayısı: **{match_count}**")
            
            if match_count == 0:
                st.error("⚠️ Seçilen dönem Schedule dosyasında bulunamadı! Fallback (Genel Katalog) devreye girer.")
            else:
                st.success("✅ Dönem eşleşmesi başarılı.")
        else:
            st.error("⚠️ Schedule verisi boş veya 'Term' sütunu yok.")
        
        # Log dosyası gösterimi
        st.divider()
        st.markdown("**📜 Son Log Kayıtları**")
        try:
            with open("app.log", "r") as log_file:
                logs = log_file.readlines()
                st.text_area(
                    "Loglar:",
                    value="".join(logs[-30:]),  # Son 30 satır
                    height=200,
                    disabled=True
                )
        except FileNotFoundError:
            st.info("Log dosyası henüz oluşturulmadı.")

# --- TAB 3: GELİŞMİŞ ARAMA VE ZİNCİR ANALİZİ ---
with tab3:
    st.header("🔍 Ders Arama ve Zincir Analizi")
    
    col_left, col_right = st.columns([1, 2], gap="medium")
    
    # 1. HOCA ADI TEMİZLİĞİ (Güvenlik için burada da dursun)
    def clean_instructor_name_safe(name_str):
        if pd.isna(name_str) or str(name_str).strip() == "": return "Unknown"
        parts = str(name_str).replace('"', '').replace("'", "").split(',')
        cleaned = [" ".join(p.split()) for p in parts]
        return ", ".join([c for c in cleaned if c])

    # 2. VERİ KONTROLÜ VE HAZIRLIĞI
    # sched_df ana yükleyiciden 'Day' olarak gelebilir, kontrol edelim.
    if not sched_df.empty:
        search_df = sched_df.copy()
        
        # Hoca sütunu varsa temizle (Eğer ana yükleyicide yapılmadıysa burada yapılır)
        if 'Instructor' in search_df.columns:
            search_df['Instructor'] = search_df['Instructor'].apply(clean_instructor_name_safe)
            
        # SÜTUN ADI STANDARDI ('Days' varsa 'Day' yap)
        if 'Days' in search_df.columns:
            search_df = search_df.rename(columns={'Days': 'Day'})
    else:
        search_df = pd.DataFrame()

    # --- SOL PANEL: FİLTRELEME ---
    with col_left:
        st.subheader("Filtreler")
        kw = st.text_input("🔍 Ara (Kod veya Ad):", placeholder="Örn: MATH 101").upper()
        
        selected_term = []
        selected_instructor = []
        
        if not search_df.empty:
            # Dönem Listesi
            if 'Term' in search_df.columns:
                all_terms = sorted(search_df['Term'].dropna().unique())
                selected_term = st.multiselect("🗓️ Dönem:", all_terms)
            
            # Hoca Listesi
            if 'Instructor' in search_df.columns:
                all_instructors = sorted(search_df['Instructor'].dropna().unique())
                selected_instructor = st.multiselect("👨‍🏫 Öğretim Üyesi:", all_instructors)

        st.divider()
        
        # --- DERS SEÇİMİ ---
        if not search_df.empty:
            temp_df = search_df.copy()
            
            if kw:
                mask = temp_df.apply(lambda x: kw in str(x.values).upper(), axis=1)
                temp_df = temp_df[mask]
            
            if selected_term and 'Term' in temp_df.columns:
                temp_df = temp_df[temp_df['Term'].isin(selected_term)]
                
            if selected_instructor and 'Instructor' in temp_df.columns:
                temp_df = temp_df[temp_df['Instructor'].isin(selected_instructor)]
            
            # Sadece Ana Dersleri Bul (R/L/D Gizle)
            all_found = temp_df['Course Code'].dropna().unique()
            # Is_Main sütunu varsa onu kullan (Hızlandırıcı), yoksa manuel yap
            if 'Is_Main' in temp_df.columns:
                main_courses = sorted(temp_df[temp_df['Is_Main']]['Course Code'].unique())
            else:
                main_courses = sorted([c for c in all_found if not str(c).endswith(('R', 'L', 'D'))])
            
            # Fallback
            if not main_courses and len(all_found) > 0: 
                main_courses = sorted(all_found)

            st.markdown(f"**Bulunan Dersler: {len(main_courses)}**")
            
            if main_courses:
                selected_course_code = st.selectbox("👉 Ders Seç:", main_courses)
            else:
                selected_course_code = None
                if kw: st.warning("Ders bulunamadı.")
        else:
            selected_course_code = None

    # --- SAĞ PANEL ---
    with col_right:
        if selected_course_code:
            st.subheader(f"🕸️ {selected_course_code} - Analiz")
            
            tab_viz, tab_details = st.tabs(["Görsel Ağaç", "Ders Programı (Kart Görünümü)"])
            
            # 1. GÖRSEL AĞAÇ
            with tab_viz:
                if not prereq_df.empty:
                    try:
                        graph = generate_prereq_graph(selected_course_code, prereq_df)
                        if graph: st.graphviz_chart(graph, use_container_width=True)
                        else: st.info("Zincir grafiği oluşturulamadı.")
                    except: st.error("Grafik hatası.")
                else:
                    st.warning("Ön koşul verisi yok.")

            # 2. DERS PROGRAMI
            with tab_details:
                if not search_df.empty:
                    target_codes = [
                        selected_course_code, 
                        selected_course_code + 'R', 
                        selected_course_code + 'L', 
                        selected_course_code + 'D'
                    ]
                    details = search_df[search_df['Course Code'].isin(target_codes)].copy()

                    if selected_term and 'Term' in details.columns:
                        details = details[details['Term'].isin(selected_term)]
                    if selected_instructor and 'Instructor' in details.columns:
                        details = details[details['Instructor'].isin(selected_instructor)]

                    if not details.empty:
                        # --- [HATA DÜZELTME BURADA] ---
                        # Sütun adı 'Days' mi 'Day' mi?
                        day_col = 'Day' if 'Day' in details.columns else 'Days'
                        
                        # dropna işlemini dinamik sütun adıyla yap
                        # Eğer sütun hiç yoksa sadece Time ve Instructor'a bak
                        cols_to_check = ['Time', 'Instructor']
                        if day_col in details.columns:
                            cols_to_check.append(day_col)
                            
                        details = details.dropna(subset=cols_to_check)
                        details = details[details['Time'] != '']
                        
                        # Her halükarda standart 'Day' ismini kullanmaya devam et
                        if day_col != 'Day' and day_col in details.columns:
                            details = details.rename(columns={day_col: 'Day'})

                        # Gün İsimleri (Türkçeleştirme)
                        day_map = {'M': 'Pazartesi', 'T': 'Salı', 'W': 'Çarşamba', 'R': 'Perşembe', 'F': 'Cuma'}
                        if 'Day' in details.columns:
                            for c, n in day_map.items():
                                details['Day'] = details['Day'].astype(str).str.replace(c, n, regex=False)

                        # Satır Formatı
                        def format_line(row):
                            d = row.get('Day', '?')
                            t = row.get('Time', '?')
                            loc = row.get('Location', '')
                            if pd.isna(loc) or loc == '': loc = row.get('Room', '')
                            return f"📅 **{d}** | ⏰ {t} | 📍 `{loc}`"

                        details['Line_Str'] = details.apply(format_line, axis=1)

                        # Gruplama
                        grouped = details.groupby(
                            ['Term', 'Course Code', 'Section', 'CRN', 'Instructor'], 
                            as_index=False
                        ).agg({
                            'Line_Str': lambda x: sorted(list(set(x)))
                        })
                        
                        grouped = grouped.sort_values(by=['Course Code', 'Section'])

                        # Kartları Bas
                        st.markdown(f"### 📅 {selected_course_code} Program Listesi")
                        
                        for _, row in grouped.iterrows():
                            with st.container(border=True):
                                c1, c2 = st.columns([1, 2])
                                with c1:
                                    st.write(f"**{row['Course Code']}** - Şube: **{row['Section']}**")
                                    st.caption(f"CRN: {row['CRN']}")
                                with c2:
                                    st.write(f"👨‍🏫 {row['Instructor']}")
                                    st.caption(f"Dönem: {row['Term']}")
                                
                                st.divider()
                                for line in row['Line_Str']:
                                    st.markdown(line)
                                    
                    else:
                        st.warning("Bu filtrelere uygun aktif şube bulunamadı.")
                else:
                    st.info("Program verisi yok.")

                # Ön Koşullar
                st.divider()
                if not prereq_df.empty:
                    prereq_info = prereq_df[prereq_df['Course Code'] == selected_course_code]
                    
                    if not prereq_info.empty:
                        raw_prereq = prereq_info.iloc[0].get('Prerequisites')
                        
                        if pd.notna(raw_prereq) and str(raw_prereq).strip() != "":
                            st.info(f"**🔑 Ön Koşullar:** {raw_prereq}")
                        else:
                            pass
        else:
            st.info("👈 Analiz için soldan ders seçin.")