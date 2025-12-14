"""
=============================================================================
MODÜL: AI / ML Engine
DOSYA: src/ml_engine.py
TANIM: Sentence-BERT modelini kullanarak metinler arası anlamsal benzerlik hesaplar.

MEVCUT FONKSİYONLAR:
1. calculate_ml_scores(df, user_query) ... Ders açıklamaları ile aranan kelime arasındaki
                                           benzerlik skorunu (0-100) döndürür.
=============================================================================
"""

from sentence_transformers import SentenceTransformer, util
import pandas as pd

# Modeli global olarak bir kere yükle (Performans için)
# Bu model küçük ve hızlıdır.
model = SentenceTransformer('all-MiniLM-L6-v2')

def calculate_ml_scores(df, user_query):
    """
    DataFrame içindeki 'Description' (yoksa 'Course Name') sütunu ile
    kullanıcı sorgusunu karşılaştırır.
    
    Returns:
        list: 0 ile 100 arasında float puan listesi.
    """
    if df.empty or not user_query:
        return [0] * len(df)
    
    # Hedef metinleri hazırla (Açıklama yoksa ismi kullan)
    corpus = df.apply(
        lambda x: str(x['Description']) if pd.notna(x['Description']) and len(str(x['Description'])) > 5 
        else str(x['Course Name']), axis=1
    ).tolist()
    
    # Embedding (Vektöre çevirme)
    query_embedding = model.encode(user_query, convert_to_tensor=True)
    corpus_embeddings = model.encode(corpus, convert_to_tensor=True)
    
    # Cosine Similarity (Benzerlik) Hesapla
    cosine_scores = util.cos_sim(query_embedding, corpus_embeddings)[0]
    
    # Skoru 100 üzerinden döndür
    return [round(score.item() * 100, 1) for score in cosine_scores]