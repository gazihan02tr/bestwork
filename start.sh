#!/bin/bash

# BestWork Application Startup Script
# Works on macOS, Linux
# Tüm kontrolleri yapıp uygulamayı güvenli şekilde başlatır

set -e

# Script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "\n${BLUE}╔════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC} $1"
    echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Main startup process
print_header "🚀 BestWork Application Starting"

# Check Python
print_info "Checking Python..."
if ! command -v python3 &> /dev/null; then
    print_error "Python3 not found!"
    echo "Please install Python 3.8+ and try again"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
print_success "Python $PYTHON_VERSION found"

# Check virtual environment
if [ ! -d ".venv" ]; then
    print_warning "Virtual environment not found"
    print_info "Creating virtual environment..."
    python3 -m venv .venv
    print_success "Virtual environment created"
fi

# Activate virtual environment
print_info "Activating virtual environment..."
source .venv/bin/activate

# Check dependencies
print_info "Checking dependencies..."
if ! python -c "import flask" 2>/dev/null; then
    print_warning "Dependencies not found"
    print_info "Installing dependencies..."
    pip install -q -r requirements.txt
    print_success "Dependencies installed"
else
    print_success "All dependencies available"
fi

# Check .env file
print_info "Checking configuration..."
if [ ! -f ".env" ]; then
    print_error ".env file not found!"
    print_info "Creating .env file with auto-generated keys..."
    
    # Generate keys and create .env
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    TCKN_SECRET=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    
    cat > .env << EOF
# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=development
FLASK_DEBUG=False

# Security Keys (Auto-generated)
SECRET_KEY=$SECRET_KEY

# MongoDB Connection
MONGO_URI=mongodb://localhost:27017/bestwork

# TCKN Encryption Key (Auto-generated)
TCKN_SECRET_KEY=$TCKN_SECRET

# Cache & Rate Limiting
REDIS_URL=redis://localhost:6379/0
RATELIMIT_STORAGE_URL=redis://localhost:6379/1

# Demo User
DEMO_USER_ID=000954
DEMO_USER_PASS=12345

# Logging
LOG_LEVEL=INFO
EOF
    
    chmod 600 .env
    print_success ".env file created"
else
    print_success ".env file found"
    
    # Check if SECRET_KEY is set
    if ! grep -q "^SECRET_KEY=[^ ]" .env; then
        print_error "SECRET_KEY not properly configured!"
        exit 1
    fi
    
    # Check if TCKN_SECRET_KEY is set
    if ! grep -q "^TCKN_SECRET_KEY=[^ ]" .env; then
        print_error "TCKN_SECRET_KEY not properly configured!"
        exit 1
    fi
fi

# Create necessary directories
mkdir -p static/uploads
mkdir -p logs

# Check MongoDB
print_info "Checking MongoDB..."
if pgrep -x "mongod" > /dev/null; then
    print_success "MongoDB is running"
else
    print_warning "MongoDB is not running"
    echo "  Start MongoDB:"
    echo "    macOS:  brew services start mongodb-community"
    echo "    Linux:  sudo systemctl start mongod"
    echo "    Docker: docker run -d -p 27017:27017 mongo"
fi

# Check Redis
print_info "Checking Redis..."
if pgrep -x "redis-server" > /dev/null || command -v redis-cli &> /dev/null && redis-cli ping &> /dev/null; then
    print_success "Redis is running"
else
    print_warning "Redis is not running (caching disabled)"
    echo "  Start Redis:"
    echo "    macOS:  brew services start redis"
    echo "    Linux:  sudo systemctl start redis"
    echo "    Docker: docker run -d -p 6379:6379 redis"
fi

# Get Flask environment
FLASK_ENV=$(grep "^FLASK_ENV=" .env | cut -d'=' -f2 | tr -d ' ')
FLASK_DEBUG=$(grep "^FLASK_DEBUG=" .env | cut -d'=' -f2 | tr -d ' ')

if [ "$FLASK_ENV" = "production" ]; then
    print_warning "Running in PRODUCTION mode"
    if [ "$FLASK_DEBUG" = "True" ] || [ "$FLASK_DEBUG" = "true" ]; then
        print_error "WARNING: DEBUG is enabled in production!"
        read -p "Disable DEBUG mode? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sed -i '' 's/FLASK_DEBUG=True/FLASK_DEBUG=False/' .env 2>/dev/null || sed -i 's/FLASK_DEBUG=True/FLASK_DEBUG=False/' .env
            print_success "DEBUG disabled"
        fi
    fi
else
    print_info "Running in DEVELOPMENT mode"
fi

# Print startup info
print_header "🎯 Application Ready"

echo "URL:           http://127.0.0.1:5000"
echo "Stop:          Press Ctrl+C"
echo ""

# Run the application
exec python app.py
