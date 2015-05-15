import json
from flask import current_app

from ..utils import modify_node_ips, run_ssh_command
from .pod import Pod
from .helpers import KubeQuery, ModelQuery, Utilities
from ..api.stream import send_event

class PodCollection(KubeQuery, ModelQuery, Utilities):
    
    def __init__(self):
        self._get_pods()
        current_app.logger.debug(self._collection)
        self._merge()
    
    def _get_replicas(self, name=None):
        replicas = []
        data = self._get(['replicationControllers'])
        
        for item in data['items']:
            try:
                replica_item = {
                    'id': item['uid'],
                    'sid': item['id'],
                    'replicas': item['currentState']['replicas'],
                    'replicaSelector': item['desiredState']['replicaSelector'],
                    'name': item['labels']['name']}

                if name is not None and replica_item['replicaSelector'] != name:
                    continue
                replicas.append(replica_item)
            except KeyError:
                pass
        return replicas
    
    def _get_pods(self, name=None):
        self._collection = {}
        pod_index = set()
        replicas_data = self._get_replicas()
        data = self._get(['pods'])
        services_data = self._get(['services'])
        
        for item in data['items']:  # iterate through pods list
            pod = Pod.populate(item)

            for r in replicas_data:
                if self._is_related(r.get('replicaSelector'), item.get('labels')):
                    pod.cluster = True
                    for i in 'id', 'sid', 'replicas':
                        setattr(pod, i, r[i])
                    break
                
            for s in services_data.get('items', []):
                if self._is_related(item.get('labels'), s.get('selector')):
                    pod.portalIP = s.get('portalIP')
                    pod.servicename = s.get('labels', {}).get('name')
                    break
            
            if pod.sid not in pod_index:
                self._collection[pod.name] = pod
                pod_index.add(pod.sid)

    def _merge(self):
        db_pods = self._fetch_pods(users=True)
        for db_pod in db_pods:
            if db_pod.name not in self._collection:
                pod = Pod(json.loads(db_pod.config))
                if not hasattr(pod, 'dockers'):
                    self._forge_dockers(pod)
                self._collection[pod.name] = pod
            else:
                self._collection[db_pod.name].id = db_pod.id
                self._collection[db_pod.name].kube_type = json.loads(db_pod.config).get('kube_type')
            if not hasattr(self._collection[db_pod.name], 'owner'):
                self._collection[db_pod.name].owner = db_pod.owner.username

    @staticmethod
    def _is_related(one, two):
        if one is None or two is None:
            return False
        for k in two.keys():
            if k not in one:
                return False
            if one[k] != two[k]:
                return False
            return True

    def _run_service(self, pod):
        ports = []
        for ci, c in enumerate(getattr(pod, 'containers', [])):
            for pi, p in enumerate(c.get('ports', [])):
                host_port = p.pop('hostPort', p.get('containerPort'))
                port_name = 'c{0}-p{1}'.format(ci, pi)
                if p.get('isPublic'):
                    port_name += '-public'
                ports.append({
                    "name": port_name,
                    "port": host_port,
                    "protocol": p.get('protocol'),
                    "targetPort": p.get('containerPort')})
    
        conf = {'kind': 'Service', 'apiVersion': 'v1beta3',
            'metadata': {'generateName': pod.name.lower() + '-service-',
                        'labels': {'name': pod._make_dash() + '-service'},
                'annotations': {
                    'public-ip-state': json.dumps({
                        'assigned-public-ip': getattr(pod, 'public_ip', None)
                    })
                },
            },
            'spec': {
                'selector': {'name': pod.name},
                'ports': ports,
            }
        }
        return self._put(['services'], json.dumps(conf), True)
    
    def _start_cluster(self):
        item_id = make_item_id(data['name'])
        rv = {}
        try:
            service_rv = json.loads(run_service(data))
            if 'kind' in service_rv and service_rv['kind'] == 'Service':
                rv['service_ok'] = True
                rv['portalIP'] = service_rv['portalIP']
        except TypeError:
            rv['service_ok'] = False
        except KeyError:
            rv['portalIP'] = None
    
        config = make_config(data, item_id)
    
        try:
            pod_rv = json.loads(tasks.create_containers_nodelay(config))
            if 'kind' in pod_rv and pod_rv['kind'] == 'ReplicationController':
                rv['replica_ok'] = True
                rv['replicas'] = pod_rv['desiredState']['replicas']
        except TypeError:
            rv['replica_ok'] = False
        except KeyError:
            rv['replicas'] = 0
        if rv['service_ok'] and rv['replica_ok']:
            rv['status'] = 'Running'
            rv.pop('service_ok')
            rv.pop('replica_ok')
        return rv

    @staticmethod
    def _forge_dockers(pod):
        pod.dockers = []
        for container in pod.containers:
            container['imageID'] = 'docker://'
            pod.dockers.append({
                'host': '',
                'info': {
                    'containerID': 'docker://',
                    'image': container['image'],
                    'imageID': container['imageID'],
                    'lastState': {},
                    'ready': False,
                    'restartCount': 0,
                    'state': {'stopped': {}}}})

    def get(self, as_json=False):
        if as_json:
            return json.dumps([pod.as_dict() for pod in self._collection.values()])
        return self._collection.values()
    
    def get_by_username(self, username, as_json=False):
        pods = filter((lambda x: getattr(x, 'owner', '') == username), self._collection.values())
        if as_json:
            return json.dumps([pod.as_dict() for pod in pods])
        return pods
    
    def get_by_id(self, pod_id, as_json=False):
        try:
            pod = filter((lambda x: x.id == pod_id), self._collection.values())[0]
            if as_json:
                return pod.as_json()
            return pod
        except IndexError:
            self._raise("No such item", 404)
    
    def _resize_replicas(self, pod, data):
        number = int(data.get('replicas', getattr(pod, 'replicas', 0)))
        replicas = self._get_replicas(pod.name)
        # TODO check replica numbers and compare to ones set in config
        for replica in replicas:
            rv = self._put(
                ['replicationControllers', replica.get('id', '')],
                json.loads({'desiredState': {'replicas': number}}))
            self._raise_if_failure(rv, "Could not resize a replica")
        return len(replicas)
    
    def _start_pod(self, pod, data=None):
        pod.status = 'pending'
        if pod.cluster:
            replicas_number = self._resize_replicas(pod)
            if replicas_number == 0:
                return self._start_cluster()
        else:
            config = pod.prepare()
            resource = '{0}{1}s'.format(config['kind'][0].lower(), config['kind'][1:])
            rv=self._post([resource], json.dumps(config), True)
            return rv
        
    def _stop_pod(self, pod, data=None):
        pod.status = 'stopped'
        if pod.cluster:
            self._resize_replicas(pod, 0)
        else:
            if hasattr(pod, 'sid'):
                rv = self._del(['pods', pod.sid])
                self._raise_if_failure(rv, "Could not stop a pod")
                return rv
    
    def _unknown_command(self, pod, data=None):
        self._raise("Unknown command")
    
    def _do_container_action(action, data, strip_part='docker://'):
        host = data.get('host')
        if not host:
            return
        rv = {}
        containers = data.get('containers', '').split(',')
        for container in containers:
            id_ = container
            if container.startswith(strip_part):
                id_ = container[len(strip_part):]
            command = 'docker {0} {1}'.format(action, id_)
            status, message = run_ssh_command(host, command)
            if status != 0:
                raise APIError('Docker error: {0} ({1}).'.format(message, status))
            if action in ('start', 'stop'):
                send_event('pull_pod_state', message)
            rv[container] = message or 'OK'
        return rv
    
    def _container_start(self, pod, data):
        self._do_container_action('start', data)
    
    def _container_stop(self, pod, data):
        self._do_container_action('stop', data)
    
    def _container_delete(self, pod, data):
        self._do_container_action('rm', data)
    
    def update(self, pod, data):
        command = data.get('command')
        if command is None:
            return
        {'start': self._start_pod,
         'stop': self._stop_pod,
         'resize': self._resize_replicas,
         'container_start': self._container_start,
         'container_stop': self._container_stop,
         'container_delete': self._container_delete,
         'unknown': self._unknown_command}.get(command, 'unknown')(pod, data)
    
    def delete(self, pod):
        if pod.owner == 'kuberdock-internal':
            self._raise('Service pod cannot be removed')
        if hasattr(pod, 'public_ip'):
            self._free_ip(pod.public_ip)
            
        #if pod.cluster:
        #    replicas_data = self._get_replicas()
        #    replicas = filter(
        #        (lambda x: x['replicaSelector'].get('name') == pod.name), replicas_data)
        #    for replica in replicas:
        #        rv = self._del([replicationControllers', replica.get('sid', '')])
        #        self._raise_if_failure(rv, "Could not remove a replica")
        
        # when we start using replicas check if all replica pods are removed
        if hasattr(pod, 'sid'):
            rv = self._del(['pods', pod.sid])
            current_app.logger.debug(rv)
            self._raise_if_failure(rv, "Could not remove a pod")
            services_data = self._get(['services'])
            services = filter(
                (lambda x: self._is_related(x.get('spec', {}).get('selector'), {'name': pod.name})),
                    services_data.get('items', []))
            for service in services:
                state = json.loads(service.get('metadata', {}).get('annotations', {}).get('public-ip-state', '{}'))
                if 'assigned-to' in state:
                    res = modify_node_ips(
                        state['assigned-to'],
                        'del',
                        state['assigned-pod-ip'],
                        state['assigned-public-ip'],
                        service.get('spec', {}).get('ports'))
                    if not res:
                        self._raise("Can't unbind ip from node({0}). Connection error".format(state['assigned-to']))
                rv = self._del([service.get('metadata', {}).get('name', '')])
                self._raise_if_failure(rv, "Could not remove a service")
        self._mark_pod_as_deleted(pod)