import os
from dotenv import load_dotenv

# .env betöltése
load_dotenv()

class Config:
    # --- Flask session / security ---
    SECRET_KEY = os.environ.get('SECRET_KEY', 'fallback_supersecret_key')

    # --- Google OAuth ---
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI')

    # --- SQLAlchemy ---
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True

    # --- Session cookie biztonság ---
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "None"

    # --- E-mail ---
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER")

    # --- Egyéb ---
    LANGUAGES = ["hu", "en", "de"]
