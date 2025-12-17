"""
FENS Fakültesi Bölüm Kuralları Veritabanı (v1.5 - HUM 2xx Fix)
Kapsam: CS, EE, IE, ME, MAT, BIO, DSA
"""

# --- YARDIMCI LİSTELER (DSA İÇİN) ---
FENS_POOL = [
    "CHEM 212", "CS 201", "CS 204", "CS 210", "DSA 210", "EE 200", "EE 202",
    "ENS 201", "ENS 202", "ENS 203", "ENS 204", "ENS 205", "ENS 206", 
    "ENS 207", "ENS 208", "ENS 209", "ENS 210", "ENS 211", "ENS 214", "ENS 216",
    "MAT 204", "MATH 201", "MATH 202", "MATH 203", "MATH 204", "MATH 212",
    "NS 201", "NS 207", "NS 213", "NS 214", "NS 216", "NS 218", "PHYS 113", "PHYS 211"
]

FASS_POOL = [
    "ANTH 214", "ANTH 255", "FILM 231", "LIT 212", "ECON 201", "ECON 202", 
    "ECON 204", "HART 292", "IR 201", "POLS 250", "SOC 201", 
    "VA 201", "VA 202", "VA 203", "VA 204"
]

SBS_POOL = ["ACC 201", "MKTG 301", "ORG 301"]

FENS_RULES = {
    "CS": {
        "credits": {"total_su": 125, "university": 41, "required": 30, "core": 31, "area": 9, "free": 15},
        "constraints": {
            "hum_restriction": "ONLY_2XX", # <--- YENİ KURAL
            "math_logic": {"type": "ONE_OF_DISCARD", "options": ["MATH 201", "MATH 212"], "message": "MATH 201 veya 212'den sadece biri sayılır."},
            "overflow_chain": ["core", "area", "free"]
        }
    },
    "EE": {
        "credits": {"total_su": 125, "university": 41, "required": 35, "core": 25, "area": 9, "free": 15},
        "constraints": {
            "hum_restriction": "ONLY_2XX", # <--- YENİ KURAL
            "math_logic": {"type": "BUNDLE_OR_DISCARD", "options": [{"courses": ["MATH 212"], "count_as_credits": 4}, {"courses": ["MATH 201", "MATH 202"], "count_as_credits": 6}], "message": "MATH 212 veya (201+202) paketi."},
            "core_sub_rule": {"type": "MIN_CREDITS", "filter_regex": r"^EE\s+4", "min_value": 9, "message": "Çekirdek havuzunda en az 9 kredi EE 4xx dersi olmalı."},
            "area_sub_rule": {"type": "MIN_COURSE_COUNT", "valid_list": ["CS 300", "CS 401", "CS 412", "ME 303", "PHYS 302", "PHYS 303"], "valid_regex": r"^EE\s+48", "min_value": 1, "message": "Alan seçmelide özel listeden ders al."},
            "overflow_chain": ["core", "area", "free"]
        }
    },
    "IE": {
        "credits": {"total_su": 125, "university": 41, "required": 31, "core": 29, "area": 9, "free": 15},
        "constraints": {
            "hum_restriction": "ONLY_2XX", # <--- YENİ KURAL
            "math_logic": {"type": "ONE_OF_DISCARD", "options": ["MATH 201", "MATH 212"], "message": "MATH 201 veya 212."},
            "cs_logic": {"type": "ONE_OF_OVERFLOW_TO_CORE", "options": ["CS 201", "DSA 201"], "priority": "DSA 201", "overflow_course": "CS 201", "message": "İkisi varsa CS 201 Core sayılır."},
            "overflow_chain": ["core", "area", "free"]
        }
    },
    "ME": {
        "credits": {"total_su": 125, "university": 41, "required": 34, "core": 26, "area": 9, "free": 15},
        "constraints": {
            "hum_restriction": "ONLY_2XX", # <--- YENİ KURAL
            "math_logic": {"type": "BUNDLE_OR_DISCARD", "options": [{"courses": ["MATH 212"], "count_as_credits": 4}, {"courses": ["MATH 201", "MATH 202"], "count_as_credits": 6}], "message": "MATH 212 veya (201+202) paketi."},
            "overflow_chain": ["core", "area", "free"]
        }
    },
    "MAT": {
        "credits": {"total_su": 125, "university": 41, "required": 26, "core": 34, "area": 9, "free": 15},
        "constraints": {
            "hum_restriction": "ONLY_2XX", # <--- YENİ KURAL
            "math_logic": {"type": "ONE_OF_DISCARD", "options": ["MATH 212", "MATH 202"], "message": "MATH 212 veya MATH 202."},
            "overflow_chain": ["core", "area", "free"]
        }
    },
    "BIO": {
        "credits": {"total_su": 127, "university": 41, "required": 33, "core": 29, "area": 9, "free": 15},
        "constraints": {
            "hum_restriction": "ONLY_2XX", # <--- YENİ KURAL
            "overflow_chain": ["core", "area", "free"]
        }
    },
    "DSA": {
        "credits": {"total_su": 125, "university": 41, "required": 30, "core": 27, "area": 12, "free": 15},
        "constraints": {
            "hum_restriction": "ONLY_2XX", # <--- YENİ KURAL
            "math_logic": {"type": "ONE_OF_DISCARD", "options": ["MATH 201", "MATH 212"], "message": "MATH 201 veya 212."},
            "intro_logic": {"type": "ONE_OF_TARGET", "options": ["DSA 210", "CS 210"], "message": "DSA 210 veya CS 210 gereklidir."},
            "core_distribution": {"type": "FACULTY_DISTRIBUTION", "pools": {"FENS": FENS_POOL, "FASS": FASS_POOL, "SBS": SBS_POOL}, "min_each": 3, "message": "Core havuzunda FENS, FASS ve SBS'den en az 3'er ders olmalı."},
            "faculty_requirement": {"type": "GLOBAL_FACULTY_CHECK", "pools": {"FENS": FENS_POOL, "FASS": FASS_POOL, "SBS": SBS_POOL}, "min_total": 5, "min_each": 1, "message": "Toplam 5 Fakülte dersi (Min 1 her birinden)."},
            "overflow_chain": ["core", "area", "free"]
        }
    }
}