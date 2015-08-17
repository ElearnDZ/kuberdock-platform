import base64
import json
import shlex
from uuid import uuid4
from flask import current_app
from .helpers import KubeQuery, ModelQuery, Utilities
from .ippool import IpAddrPool

from .pstorage import CephStorage, AmazonStorage
from ..billing import kubes_to_limits
from ..settings import KUBE_API_VERSION, PD_SEPARATOR, KUBERDOCK_INTERNAL_USER, AWS, CEPH

class Pod(KubeQuery, ModelQuery, Utilities):

    def __init__(self, data=None):
        if data is not None:
            for c in data['containers']:
                if len(c['command']) == 1:
                    # it seems the command has been changed
                    # or may be its length is only 1 item
                    c['command'] = self._parse_cmd_string(c['command'][0])
            for k, v in data.items():
                setattr(self, k, v)

    @staticmethod
    def create(data):
        set_public_ip = data.pop('set_public_ip', None)
        owner = data.pop('owner', None)
        pod = Pod(data)
        pod._check_pod_name(owner)
        if set_public_ip:
            if AWS:
                pod.public_aws = True
            else:
                ip = IpAddrPool().get_free()
                pod.public_ip = unicode(ip, encoding='utf-8') if ip is not None else None
        pod._make_uuid_if_missing()
        pod.sid = pod._make_sid()
        return pod

    @staticmethod
    def populate(data):
        pod = Pod()
        metadata = data.get('metadata', {})
        status = data.get('status', {})
        spec = data.get('spec', {})
        pod.sid        = metadata.get('name')
        pod.id         = metadata.get('uid')
        pod.name       = metadata.get('labels', {}).get('name')
        pod.namespace  = metadata.get('namespace')
        pod.replicationController = False
        pod.replicas   = 1
        pod.status     = status.get('phase', 'pending').lower()
        pod.host       = spec.get('nodeName')
        pod.kube_type  = spec.get('nodeSelector', {}).get('kuberdock-kube-type')
        pod.node       = spec.get('nodeSelector', {}).get('kuberdock-node-hostname')
        pod.volumes    = spec.get('volumes', [])
        pod.labels     = metadata.get('labels')
        pod.containers = spec.get('containers', [])
        pod.restartPolicy = spec.get('restartPolicy')

        if pod.status == 'running':
            for pod_item in status.get('containerStatuses', []):
                if pod_item['name'] == 'POD':
                    continue
                for container in pod.containers:
                    if container['name'] == pod_item['name']:
                        state, startedAt = pod_item.pop('state').items()[0]
                        pod_item['state'] = state
                        pod_item['startedAt'] = startedAt.get('startedAt')
                        container_id = pod_item.get('containerID', container['name'])
                        image_id = pod_item.get('imageID', container['image'])
                        pod_item['containerID'] = container_id.strip('docker://')
                        pod_item['imageID'] = image_id.strip('docker://')
                        container.update(pod_item)
        else:
            pod._forge_dockers(status=pod.status)
        return pod

    def as_dict(self):
        return dict([(k, v) for k, v in vars(self).items()])

    def as_json(self):
        return json.dumps(self.as_dict())

    def _make_uuid_if_missing(self):
        if hasattr(self, 'id'):
            return
        self.id = str(uuid4())

    def compose_persistent(self, owner):
        if not getattr(self, 'volumes', False):
            return
        for volume in self.volumes:
            try:
                pd = volume.pop('persistentDisk')
                device = '{0}{1}{2}'.format(
                    pd.get('pdName'), PD_SEPARATOR, owner.username)
                size = pd.get('pdSize')
                if CEPH:
                    volume['rbd'] = {
                        'image': device,
                        'keyring': '/etc/ceph/ceph.client.admin.keyring',
                        'fsType': 'ext4',
                        'user': 'admin',
                        'pool': 'rbd'
                    }
                    if size is not None:
                        volume['rbd']['size'] = size
                    try:
                        volume['rbd']['monitors'] = monitors
                    except NameError:
                        cs = CephStorage()
                        monitors = cs.get_monitors()
                        volume['rbd']['monitors'] = monitors
            except KeyError:
                continue

    #def compose_persistent(self, username):
    #    if not getattr(self, 'volumes', False):
    #        return
    #    path = 'pd.sh'
    #    for volume in self.volumes:
    #        try:
    #            pd = volume.pop('persistentDisk')
    #            name = volume['name']
    #            device = '{0}{1}{2}'.format(
    #                pd.get('pdName'), PD_SEPARATOR, username)
    #            size = pd.get('pdSize')
    #            if size is None:
    #                array = ['mount', device, name]
    #            else:
    #                array = ['create', device, name, size]
    #                if AWS:
    #                    try:
    #                        from ..settings import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
    #                        array.extend([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY])
    #                    except ImportError:
    #                        pass
    #            fmt = ';'.join(['{{{0}}}'.format(i) for i in range(len(array))])
    #            params = base64.b64encode(fmt.format(*array))
    #
    #            volume['scriptableDisk'] = {
    #                'pathToScript': path,
    #                'params': params
    #            }
    #        except KeyError:
    #            continue

    def prepare(self):
        kube_type = getattr(self, 'kube_type', 0)
        if self.replicationController:
            config = {
                "kind": "ReplicationController",
                "apiVersion": KUBE_API_VERSION,
                "metadata": {
                    "name": self.sid,
                    "namespace": self.namespace,
                    "uid": self.id,
                    "labels": {
                        "name": self.name
                    }
                },
                "spec": {
                    "replicas": 1,
                    "selector": {
                        "name": self.name
                    },
                    "template": {
                        "metadata": {
                            "labels": {
                                "name": self.name
                            }
                        },
                        "spec": {
                            "volumes": getattr(self, 'volumes', []),
                            "containers": [self._prepare_container(c, kube_type)
                                           for c in self.containers],
                            "nodeSelector": {
                                "kuberdock-kube-type": "type_{0}".format(kube_type)
                            },
                        }
                    }
                }
            }
            pod_config = config['spec']['template']
        else:
            config = {
                "kind": "Pod",
                "apiVersion": KUBE_API_VERSION,
                "metadata": {
                    "name": self.sid,
                    "namespace": self.namespace,
                    "uid": self.id,
                    "labels": {
                        "name": self.name
                    }
                },
                "spec": {
                    "volumes": getattr(self, 'volumes', []),
                    "containers": [
                        self._prepare_container(c, kube_type)
                            for c in self.containers],
                    "restartPolicy": getattr(self, 'restartPolicy', 'Always'),
                    "nodeSelector": {
                        "kuberdock-kube-type": "type_{0}".format(kube_type)
                    },
                }
            }
            pod_config = config
        if hasattr(self, 'node') and self.node:
            pod_config['spec']['nodeSelector']['kuberdock-node-hostname'] = self.node
        if hasattr(self, 'public_ip'):
            pod_config['metadata']['labels']['kuberdock-public-ip'] = self.public_ip
        return config

    def _prepare_container(self, data, kube_type=0):
        if not data.get('name'):
            data['name'] = self._make_name_from_image(data.get('image', ''))

        try:
            kubes = int(data.pop('kubes'))
        except (KeyError, ValueError):
            pass
        else:   # if we create pod, not start stopped
            data.update(kubes_to_limits(kubes, kube_type))

        wd = data.get('workingDir', '.')
        if type(wd) is list:
            data['workingDir'] = ','.join(data['workingDir'])

        for p in data.get('ports', []):
            p['protocol'] = p.get('protocol', 'TCP').upper()

        if self.owner != KUBERDOCK_INTERNAL_USER:
            for p in data.get('ports', []):
                p.pop('hostPort', None)
        return data

    def _parse_cmd_string(self, cmd_string):
        lex = shlex.shlex(cmd_string, posix=True)
        lex.whitespace_split = True
        lex.commenters = ''
        lex.wordchars += '.'
        try:
            return list(lex)
        except ValueError:
            self._raise('Incorrect cmd string')

    @property
    def kind(self):
        if getattr(self, 'replicationController', False):
            return 'replicationcontrollers'
        else:
            return 'pods'

    def _forge_dockers(self, status='stopped'):
        for container in self.containers:
            container.update({
                'containerID': container['name'],
                'imageID': container['image'],
                'lastState': {},
                'ready': False,
                'restartCount': 0,
                'state': status,
                'startedAt': None,
            })

    def __repr__(self):
        return "<Pod ('name':{0})>".format(self.name)