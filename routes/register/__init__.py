# routes/register/__init__.py
from flask import Blueprint

register_bp = Blueprint('register', __name__, url_prefix='/register')

from . import views  # a view-ek itt kerülnek betöltésre (nem main-t hívunk)
