from flask import Blueprint, current_app, request
from flask.ext.login import current_user
from ..core import ConnectionPool, EvtStream
from ..decorators import login_required_or_basic_or_token

stream = Blueprint('stream', __name__, url_prefix='/stream')


@stream.route('')
@login_required_or_basic_or_token
def send_stream():
    conn = ConnectionPool.get_connection()
    if current_user.is_administrator():
        channel = 'common'
    else:
        channel = 'user_{0}'.format(current_user.id)
    return current_app.response_class(
        EvtStream(conn, channel, request.headers.get('Last-Event-Id')),
        direct_passthrough=True,
        mimetype='text/event-stream')
