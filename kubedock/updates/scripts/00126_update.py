from kubedock.kapi.helpers import KubeQuery, get_pod_config, replace_pod_config
from kubedock.kapi.podcollection import PodCollection


def upgrade(upd, with_testing, *args, **kwargs):
    pod_collection = PodCollection()
    for pod_dict in pod_collection.get(as_json=False):
        pod = pod_collection._get_by_id(pod_dict['id'])
        db_config = get_pod_config(pod.id)
        cluster_ip = db_config.pop('clusterIP', None)
        if cluster_ip is None:
            service_name = db_config.get('service')
            if service_name is None:
                continue
            namespace = db_config.get('namespace') or pod.id
            service = KubeQuery().get(['services', service_name], ns=namespace)
            cluster_ip = service.get('spec', {}).get('clusterIP')
            if cluster_ip is not None:
                db_config['podIP'] = cluster_ip
        replace_pod_config(pod, db_config)


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('No downgrade provided')
