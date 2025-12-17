"""
=============================================================================
PROJE: SABANCI UNIVERSITY SMART ADVISOR
DOSYA: src/audit_engine.py
TANIM: FENS Fakültesi Mezuniyet Denetim Motoru (Audit Engine).
       Öğrenci transkriptini, bölüm kuralları ve kredi haritası ile 
       birleştirerek detaylı mezuniyet durumu ve yol haritası çıkarır.

YOL HARİTASI (ROADMAP):
1. UTILS .................. Dinamik kredi haritası ve havuz ayrıştırma araçları
2. LOGIC GATES ............ Math seçimi ve Fakülte dağılım kontrolleri
3. REPORTING .............. Raporlama ve Yol Haritası (Roadmap) üretimi
4. CORE AUDIT ............. Ana denetim döngüsü ve Şelale (Waterfall) mantığı
=============================================================================
"""

import re
import sys
import os

# Path ayarı (src modüllerini bulabilmesi için)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from major_rules import FENS_RULES
except ImportError:
    from src.major_rules import FENS_RULES

# =============================================================================
# 1. UTILS (YARDIMCI ARAÇLAR)
# =============================================================================

def create_course_credit_map(raw_data_json, major_code):
    """Ders kredilerini JSON'dan çekip {KOD: KREDI} sözlüğü oluşturur."""
    credit_map = {}
    reqs = raw_data_json.get(major_code, {}).get("requirements", {})
    all_lists = [
        reqs.get("university_courses", []),
        reqs.get("required_courses", []),
        reqs.get("core_electives", []),
        reqs.get("area_electives", []),
        reqs.get("free_electives", [])
    ]
    for lst in all_lists:
        for course in lst:
            try: credit = float(course.get('su_credit', 3.0))
            except: credit = 3.0
            credit_map[course['code']] = credit
            
    defaults = {
        "MATH 201": 3.0, "MATH 202": 3.0, "MATH 212": 4.0, 
        "MATH 101": 3.0, "MATH 102": 3.0, 
        "CS 201": 3.0, "DSA 210": 3.0, "CS 210": 3.0, "DSA 201": 3.0
    }
    for k, v in defaults.items():
        if k not in credit_map: credit_map[k] = v
    return credit_map

def get_credits(course_list, credit_map):
    """Listeki derslerin toplam kredisini hesaplar."""
    total = 0
    for c in course_list:
        clean_code = c.split(" (")[0]
        total += credit_map.get(clean_code, 3.0)
    return total

def get_faculty_counts(taken_courses, pools):
    """DSA için Fakülte (FENS, FASS, SBS) dağılımını sayar."""
    counts = {"FENS": 0, "FASS": 0, "SBS": 0}
    for course_raw in taken_courses:
        course = course_raw.split(" (")[0]
        if course in pools["FENS"]: counts["FENS"] += 1
        elif course in pools["FASS"]: counts["FASS"] += 1
        elif course in pools["SBS"]: counts["SBS"] += 1
    return counts

# =============================================================================
# 2. LOGIC GATES (MANTIK KAPILARI)
# =============================================================================

def check_math_requirement(taken_set, constraints):
    """Matematik kuralını kontrol eder (Bundle/Discard)."""
    logic = constraints.get("math_logic", {}).get("type")
    options = constraints.get("math_logic", {}).get("options", [])
    if not logic: return True, [], [] 

    if logic == "ONE_OF_DISCARD":
        found = [opt for opt in options if opt in taken_set]
        if found: return True, [found[0]], found[1:]
        return False, [], []

    elif logic == "BUNDLE_OR_DISCARD":
        for bundle in options:
            if len(bundle["courses"]) == 1 and bundle["courses"][0] in taken_set:
                 other_courses = []
                 for other_b in options:
                     if other_b != bundle: other_courses.extend(other_b["courses"])
                 discard = [c for c in other_courses if c in taken_set]
                 return True, bundle["courses"], discard
        for bundle in options:
            required = bundle["courses"]
            if set(required).issubset(taken_set):
                return True, required, []     
    return False, [], []

def check_sub_rules(taken_subset, rule, pools=None):
    """Alt kuralları kontrol eder."""
    if not rule: return True, ""
    if rule["type"] == "MIN_CREDITS":
        matches = [c for c in taken_subset if re.match(rule["filter_regex"], c)]
        total_cr = len(matches) * 3 
        if total_cr >= rule["min_value"]: return True, "✅ Kural Sağlandı"
        return False, f"⚠️ {rule['message']} (Şu an: {total_cr} kr)"
    elif rule["type"] == "MIN_COURSE_COUNT":
        count = 0
        for c in taken_subset:
            if c in rule.get("valid_list", []) or (rule.get("valid_regex") and re.match(rule["valid_regex"], c)):
                count += 1
        if count >= rule["min_value"]: return True, "✅ Kural Sağlandı"
        return False, f"⚠️ {rule['message']}"
    elif rule["type"] == "FACULTY_DISTRIBUTION":
        counts = get_faculty_counts(taken_subset, rule["pools"])
        min_req = rule["min_each"]
        missing = []
        for fac, count in counts.items():
            if count < min_req: missing.append(f"{fac} ({count}/{min_req})")
        if missing: return False, f"⚠️ Dağılım Eksik: {', '.join(missing)}"
        return True, "✅ Fakülte Dağılımı Tamam"
    return True, ""

def check_global_faculty_requirement(all_taken, rule):
    """DSA Global Fakülte Kuralı."""
    if not rule: return {}
    counts = get_faculty_counts(all_taken, rule["pools"])
    total = sum(counts.values())
    is_ok = True
    status_msg = []
    if total < rule["min_total"]:
        status_msg.append(f"Toplam Eksik ({total}/{rule['min_total']})")
        is_ok = False
    for fac, count in counts.items():
        if count < rule["min_each"]:
            status_msg.append(f"{fac} Eksik")
            is_ok = False
    return {
        "status": "OK" if is_ok else "Eksik",
        "message": ", ".join(status_msg) if status_msg else "Tamamlandı",
        "detail": f"{counts} (Top: {total})"
    }

# =============================================================================
# 3. REPORTING (RAPORLAMA VE YOL HARİTASI)
# =============================================================================

def generate_roadmap(report):
    """Rapor sonuçlarına göre öğrenciye adım adım yol haritası çıkarır."""
    roadmap = []
    
    req_missing = report["Required"]["missing"]
    if req_missing:
        roadmap.append(f"🚨 **Kritik:** Zorunlu derslerini tamamla: {', '.join(req_missing)}")
    
    uni = report["University"]
    if uni["credits"] < uni["target"]:
        roadmap.append(f"📚 **Üniversite:** {int(uni['target'] - uni['credits'])} kredi eksiğin var.")

    core = report["Core"]
    if core["credits"] < core["target"]:
        roadmap.append(f"⚙️ **Çekirdek (Core):** {int(core['target'] - core['credits'])} kredi daha lazım.")
    if "⚠️" in core["note"]:
        roadmap.append(f"   ↳ **Dikkat:** {core['note']}")

    area = report["Area"]
    if area["credits"] < area["target"]:
        roadmap.append(f"🌍 **Alan (Area):** {int(area['target'] - area['credits'])} kredi eksiğin var.")
    if "⚠️" in area["note"]:
        roadmap.append(f"   ↳ **Dikkat:** {area['note']}")

    if "FacultyCheck" in report and report["FacultyCheck"]["status"] != "OK":
        roadmap.append(f"🏛️ **Fakülte Dağılımı:** {report['FacultyCheck']['message']}")

    if not roadmap:
        roadmap.append("🎉 **Tebrikler!** Mezuniyet için tüm akademik şartları sağladın.")
    return roadmap

# =============================================================================
# 4. CORE AUDIT (ANA DENETİM DÖNGÜSÜ)
# =============================================================================

def run_fens_audit(major_code, taken_courses, raw_data_json):
    """Tüm kuralları ve verileri birleştirip hesap yapan ana fonksiyon."""
    if major_code not in FENS_RULES:
        return {"Error": "Bölüm kuralları bulunamadı."}
        
    rules = FENS_RULES[major_code]
    reqs_data = raw_data_json.get(major_code, {}).get("requirements", {})
    credit_map = create_course_credit_map(raw_data_json, major_code)
    taken_set = set(taken_courses)
    
    # --- YENİ: Kural Dosyasından HUM Kısıtlamasını Oku ---
    hum_rule = rules["constraints"].get("hum_restriction", None)

    # --- A. ÜNİVERSİTE DERSLERİ ---
    raw_uni_pool = [c['code'] for c in reqs_data.get("university_courses", [])]
    
    # HUM FİLTRESİ (HUM 3xx Üniversite sayılmasın!)
    uni_pool = []
    for c in raw_uni_pool:
        # Eğer FENS kuralı aktifse (ONLY_2XX) ve ders HUM ise:
        if hum_rule == "ONLY_2XX" and c.startswith("HUM") and not c.startswith("HUM 2"):
            continue # HUM 3xx, 4xx gibi dersleri üniversite havuzuna ALMA. (Free'ye düşsün)
        uni_pool.append(c)
            
    uni_set = set(uni_pool) # Kesişim kontrolü için set yap
    
    std_uni = [c for c in uni_pool if not c.startswith("HUM")]
    
    taken_u = [c for c in std_uni if c in taken_set]
    missing_u = [c for c in std_uni if c not in taken_set]
    
    # HUM 2xx Kontrolü (Özel Slot: Sadece 1 tane HUM 2xx sayılır)
    taken_hums = [c for c in taken_courses if c.startswith("HUM 2")]
    if taken_hums: taken_u.append(f"{taken_hums[0]} (HUM)")
    else: missing_u.append("HUM 2xx")
    
    u_credits = get_credits(taken_u, credit_map)
    report_u = {
        "taken": taken_u, "missing": missing_u, 
        "credits": u_credits, "target": rules["credits"]["university"]
    }

    # --- B. ZORUNLU DERSLER ---
    math_ok, math_taken, math_discard = check_math_requirement(taken_set, rules["constraints"])
    raw_reqs = [c['code'] for c in reqs_data.get("required_courses", [])]
    math_excludes = {"MATH 201", "MATH 202", "MATH 212"}
    
    # --- ZORUNLU FİLTRESİ (Çakışma Önleyici) ---
    pure_reqs = []
    for c in raw_reqs:
        # Math zaten özel hesaplanıyor, atla
        if c in math_excludes: continue
        
        # Eğer ders zaten Üniversite havuzunda varsa, Zorunlu'da gösterme (Overlap Fix)
        if c in uni_set: continue
        
        # HUM KURALI (Buraya da sızmış olabilir, temizle)
        if hum_rule == "ONLY_2XX" and c.startswith("HUM") and not c.startswith("HUM 2"):
            continue
            
        pure_reqs.append(c)
    
    taken_r = []
    missing_r = []
    special_overflow = None
    
    # IE Kuralı: CS 201 vs DSA 201
    if major_code == "IE":
        if "CS 201" in taken_set and "DSA 201" in taken_set:
            special_overflow = "CS 201"
            if "CS 201" in pure_reqs: pure_reqs.remove("CS 201")
            taken_r.append("DSA 201")
        elif "DSA 201" in taken_set and "CS 201" not in taken_set:
            if "CS 201" in pure_reqs: pure_reqs.remove("CS 201")
            taken_r.append("DSA 201")
    
    # DSA Kuralı: CS 210 vs DSA 210
    if major_code == "DSA":
        # Manuel Kontrol: JSON'dan eksik gelse bile düzelt
        has_dsa = "DSA 210" in taken_set
        has_cs = "CS 210" in taken_set
        
        if "DSA 210" in pure_reqs: pure_reqs.remove("DSA 210")
        if "CS 210" in pure_reqs: pure_reqs.remove("CS 210")
        
        if has_dsa: taken_r.append("DSA 210")
        elif has_cs: taken_r.append("CS 210")
        else: missing_r.append("DSA 210 / CS 210")

    for c in pure_reqs:
        if c in taken_set: taken_r.append(c)
        else: missing_r.append(c)
        
    if math_ok: taken_r.extend([f"{m} (Math)" for m in math_taken])
    else: missing_r.append(rules["constraints"]["math_logic"]["message"])
    
    r_credits = get_credits(taken_r, credit_map)
    report_r = {
        "taken": taken_r, "missing": missing_r,
        "credits": r_credits, "target": rules["credits"]["required"]
    }

    # --- C. SEÇMELİLER ---
    used = set(taken_u) | set(taken_r) | set(math_taken) | set(math_discard)
    used = {c.split(" (")[0] for c in used}
    
    if special_overflow and special_overflow in used: used.remove(special_overflow)
    remaining_pool = [c for c in taken_courses if c not in used]
    
    # C.1 Core
    core_codes = {c['code'] for c in reqs_data.get("core_electives", [])}
    if major_code == "IE": core_codes.add("CS 201")
    
    taken_core = [c for c in remaining_pool if c in core_codes]
    if special_overflow == "CS 201" and special_overflow not in taken_core:
        taken_core.append(special_overflow)

    curr_core_cr = get_credits(taken_core, credit_map)
    req_core_cr = rules["credits"]["core"]
    
    core_overflow = []
    if curr_core_cr > req_core_cr:
        accumulated = 0
        keep_core = []
        for c in taken_core:
            cr = credit_map.get(c, 3.0)
            if accumulated + cr <= req_core_cr + 2:
                accumulated += cr
                keep_core.append(c)
            else: core_overflow.append(c)
        taken_core = keep_core
        curr_core_cr = accumulated

    sub_status, sub_msg = check_sub_rules(taken_core, rules["constraints"].get("core_sub_rule"))
    if "core_distribution" in rules["constraints"]:
        sub_status, sub_msg = check_sub_rules(taken_core, rules["constraints"]["core_distribution"], rules["constraints"]["core_distribution"].get("pools"))

    report_core = {
        "taken": taken_core, "credits": curr_core_cr, "target": req_core_cr,
        "note": sub_msg, "status": "OK" if sub_status else "Eksik"
    }

    # C.2 Area
    used_in_core = set(taken_core)
    remaining_pool = [c for c in remaining_pool if c not in used_in_core] 
    area_codes = {c['code'] for c in reqs_data.get("area_electives", [])}
    
    taken_area = [c for c in remaining_pool if c in area_codes or c in core_overflow]
    curr_area_cr = get_credits(taken_area, credit_map)
    req_area_cr = rules["credits"]["area"]
    
    area_overflow = []
    if curr_area_cr > req_area_cr:
        accumulated = 0
        keep_area = []
        for c in taken_area:
            cr = credit_map.get(c, 3.0)
            if accumulated + cr <= req_area_cr + 2:
                accumulated += cr
                keep_area.append(c)
            else: area_overflow.append(c)
        taken_area = keep_area
        curr_area_cr = accumulated
        
    sub_status_area, sub_msg_area = check_sub_rules(taken_area, rules["constraints"].get("area_sub_rule"))
    report_area = {
        "taken": taken_area, "credits": curr_area_cr, "target": req_area_cr,
        "note": sub_msg_area
    }

    # C.3 Free
    used_in_area = set(taken_area)
    remaining_pool = [c for c in remaining_pool if c not in used_in_area] 
    taken_free = remaining_pool + area_overflow
    curr_free_cr = get_credits(taken_free, credit_map)
    
    report_free = {
        "taken": taken_free, "credits": curr_free_cr, "target": rules["credits"]["free"]
    }

    # --- RAPOR TOPLAMA ---
    final_report = {
        "University": report_u, "Required": report_r,
        "Core": report_core, "Area": report_area, "Free": report_free
    }
    
    if major_code == "DSA" and "faculty_requirement" in rules["constraints"]:
        valid_all = set(taken_courses) - set(math_discard)
        fac_rep = check_global_faculty_requirement(list(valid_all), rules["constraints"]["faculty_requirement"])
        final_report["FacultyCheck"] = fac_rep

    final_report["Roadmap"] = generate_roadmap(final_report)
    return final_report