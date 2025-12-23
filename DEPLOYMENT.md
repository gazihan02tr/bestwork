# 🚀 Production Deployment Rehberi

## Server Gereksinimleri

### Minimum
- **CPU:** 2 core
- **RAM:** 4 GB
- **Disk:** 20 GB SSD
- **OS:** Ubuntu 20.04+ / CentOS 8+ / Debian 11+

### Önerilen
- **CPU:** 4+ core
- **RAM:** 8+ GB
- **Disk:** 50+ GB SSD
- **OS:** Ubuntu 22.04 LTS

## 1. Server Hazırlığı

```bash
# System güncelleme
sudo apt update && sudo apt upgrade -y

# Gerekli paketler
sudo apt install -y \
  python3.11 \
  python3.11-venv \
  python3-pip \
  nginx \
  git \
  ufw \
  fail2ban \
  certbot \
  python3-certbot-nginx

# MongoDB kurulumu
wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list
sudo apt update
sudo apt install -y mongodb-org
sudo systemctl start mongod
sudo systemctl enable mongod

# Redis kurulumu
sudo apt install -y redis-server
sudo systemctl enable redis-server
```

## 2. Application Deployment

```bash
# Kullanıcı oluştur
sudo adduser --system --group --home /opt/bestwork bestwork

# Uygulama klonla
sudo -u bestwork git clone https://github.com/yourrepo/bestwork.git /opt/bestwork/app
cd /opt/bestwork/app

# Virtual environment
sudo -u bestwork python3.11 -m venv /opt/bestwork/venv
source /opt/bestwork/venv/bin/activate
pip install -r requirements.txt
pip install gunicorn gevent

# Environment setup
sudo -u bestwork cp .env.example .env
sudo -u bestwork nano .env  # Değerleri düzenle

# Permissions
sudo chown -R bestwork:bestwork /opt/bestwork
sudo chmod -R 755 /opt/bestwork
sudo chmod 600 /opt/bestwork/app/.env
```

## 3. Systemd Service

```bash
# /etc/systemd/system/bestwork.service
sudo nano /etc/systemd/system/bestwork.service
```

```ini
[Unit]
Description=BestWork Flask Application
After=network.target mongod.service redis.service
Wants=mongod.service redis.service

[Service]
Type=notify
User=bestwork
Group=bestwork
WorkingDirectory=/opt/bestwork/app
Environment="PATH=/opt/bestwork/venv/bin"
ExecStart=/opt/bestwork/venv/bin/gunicorn \
    --bind 127.0.0.1:8000 \
    --workers 4 \
    --worker-class gevent \
    --worker-connections 1000 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --timeout 30 \
    --graceful-timeout 30 \
    --keep-alive 5 \
    --log-level info \
    --access-logfile /var/log/bestwork/access.log \
    --error-logfile /var/log/bestwork/error.log \
    --capture-output \
    --enable-stdio-inheritance \
    app:app

# Restart policy
Restart=always
RestartSec=10

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/bestwork/app/static/uploads /var/log/bestwork

[Install]
WantedBy=multi-user.target
```

```bash
# Log dizini oluştur
sudo mkdir -p /var/log/bestwork
sudo chown bestwork:bestwork /var/log/bestwork

# Service başlat
sudo systemctl daemon-reload
sudo systemctl start bestwork
sudo systemctl enable bestwork
sudo systemctl status bestwork
```

## 4. Nginx Yapılandırması

```bash
# /etc/nginx/sites-available/bestwork
sudo nano /etc/nginx/sites-available/bestwork
```

```nginx
# Rate limiting
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=general:10m rate=100r/s;

# Upstream
upstream bestwork_app {
    server 127.0.0.1:8000 fail_timeout=0;
}

# HTTPS
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL Certificates (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_trusted_certificate /etc/letsencrypt/live/yourdomain.com/chain.pem;

    # SSL Configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_stapling on;
    ssl_stapling_verify on;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Logs
    access_log /var/log/nginx/bestwork_access.log;
    error_log /var/log/nginx/bestwork_error.log;

    # Max upload size
    client_max_body_size 16M;

    # Static files
    location /static/ {
        alias /opt/bestwork/app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Uploads
    location /static/uploads/ {
        alias /opt/bestwork/app/static/uploads/;
        expires 7d;
        add_header Cache-Control "public";
    }

    # Login rate limiting
    location /login {
        limit_req zone=login burst=3 nodelay;
        proxy_pass http://bestwork_app;
        include proxy_params;
    }

    # API rate limiting
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://bestwork_app;
        include proxy_params;
    }

    # General
    location / {
        limit_req zone=general burst=50 nodelay;
        proxy_pass http://bestwork_app;
        include proxy_params;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

# HTTP to HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

```bash
# Nginx yapılandırmayı aktifleştir
sudo ln -s /etc/nginx/sites-available/bestwork /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 5. SSL Certificate (Let's Encrypt)

```bash
# Certbot ile SSL sertifikası al
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Otomatik yenileme testi
sudo certbot renew --dry-run

# Cron job (otomatik yenileme)
sudo crontab -e
# Ekle:
0 0 * * * certbot renew --quiet --post-hook "systemctl reload nginx"
```

## 6. Firewall Yapılandırması

```bash
# UFW kuralları
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable
sudo ufw status
```

## 7. Fail2Ban Yapılandırması

```bash
# /etc/fail2ban/jail.local
sudo nano /etc/fail2ban/jail.local
```

```ini
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
logpath = /var/log/nginx/bestwork_error.log

[nginx-botsearch]
enabled = true
logpath = /var/log/nginx/bestwork_access.log

[sshd]
enabled = true
maxretry = 3
```

```bash
sudo systemctl enable fail2ban
sudo systemctl restart fail2ban
```

## 8. MongoDB Production Setup

```bash
# MongoDB authentication
mongosh
```

```javascript
use admin
db.createUser({
  user: "admin",
  pwd: "STRONG_PASSWORD",
  roles: ["userAdminAnyDatabase", "dbAdminAnyDatabase", "readWriteAnyDatabase"]
})

use bestwork
db.createUser({
  user: "bestwork_app",
  pwd: "STRONG_APP_PASSWORD",
  roles: ["readWrite"]
})
```

```bash
# /etc/mongod.conf
sudo nano /etc/mongod.conf
```

```yaml
security:
  authorization: enabled

net:
  bindIp: 127.0.0.1
  port: 27017
```

```bash
sudo systemctl restart mongod

# .env dosyasını güncelle
MONGO_URI=mongodb://bestwork_app:STRONG_APP_PASSWORD@localhost:27017/bestwork
```

## 9. Redis Production Setup

```bash
# /etc/redis/redis.conf
sudo nano /etc/redis/redis.conf
```

```conf
# Password
requirepass YOUR_REDIS_PASSWORD

# Bind
bind 127.0.0.1

# Persistence
save 900 1
save 300 10
save 60 10000

# Memory
maxmemory 256mb
maxmemory-policy allkeys-lru

# Security
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG ""
```

```bash
sudo systemctl restart redis
```

## 10. Backup Sistemi

```bash
# /usr/local/bin/backup-bestwork.sh
sudo nano /usr/local/bin/backup-bestwork.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/backup/bestwork"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# MongoDB backup
mongodump --uri="mongodb://bestwork_app:PASSWORD@localhost:27017/bestwork" \
  --out="$BACKUP_DIR/mongodb/$DATE"

# Application backup
tar -czf "$BACKUP_DIR/app/$DATE.tar.gz" \
  /opt/bestwork/app \
  --exclude='*.pyc' \
  --exclude='__pycache__' \
  --exclude='.venv'

# Clean old backups
find $BACKUP_DIR -type f -mtime +$RETENTION_DAYS -delete
find $BACKUP_DIR -type d -empty -delete

# Log
echo "$(date): Backup completed" >> /var/log/bestwork/backup.log
```

```bash
sudo chmod +x /usr/local/bin/backup-bestwork.sh

# Cron job (günlük 2:00)
sudo crontab -e
# Ekle:
0 2 * * * /usr/local/bin/backup-bestwork.sh
```

## 11. Monitoring

```bash
# System monitoring
sudo apt install -y htop iotop nethogs

# Application monitoring - healthcheck endpoint
curl https://yourdomain.com/health

# Log monitoring
sudo tail -f /var/log/bestwork/error.log
sudo tail -f /var/log/nginx/bestwork_error.log
```

## 12. Deployment Scripti

```bash
# /opt/bestwork/deploy.sh
nano /opt/bestwork/deploy.sh
```

```bash
#!/bin/bash
set -e

echo "🚀 BestWork Deployment Starting..."

cd /opt/bestwork/app

# Backup current version
echo "📦 Creating backup..."
tar -czf /opt/bestwork/backups/pre-deploy-$(date +%Y%m%d_%H%M%S).tar.gz \
  /opt/bestwork/app

# Pull latest code
echo "📥 Pulling latest code..."
sudo -u bestwork git pull origin main

# Install dependencies
echo "📚 Installing dependencies..."
source /opt/bestwork/venv/bin/activate
pip install -r requirements.txt

# Run migrations (if any)
echo "🗃️  Running migrations..."
# python manage.py migrate

# Collect static files (if needed)
# python manage.py collectstatic --noinput

# Restart application
echo "🔄 Restarting application..."
sudo systemctl restart bestwork

# Health check
echo "🏥 Health check..."
sleep 5
curl -f http://127.0.0.1:8000/ || {
  echo "❌ Health check failed! Rolling back..."
  # Restore from backup logic here
  exit 1
}

echo "✅ Deployment completed successfully!"
```

```bash
chmod +x /opt/bestwork/deploy.sh
```

## 13. Post-Deployment Kontroller

```bash
# Service durumu
sudo systemctl status bestwork
sudo systemctl status nginx
sudo systemctl status mongod
sudo systemctl status redis

# Log kontrol
sudo tail -100 /var/log/bestwork/error.log

# Disk kullanımı
df -h

# Memory kullanımı
free -h

# SSL sertifika kontrolü
sudo certbot certificates

# Application test
curl -I https://yourdomain.com
```

## 14. Güncelleme Prosedürü

```bash
# 1. Backup al
/usr/local/bin/backup-bestwork.sh

# 2. Maintenance mode (opsiyonel)
sudo touch /opt/bestwork/app/maintenance.flag

# 3. Deploy
/opt/bestwork/deploy.sh

# 4. Test
curl https://yourdomain.com

# 5. Maintenance mode kaldır
sudo rm /opt/bestwork/app/maintenance.flag
```

## Sorun Giderme

### Service başlamıyor
```bash
sudo journalctl -u bestwork -n 100
sudo systemctl restart bestwork
```

### 502 Bad Gateway
```bash
# Gunicorn çalışıyor mu?
sudo systemctl status bestwork

# Port dinliyor mu?
sudo netstat -tulpn | grep 8000
```

### MongoDB bağlantı hatası
```bash
# MongoDB çalışıyor mu?
sudo systemctl status mongod

# Authentication test
mongosh -u bestwork_app -p PASSWORD --authenticationDatabase bestwork
```

## İletişim

Deployment sorunları için:
- DevOps: devops@bestwork.com
- Documentation: https://docs.bestwork.com/deployment

---

**Versiyon:** 2.0.0
**Son Güncelleme:** 23 Aralık 2025
