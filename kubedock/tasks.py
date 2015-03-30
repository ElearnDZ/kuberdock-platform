import json
import requests
import time
import operator
from collections import OrderedDict
from datetime import datetime

from .settings import DEBUG, NODE_SSH_AUTH
from .api.stream import send_event
from .core import ConnectionPool, db, ssh_connect, fast_cmd
from .factory import make_celery
from .utils import update_dict
from .stats import StatWrap5Min
from .kubedata.kubestat import KubeUnitResolver, KubeStat
from .models import Pod, ContainerState
from .settings import KUBE_API_VERSION

from .utils import get_api_url


DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


celery = make_celery()


def search_image(term, url=None, page=None):
    page = page or 1
    if url is None:
        url = 'https://registry.hub.docker.com/v1/search'
    else:
        if not url.rstrip('/').endswith('v1/search'):
            url = '{0}/v1/search'.format(url.rstrip('/'))
    data = {'q': term, 'n': 10, 'page': page}
    r = requests.get(url, params=data)
    return r.text


@celery.task()
def get_container_images(term, url=None, page=None):
    return search_image(term, url, page)


@celery.task()
def get_pods(pod_id=None):
    url = get_api_url('pods')
    if pod_id is not None:
        url = get_api_url('pods', pod_id)
    r = requests.get(url)
    return json.loads(r.text)


def get_pods_nodelay(pod_id=None):
    url = get_api_url('pods')
    if pod_id is not None:
        url = get_api_url('pods', pod_id)
    r = requests.get(url)
    return json.loads(r.text)


@celery.task()
def get_replicas():
    r = requests.get(get_api_url('replicationControllers'))
    return json.loads(r.text)


def get_replicas_nodelay():
    r = requests.get(get_api_url('replicationControllers'))
    return json.loads(r.text)


@celery.task()
def get_services():
    r = requests.get(get_api_url('services'))
    return json.loads(r.text)


def get_services_nodelay():
    r = requests.get(get_api_url('services'))
    return json.loads(r.text)


@celery.task()
def create_containers(data):
    kind = data['kind'][0].lower() + data['kind'][1:] + 's'
    r = requests.post(get_api_url(kind), data=json.dumps(data))
    return r.text


def create_containers_nodelay(data):
    kind = data['kind'][0].lower() + data['kind'][1:] + 's'
    r = requests.post(get_api_url(kind), data=json.dumps(data))
    return r.text


@celery.task()
def create_service(data):
    r = requests.post(get_api_url('services'), data=json.dumps(data))
    return r.text


def create_service_nodelay(data):
    r = requests.post(get_api_url('services'), data=json.dumps(data))
    return r.text


@celery.task()
def delete_pod(item):
    r = requests.delete(get_api_url('pods', item))
    return json.loads(r.text)


def delete_pod_nodelay(item):
    r = requests.delete(get_api_url('pods', item))
    return json.loads(r.text)


@celery.task()
def delete_replica(item):
    r = requests.delete(get_api_url('replicationControllers', item))
    return json.loads(r.text)


def delete_replica_nodelay(item):
    r = requests.delete(get_api_url('replicationControllers', item))
    return json.loads(r.text)


@celery.task()
def update_replica(item, diff):
    url = get_api_url('replicationControllers', item)
    r = requests.get(url)
    data = json.loads(r.text, object_pairs_hook=OrderedDict)
    update_dict(data, diff)
    headers = {'Content-Type': 'application/json'}
    r = requests.put(url, data=json.dumps(data), headers=headers)
    return json.loads(r.text)


def update_replica_nodelay(item, diff):
    url = get_api_url('replicationControllers', item)
    r = requests.get(url)
    data = json.loads(r.text, object_pairs_hook=OrderedDict)
    update_dict(data, diff)
    headers = {'Content-Type': 'application/json'}
    r = requests.put(url, data=json.dumps(data), headers=headers)
    return json.loads(r.text)


@celery.task()
def delete_service(item):
    r = requests.delete(get_api_url('services', item))
    return json.loads(r.text)


def delete_service_nodelay(item):
    r = requests.delete(get_api_url('services', item))
    return json.loads(r.text)


@celery.task()
def get_dockerfile(data):
    url = 'https://registry.hub.docker.com/u/{0}/dockerfile/raw'.format(
        data.strip('/'))
    r = requests.get(url)
    return r.text


def get_dockerfile_nodelay(data):
    url = 'https://registry.hub.docker.com/u/{0}/dockerfile/raw'.format(
        data.strip('/'))
    r = requests.get(url)
    return r.text


def get_all_nodes():
    r = requests.get(get_api_url('nodes'))
    return r.json().get('items') or []


def get_node_by_host(host):
    r = requests.get(get_api_url('nodes', host))
    return r.json()


def remove_node_by_host(host):
    r = requests.delete(get_api_url('nodes', host))
    return r.json()


def compute_capacity(cpu_count, cpu_mhz, mem_total):
    CPU_SCALE_FACTOR = 0.2
    MEM_PART_FACTOR = 1.0
    return {
        'cpu': int(round(cpu_count * cpu_mhz * CPU_SCALE_FACTOR)),
        'memory': int(round(mem_total * MEM_PART_FACTOR))
    }


@celery.task()
def add_new_node(host, kube_type):
    if DEBUG:
        send_event('install_logs',
                   'Connecting to {0} with ssh with user root ...'
                   .format(host))
    else:
        send_event('install_logs',
                   'Connecting to {0} with ssh with user = root and '
                   'ssh_key_filename = {1} ...'.format(host, NODE_SSH_AUTH))
    ssh, error_message = ssh_connect(host)
    if error_message:
        send_event('install_logs', error_message)
        return error_message

    sftp = ssh.open_sftp()
    sftp.put('kub_install.sh', '/kub_install.sh')
    sftp.close()
    i, o, e = ssh.exec_command('bash /kub_install.sh')
    s_time = time.time()
    while not o.channel.exit_status_ready():
        if o.channel.recv_ready():
            for line in o.channel.recv(1024).split('\n'):
                send_event('install_logs', line)
        if (time.time() - s_time) > 15*60:   # 15 min timeout
            err = 'Timeout during install. Installation has failed.'
            send_event('install_logs', err)
            ssh.exec_command('rm /kub_install.sh')
            ssh.close()
            return err
        time.sleep(0.2)
    s = o.channel.recv_exit_status()
    ssh.exec_command('rm /kub_install.sh')
    if s != 0:
        res = 'Installation script error. Exit status: {0}. Error: {1}'\
            .format(s, e.read())
        send_event('install_logs', res)
    else:
        ok, data = fast_cmd(ssh, 'lscpu | grep ^CPU\(s\) | cut -f 2 -d\:')
        if not ok:
            send_event('install_logs', "Can't retrieve cpu count using lscpu")
            ssh.close()
            return data
        cpu_count = int(data.strip())

        # TODO this MHz is not true
        ok, data = fast_cmd(ssh, 'lscpu | grep ^CPU\ MHz | cut -f 2 -d\:')
        if not ok:
            send_event('install_logs', "Can't retrieve cpu MHz using lscpu")
            ssh.close()
            return data
        cpu_mhz = float(data.strip())

        ok, data = fast_cmd(ssh, 'cat /proc/meminfo | grep MemTotal |'
                                 ' cut -f 2 -d\: | cut -f 1 -dk')
        if not ok:
            send_event('install_logs', "Can't retrieve MemTotal using /proc")
            ssh.close()
            return data
        mem_total = int(data.strip()) * 1024  # was in Kb

        cap = compute_capacity(cpu_count, cpu_mhz, mem_total)

        res = requests.post(get_api_url('nodes'),
                            json={'id': host,
                                  'apiVersion': KUBE_API_VERSION,
                                  'resources': {
                                      'capacity': cap
                                  },
                                  'labels': {
                                      'kuberdock-node-hostname': host,
                                      'kuberdock-kube-type': 'type_' +
                                                             str(kube_type)
                                  }
                            }).json()
        send_event('install_logs', 'Adding Node completed successful.')
        send_event('install_logs', '===================================')
    ssh.close()
    return res


def parse_pods_statuses(data):
    db_pods = {}
    for pod in Pod.query.filter(Pod.status != 'deleted').values(
            Pod.name, Pod.id, Pod.config):
        kubes = {}
        for container in json.loads(pod[2])['containers']:
            if 'kubes' in container:
                kubes[container['name']] = container['kubes']
        db_pods[pod[0]] = {'uid': pod[1], 'kubes': kubes}
    items = data.get('items')
    res = []
    for item in items:
        current_state = item['currentState']
        pod_name = item['labels']['name']
        if pod_name in db_pods:
            current_state['uid'] = db_pods[pod_name]['uid']
            if 'info' in current_state:
                for name, data in current_state['info'].items():
                    if name in db_pods[pod_name]['kubes']:
                        data['kubes'] = db_pods[pod_name]['kubes'][name]
            res.append(current_state)
    return res


def parse_nodes_statuses(items):
    res = []
    if not items:
        return res
    for item in items:
        try:
            conditions = item['status']['conditions']
            for cond in conditions:
                status = cond['status']
                res.append(status)
        except KeyError:
            res.append('')
    return res


@celery.task()
def check_events():
    redis = ConnectionPool.get_connection()

    lock = redis.get('events_lock')
    if not lock:
        redis.setex('events_lock', 30 + 1, 'true')
    else:
        return

    nodes_list = redis.get('cached_nodes')
    if not nodes_list:
        nodes_list = get_all_nodes()
        nodes_list = parse_nodes_statuses(nodes_list)
        redis.set('cached_nodes', json.dumps(nodes_list))
        send_event('pull_nodes_state', 'ping')
    else:
        temp = get_all_nodes()
        temp = parse_nodes_statuses(temp)
        if temp != json.loads(nodes_list):
            redis.set('cached_nodes', json.dumps(temp))
            send_event('pull_nodes_state', 'ping')

    pods_list = redis.get('cached_pods')
    if not pods_list:
        pods_list = requests.get(get_api_url('pods')).json()
        pods_list = parse_pods_statuses(pods_list)
        redis.set('cached_pods', json.dumps(pods_list))
        send_event('pull_pods_state', 'ping')
    else:
        pods_list = json.loads(pods_list)
        temp = requests.get(get_api_url('pods')).json()
        temp = parse_pods_statuses(temp)
        if temp != pods_list:
            redis.set('cached_pods', json.dumps(temp))
            send_event('pull_pods_state', 'ping')

    now = datetime.now()
    now = now.replace(microsecond=0)

    for pod in pods_list:
        if 'info' in pod:
            for container_name, container_data in pod['info'].items():
                kubes = container_data.get('kubes', 1)
                for s in container_data['state'].values():
                    start = s.get('startedAt')
                    if start is None:
                        continue
                    start = datetime.strptime(start, DATETIME_FORMAT)
                    end = s.get('finishedAt')
                    if end is not None:
                        end = datetime.strptime(end, DATETIME_FORMAT)
                    add_container_state(pod['uid'], container_name, kubes,
                                        start, end)
        else:
            end_container_state(pod['uid'], now)

    pod_ids = [pod['uid'] for pod in pods_list]
    css = ContainerState.query.filter_by(end_time=None)
    for cs in css:
        exist = ContainerState.query.filter(ContainerState.pod_id == cs.pod_id,
            ContainerState.container_name == cs.container_name,
            ContainerState.start_time > cs.start_time).order_by(
            ContainerState.start_time).first()
        if exist is not None:
            cs.end_time = exist.start_time
            db.session.add(cs)
            continue
        if cs.pod_id not in pod_ids:
            cs.end_time = now
            db.session.add(cs)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    redis.delete('events_lock')


def add_container_state(pod, container, kubes, start, end):
    cs = ContainerState.query.filter_by(pod_id=pod, container_name=container,
                                        kubes=kubes, start_time=start).first()
    if cs:
        cs.end_time = end
    else:
        cs = ContainerState(pod_id=pod, container_name=container,
                            kubes=kubes, start_time=start, end_time=end)
        db.session.add(cs)


def end_container_state(pod, now):
    css = ContainerState.query.filter_by(pod_id=pod, end_time=None)
    for cs in css:
        cs.end_time = now
        db.session.add(cs)


@celery.task()
def pull_hourly_stats():
    data = KubeStat(resolution=300).stats(KubeUnitResolver().all())
    time_windows = set(map(operator.itemgetter('time_window'), data))
    rv = db.session.query(StatWrap5Min).filter(
        StatWrap5Min.time_window.in_(time_windows))
    existing_windows = set(map((lambda x: x.time_window), rv))
    for entry in data:
        if entry['time_window'] in existing_windows:
            continue
        db.session.add(StatWrap5Min(**entry))
    db.session.commit()
