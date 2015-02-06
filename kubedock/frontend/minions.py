from flask import Blueprint, render_template
import json
from ..api import minions as api_minions

minions = Blueprint('minions', __name__)


@minions.route('/minions/')
@minions.route('/minions/<path:p>/', endpoint='other')
def index(**kwargs):
    return render_template(
        'minions/index.html',
        minions_collection=json.dumps(api_minions.get_minions_collection()))

