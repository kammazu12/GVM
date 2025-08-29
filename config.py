import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'supersecretkey')
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '766372481029-42t68pqcoclakd9la47qci3nc9ktgd33.apps.googleusercontent.com')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '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')
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://127.0.0.1:5000/oauth2callback')
