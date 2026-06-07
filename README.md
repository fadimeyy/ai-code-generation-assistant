# ◈ CodeSense

> **AI destekli Python kod inceleme ve üretim sistemi**  
> Statik analiz araçları (Ruff + Bandit) ile Büyük Dil Modeli'ni (Llama 3.3-70B) birleştiren hibrit sistem

🔗 **Çalışan Demo:** [codesensee.streamlit.app](https://codesensee.streamlit.app)

---

## Ne Yapar?

CodeSense, Python kodlarını otomatik olarak inceleyen, güvenlik açıklarını tespit eden ve kod üretebilen bir yapay zeka uygulamasıdır. Yalnızca LLM kullanmak yerine, önce Ruff ve Bandit ile statik analiz çalıştırır; bu bulguları LLM'ye bağlam olarak vererek daha isabetli ve az hatalı incelemeler üretir.

**Araştırma sorusu:** Statik analiz çıktıları LLM'ye bağlam olarak sağlandığında tespit performansı anlamlı biçimde artıyor mu?

**Temel bulgu:** Static+LLM modu, LLM Only modunu genel F1 skorunda +1.2 puan geride bırakıyor (%25.5 vs %24.3) ve yanlış pozitif sayısını 47 birim azaltıyor — 50 etiketli test vakası üzerinde ölçüldü.

---

## Nasıl Kullanılır?

### 1. Kod İnceleme (Chat)

Sol menüden **💬 Chat** sekmesine gel.

Kodunu üç şekilde inceleyebilirsin:

**a) Direkt yapıştır:**
```
Şu kodu incele:
```python
import sqlite3
def get_user(username):
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    ...
```
```

**b) İnceleme modunu seç** (altta sağ köşe):
- 🧠 **LLM Only** — Sadece yapay zeka inceler, hızlı ama daha fazla yanlış alarm
- 🔬 **Static + LLM** — Önce Ruff + Bandit çalışır, bulgular LLM'ye verilir, daha isabetli
- 🔗 **Repo + LLM** — GitHub reposu bağlanır, ilgili dosyalar da bağlama eklenir

**c) ▶ Send** butonuna bas, inceleme gelir.

---

### 2. GitHub Reposu Bağlama

Sol üstteki **🔗 Connect GitHub Repository** bölümünü aç.

```
Repository URL: https://github.com/kullanici/repo
File path (opsiyonel): src/main.py
```

**Connect** butonuna bas. Sistem repoyu klonlar, Python dosyalarını okur ve özet çıkarır. Bundan sonra sohbet sırasında o reponun bağlamı otomatik kullanılır.

---

### 3. Kod Üretme

Chat kutusuna doğal dilde yaz:

```
Kullanıcı girişi doğrulayan bir fonksiyon yaz
```
```
JWT token oluşturan bir sınıf oluştur
```

Sistem kodu üretir, ardından otomatik Ruff + Bandit çalıştırır, sorun varsa düzeltilmiş versiyonu da sunar.

---

### 4. A/B Karşılaştırma

Sol menüden **⚡ A/B Compare** sekmesine gel.

Aynı kodu iki farklı moddan aynı anda geçirir, sonuçları yan yana gösterir. Hangi modun ne bulduğunu, kaç satır referans verdiğini karşılaştırabilirsin.

---

### 5. Benchmark Çalıştırma

Sol menüden **🎯 Benchmark** sekmesine gel.

50 adet önceden etiketlenmiş Python test vakası üzerinde seçtiğin modları çalıştırır. Precision, Recall ve F1 metrikleri hesaplanır, grafikler ve CSV export sunulur.

> ⚡ Quick Mode işaretliyse 10 rastgele vaka seçilir, ~1 dakikada tamamlanır.

---

### 6. Metrik Takibi

Sol menüden **📊 Metrics** sekmesine gel.

Her inceleme oturumu otomatik kaydedilir. Toplam analiz sayısı, Ruff/Bandit sorun dağılımı, mod bazında tespit oranları ve kümülatif eğri grafikleri görüntülenir. CSV olarak dışa aktarılabilir.

---

## Kurulum (Lokal)

**Gereksinimler:** Python 3.9+, Git

```bash
# Repoyu klonla
git clone https://github.com/fadimeyy/ai-code-generation-assistant
cd ai-code-generation-assistant

# Bağımlılıkları yükle
pip install -r requirements.txt

# .env dosyasını oluştur
cp .env.example .env
# .env içine GROQ_API_KEY değerini ekle

# Uygulamayı başlat
streamlit run app.py
```

**.env.example:**
```
GROQ_API_KEY=your_groq_api_key_here
```

Ücretsiz Groq API anahtarı için: [console.groq.com](https://console.groq.com)

---

## Proje Yapısı

```
├── app.py                  # Ana Streamlit uygulaması
├── core/
│   ├── analysis.py         # LLM çağrıları, Ruff/Bandit çalıştırıcılar
│   ├── database.py         # SQLite işlemleri
│   └── benchmark_data.py   # 50 test vakası + puanlama mantığı
├── tabs/
│   ├── benchmark_tab.py    # Benchmark çalıştırıcı ve görseller
│   ├── ab_compare.py       # A/B karşılaştırma modülü
│   ├── metrics.py          # Metrik dashboard
│   └── docs.py             # Dokümantasyon sekmesi
├── requirements.txt
└── .env.example
```

---

## Teknoloji Yığını

| Katman | Teknoloji |
|---|---|
| Arayüz | Streamlit |
| LLM | Llama 3.3-70B — Groq API |
| Statik Analiz | Ruff v0.4, Bandit v1.7 |
| Veritabanı | SQLite |
| Grafikler | Plotly |

---

## Benchmark Sonuçları

50 etiketli Python test vakası üzerinde (Güvenlik n=20, Kalite n=21, Stil n=9), her vaka iki modla çalıştırıldı — toplam 100 API çağrısı.

| Mod | Precision | Recall | F1 | TP | FP |
|---|---|---|---|---|---|
| LLM Only | 14.4% | 97.0% | 24.3% | 57 | 414 |
| Static + LLM | 15.3% | 92.0% | **25.5%** | 55 | **367** |

| Kategori | LLM Only F1 | Static+LLM F1 |
|---|---|---|
| Güvenlik | 27.0% | **28.6%** |
| Kalite | 21.8% | **23.8%** |
| Stil | **24.2%** | 22.5% |

---

Fadime Erbay — Mehmet Akif Ersoy Üniversitesi, Yüksek Lisans Yazılım Mühendisliği

---
