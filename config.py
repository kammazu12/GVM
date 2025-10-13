# config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'supersecretkey')
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '766372481029-42t68pqcoclakd9la47qci3nc9ktgd33.apps.googleusercontent.com')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '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')
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://127.0.0.1:5000/login/oauth2callback')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "None"

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", 'alex@gvmszallitmanyozas.hu')
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", 'jxow dezy evws fxuo')
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", ('GVM Europe', 'alex@gvmszallitmanyozas.hu'))

    LANGUAGES = ["hu", "en", "de"]
