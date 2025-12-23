# 🔒 SECURITY.md

## Güvenlik Politikası

### Desteklenen Versiyonlar

| Versiyon | Destekleniyor |
| ------- | ------------ |
| 2.0.x   | ✅           |
| < 2.0   | ❌           |

## Güvenlik Açığı Bildirimi

Güvenlik açığı bulduysanız lütfen **herkese açık issue açmayın**. Bunun yerine:
- Email: security@bestwork.com
- Encrypted: PGP key available on request

## Güvenlik En İyi Uygulamaları

### 1. Environment Variables
```bash
# ASLA git'e commit etmeyin
.env
.env.local
.env.*.local

# Güçlü key'ler kullanın
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
TCKN_SECRET_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

### 2. Production Deployment

#### HTTPS Zorunluluğu
```nginx
server {
    listen 443 ssl http2;
    server_name yoursite.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# HTTP'den HTTPS'e yönlendirme
server {
    listen 80;
    server_name yoursite.com;
    return 301 https://$server_name$request_uri;
}
```

#### Gunicorn ile Production
```bash
# Güvenli çalıştırma
gunicorn \
  --bind 127.0.0.1:8000 \
  --workers 4 \
  --worker-class gevent \
  --worker-connections 1000 \
  --max-requests 1000 \
  --max-requests-jitter 100 \
  --timeout 30 \
  --keep-alive 5 \
  --log-level info \
  --access-logfile /var/log/bestwork/access.log \
  --error-logfile /var/log/bestwork/error.log \
  --capture-output \
  --enable-stdio-inheritance \
  app:app
```

### 3. MongoDB Güvenliği

```javascript
// MongoDB authentication
use admin
db.createUser({
  user: "bestwork_admin",
  pwd: "STRONG_PASSWORD_HERE",
  roles: [
    { role: "readWrite", db: "bestwork" }
  ]
})

// IP whitelisting
# /etc/mongod.conf
net:
  bindIp: 127.0.0.1
  port: 27017
  
security:
  authorization: enabled
```

### 4. Redis Güvenliği

```bash
# /etc/redis/redis.conf

# Password protection
requirepass YOUR_STRONG_PASSWORD

# Bind to localhost only
bind 127.0.0.1

# Disable dangerous commands
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG ""
rename-command SHUTDOWN ""
```

### 5. Firewall Yapılandırması

```bash
# UFW (Ubuntu)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Sadece localhost'tan MongoDB ve Redis
sudo ufw deny 27017
sudo ufw deny 6379
```

### 6. Regular Updates

```bash
# Her hafta dependency güncellemeleri kontrol edin
pip list --outdated

# Güvenlik güncellemelerini uygulayın
pip install --upgrade package_name

# MongoDB ve Redis güncellemelerini takip edin
```

### 7. Backup Stratejisi

```bash
# Günlük MongoDB backup
mongodump --db bestwork --out /backup/mongodb/$(date +%Y%m%d)

# Haftalık full backup
tar -czf /backup/full/bestwork_$(date +%Y%m%d).tar.gz \
  /path/to/bestwork \
  /backup/mongodb/$(date +%Y%m%d)

# 30 günden eski backupları sil
find /backup -type f -mtime +30 -delete
```

### 8. Monitoring ve Alerting

```python
# Sentry integration (önerilir)
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn="YOUR_SENTRY_DSN",
    integrations=[FlaskIntegration()],
    traces_sample_rate=1.0,
    environment="production"
)
```

### 9. Rate Limiting Ayarları

```python
# Production için daha sıkı limitler
RATELIMIT_DEFAULTS = [
    "100 per day",
    "20 per hour"
]

# Login endpoint için
@limiter.limit("3 per minute")
def login():
    ...
```

### 10. Security Headers

```python
# Eklenen headers
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'
```

## Güvenlik Kontrol Listesi

### Deployment Öncesi
- [ ] .env dosyası git'te yok
- [ ] SECRET_KEY güçlü ve unique
- [ ] DEBUG=False production'da
- [ ] HTTPS enabled
- [ ] MongoDB authentication aktif
- [ ] Redis password korumalı
- [ ] Firewall yapılandırıldı
- [ ] Backup sistemi kuruldu
- [ ] Monitoring aktif
- [ ] Log rotation yapılandırıldı

### Aylık Kontroller
- [ ] Dependency güncellemeleri
- [ ] Security patches
- [ ] Log analizi
- [ ] Backup testi
- [ ] Performance metrikleri
- [ ] Rate limit ayarları

### Acil Durum Planı

1. **Veri İhlali Tespit Edildiğinde:**
   - Tüm kullanıcı şifrelerini reset edin
   - SECRET_KEY'i değiştirin
   - Tüm session'ları temizleyin
   - Kullanıcıları bilgilendirin
   - Log'ları analiz edin

2. **DDoS Saldırısı:**
   - Cloudflare gibi CDN kullanın
   - Rate limiting'i sıkılaştırın
   - IP blacklist uygulayın

3. **Database Compromise:**
   - En son backup'tan restore edin
   - Tüm credentials'ı değiştirin
   - Security audit yapın

## Kaynaklar

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Flask Security Guide](https://flask.palletsprojects.com/en/2.3.x/security/)
- [MongoDB Security Checklist](https://docs.mongodb.com/manual/administration/security-checklist/)
- [Redis Security](https://redis.io/topics/security)

## İletişim

Güvenlik sorunları için:
- Email: security@bestwork.com
- Response time: 24-48 saat
- Bounty program: Available for critical issues

---

**Son Güncelleme:** 23 Aralık 2025
**Versiyon:** 2.0.0
