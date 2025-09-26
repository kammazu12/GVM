# routes/company/__init__.py
from flask import Blueprint

company_bp = Blueprint('company', __name__, url_prefix='/company')

from . import views  # a view-ek itt kerülnek betöltésre (nem main-t hívunk)
