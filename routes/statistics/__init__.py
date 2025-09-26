# routes/stats/__init__.py
from flask import Blueprint

statistics_bp = Blueprint('statistics', __name__, url_prefix='/statistics')

from . import views  # a view-ek itt kerülnek betöltésre (nem main-t hívunk)
