# routes/cargo/__init__.py
from flask import Blueprint

cargo_bp = Blueprint('cargo', __name__, url_prefix='/cargo')

from . import views  # a view-ek itt kerülnek betöltésre (nem main-t hívunk)
