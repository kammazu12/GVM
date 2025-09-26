# routes/home/__init__.py
from flask import Blueprint

home_bp = Blueprint('home', __name__, url_prefix='/')

from . import views  # a view-ek itt kerülnek betöltésre (nem main-t hívunk)
