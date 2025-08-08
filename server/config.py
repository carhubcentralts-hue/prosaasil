"""
Configuration classes for different environments
"""
import os
from datetime import timedelta

class BaseConfig:
    """Base configuration with common settings"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET', 'jwt-secret-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    
    # Database
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    
    # External APIs
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    
    # CORS
    CORS_ORIGINS = ['*']
    
    # Features
    ENABLE_DEBUG_LOGS = False
    ENABLE_FILE_UPLOADS = True
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

class DevConfig(BaseConfig):
    """Development configuration"""
    DEBUG = True
    ENABLE_DEBUG_LOGS = True
    CORS_ORIGINS = ['http://localhost:3000', 'http://127.0.0.1:3000']

class TestConfig(BaseConfig):
    """Testing configuration"""
    TESTING = True
    DATABASE_URL = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class ProdConfig(BaseConfig):
    """Production configuration"""
    DEBUG = False
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '').split(',') if os.getenv('CORS_ORIGINS') else ['*']
    
    # Security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Performance
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }