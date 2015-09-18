import yaml
from flask import Blueprint
from flask.views import MethodView
from kubedock.utils import (login_required_or_basic_or_token, KubeUtils,
                            register_api, maintenance_protected, APIError,
                            send_event)
from kubedock.kapi.podcollection import PodCollection
from kubedock.validation import check_new_pod_data
from kubedock.settings import KUBE_API_VERSION

yamlapi = Blueprint('yaml_api', __name__, url_prefix='/yamlapi')


class YamlAPI(KubeUtils, MethodView):
    decorators = (
        KubeUtils.jsonwrap,
        KubeUtils.pod_permissions,
        KubeUtils.pod_start_permissions,
        login_required_or_basic_or_token
    )

    @maintenance_protected
    def post(self):
        user = self._get_current_user()
        data = self._get_params().get('data')
        if data is None:
            raise APIError('No "data" provided')
        try:
            parsed_data = list(yaml.safe_load_all(data))
        except yaml.YAMLError as e:
            raise APIError('Incorrect yaml, parsing failed: "{0}"'.format(e))
        new_pod = dispatch_kind(parsed_data)
        check_new_pod_data(new_pod, user)

        try:
            res = PodCollection(user).add(new_pod)
        except APIError as e:
            raise e
        except Exception as e:
            raise APIError('Unknown error during creating pod: {0}'.format(e))
        send_event('pull_pods_state', 'ping', channel='user_%s' % user.id)
        return res

register_api(yamlapi, YamlAPI, 'yamlapi', '/', 'pod_id', strict_slashes=False)


def dispatch_kind(docs):
    if not docs or not docs[0]:     # at least one needed
        raise APIError("No objects found in data")
    pod, rc, service = None, None, None
    for doc in docs:
        kind = doc.get('kind')
        if not kind:
            raise APIError('No object kind information')
        api_version = doc.get('apiVersion')
        if api_version != KUBE_API_VERSION:
            raise APIError(
                'Not supported apiVersion. Must be {0}'.format(KUBE_API_VERSION))
        if kind == 'Pod':
            pod = doc
        elif kind == 'ReplicationController':
            rc = doc
        elif kind == 'Service':
            service = doc
        else:
            raise APIError('Unsupported object kind')
    if not pod and not rc:
        raise APIError('At least Pod or ReplicationController is needed')
    if pod and rc:
        raise APIError('Only one Pod or ReplicationController is allowed '
                       'but not both')
    return process_pod(pod, rc, service)


def process_pod(pod, rc, service):
    # TODO for now Services are useless and ignored
    if rc:
        pod_name = rc.get('metadata', {}).get('name', '')
        rc_spec = rc.get('spec', {})
        spec_body = rc_spec.get('template', {}).get('spec', {})
        kube_type = rc_spec.get('kube_type', 0)
        replicas = rc_spec.get('replicas', 1)
    else:
        pod_name = pod.get('metadata', {}).get('name', '')
        spec_body = pod.get('spec', {})
        kube_type = spec_body.get('kube_type', 0)
        replicas = spec_body.get('replicas', 1)

    new_pod = {
        'name': pod_name,
        'restartPolicy': spec_body.get('restartPolicy', "Always")
    }

    if 'containers' in spec_body:
        containers = spec_body['containers'] or []
        for c in containers:
            for p in c.get('ports', []):
                if p.get('isPublic'):
                    new_pod['set_public_ip'] = True
                p.pop('name', '')
        new_pod['containers'] = containers

    if 'volumes' in spec_body:
        new_pod['volumes'] = spec_body['volumes'] or []

    new_pod['kube_type'] = kube_type
    new_pod['replicas'] = replicas
    return new_pod
