#!/usr/bin/env python3
"""
BestWork Application Setup Script
Tüm sistemlerde (Windows, macOS, Linux) çalışacak kurulum
"""

import os
import sys
import platform
import subprocess
import shutil
import secrets
from pathlib import Path

try:
    from cryptography.fernet import Fernet
except ImportError:
    print("Warning: cryptography module not found. Will skip TCKN_SECRET_KEY generation.")
    Fernet = None

# Color codes for output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    @staticmethod
    def disable():
        """Disable colors on Windows if needed"""
        if platform.system() == 'Windows':
            Colors.HEADER = ''
            Colors.OKBLUE = ''
            Colors.OKCYAN = ''
            Colors.OKGREEN = ''
            Colors.WARNING = ''
            Colors.FAIL = ''
            Colors.ENDC = ''
            Colors.BOLD = ''
            Colors.UNDERLINE = ''

# Check if Windows
if platform.system() == 'Windows':
    Colors.disable()

BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / '.venv'
ENV_FILE = BASE_DIR / '.env'
REQUIREMENTS_FILE = BASE_DIR / 'requirements.txt'


def print_header(text):
    """Print colored header"""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*50}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*50}{Colors.ENDC}\n")


def print_success(text):
    """Print success message"""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_info(text):
    """Print info message"""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


def run_command(cmd, shell=False):
    """Run shell command safely"""
    try:
        result = subprocess.run(
            cmd,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=300
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timeout"
    except Exception as e:
        return False, "", str(e)


def check_python():
    """Check Python version"""
    print_info("Python sürümü kontrol ediliyor...")
    version = sys.version_info
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print_error(f"Python 3.8+ gerekli, şu an {version.major}.{version.minor} kullanılıyor")
        sys.exit(1)
    
    print_success(f"Python {version.major}.{version.minor}.{version.micro} bulundu")


def check_system():
    """Check system information"""
    system = platform.system()
    print_info(f"İşletim Sistemi: {system} {platform.release()}")
    return system


def create_venv():
    """Create virtual environment"""
    print_info("Virtual environment kontrol ediliyor...")
    
    if VENV_DIR.exists():
        print_warning("Virtual environment zaten var, atlanıyor...")
        return True
    
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            timeout=60
        )
        print_success(f"Virtual environment oluşturuldu: {VENV_DIR}")
        return True
    except Exception as e:
        print_error(f"Virtual environment oluşturulamadı: {e}")
        return False


def get_python_executable():
    """Get the Python executable path in virtual environment"""
    if platform.system() == 'Windows':
        return VENV_DIR / 'Scripts' / 'python.exe'
    else:
        return VENV_DIR / 'bin' / 'python'


def get_pip_executable():
    """Get the pip executable path in virtual environment"""
    if platform.system() == 'Windows':
        return VENV_DIR / 'Scripts' / 'pip.exe'
    else:
        return VENV_DIR / 'bin' / 'pip'


def install_requirements():
    """Install Python dependencies"""
    print_info("Bağımlılıklar kontrol ediliyor...")
    
    if not REQUIREMENTS_FILE.exists():
        print_error(f"requirements.txt bulunamadı: {REQUIREMENTS_FILE}")
        return False
    
    try:
        pip_exe = str(get_pip_executable())
        
        # Update pip
        print_info("pip güncelleniyorsa...")
        subprocess.run(
            [pip_exe, "install", "--upgrade", "pip"],
            timeout=60,
            capture_output=True
        )
        
        # Install requirements
        print_info("Paketler kuruluyor (bu birkaç dakika sürebilir)...")
        success, stdout, stderr = run_command(
            [pip_exe, "install", "-r", str(REQUIREMENTS_FILE)]
        )
        
        if success:
            print_success("Tüm paketler başarıyla kuruldu")
            return True
        else:
            print_error(f"Paket kurulumu başarısız: {stderr}")
            return False
            
    except Exception as e:
        print_error(f"Bağımlılık kurulumu hatası: {e}")
        return False


def create_env_file():
    """Create .env file with auto-generated keys"""
    print_info(".env dosyası kontrol ediliyor...")
    
    if ENV_FILE.exists():
        print_warning(".env dosyası zaten var, yeni oluşturulmayacak")
        return True
    
    try:
        # Generate keys
        secret_key = secrets.token_hex(32)
        
        # Try to generate TCKN secret using cryptography, fallback if not available
        try:
            if Fernet is not None:
                tckn_secret = Fernet.generate_key().decode()
            else:
                tckn_secret = secrets.token_hex(32)
        except Exception:
            tckn_secret = secrets.token_hex(32)
        
        env_content = f"""# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=development
FLASK_DEBUG=False

# Security Keys (Otomatik oluşturuldu)
SECRET_KEY={secret_key}

# MongoDB Connection
MONGO_URI=mongodb://localhost:27017/bestwork

# TCKN Encryption Key (Otomatik oluşturuldu)
TCKN_SECRET_KEY={tckn_secret}

# Cache & Rate Limiting
REDIS_URL=redis://localhost:6379/0
RATELIMIT_STORAGE_URL=redis://localhost:6379/1

# Demo User (Test amaçlı)
DEMO_USER_ID=000954
DEMO_USER_PASS=12345

# Logging
LOG_LEVEL=INFO
"""
        
        with open(ENV_FILE, 'w') as f:
            f.write(env_content)
        
        # Set proper permissions on Unix-like systems
        if platform.system() != 'Windows':
            os.chmod(ENV_FILE, 0o600)
        
        print_success(f".env dosyası oluşturuldu: {ENV_FILE}")
        return True
        
    except Exception as e:
        print_error(f".env dosyası oluşturulamadı: {e}")
        return False


def check_database():
    """Check MongoDB connection"""
    print_info("MongoDB bağlantısı kontrol ediliyor...")
    
    try:
        from pymongo import MongoClient
        client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=2000)
        client.server_info()
        print_success("MongoDB çalışıyor")
        return True
    except Exception as e:
        print_warning(f"MongoDB bağlanılamadı: {e}")
        print_info("  macOS: brew install mongodb-community")
        print_info("  Linux: sudo apt install mongodb")
        print_info("  Windows: https://docs.mongodb.com/manual/tutorial/install-mongodb-on-windows/")
        return False


def check_redis():
    """Check Redis connection"""
    print_info("Redis bağlantısı kontrol ediliyor...")
    
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=2)
        r.ping()
        print_success("Redis çalışıyor")
        return True
    except Exception as e:
        print_warning(f"Redis bağlanılamadı: {e}")
        print_info("  macOS: brew install redis")
        print_info("  Linux: sudo apt install redis-server")
        print_info("  Windows: https://github.com/microsoftarchive/redis/releases")
        return False


def create_directories():
    """Create necessary directories"""
    print_info("Dizinler kontrol ediliyor...")
    
    directories = [
        BASE_DIR / 'static' / 'uploads',
        BASE_DIR / 'logs',
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print_success(f"Dizin hazır: {directory}")


def main():
    """Main setup process"""
    print_header("🚀 BestWork Application Setup")
    
    # Check Python
    check_python()
    
    # Check system
    system = check_system()
    
    # Create directories
    create_directories()
    
    # Create virtual environment
    if not create_venv():
        sys.exit(1)
    
    # Install requirements
    if not install_requirements():
        print_error("Bağımlılıkları yükleyemedi, kurulum durduruldu")
        sys.exit(1)
    
    # Create .env file
    if not create_env_file():
        print_error(".env dosyası oluşturulamadı, kurulum durduruldu")
        sys.exit(1)
    
    # Check database and cache
    print_header("🔍 Sistem Kontrolleri")
    mongodb_ok = check_database()
    redis_ok = check_redis()
    
    # Summary
    print_header("✨ Kurulum Tamamlandı!")
    
    print_info("Sonraki adımlar:")
    print("  1. MongoDB ve Redis'i başlatın (eğer çalışmıyorsa)")
    print("  2. Uygulamayı çalıştırın:")
    
    if platform.system() == 'Windows':
        print(f"     .\\venv\\Scripts\\python app.py")
    else:
        print(f"     ./start.sh  veya")
        print(f"     source .venv/bin/activate && python app.py")
    
    print("  3. Web tarayıcıda: http://localhost:5000")
    
    if not mongodb_ok:
        print_warning("⚠️  MongoDB çalışmıyor - veritabanı işlemleri başarısız olacak")
    
    if not redis_ok:
        print_warning("⚠️  Redis çalışmıyor - caching devre dışı olacak")
    
    print()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print_error("\n\nKurulum iptal edildi")
        sys.exit(1)
    except Exception as e:
        print_error(f"\n\nBeklenmeyen hata: {e}")
        sys.exit(1)
