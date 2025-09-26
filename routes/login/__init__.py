# routes/login/__init__.py
from flask import Blueprint

login_bp = Blueprint('login', __name__, url_prefix='/login')

from . import views  # a view-ek itt kerülnek betöltésre (nem main-t hívunk)
