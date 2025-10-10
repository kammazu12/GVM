# routes/matching/__init__.py
from flask import Blueprint

matching_bp = Blueprint('matching', __name__)

from . import views  # a view-ek itt kerülnek betöltésre (nem main-t hívunk)
