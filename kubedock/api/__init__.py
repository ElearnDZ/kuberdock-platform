from functools import wraps

from fabric.api import env, run, put, output
from flask import jsonify, request, g

from kubedock.core import current_app
from kubedock.utils import KubeUtils, send_event_to_role, API_VERSIONS, \
    InvalidAPIVersion
from kubedock import factory
from kubedock import sessions
from kubedock.exceptions import APIError, InternalAPIError, NotFound
from kubedock.settings import SSH_KEY_FILENAME, SESSION_LIFETIME


def create_app(settings_override=None, fake_sessions=False):
    app = factory.create_app(__name__, __path__, settings_override)
    if fake_sessions:
        app.session_interface = sessions.FakeSessionInterface()
    else:
        app.session_interface = sessions.ManagedSessionInterface(
            sessions.DataBaseSessionManager(), SESSION_LIFETIME)

    # registering blueprints
    from .images import images
    from .stream import stream
    from .nodes import nodes
    from .stats import stats
    from .users import users
    from .usage import usage
    from .pricing import pricing
    from .ippool import ippool
    from .settings import settings
    from .podapi import podapi
    from .yaml_api import yamlapi
    from .auth import auth
    from .pstorage import pstorage
    from .predefined_apps import predefined_apps
    from .logs import logs
    from .hosts import hosts
    from .billing import billing
    from .domains import domains
    from .allowed_ports import allowed_ports
    from .restricted_ports import restricted_ports

    for bp in (images, stream, nodes, stats, users, yamlapi,
               usage, pricing, ippool, settings, podapi, auth,
               pstorage, predefined_apps, logs, hosts, billing, domains,
               allowed_ports, restricted_ports):
        app.register_blueprint(bp)

    app.errorhandler(404)(on_404)
    app.errorhandler(APIError)(on_app_error)

    app.before_request(handle_api_version)

    return app


def handle_api_version():
    api_version = request.headers.get('kuberdock-api-version',
                                      API_VERSIONS.default)
    g.api_version = api_version
    if api_version not in API_VERSIONS.acceptable:
        return on_app_error(InvalidAPIVersion())


def pre_start_hook(app):
    from ..nodes.models import Node
    # env.warn_only = True
    env.user = 'root'
    env.key_filename = SSH_KEY_FILENAME
    output.stdout = False
    output.running = False
    PLUGIN_DIR = '/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock/'
    with app.app_context():
        for node in Node.query.all():
            env.host_string = node.hostname
            put('./node_network_plugin.sh', PLUGIN_DIR + 'kuberdock')
            put('./node_network_plugin.py', PLUGIN_DIR + 'kuberdock.py')
            run('systemctl restart kuberdock-watcher')
            print 'Kuberdock node parts are updated'


def on_app_error(e):
    try:
        current_user = KubeUtils.get_current_user()
    except AttributeError:
        current_user = None

    if isinstance(e, InternalAPIError):
        current_app.logger.error(e.message, exc_info=e.exc_info)

        if current_user and current_user.is_administrator():
            return _jsonify_api_error(e)
        else:
            send_event_to_role('notify:error', {'message': e.message}, 'Admin')
            return _jsonify_api_error(
                APIError(e.response_message or 'Unknown error', 500))

    elif isinstance(e, APIError):
        return _jsonify_api_error(e)

    else:  # unexpected error
        current_app.logger.exception(e.message)
        if current_user and current_user.is_administrator():
            return _jsonify_api_error(APIError(repr(e), 500))
        else:
            send_event_to_role('notify:error',
                               {'message': 'Unexpected error: ' + repr(e)},
                               'Admin')
            _jsonify_api_error(
                APIError('Internal error, please contact administrator', 500))


def _jsonify_api_error(e):
    api_version = (g.api_version if g.api_version in API_VERSIONS.acceptable
                   else API_VERSIONS.default)

    if api_version == API_VERSIONS.v1:
        return jsonify({
            'status': 'error',
            'data': e.message,  # left for backwards compatibility
            'details': e.details,
            'type': e.type,
        }), e.status_code
    else:
        return jsonify({
            'status': 'error',
            'message': e.message,
            'details': e.details,
            'type': e.type,
        }), e.status_code


def on_404(e):
    return on_app_error(NotFound())


def populate_registered_hosts(app):
    from ..kapi.nginx_utils import update_nginx_proxy_restriction

    with app.app_context():
        update_nginx_proxy_restriction()


class check_api_version(object):
    """Check that api version in request is one of `acceptable_versions`.

    Can be used as decorator, callback (use #check method), or coerced to
    boolean.
    """
    def __init__(self, acceptable_versions):
        self.acceptable_versions = acceptable_versions

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return wraps(func)(wrapper)

    def __enter__(self):
        self.check()
        return self

    def __exit__(self, *args, **kwargs):
        pass

    def __nonzero__(self):
        version = g.api_version if hasattr(g, 'api_version') else \
            API_VERSIONS.v1
        return version in self.acceptable_versions

    def check(self):
        if not self:
            raise InvalidAPIVersion(
                acceptableVersions=self.acceptable_versions)
