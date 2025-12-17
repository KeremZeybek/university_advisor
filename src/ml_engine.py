"""
=============================================================================
MODÜL: AI / ML Engine
DOSYA: src/ml_engine.py
TANIM: Ders açıklamaları ile ilgi alanı arasındaki benzerliği hesaplar.
=============================================================================
"""

try:
    from sentence_transformers import SentenceTransformer, util
    MODEL_AVAILABLE = True
except ImportError:
    MODEL_AVAILABLE = False

import pandas as pd

# Modeli global yükle (Performans için tek sefer)
model = None
if MODEL_AVAILABLE:
    try:
        model = SentenceTransformer('all-MiniLM-L6-v2')
    except:
        MODEL_AVAILABLE = False

def calculate_ml_scores(df, user_query):
    """
    DataFrame içindeki 'Description' (yoksa 'Course Name') ile sorguyu karşılaştırır.
    """
    if df.empty or not user_query:
        return [0] * len(df)
    
    if not MODEL_AVAILABLE or model is None:
        # Fallback: Kütüphane yoksa basit kelime sayımı yap
        scores = []
        q_tokens = set(user_query.lower().split())
        for _, row in df.iterrows():
            text = (str(row.get('Description', '')) + " " + str(row.get('Course Name', ''))).lower()
            match_count = sum(1 for t in q_tokens if t in text)
            scores.append(min(match_count * 20, 100))
        return scores
    
    # Hedef metinleri hazırla
    corpus = df.apply(
        lambda x: str(x['Description']) if pd.notna(x.get('Description')) and len(str(x.get('Description'))) > 5 
        else str(x['Course Name']), axis=1
    ).tolist()
    
    # Embedding & Benzerlik
    query_embedding = model.encode(user_query, convert_to_tensor=True)
    corpus_embeddings = model.encode(corpus, convert_to_tensor=True)
    cosine_scores = util.cos_sim(query_embedding, corpus_embeddings)[0]
    
    return [round(score.item() * 100, 1) for score in cosine_scores]