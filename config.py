"""
Application Configuration Management
Farklı environment'lar için yapılandırma sınıfları
"""
import os
from datetime import timedelta


class Config:
    """Base configuration"""
    
    # Flask Core
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY ortam değişkeni tanımlanmalı! "
            "Üretmek için: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    
    # MongoDB
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/bestwork')
    MONGO_MAX_POOL_SIZE = int(os.environ.get('MONGO_MAX_POOL_SIZE', 50))
    MONGO_MIN_POOL_SIZE = int(os.environ.get('MONGO_MIN_POOL_SIZE', 10))
    
    # Security
    TCKN_SECRET_KEY = os.environ.get('TCKN_SECRET_KEY')
    if not TCKN_SECRET_KEY:
        raise RuntimeError(
            "TCKN_SECRET_KEY ortam değişkeni tanımlanmalı! "
            "Üretmek için: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    
    # Session Configuration
    SESSION_COOKIE_SECURE = True  # HTTPS only
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_NAME = 'bestwork_session'
    
    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # No expiration
    WTF_CSRF_SSL_STRICT = True
    
    # Rate Limiting
    RATELIMIT_STORAGE_URL = os.environ.get('RATELIMIT_STORAGE_URL', 'memory://')
    RATELIMIT_STRATEGY = 'fixed-window'
    RATELIMIT_HEADERS_ENABLED = True
    
    # Cache
    CACHE_TYPE = os.environ.get('CACHE_TYPE', 'SimpleCache')
    CACHE_DEFAULT_TIMEOUT = 300
    CACHE_REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    
    # File Upload
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = 'static/uploads'
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'


class DevelopmentConfig(Config):
    """Development environment configuration"""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False  # Allow HTTP in development
    WTF_CSRF_SSL_STRICT = False


class ProductionConfig(Config):
    """Production environment configuration"""
    DEBUG = False
    TESTING = False
    
    # Stricter security in production
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_SSL_STRICT = True


class TestingConfig(Config):
    """Testing environment configuration"""
    DEBUG = True
    TESTING = True
    WTF_CSRF_ENABLED = False
    MONGO_URI = 'mongodb://localhost:27017/bestwork_test'


# Environment mapping
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Get configuration based on FLASK_ENV"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config_by_name.get(env, DevelopmentConfig)
