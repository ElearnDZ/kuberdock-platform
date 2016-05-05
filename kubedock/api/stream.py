from flask import Blueprint, current_app, request
from ..core import ConnectionPool, EvtStream
from ..login import current_user, auth_required


stream = Blueprint('stream', __name__, url_prefix='/stream')


@stream.route('')
@auth_required
def send_stream():
    conn = ConnectionPool.get_connection()
    if current_user.is_administrator():
        channel = 'common'
    else:
        channel = 'user_{0}'.format(current_user.id)
    last_id = request.headers.get('Last-Event-Id')
    if last_id is None:
        last_id = request.args.get('lastid')
    return current_app.response_class(
        EvtStream(conn, channel, last_id),
        direct_passthrough=True,
        mimetype='text/event-stream')
