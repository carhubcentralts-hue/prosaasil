import os

class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-not-for-production")
    HOST = os.getenv("HOST", "localhost:5000")

class ProdConfig(BaseConfig):
    DEBUG = False
    TESTING = False

class DevConfig(BaseConfig):
    DEBUG = True
    TESTING = True