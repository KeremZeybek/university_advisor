import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer, util
import streamlit as st

# Modeli önbelleğe alıyoruz ki her seferinde tekrar indirmesin (80MB civarı)
@st.cache_resource
def load_model():
    # 'all-MiniLM-L6-v2' -> Hızlı ve çok güçlü bir modeldir.
    return SentenceTransformer('all-MiniLM-L6-v2')

def calculate_ml_scores(df, user_interest_text):
    """
    Sentence-BERT kullanarak anlamsal benzerlik (Semantic Similarity) hesaplar.
    Bu yöntem, kelime geçmese bile anlamı yakalar.
    """
    model = load_model()
    
    # 1. Veri Hazırlığı: Ders Adı + Açıklama
    # Açıklaması olmayanlara sadece isim veriyoruz
    course_texts = (
        df['Course Name'].fillna('') + ": " + 
        df['Description'].fillna('')
    ).tolist()
    
    # 2. Embedding (Metni Sayısal Vektöre Çevirme)
    # Bu adımda model, internetten öğrendiği bilgiyi kullanarak dersleri vektöre çevirir.
    course_embeddings = model.encode(course_texts, convert_to_tensor=True)
    
    # 3. Kullanıcının İsteğini Vektöre Çevir
    query_embedding = model.encode(user_interest_text, convert_to_tensor=True)
    
    # 4. Cosine Similarity Hesapla
    # Kullanıcının hayali ile derslerin gerçeği arasındaki benzerlik
    cosine_scores = util.cos_sim(query_embedding, course_embeddings)[0]
    
    # 5. Puanları 0-100 arasına çek (Tensor'dan numpy'a çeviriyoruz)
    # Model -1 ile 1 arası döndürür, biz negatifleri 0 yapıp 100 ile çarpalım.
    scores = cosine_scores.cpu().numpy()
    scores = np.maximum(scores, 0) * 100
    scores = np.round(scores, 1)
    
    return scores