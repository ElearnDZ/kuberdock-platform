import logging
import itertools
from time import sleep

from tests_integration.lib import utils
from tests_integration.lib.pipelines import pipeline


LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

IMAGE = 'nginx'

PODS = [
    {
        'name': 'test_nginx_never',
        'image': IMAGE,
        'restart_policy': 'Never',
        'owner': 'test_user',
    },
    {
        'name': 'test_nginx_on_failure',
        'image': IMAGE,
        'restart_policy': 'OnFailure',
        'owner': 'test_user',
    },
    {
        'name': 'test_nginx_always',
        'image': IMAGE,
        'restart_policy': 'Always',
        'owner': 'test_user',
    }
]


@pipeline('fail_conditions')
def test_resume_halt_host(cluster):
    node = cluster.nodes.get_node('node1')

    cluster.power_off('node1')
    node.wait_for_status('troubles')

    cluster.power_on('node1')
    node.wait_for_status('running')
    cluster.ssh_exec('node1', "echo 'hello world'", check_retcode=True)


@pipeline('fail_conditions')
def test_pod_restart_policy(cluster):
    """
    This test automates TR case "Running pod restart policy"
    https://cloudlinux.testrail.net/index.php?/cases/view/235
    """
    pods = {
        p['name']: cluster.pods.create(**p) for p in PODS
    }

    for pod in pods.values():
        pod.wait_for_status('running')

    # FIXME in AC-4123. Expected test behavior is not implemented inside KD yet
    # _test_hosting_node_failure(cluster, pods)

    for pod in pods.values():
        _test_container_failure(cluster, pod)

    # NOTE: We will sequentially change policy policies[i] -> policies[i+1],
    # this way we cover all possible policy changes.
    policies = ['Always', 'OnFailure', 'Never', 'Always', 'Never', 'OnFailure',
                'Always']

    # Try all possible restart policies on any pod
    pod = pods.values()[0]
    for policy in policies:
        # This may accur only on first policy change.
        if pod.restart_policy == policy:
            continue
        _test_change_restart_policy(cluster, pod, policy)


def _test_container_failure(cluster, pod):
    msg = ("Check that pod '{}' with restart policy '{}' becomes '{}' after "
           "container failure")
    utils.log_debug(
        msg.format(pod.name, pod.restart_policy,
                   'failed' if pod.restart_policy == 'Never' else 'running'),
        LOG)

    c_id = pod.get_container_id(container_image=IMAGE)
    hosting_node = pod.node

    cluster.ssh_exec(hosting_node, 'docker kill {}'.format(c_id))

    if pod.restart_policy == 'Never':
        utils.log_debug(
            "Pod '{}' should become 'failed' after container failure".format(
                pod.name),
            LOG)
        pod.wait_for_status('failed')
    else:
        utils.log_debug(
            "Pod '{}' should become 'running' after container failure "
            "New container should be started as well".format(pod.name),
            LOG)
        utils.wait_for(
            lambda: c_id != pod.get_container_id(container_image=IMAGE))
        pod.wait_for_status('running')


def _test_change_restart_policy(cluster, pod, policy):
    c_id = pod.get_container_id(container_image=IMAGE)

    msg = "Pod '{}'. change restartPolicy from '{}' to restartPolicy '{}'"
    utils.log_debug(msg.format(pod.name, pod.restart_policy, policy), LOG)
    pod.set_restart_policy(policy)
    utils.wait_for(lambda: c_id != pod.get_container_id(container_image=IMAGE))
    pod.wait_for_status('running')

    _test_container_failure(cluster, pod)


def _test_hosting_node_failure(cluster, pods):
    # There's only one node in this pipeline, so it's guaranteed that all
    # of the pods land on a single node
    hosting_node = pods[pods.keys()[0]].node
    # FIXME in AC-4123.
    # NOTE: Current behavior is to STOP pods on node failure.
    msg = "Make sure pod '{}' becomes 'pending'"
    container_ids = {pod.name: pod.get_container_id(container_image=IMAGE)
                     for pod in pods.values()}
    with cluster.temporary_stop_host(hosting_node):
        for pod_name, pod in pods.items():
            utils.log_debug(msg.format(pod_name), LOG)
            pod.wait_for_status('pending')

    msg = "Wait until container ID for pod '{}' changes"
    for pod_name, c_id in container_ids.items():
        utils.log_debug(msg.format(pod_name), LOG)
        utils.wait_for(lambda: c_id !=
                       pod[pod_name].get_container_id(container_image=IMAGE))

    # Wait until pods become running again
    for pod in pods.values():
        pod.wait_for_status('running')
