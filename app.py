"""
=============================================================================
PROJE: SABANCI UNIVERSITY SMART ADVISOR
DOSYA: app.py
TANIM: Streamlit tabanlı ana web arayüzü.
DURUM: FINAL (Gereksiz importlar temizlendi, Yeni Recommender aktif).

YOL HARİTASI:
1. AYARLAR ................ Kütüphaneler ve Config
2. VERİ YÜKLEME ........... Standart ve Güvenli CSV Okuma
3. AUDIT MOTORU ........... Mezuniyet Kontrolü (Görselleştirme için)
4. ARAYÜZ (SIDEBAR) ....... Transkript Yöneticisi (Ekle/Çıkar)
5. ARAYÜZ (SEKMELER) ...... Denetim, Puanlı Öneri ve Arama
=============================================================================
"""

import streamlit as st
import pandas as pd
import json
import os
import re

from src.advisor import UniversityAdvisor
from src.recommender import get_recommendations

# =============================================================================
# 1. AYARLAR
# =============================================================================
st.set_page_config(page_title="SU Smart Advisor", page_icon="🎓", layout="wide")

# =============================================================================
# 2. VERİ YÜKLEME
# =============================================================================
@st.cache_data
def load_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Dosya Yolları
    major_path = os.path.join(base_dir, 'data', 'json', 'undergrad_majors.json')
    minor_path = os.path.join(base_dir, 'data', 'json', 'undergrad_minors.json')
    dsa_req_path = os.path.join(base_dir, 'data', 'json', 'dsa_requirements_full.json')
    catalog_path = os.path.join(base_dir, 'data', 'csv', 'course_full_data_v2.csv')
    schedule_path = os.path.join(base_dir, 'data', 'csv', 'active_schedule_master.csv')
    
    # JSON Yükleme
    majors = json.load(open(major_path, 'r', encoding='utf-8')) if os.path.exists(major_path) else {}
    minors = json.load(open(minor_path, 'r', encoding='utf-8')) if os.path.exists(minor_path) else {}
    dsa_reqs = json.load(open(dsa_req_path, 'r', encoding='utf-8')) if os.path.exists(dsa_req_path) else None
    
    # Katalog Yükleme
    if not os.path.exists(catalog_path):
        return majors, minors, dsa_reqs, pd.DataFrame()
        
    catalog_df = pd.read_csv(catalog_path)
    catalog_df.columns = [c.strip() for c in catalog_df.columns]
    catalog_df['Course Code'] = catalog_df['Course Code'].astype(str).str.strip().str.upper()
    
    if 'Term' in catalog_df.columns:
        catalog_df = catalog_df.drop(columns=['Term'])

    # Schedule Yükleme ve Birleştirme
    if os.path.exists(schedule_path):
        try:
            schedule_df = pd.read_csv(schedule_path)
            schedule_df.columns = [c.strip() for c in schedule_df.columns]
            
            if 'Course Code' in schedule_df.columns and 'Term' in schedule_df.columns:
                schedule_df['Course Code'] = schedule_df['Course Code'].astype(str).str.strip().str.upper()
                term_info = schedule_df.groupby('Course Code')['Term'].apply(
                    lambda x: ', '.join(sorted(set([str(i) for i in x if pd.notna(i)])))
                ).reset_index()
                catalog_df = pd.merge(catalog_df, term_info, on='Course Code', how='left')
                catalog_df['Term'] = catalog_df['Term'].fillna("Unknown")
            else:
                catalog_df['Term'] = 'Unknown'
        except:
            catalog_df['Term'] = 'Unknown'
    else:
        catalog_df['Term'] = 'Unknown'

    # Seviye (Level) Bilgisi Ekle
    def extract_level(code):
        try: return int(re.search(r"(\d+)", str(code)).group(1)) // 100
        except: return 0
    catalog_df['Level'] = catalog_df['Course Code'].apply(extract_level)

    return majors, minors, dsa_reqs, catalog_df

try:
    major_data, minor_data, dsa_requirements, courses_df = load_data()
    advisor = UniversityAdvisor(major_data, minor_data)
except Exception as e:
    st.error(f"Sistem başlatılırken hata: {e}")
    st.stop()

# =============================================================================
# 3. AUDIT MOTORU (Görselleştirme İçin - DÜZELTİLMİŞ versiyon)
# =============================================================================
def run_degree_audit(taken_courses, requirements):
    if not requirements: return None, 0
    
    report = {}
    reqs = requirements['requirements']
    total_su_completed = 0
    
    # --- 1. UNIVERSITY COURSES ---
    uc_data = reqs.get('university_courses', {})
    uc_objects = uc_data.get('course_objects', [])
    mandatory_uc = [c for c in uc_objects if not c['code'].startswith('HUM')]
    
    taken_uc = [c['code'] for c in mandatory_uc if c['code'] in taken_courses]
    missing_uc = [c['code'] for c in mandatory_uc if c['code'] not in taken_courses]
    
    taken_hums = [c for c in taken_courses if c.startswith('HUM 2')]
    if not taken_hums: missing_uc.append("HUM 2xx")
    
    uc_credits = sum([c['su_credit'] for c in mandatory_uc if c['code'] in taken_uc]) + (3 if taken_hums else 0)
    
    report['University Courses'] = {
        "taken": taken_uc + taken_hums[:1], 
        "missing": missing_uc,
        "progress": uc_credits / 41, 
        "credits_total": 41, 
        "credits_done": uc_credits # EKLENDİ
    }
    total_su_completed += uc_credits

    # --- 2. REQUIRED COURSES ---
    maj_data = reqs.get('major_required', {})
    maj_objects = maj_data.get('course_objects', [])
    
    group_cs = {'CS 210', 'DSA 210'}
    group_math = {'MATH 201', 'MATH 212'}
    pure_mandatory = [c for c in maj_objects if c['code'] not in group_cs and c['code'] not in group_math]
    
    taken_maj, missing_maj = [], []
    maj_credits = 0
    
    if group_cs.intersection(taken_courses):
        found = list(group_cs.intersection(taken_courses))[0]
        taken_maj.append(found)
        maj_credits += 3
    else: missing_maj.append("CS/DSA 210")
        
    if group_math.intersection(taken_courses):
        found = list(group_math.intersection(taken_courses))[0]
        taken_maj.append(found)
        maj_credits += 3
    else: missing_maj.append("MATH 201/212")
        
    for c in pure_mandatory:
        if c['code'] in taken_courses: 
            taken_maj.append(c['code'])
            maj_credits += c['su_credit']
        else: missing_maj.append(c['code'])
            
    report['Required Courses'] = {
        "taken": taken_maj, 
        "missing": missing_maj,
        "progress": maj_credits / 30, 
        "credits_total": 30, 
        "credits_done": maj_credits # EKLENDİ
    }
    total_su_completed += maj_credits

    # --- 3. ELECTIVES ---
    used = set(report['University Courses']['taken']) | set(report['Required Courses']['taken'])
    remaining = taken_courses - used
    
    # Core Electives
    core_pool = {c['code']: c['su_credit'] for c in reqs['core_electives'].get('pool_objects', [])}
    core_matches = [c for c in remaining if c in core_pool]
    core_cr = sum([core_pool[c] for c in core_matches])
    
    report['Core Electives'] = {
        "taken": core_matches, 
        "progress": min(core_cr / 27, 1.0), 
        "credits_total": 27, 
        "credits_done": core_cr # EKLENDİ
    }
    total_su_completed += core_cr
    
    # Area Electives
    remaining -= set(core_matches)
    area_pool = {c['code']: c['su_credit'] for c in reqs['area_electives'].get('pool_objects', [])}
    area_matches = [c for c in remaining if c in area_pool]
    area_cr = sum([area_pool[c] for c in area_matches])
    
    report['Area Electives'] = {
        "taken": area_matches, 
        "progress": min(area_cr / 12, 1.0), 
        "credits_total": 12, 
        "credits_done": area_cr # EKLENDİ
    }
    total_su_completed += area_cr
    
    # Free Electives
    remaining -= set(area_matches)
    free_cr = len(remaining) * 3
    
    report['Free Electives'] = {
        "taken": list(remaining), 
        "progress": min(free_cr / 15, 1.0), 
        "credits_total": 15, 
        "credits_done": free_cr # EKLENDİ
    }
    total_su_completed += free_cr
    
    return report, total_su_completed

# =============================================================================
# 4. SIDEBAR (Transkript Yöneticisi - Session State)
# =============================================================================
# Sidebar genel olarak sıkıntılı, arayüz düzgün gözükmüyor ve search engine problemini bir türlü çözemedim birkaç farklı sorting algorithm denedim ama olmadı. 
# Yine de temel işlevsellik var. Aynı zamanda ders ekleme UI pratik değil her seçiminde sonra mouse ile tıklamak gerekiyor klavye üstünden ekleme seçeneği daha yok.

with st.sidebar:
    st.header("⚙️ Öğrenci Profili")
    
    c1, c2 = st.columns(2)
    with c1: program_mode = st.selectbox("Program:", ["Data Science (DSA)", "CS (Demo)"])
    with c2: level_choice = st.selectbox("Seviye:", ["Lisans", "Yüksek Lisans"])
        
    c3, c4 = st.columns(2)
    with c3: student_year = st.selectbox("Sınıf:", [1, 2, 3, 4], index=1)
    with c4: current_term = st.selectbox("Dönem:", ["Fall", "Spring"])
    
    st.divider()
    st.subheader("📝 Transkript Yöneticisi") # BOZUK BİR ARA DÜZELT

    # Session State
    if 'transcript_set' not in st.session_state:
        if student_year >= 1:
            """
            default_codes = {
                "MATH 101", "MATH 102", "NS 101", "NS 102",
                "SPS 101", "SPS 102", "TLL 101", "TLL 102",
                "HIST 191", "HIST 192", "IF 100", "CIP 101N", "AL 102", "PROJ 201"
            }
            """
            default_codes = {
                "MATH 101", "MATH 102", "NS 101", "NS 102",
                "SPS 101", "SPS 102", "TLL 101", "TLL 102",
                "HIST 191", "HIST 192", "IF 100", "CIP 101N", "AL 102", "PROJ 201",
                "DSA 201", "DSA 210", "MATH 201", "MATH 203", "MATH 204", "MATH 306",
                "CS 201", "PSY 202", "MKTG 301", "ENS 205", "ENS 208", "HUM 202"
            }
        else: default_codes = set()
        st.session_state.transcript_set = default_codes

    # Sıralama Yardımcısı
    def get_sort_key(text):
        code = text.split(' - ')[0]
        match = re.match(r"([A-Z]+)\s*(\d+)", code)
        if match: return (match.group(1), int(match.group(2)))
        return (code, 0)

    # Liste Hazırlığı
    if not courses_df.empty:
        clean_df = courses_df[~courses_df['Course Code'].str.contains(r"\d[RL]$", regex=True)].copy()
        all_options = clean_df.apply(lambda x: f"{x['Course Code']} - {x['Course Name']}", axis=1).unique().tolist()
        all_options_sorted = sorted(all_options, key=get_sort_key)
    else: all_options_sorted = []

    # Ekleme Paneli
    with st.expander("➕ Ders Ekle", expanded=True):
        taken_codes = st.session_state.transcript_set
        available_options = [opt for opt in all_options_sorted if opt.split(' - ')[0] not in taken_codes]
        
        selected_to_add = st.selectbox("Ders Seç:", options=available_options, placeholder="Ara...", label_visibility="collapsed")
        
        if st.button("Listeye Ekle", type="secondary", use_container_width=True):
            if selected_to_add:
                st.session_state.transcript_set.add(selected_to_add.split(' - ')[0])
                st.rerun()

    # Çıkarma Paneli
    if st.session_state.transcript_set:
        with st.expander("➖ Ders Çıkar", expanded=False):
            current_taken_list = sorted(
                [opt for opt in all_options_sorted if opt.split(' - ')[0] in st.session_state.transcript_set],
                key=get_sort_key
            )
            selected_to_remove = st.selectbox("Silinecek:", options=current_taken_list, label_visibility="collapsed")
            
            if st.button("Listeden Sil", type="primary", use_container_width=True):
                if selected_to_remove:
                    st.session_state.transcript_set.discard(selected_to_remove.split(' - ')[0])
                    st.rerun()

    # Tablo Gösterimi
    st.caption(f"📚 Alınan Dersler ({len(st.session_state.transcript_set)})")
    if st.session_state.transcript_set:
        taken_list_data = []
        for code in st.session_state.transcript_set:
            name_row = courses_df[courses_df['Course Code'] == code]
            course_name = name_row.iloc[0]['Course Name'] if not name_row.empty else "Unknown"
            taken_list_data.append({"Kod": code, "Ders Adı": course_name})
        
        transcript_df = pd.DataFrame(taken_list_data)
        transcript_df['S'] = transcript_df['Kod'].str.extract(r'([A-Z]+)')
        transcript_df['N'] = transcript_df['Kod'].str.extract(r'(\d+)').fillna(0).astype(int)
        transcript_df = transcript_df.sort_values(by=['S', 'N']).drop(columns=['S', 'N'])
        
        st.dataframe(transcript_df, hide_index=True, use_container_width=True, height=300)
    else: st.info("Listeniz boş.")

    taken_courses = st.session_state.transcript_set

# =============================================================================
# 5. ANA ARAYÜZ (SEKMELER)
# =============================================================================
st.title("🎓 Sabancı Akıllı Danışman")
tab_audit, tab_rec, tab_search = st.tabs(["📊 Mezuniyet Durumu", "🤖 Ders Önerisi", "🔍 Bölüm Arama"])

# --- TAB 1: MEZUNİYET DURUMU (KeyError Çözülmüş) ---
with tab_audit:
    if "DSA" in program_mode and dsa_requirements:
        audit_report, total_credits = run_degree_audit(taken_courses, dsa_requirements)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Kredi", f"{total_credits} / 125", delta=125-total_credits, delta_color="inverse")
        c2.metric("Tamamlanan", len(taken_courses))
        c3.metric("Zorunlu Eksik", len(audit_report['Required Courses']['missing']) + len(audit_report['University Courses']['missing']), delta_color="inverse")
        
        st.divider()
        for cat, data in audit_report.items():
            icon = "✅" if data['progress'] >= 1.0 else "⏳"
            with st.expander(f"{icon} {cat} (%{int(data['progress']*100)})", expanded=data['progress'] < 1.0):
                st.progress(data['progress'])
                
                # İki Kolon: Alınanlar ve Eksikler
                col_taken, col_missing = st.columns(2)
                with col_taken:
                    st.caption("✅ **Alınanlar**")
                    if data['taken']: st.success(", ".join(data['taken']))
                    else: st.info("Yok")
                
                with col_missing:
                    st.caption("❌ **Eksikler / Kalanlar**")
                    if data.get('missing'): 
                        st.error(", ".join(data['missing']))
                    elif data['credits_total'] > data['credits_done']: 
                        gap = data['credits_total'] - data['credits_done']
                        st.warning(f"{gap} kredi açığı var.")
                    else: 
                        st.write("Tamamlandı 🎉")

    else:
        st.info("Bu modül sadece DSA için aktiftir.")

# --- TAB 2: ÖNERİ MOTORU (Dinamik) ---
with tab_rec:
    st.header(f"📅 {current_term} Dönemi Tavsiyeleri")
    all_progs = {f"{p['name']} ({m['short_code']})": {'keys': p['keywords'], 'codes': p['subject_codes']} 
                 for m in major_data.get('faculties', []) for p in m['programs']}
    target_focus = st.selectbox("İlgi Alanı Seç:", list(all_progs.keys()))
    active_keys = all_progs[target_focus]['keys']
    
    if st.button("Analizi Başlat", type="primary"):
        with st.spinner('Müfredat, Ön Koşullar ve Yapay Zeka çalışıyor...'):
            audit_report, _ = run_degree_audit(taken_courses, dsa_requirements)
            audit_data = {'critical': set(), 'pool': set()}
            if audit_report:
                audit_data['critical'].update(audit_report['Required Courses']['missing'])
                audit_data['critical'].update(audit_report['University Courses']['missing'])
                audit_data['pool'].update([c['code'] for c in dsa_requirements['requirements']['core_electives']['pool_objects']])

            recs = get_recommendations(
                courses_df, 
                {'year': student_year, 'term': current_term, 'level': level_choice, 'taken': taken_courses},
                audit_data, 
                " ".join(active_keys)
            )
            
            if not recs.empty:
                st.success(f"Akademik öncelik ve ilgi alanına göre {len(recs)} ders sıralandı.")
                
                st.dataframe(
                    # 'Explanation' sütununu buraya ekledik
                    recs[['Course Code', 'Course Name', 'Category', 'Final_Score', 'Explanation']],
                    column_config={
                        "Category": st.column_config.TextColumn("Durum", width="small"),
                        "Final_Score": st.column_config.ProgressColumn("Öncelik", format="%d", min_value=0, max_value=100),
                        # Explanation sütununu 'Neden?' başlığıyla gösteriyoruz
                        "Explanation": st.column_config.TextColumn("Neden Önerildi?", width="large"),
                        "Course Name": st.column_config.TextColumn("Ders Adı", width="medium")
                    },
                    hide_index=True
                )
            else:
                st.warning("Bu kriterlere uygun ders bulunamadı.")


# --- TAB 3: ARAMA ---
with tab_search:
    st.header("Bölüm Keşfi")
    kw = st.text_input("Anahtar Kelime:")
    if kw:
        results = advisor.find_program_by_keyword(kw)
        for res in results:
            st.write(f"**{res['program']}** - Skor: {res['score']}")