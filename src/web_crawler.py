import pandas as pd
import requests
import time
from bs4 import BeautifulSoup

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
INPUT_FILE = "course_links_master.csv"
OUTPUT_FILE = "course_full_data_v2.csv" 
SLEEP_INTERVAL = 0.5 

# ---------------------------------------------------------
# HELPER FUNCTION: PARSER
# ---------------------------------------------------------
def parse_course_page(html_content):
    """
    Extracts Description, Restrictions, Prerequisites, and Corequisites.
    Uses 'split' logic to handle multi-line blocks effectively.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Get full clean text
    full_text = soup.get_text(separator='\n')
    
    # Initialize variables
    description = "None"
    restrictions = "None"
    prerequisites = "None"
    corequisites = "None"
    
    # -------------------------------------------------------
    # 1. EXTRACT DESCRIPTION (Top of the page logic)
    # -------------------------------------------------------
    # Strategy: Take everything until "Credit hours"
    if "Credit hours" in full_text:
        # Split by "Credit hours" and take the first part
        # Then clean up the top part (Course Code repetitions)
        top_part = full_text.split("Credit hours")[0]
        lines = [line.strip() for line in top_part.split('\n') if line.strip()]
        
        # Filter out lines that look like headers (e.g. "ACC 201 - ...")
        desc_lines = [line for line in lines if " - " not in line or not any(c.isdigit() for c in line)]
        
        if desc_lines:
            description = " ".join(desc_lines).strip()

    # -------------------------------------------------------
    # 2. EXTRACT BOTTOM BLOCKS (Restrictions, Pre-reqs, Co-reqs)
    # -------------------------------------------------------
    # We use string splitting because these blocks can span multiple lines.
    # We look for the keyword, take everything after it, then stop at the next keyword.
    
    # Helper to extract text between two markers
    def extract_block(text, start_marker, stop_markers):
        if start_marker not in text:
            return "None"
        
        # Start after the marker
        chunk = text.split(start_marker)[1]
        
        # Find the earliest occurrence of any stop marker
        end_index = len(chunk)
        for marker in stop_markers:
            if marker in chunk:
                idx = chunk.find(marker)
                if idx != -1 and idx < end_index:
                    end_index = idx
        
        return chunk[:end_index].strip()

    # Define markers based on BannerWeb structure order
    # Order usually: Restrictions -> Prerequisites -> Corequisites
    
    # Restrictions: Stops at Prereq or Coreq
    restrictions = extract_block(full_text, "Restrictions:", ["Prerequisites:", "Corequisites:"])
    
    # Prerequisites: Stops at Coreq
    prerequisites = extract_block(full_text, "Prerequisites:", ["Corequisites:"])
    
    # Corequisites: Stops at nothing (end of logic usually)
    corequisites = extract_block(full_text, "Corequisites:", ["General Requirements:"]) # Gen. Req. sometimes appears

    return description, restrictions, prerequisites, corequisites

# ---------------------------------------------------------
# MAIN CRAWLING LOOP
# ---------------------------------------------------------
try:
    df_links = pd.read_csv(INPUT_FILE)
    print(f"Loaded {len(df_links)} courses. Crawler v2.1 (Restrictions) starting...")
except FileNotFoundError:
    print(f"ERROR: '{INPUT_FILE}' not found.")
    exit()

results = []
total = len(df_links)

for index, row in df_links.iterrows():
    code = row['Course Code']
    url = row['URL']
    
    print(f"[{index+1}/{total}] {code}...", end=" ")
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            desc, rest, pre, cor = parse_course_page(response.content)
            
            # Console Feedback
            # Show 'R' if restrictions exist, 'P' if prereqs exist
            info_flags = []
            if rest != "None": info_flags.append("Restr")
            if pre != "None": info_flags.append("Prereq")
            
            flag_str = ", ".join(info_flags) if info_flags else "Clean"
            print(f"✅ ({flag_str})")
            
            results.append({
                "Course Code": code,
                "Course Name": row['Course Name'],
                "Description": desc,
                "Restrictions": rest,     
                "Prerequisites": pre,
                "Corequisites": cor,
                "Term": row['Term']
            })
            
        else:
            print(f"❌ HTTP {response.status_code}")
            
    except Exception as e:
        print(f"⚠️ Err: {e}")

    time.sleep(SLEEP_INTERVAL)

# ---------------------------------------------------------
# EXPORT
# ---------------------------------------------------------
df_final = pd.DataFrame(results)
df_final.to_csv(OUTPUT_FILE, index=False)
print(f"\nDONE! Dataset with RESTRICTIONS saved to '{OUTPUT_FILE}'")