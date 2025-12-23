# 🚀 Quick Start Guide - BestWork

Tüm işletim sistemlerinde (Windows, macOS, Linux) çalışacak kurulum ve başlatma rehberi.

## 📋 Gereksinimler

- **Python:** 3.8+
- **MongoDB:** 4.4+ (opsiyonel, yerel test için)
- **Redis:** 6.0+ (opsiyonel, cache için)

## 🔧 Kurulum

### Windows

1. **Otomatik Kurulum (Önerilen)**
   ```cmd
   setup.bat
   ```
   
2. **Manuel Kurulum**
   ```cmd
   # Virtual environment oluştur
   python -m venv .venv
   
   # Aktifleştir
   .venv\Scripts\activate
   
   # Paketleri kur
   pip install -r requirements.txt
   
   # Uygulamayı çalıştır
   python app.py
   ```

### macOS / Linux

1. **Otomatik Kurulum (Önerilen)**
   ```bash
   python3 setup.py
   ```
   
2. **Başlatma Scripti Kullanan Kurulum**
   ```bash
   chmod +x start.sh
   ./start.sh
   ```
   
3. **Manuel Kurulum**
   ```bash
   # Virtual environment oluştur
   python3 -m venv .venv
   
   # Aktifleştir
   source .venv/bin/activate
   
   # Paketleri kur
   pip install -r requirements.txt
   
   # Uygulamayı çalıştır
   python app.py
   ```

## 🎯 Başlatma

### Windows
```cmd
.venv\Scripts\python app.py
```

### macOS / Linux
```bash
source .venv/bin/activate
python app.py
```

Veya basitçe:
```bash
./start.sh
```

## 🌐 Web Adresi

```
http://localhost:5000
```

## 🔑 Demo Kimlik Bilgileri

- **Kullanıcı ID:** 000954
- **Şifre:** 12345

## 📝 Ortam Değişkenleri (.env)

Kurulum sırasında `.env` dosyası otomatik olarak oluşturulur. El ile değiştirmek isterseniz:

```dotenv
FLASK_ENV=development          # development veya production
SECRET_KEY=...                  # Otomatik oluşturuldu
TCKN_SECRET_KEY=...            # Otomatik oluşturuldu
MONGO_URI=mongodb://localhost:27017/bestwork
REDIS_URL=redis://localhost:6379/0
```

## 🗄️ MongoDB Kurulumu

### macOS
```bash
brew install mongodb-community
brew services start mongodb-community
```

### Ubuntu/Debian
```bash
sudo apt install mongodb
sudo systemctl start mongod
```

### Docker
```bash
docker run -d -p 27017:27017 --name mongodb mongo:latest
```

## 💾 Redis Kurulumu

### macOS
```bash
brew install redis
brew services start redis
```

### Ubuntu/Debian
```bash
sudo apt install redis-server
sudo systemctl start redis-server
```

### Docker
```bash
docker run -d -p 6379:6379 --name redis redis:latest
```

## 🐛 Hata Çözümleri

### "ModuleNotFoundError: No module named 'flask'"
```bash
# Virtual environment aktifleştir ve paketleri kur
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate      # Windows

pip install -r requirements.txt
```

### "MongoDB bağlantısı kurulamadı"
```bash
# MongoDB çalışıyor mu kontrol et
mongosh
# veya
mongo

# MongoDB'yi başlat (platform'a göre yukarıdaki komutları kullan)
```

### "Redis bağlantısı kurulamadı"
```bash
# Bu hata opsiyonel. Uygulama cache olmadan çalışabilir
# Redis'i başlatmak isterseniz yukarıdaki komutları kullan
```

### "SECRET_KEY oluşturulamadı"
```bash
# .env dosyasını kontrol et
cat .env  # Linux/macOS
type .env  # Windows

# Manuel oluştur
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"
```

## 🧪 Test Etme

### Uygulamayı Test Et
```bash
curl http://localhost:5000
```

### MongoDB'yi Test Et
```bash
mongosh
db.adminCommand({ ping: 1 })
exit
```

### Redis'i Test Et
```bash
redis-cli
ping
exit
```

## 📁 Proje Yapısı

```
.
├── app.py                 # Ana uygulama
├── config.py             # Yapılandırma
├── setup.py              # Python kurulum scripti
├── setup.bat             # Windows kurulum scripti
├── start.sh              # Linux/macOS başlatma scripti
├── requirements.txt      # Python bağımlılıkları
├── .env                  # Ortam değişkenleri (otomatik oluşturuldu)
├── .env.example          # Örnek env dosyası
├── templates/            # HTML şablonları
├── static/               # CSS, JS, Görseller
│   └── uploads/          # Kullanıcı yüklemeleri
└── logs/                 # Uygulama logları
```

## 📚 Daha Fazla Bilgi

- [DEPLOYMENT.md](DEPLOYMENT.md) - Production deployment rehberi
- [SECURITY.md](SECURITY.md) - Güvenlik yapılandırması
- [README.md](README.md) - Proje hakkında

## 💬 Destek

Hata raporlaması veya sorularınız için lütfen GitHub Issues'i kullanın.
