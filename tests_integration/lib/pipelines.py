import os
from collections import defaultdict
from functools import wraps

from tests_integration.lib.pipelines_base import Pipeline, \
    UpgradedPipelineMixin


class MainPipeline(Pipeline):
    NAME = 'main'
    ROUTABLE_IP_COUNT = 1
    ENV = {
        'KD_NODES_COUNT': '1',
        'KD_TIMEZONE': 'Europe/Moscow'
    }


class MainUpgradedPipeline(UpgradedPipelineMixin, MainPipeline):
    NAME = 'main_upgraded'


class NetworkingPipeline(Pipeline):
    NAME = 'networking'
    ROUTABLE_IP_COUNT = 2
    ENV = {
        'KD_NODES_COUNT': '2',
        'KD_RHOSTS_COUNT': '1',
        # rhost: use the same template as for master/nodes - cent7
        'KD_NEBULA_RHOST_TEMPLATE_ID': os.environ.get('KD_NEBULA_TEMPLATE_ID')
    }

    def set_up(self):
        super(NetworkingPipeline, self).set_up()
        self.cluster.preload_docker_image('nginx')
        self.cluster.recreate_routable_ip_pool()


class NetworkingUpgradedPipeline(UpgradedPipelineMixin, NetworkingPipeline):
    NAME = 'networking_upgraded'


class NetworkingRhostCent6Pipeline(NetworkingPipeline):
    NAME = 'networking_rhost_cent6'
    ENV = {
        # KD_NEBULA_RHOST_TEMPLATE_ID set in kuberdock-ci-env points to cent6
        'KD_NEBULA_RHOST_TEMPLATE_ID':
            os.environ['KD_NEBULA_RHOST_TEMPLATE_ID']
    }


class NonfloatingPipeline(Pipeline):
    NAME = 'nonfloating'
    ROUTABLE_IP_COUNT = 3
    ENV = {
        'KD_NONFLOATING_PUBLIC_IPS': 'true',
        'KD_NODES_COUNT': '2',
    }

    def cleanup(self):
        super(NonfloatingPipeline, self).cleanup()
        self.cluster.delete_all_ip_pools()


class CephPipeline(Pipeline):
    NAME = 'ceph'
    ROUTABLE_IP_COUNT = 2
    ENV = {
        'KD_NODES_COUNT': '1',
        'KD_DEPLOY_SKIP': 'predefined_apps,cleanup,ui_patch,route',
        'KD_CEPH': '1',
        'KD_CEPH_USER': 'jenkins',
        'KD_CEPH_CONFIG': 'ceph_configs/ceph.conf',
        'KD_CEPH_USER_KEYRING': 'ceph_configs/client.jenkins.keyring',
        'KD_PD_NAMESPACE': 'jenkins_pool'
    }

    def tear_down(self):
        """
        Remove all Ceph images
        """
        self.cleanup()


class CephUpgradedPipeline(UpgradedPipelineMixin, CephPipeline):
    NAME = 'ceph_upgraded'


class KubeTypePipeline(Pipeline):
    NAME = 'kubetype'
    ROUTABLE_IP_COUNT = 2
    ENV = {
        'KD_NODES_COUNT': '2',
        'KD_NODE_TYPES': 'node1=standard,node2=tiny'
    }


class FailConditionsPipeline(Pipeline):
    NAME = 'fail_conditions'
    ROUTABLE_IP_COUNT = 1
    ENV = {
        'KD_NODES_COUNT': '1',
    }


class PodRestorePipeline(Pipeline):
    NAME = 'pod_restore'
    ROUTABLE_IP_COUNT = 2
    ENV = {
        'KD_NODES_COUNT': '1',
    }

    def cleanup(self):
        super(PodRestorePipeline, self).cleanup()
        self.cluster.recreate_routable_ip_pool()


# TODO: Drop in 1.4 release
class PodRestoreUpgradedPipeline(UpgradedPipelineMixin, PodRestorePipeline):
    NAME = 'pod_restore_upgraded'


class MasterRestorePipeline(Pipeline):
    NAME = 'master_backup_restore'
    ROUTABLE_IP_COUNT = 2
    ENV = {
        'KD_NODES_COUNT': '1',
        'KD_DEPLOY_SKIP': 'cleanup,ui_patch'
    }

    def set_up(self):
        self.cleanup()


pipelines = defaultdict(list)


def pipeline(name, thread=1):
    """
    Register that a test should be executed in a pipeline with a given name
    in a specified thread. Decorator can be used multiple times which means
    that a test should be executed in different pipelines.
    That allows a test runner to know which pipelines should it create and
    which tests should it run in them. Does nothing to the test function

    :param name: the name of a pipeline. Is used to find a Pipeline class
        defined above
    :param thread: the thread id to pin the test to. Is used to create
        multiple pipelines of the same type and run a test in a particular
        one.
        Eg. If you decorate one test with pipeline('main', thread=1) and
        another with pipeline('main', thread=2) then a runner will create 2
        main clusters and run each test on its own cluster
    """

    def wrap(f):
        pipelines[(name, thread)].append(f)

        @wraps(f)
        def wrapped(*args, **kwargs):
            return f(*args, **kwargs)

        return wrapped

    return wrap
