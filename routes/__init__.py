# routes/__init__.py
from .company import company_bp
from .home import home_bp
from .profile import profile_bp
from .register import register_bp
from .cargo import cargo_bp
from .login import login_bp
from .email import email_bp
from .statistics import statistics_bp
from .vehicles import vehicles_bp
from .chat import chat_bp

blueprints = [
    company_bp,
    profile_bp,
    register_bp,
    cargo_bp,
    login_bp,
    email_bp,
    home_bp,
    statistics_bp,
    chat_bp,
    vehicles_bp
]
