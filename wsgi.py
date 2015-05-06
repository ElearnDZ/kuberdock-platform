import gevent
import gevent.monkey
gevent.monkey.patch_all()
from psycogreen.gevent import patch_psycopg; patch_psycopg()

from werkzeug.wsgi import DispatcherMiddleware
from werkzeug.serving import run_with_reloader
from werkzeug.debug import DebuggedApplication
from gevent.wsgi import WSGIServer

from kubedock import frontend, api

application = DispatcherMiddleware(
    frontend.create_app(),
    {'/api': api.create_app()}
)

try:
    import uwsgi
except ImportError:
    pass
else:
    if uwsgi.worker_id() == 1:
        g = gevent.spawn(api.listen_endpoints)

if __name__ == "__main__":

    import os
    if os.environ.get('WERKZEUG_RUN_MAIN'):
        g = gevent.spawn(api.listen_endpoints)

    @run_with_reloader
    def run_server():
        http_server = WSGIServer(('', 5000), DebuggedApplication(application))
        http_server.serve_forever()