# routes/vehicles/__init__.py
from flask import Blueprint

vehicles_bp = Blueprint('vehicles', __name__, url_prefix='/vehicles')

from . import views  # a view-ek itt kerülnek betöltésre (nem main-t hívunk)
