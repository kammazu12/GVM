# routes/profile/__init__.py
from flask import Blueprint

profile_bp = Blueprint('profile', __name__)

from . import views  # a view-ek itt kerülnek betöltésre (nem main-t hívunk)
