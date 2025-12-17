"""
=============================================================================
MODÜL: Utilities
DOSYA: src/utils.py
TANIM: Karmaşık JSON veri yapılarından (Majors/Minors) anahtar kelime
       ve program bilgilerini ayıklayan yardımcı fonksiyonlar.
=============================================================================
"""

import graphviz
import pandas as pd
import re
import logging

def extract_program_keywords(json_data):
    """
    undergrad_majors.json veya minors.json dosyasını tarar.
    Çıktı Formatı:
    {
        "Computer Science (FENS)": "software algo ai...",
        "Finance (SBS)": "money bank economy..."
    }
    """
    if not json_data or 'faculties' not in json_data:
        return {}

    mapping = {}
    
    for faculty in json_data['faculties']:
        fac_code = faculty.get('short_code', 'GEN')
        
        for program in faculty.get('programs', []):
            # Program Adı
            label = f"{program['name']} ({fac_code})"
            
            # Veri Toplama: Keywords + Subject Codes
            keywords = program.get('keywords', [])
            subjects = program.get('subject_codes', [])
            
            # Hepsini tek bir string yap (ML motoru için)
            # Örn: "CS ENS software algorithm data..."
            full_text = " ".join(subjects + keywords)
            
            mapping[label] = full_text.lower()
            
    return mapping

def merge_keywords(*maps):
    """Birden fazla keyword sözlüğünü (Major + Minor) birleştirir."""
    final_map = {}
    for m in maps:
        final_map.update(m)
    return final_map


logger = logging.getLogger(__name__)

def extract_codes(text):
    """Metinden ders kodlarını (örn: CS 201) çıkarır."""
    if not isinstance(text, str): return []
    return re.findall(r"([A-Z]{2,5}\s+\d{3,4})", text)

def generate_prereq_graph(course_code, catalog_df):
    """
    Seçilen dersin (Kök) ve onun açtığı derslerin (Hedef) grafiğini çizer.
    Recitation (R), Lab (L), Discussion (D) derslerini GÖSTERMEZ.
    """
    try:
        # Graphviz objesi
        dot = graphviz.Digraph(comment='Prerequisite Chain')
        dot.attr(rankdir='LR') 
        
        # Düğüm Stilleri
        dot.attr('node', shape='box', style='filled', 
                 fillcolor='aliceblue', fontname='Helvetica', fontsize='10')
        dot.attr('edge', color='gray50', arrowsize='0.7')
        
        # 1. Kök Düğüm (Seçilen Ders)
        # Eğer yanlışlıkla kök ders R/L/D seçildiyse (örn MATH 101R), onu ana koda (MATH 101) çevir
        clean_root = course_code
        if clean_root.endswith(('R', 'L', 'D')):
            clean_root = clean_root[:-1]

        dot.node(clean_root, clean_root, fillcolor='gold', penwidth='2')
        
        connections_found = False
        
        # 2. Doğrudan Bağlantıları Bul
        for _, row in catalog_df.iterrows():
            target_code = row['Course Code']
            
            # --- [DEĞİŞİKLİK BURADA] ---
            # Hedef ders R/L/D ise grafiğe ekleme, pas geç
            if str(target_code).endswith(('R', 'L', 'D')):
                continue

            prereq_text = str(row.get('Prerequisites', ''))
            
            # Eğer hedef dersin ön koşulunda bizim dersimiz varsa
            if clean_root in extract_codes(prereq_text.upper()):
                connections_found = True
                
                # Hedef Düğüm
                dot.node(target_code, target_code)
                dot.edge(clean_root, target_code)
                
                # 3. İkinci Seviye (Derinlik 2)
                for _, sub_row in catalog_df.iterrows():
                    sub_target = sub_row['Course Code']
                    
                    # --- [DEĞİŞİKLİK BURADA] ---
                    # Alt hedef R/L/D ise grafiğe ekleme
                    if str(sub_target).endswith(('R', 'L', 'D')):
                        continue
                        
                    sub_prereq = str(sub_row.get('Prerequisites', ''))
                    
                    if target_code in extract_codes(sub_prereq.upper()):
                        dot.node(sub_target, sub_target, fillcolor='mistyrose') 
                        dot.edge(target_code, sub_target)

        if not connections_found:
            note_id = f"note_{clean_root}"
            dot.node(note_id, "Bu ders bir zincir başlatmıyor.", shape='plaintext', style='')
            dot.edge(clean_root, note_id, style='dotted', arrowhead='none')
            
        return dot

    except Exception as e:
        logger.error(f"Grafik oluşturma hatası: {e}")
        return None