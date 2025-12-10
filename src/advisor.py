import json

MAJOR_DATA = "undergrad_majors.json"
MINOR_DATA = "undergrad_minors.json"

major_data = MAJOR_DATA
minor_data = MINOR_DATA

class UniversityAdvisor:
    def __init__(self, major_data, minor_data):
        self.majors = self._flatten_programs(major_data)
        self.minors = self._flatten_programs(minor_data)

    def _flatten_programs(self, data):
        """Hiyerarşik JSON yapısını analiz için düz (flat) listeye çevirir."""
        flat_list = []
        for faculty in data['faculties']:
            for program in faculty['programs']:
                program['faculty_code'] = faculty['short_code']
                flat_list.append(program)
        return flat_list

    def find_program_by_keyword(self, query, search_type="all"):
        """
        Kullanıcının girdiği kelimeye göre (örn: 'AI', 'Money') program önerir.
        search_type: 'major', 'minor', veya 'all'
        """
        query_tokens = set(query.lower().split())
        results = []

        target_list = []
        if search_type == "major": target_list = self.majors
        elif search_type == "minor": target_list = self.minors
        else: target_list = self.majors + self.minors

        for prog in target_list:
            prog_keywords = set([k.lower() for k in prog.get('keywords', [])])
            prog_name_tokens = set(prog['name'].lower().split())
            
            keyword_match = len(query_tokens.intersection(prog_keywords))
            name_match = len(query_tokens.intersection(prog_name_tokens))
            
            score = (name_match * 5) + (keyword_match * 2) 

            if score > 0:
                results.append({
                    "program": prog['name'],
                    "type": "Major" if prog in self.majors else "Minor",
                    "score": score,
                    "matched_keywords": list(query_tokens.intersection(prog_keywords))
                })

        return sorted(results, key=lambda x: x['score'], reverse=True)

    def calculate_synergy(self, major_id):
        """
        Seçilen bir Major için en uyumlu Minor programlarını hesaplar.
        Uyumluluk: Ortak ders kodları ve ortak anahtar kelimelere göre belirlenir.
        """

        selected_major = next((m for m in self.majors if m['id'] == major_id), None)
        if not selected_major:
            return "Major ID not found."

        recommendations = []
        major_codes = set(selected_major.get('subject_codes', []))
        major_keywords = set(selected_major.get('keywords', []))

        for minor in self.minors:
            minor_codes = set(minor.get('subject_codes', []))
            minor_keywords = set(minor.get('keywords', []))

            code_intersection = major_codes.intersection(minor_codes)

            keyword_intersection = major_keywords.intersection(minor_keywords)

            synergy_score = (len(code_intersection) * 3) + (len(keyword_intersection) * 1)

            if synergy_score > 0:
                recommendations.append({
                    "minor_name": minor['name'],
                    "faculty": minor['faculty_code'],
                    "score": synergy_score,
                    "shared_codes": list(code_intersection),
                    "shared_topics": list(keyword_intersection)
                })

        return sorted(recommendations, key=lambda x: x['score'], reverse=True)
