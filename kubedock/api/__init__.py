import datetime
from .. import factory
from .. import sessions
from ..rbac import get_user_role
from ..settings import SERVICES_VERBOSE_LOG, PODS_VERBOSE_LOG
from ..utils import APIError, modify_node_ips, get_api_url, set_limit

from flask.ext.login import current_user
from flask import jsonify
import json
import requests
import gevent
import os
from rbac.context import PermissionDenied
from websocket import create_connection, WebSocketException


def create_app(settings_override=None, fake_sessions=False):
    skip_paths = []
    app = factory.create_app(__name__, __path__, settings_override)
    if fake_sessions:
        app.session_interface = sessions.FakeSessionInterface()
    else:
        app.session_interface = sessions.ManagedSessionInterface(
            sessions.DataBaseSessionManager(app.config['SECRET_KEY']),
            skip_paths, datetime.timedelta(days=1))

    # registering blueprings
    from .images import images
    from .stream import stream
    from .nodes import nodes
    from .stats import stats
    from .users import users
    from .notifications import notifications
    from .static_pages import static_pages
    from .usage import usage
    from .pricing import pricing
    from .ippool import ippool
    from .settings import settings
    from .podapi import podapi
    from .auth import auth
    from .pstorage import pstorage

    for bp in images, stream, nodes, stats, users, notifications, \
              static_pages, usage, pricing, ippool, settings, podapi, auth, \
              pstorage:
        app.register_blueprint(bp)

    #app.json_encoder = JSONEncoder
    app.errorhandler(404)(on_404)
    app.errorhandler(PermissionDenied)(on_permission_denied)
    app.errorhandler(APIError)(on_app_error)

    return app


def on_app_error(e):
    return jsonify({'status': 'error', 'data': e.message}), e.status_code


def on_permission_denied(e):
    message = e.kwargs['message'] or 'Denied to {0}'.format(get_user_role())
    return on_app_error(APIError('Error. {0}'.format(message), status_code=403))


def on_404(e):
    return on_app_error(APIError('Not found', status_code=404))


def filter_event(data):
    metadata = data['object']['metadata']
    if metadata['name'] in ('kubernetes', 'kubernetes-ro'):
        return None

    return data


def process_endpoints_event(data, app):
    if data is None:
        return
    if SERVICES_VERBOSE_LOG >= 2:
        print 'ENDPOINT EVENT', data
    service_name = data['object']['metadata']['name']
    current_namespace = data['object']['metadata']['namespace']
    r = requests.get(get_api_url('services', service_name,
                                 namespace=current_namespace))
    if r.status_code == 404:
        return
    service = r.json()
    event_type = data['type']
    pods = data['object']['subsets']
    if len(pods) == 0:
        if event_type == 'ADDED':
            # Handle here if public-ip added during runtime
            if SERVICES_VERBOSE_LOG >= 2:
                print 'SERVICE IN ADDED(pods 0)', service
        elif event_type == 'MODIFIED':      # when stop pod
            if SERVICES_VERBOSE_LOG >= 2:
                print 'SERVICE IN MODIF(pods 0)', service
            state = json.loads(service['metadata']['annotations']['public-ip-state'])
            if 'assigned-to' in state:
                res = modify_node_ips(service_name, state['assigned-to'], 'del',
                                      state['assigned-pod-ip'],
                                      state['assigned-public-ip'],
                                      service['spec']['ports'], app)
                if res is True:
                    del state['assigned-to']
                    del state['assigned-pod-ip']
                    service['metadata']['annotations']['public-ip-state'] = json.dumps(state)
                    # TODO what if resourceVersion has changed?
                    r = requests.put(get_api_url('services', service_name,
                                     namespace=current_namespace),
                                     json.dumps(service))
        elif event_type == 'DELETED':
            pass
            # Handle here if public-ip removed during runtime
        else:
            print 'Unknown event type in endpoints event listener:', event_type
    elif len(pods) == 1:
        state = json.loads(service['metadata']['annotations']['public-ip-state'])
        public_ip = state['assigned-public-ip']
        if not public_ip:
            # TODO change with "release ip" feature
            return
        assigned_to = state.get('assigned-to')
        podname = pods[0]['addresses'][0]['targetRef']['name']
        # Can't use task.get_pods_nodelay due cyclic imports
        kub_pod = requests.get(get_api_url('pods', podname,
                                           namespace=current_namespace)).json()
        ports = service['spec']['ports']
        # TODO what to do here when pod yet not assigned to node at this moment?
        # skip only this event or reconnect(like now)?
        current_host = kub_pod['spec']['nodeName']
        pod_ip = pods[0]['addresses'][0]['ip']
        if not assigned_to:
            res = modify_node_ips(service_name, current_host, 'add', pod_ip, public_ip, ports, app)
            if res is True:
                state['assigned-to'] = current_host
                state['assigned-pod-ip'] = pod_ip
                service['metadata']['annotations']['public-ip-state'] = json.dumps(state)
                r = requests.put(get_api_url('services', service_name,
                                 namespace=current_namespace),
                                 json.dumps(service))
        else:
            if current_host != assigned_to:     # migrate pod
                if SERVICES_VERBOSE_LOG >= 2:
                    print 'MIGRATE POD'
                res = modify_node_ips(service_name, assigned_to, 'del',
                                      state['assigned-pod-ip'],
                                      public_ip, ports, app)
                if res is True:
                    res2 = modify_node_ips(service_name, current_host, 'add', pod_ip,
                                           public_ip, ports, app)
                    if res2 is True:
                        state['assigned-to'] = current_host
                        state['assigned-pod-ip'] = pod_ip
                        service['metadata']['annotations']['public-ip-state'] = json.dumps(state)
                        r = requests.put(get_api_url('services', service_name,
                                         namespace=current_namespace), service)
    else:   # more? replica case
        pass


def process_pods_event(data, app):
    if data is None:
        return
    if PODS_VERBOSE_LOG >= 2:
        print 'POD EVENT', data
    event_type = data['type']
    if event_type != 'MODIFIED':
        return
    host = data['object']['spec']['nodeName']
    pod_name = data['object']['metadata']['labels']['name']
    containers = {}
    for container in data['object']['status'].get('containerStatuses', []):
        if 'containerID' in container:
            container_name = container['name']
            container_id = container['containerID'].partition('docker://')[2]
            containers[container_name] = container_id
    if containers:
        set_limit(host, pod_name, containers, app)


def listen_fabric(url, func, verbose=1):
    fn_name = func.func_name

    def result(app):
        while True:
            try:
                if verbose >= 2:
                    print '==START WATCH {0} == pid: {1}'.format(
                        fn_name, os.getpid())
                try:
                    ws = create_connection(url)
                except WebSocketException as e:
                    print e.__repr__()
                    gevent.sleep(0.1)
                    continue
                while True:
                    content = ws.recv()
                    if verbose >= 2:
                        print '==EVENT CONTENT {0} ==: {1}'.format(
                            fn_name, content)
                    data = json.loads(content)
                    data = filter_event(data)
                    func(data, app)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print e.__repr__(), '..restarting listen {0}...'.format(fn_name)
                gevent.sleep(0.2)
    return result


listen_pods = listen_fabric(
    get_api_url('pods', namespace=False, watch=True).replace('http', 'ws'),
    process_pods_event,
    PODS_VERBOSE_LOG
)

listen_endpoints = listen_fabric(
    get_api_url('endpoints', namespace=False, watch=True).replace('http', 'ws'),
    process_endpoints_event,
    SERVICES_VERBOSE_LOG
)
