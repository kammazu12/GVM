# routes/register/views.py
from flask import render_template
from flask_login import login_required, current_user
from . import statistics_bp
from utils import *

@statistics_bp.route('/statistics')
@login_required
@no_cache
def statistics():
    return render_template('statistics.html', user=current_user)