#!/bin/bash

# BestWork Application Startup Script
# This script checks requirements and starts the application safely

echo "🚀 BestWork Application Başlatılıyor..."
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python
echo "📌 Python kontrolü..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 bulunamadı!${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python3 bulundu${NC}"

# Check MongoDB
echo "📌 MongoDB kontrolü..."
if ! pgrep -x mongod > /dev/null; then
    echo -e "${YELLOW}⚠️  MongoDB çalışmıyor!${NC}"
    echo "MongoDB'yi başlatmak için:"
    echo "  macOS: brew services start mongodb-community"
    echo "  Linux: sudo systemctl start mongod"
    read -p "Devam etmek istiyor musunuz? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✓ MongoDB çalışıyor${NC}"
fi

# Check .env file
echo "📌 Environment dosyası kontrolü..."
if [ ! -f .env ]; then
    echo -e "${RED}❌ .env dosyası bulunamadı!${NC}"
    echo "Lütfen .env.example dosyasını .env olarak kopyalayın:"
    echo "  cp .env.example .env"
    echo "Ve gerekli ayarları yapın."
    exit 1
fi
echo -e "${GREEN}✓ .env dosyası bulundu${NC}"

# Check SECRET_KEY
echo "📌 SECRET_KEY kontrolü..."
if ! grep -q "SECRET_KEY=.\+" .env; then
    echo -e "${RED}❌ SECRET_KEY tanımlı değil!${NC}"
    echo "Yeni bir SECRET_KEY oluşturmak için:"
    echo "  python3 -c \"import secrets; print('SECRET_KEY=' + secrets.token_hex(32))\""
    exit 1
fi
echo -e "${GREEN}✓ SECRET_KEY tanımlı${NC}"

# Check TCKN_SECRET_KEY
echo "📌 TCKN_SECRET_KEY kontrolü..."
if ! grep -q "TCKN_SECRET_KEY=.\+" .env; then
    echo -e "${RED}❌ TCKN_SECRET_KEY tanımlı değil!${NC}"
    echo "Yeni bir TCKN_SECRET_KEY oluşturmak için:"
    echo "  python3 -c \"from cryptography.fernet import Fernet; print('TCKN_SECRET_KEY=' + Fernet.generate_key().decode())\""
    exit 1
fi
echo -e "${GREEN}✓ TCKN_SECRET_KEY tanımlı${NC}"

# Check virtual environment
echo "📌 Virtual environment kontrolü..."
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment bulunamadı!${NC}"
    echo "Oluşturuluyor..."
    python3 -m venv .venv
    echo -e "${GREEN}✓ Virtual environment oluşturuldu${NC}"
fi

# Activate virtual environment
echo "📌 Virtual environment aktifleştiriliyor..."
source .venv/bin/activate

# Check dependencies
echo "📌 Dependencies kontrolü..."
if ! python -c "import flask" &> /dev/null; then
    echo -e "${YELLOW}⚠️  Dependencies eksik!${NC}"
    echo "Kuruluyor..."
    pip install -q -r requirements.txt
    echo -e "${GREEN}✓ Dependencies kuruldu${NC}"
else
    echo -e "${GREEN}✓ Dependencies mevcut${NC}"
fi

# Check Redis (optional)
echo "📌 Redis kontrolü (opsiyonel)..."
if ! pgrep -x redis-server > /dev/null; then
    echo -e "${YELLOW}⚠️  Redis çalışmıyor (cache devre dışı)${NC}"
    echo "Redis'i başlatmak için:"
    echo "  macOS: brew services start redis"
    echo "  Linux: sudo systemctl start redis"
else
    echo -e "${GREEN}✓ Redis çalışıyor${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✨ Tüm kontroller başarılı!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check environment mode
FLASK_ENV=$(grep "^FLASK_ENV=" .env | cut -d'=' -f2)
FLASK_DEBUG=$(grep "^FLASK_DEBUG=" .env | cut -d'=' -f2)

if [ "$FLASK_ENV" = "production" ]; then
    echo -e "${GREEN}🔐 Production mode${NC}"
    if [ "$FLASK_DEBUG" = "True" ] || [ "$FLASK_DEBUG" = "true" ]; then
        echo -e "${RED}⚠️  WARNING: DEBUG is enabled in production!${NC}"
        read -p "Debug modunu kapatmak istiyor musunuz? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sed -i '' 's/FLASK_DEBUG=True/FLASK_DEBUG=False/' .env
            sed -i '' 's/FLASK_DEBUG=true/FLASK_DEBUG=False/' .env
            echo -e "${GREEN}✓ DEBUG kapatıldı${NC}"
        fi
    fi
else
    echo -e "${YELLOW}🔧 Development mode${NC}"
fi

echo ""
echo "🌐 Uygulama başlatılıyor..."
echo "   URL: http://127.0.0.1:5000"
echo "   Durdurmak için: Ctrl+C"
echo ""

# Start the application
python app.py
