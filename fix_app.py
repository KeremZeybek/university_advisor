import os

# Streamlit ayar klasörünü ve dosyasını oluştur
config_dir = ".streamlit"
config_file = os.path.join(config_dir, "config.toml")

# Klasör yoksa oluştur
if not os.path.exists(config_dir):
    os.makedirs(config_dir)

# Dosya izlemeyi (fileWatcher) kapatan ayar
content = """[server]
fileWatcherType = "none"
"""

with open(config_file, "w", encoding="utf-8") as f:
    f.write(content)

print("✅ ONARIM BAŞARILI!")
print(f"'{config_file}' dosyası oluşturuldu.")
print("Artık 'streamlit run app.py' komutu hatasız çalışacaktır.")