import ipaddress
import operator
import sqlalchemy

from flask import current_app
from ..usage.models import IpState
from ..core import db
from ..exceptions import APIError, NoFreeIPs
from .podcollection import PodCollection
from ..pods.models import IPPool, PodIP, ip_network, Pod
from ..utils import atomic, ip2int, int2ip
from ..validation import V, ippool_schema
from ..nodes.models import Node
from ..kapi.node import Node as K8SNode, NodeException, NodeNotFound
from .lbpoll import LoadBalanceService
from ..settings import AWS, KUBERDOCK_INTERNAL_USER


class IpAddrPool(object):
    def get(self, net=None, page=None):
        """Returns list of networks or a single network.
        :param net: network ('x.x.x.x/x') optional. If it is not specified,
        then will be returned list of all networks. If it specified, then will
        be returned single network or None
        :param page: optional page to restrict list of hosts in each selected
            network
        """
        if AWS:
            all_pods = Pod.query.filter(Pod.status != 'deleted').all()
            pods_data = [(i.id, i.name, i.owner.username) for i in all_pods
                         if i.owner.username != KUBERDOCK_INTERNAL_USER]
            lbs = LoadBalanceService()
            names = lbs.get_dns_by_pods([i[0] for i in pods_data])
            allocation = [(names[i[0]], i[1], 'busy', i[2]) for i in pods_data
                          if i[0] in names]
            return {'allocation': allocation,
                    'free_hosts': [],
                    'blocked_list': [],
                    'id': None,
                    'network': None,
                    'page': page or 1,
                    'pages': 1,
                    'ipv6': False,
                    'node': None}
        if net is None:
            return [p.to_dict(page=page) for p in IPPool.all()]
        rv = IPPool.filter_by(network=net).first()
        if rv is not None:
            return rv.to_dict(page=page)

    def get_free(self):
        """Returns first free ip address from pool of defined networks."""
        return IPPool.get_free_host()

    def create(self, data):
        # type: (dict) -> dict
        """Creates network instance in db pool of networks.
        :param data: dict with fields 'network' ('x.x.x.x/x'), and optional
            'autoblock' - string of comma separated IPs or IP ranges,
            which define a list of IP addresses to exclude. IP range has a
            following format 10.0.0.1-10.0.0.32. You can mix ranges with
            single IPs, like 10.0.0.1,10.0.0.30-10.0.1.32,10.0.0.2
        :return: dict with fields 'network' and 'autoblock'

        """
        data = V()._api_validation(data or {}, ippool_schema)

        self._check_if_network_exists(data['network'])

        node_name = data.get('node')
        node = Node.query.filter_by(hostname=node_name).first()
        if node_name is not None:
            if node is None:
                raise APIError('Node does not exist ({})'.format(node_name))

        with atomic():
            pool = IPPool(network=data['network'], node=node)
            auto_block = data.get('autoblock', '').replace(' ', '')
            block_list = self.parse_autoblock(auto_block) if auto_block else []
            pool.block_ip(block_list)

            if node_name and current_app.config['NONFLOATING_PUBLIC_IPS']:
                try:
                    node = K8SNode(hostname=node_name)
                    node.increment_free_public_ip_count(len(pool.free_hosts()))
                except NodeNotFound:
                    raise APIError(
                        'Node isn\'t deployed yet. Please try later.')

        pool.save()
        return pool.to_dict(page=1)

    @atomic(nested=False)
    def update(self, network, params):
        net = self._get_network_by_cidr(network)
        if not params:
            return net.to_dict()

        block_ip = params.get('block_ip')
        unblock_ip = params.get('unblock_ip')
        unbind_ip = params.get('unbind_ip')
        node_name = params.get('node')

        if block_ip and net.block_ip(block_ip) == 0:
            raise APIError("IP is already blocked")

        if unblock_ip and net.unblock_ip(unblock_ip) == 0:
            raise APIError("IP is already unblocked")

        if unbind_ip:
            PodCollection._remove_public_ip(ip=unbind_ip)

        if node_name and current_app.config['NONFLOATING_PUBLIC_IPS']:
            net.node = self._get_node_by_name(net, node_name)
            self._update_free_public_ip_counter(net.node.hostname, block_ip,
                                                unblock_ip,
                                                unbind_ip)
        return net.to_dict()

    def _update_free_public_ip_counter(self, hostname, block_ip, unblock_ip,
                                       unbind_ip):
        delta, k8s_node = 0, K8SNode(hostname=hostname)

        if block_ip:
            delta -= 1

        if unblock_ip:
            delta += 1

        if unbind_ip:
            delta += 1

        try:
            k8s_node.increment_free_public_ip_count(delta)
        except NodeException:
            raise APIError('Could not modify IP. Please try later')

    def _get_node_by_name(self, net, node_name):
        if PodIP.filter_by(network=net.network).first() is not None:
            raise APIError(
                "You cannot change the node of network '{0}' while "
                "some of IP-addresses of this network were assigned to "
                "Pods".format(net.network)
            )
        node = Node.query.filter_by(hostname=node_name).first()
        if node is None:
            raise APIError('Node is not exists ({0})'.format(node_name))
        return node

    def _check_if_network_exists(self, network):
        net = ipaddress.IPv4Network(network)
        for pool in IPPool.all():
            if pool.network == net:
                raise APIError('Network {} already exists'.format(network))
            if net.overlaps(ipaddress.IPv4Network(pool.network)):
                raise APIError(
                    'New {} network overlaps {} which already exists'.format(
                        network, pool.network))

    def get_user_addresses(self, user):
        pods = {pod.id: pod.name
                for pod in user.pods if pod.status != 'deleted'}

        # AWS requires different processing because of ELB instead of IPs
        if AWS:
            elb_dict = LoadBalanceService().get_dns_by_user(user.id)
            return [dict(id=v, pod=pods.get(k), pod_id=k)
                    for k, v in elb_dict.items()]

        return [{
                    'id': str(ipaddress.ip_address(i.ip_address)),
                    'pod': pods[i.pod_id],
                    'pod_id': i.pod_id
                } for i in PodIP.filter(PodIP.pod_id.in_(pods.keys()))]

    @atomic(nested=False)
    def delete(self, network):
        network = str(ip_network(network))
        pool = IPPool.filter_by(network=network).first()
        if not pool:
            raise APIError("Network '{0}' does not exist".format(network), 404)
        self._check_if_network_used_by_pod(network)
        self._delete_network(network, pool)

    def _delete_network(self, network, pool):
        free_ip_count = len(pool.free_hosts())
        IPPool.query.filter_by(network=network).delete()

        if pool.node and current_app.config['NONFLOATING_PUBLIC_IPS']:
            try:
                node = K8SNode(hostname=pool.node.hostname)
                node.increment_free_public_ip_count(-free_ip_count)
            except NodeNotFound:
                # If node is missing in kubernetes it is safe to fail silently
                # because ip counters are missing too
                pass

    def _check_if_network_used_by_pod(self, network):
        pod_ip = PodIP.filter_by(network=network).first()
        if pod_ip is not None:
            raise APIError("You cannot delete this network '{0}' while "
                           "some of IP-addresses of this network are "
                           "assigned to Pods".format(network))

    def _get_network_by_cidr(self, network):
        net = IPPool.filter_by(network=network).first()
        if net is None:
            raise APIError("Network '{0}' does not exist".format(network), 404)
        return net

    def parse_autoblock(self, data):
        # type: (str) -> set
        def _parse(item):
            # Try to parse item as a single IP
            try:
                ipaddress.IPv4Address(item)
                return {item}
            except ipaddress.AddressValueError:
                pass

            # Try parse item as ip range: ip1-ip2
            try:
                first_ip, last_ip = [ip2int(i) for i in item.split('-')]
                return {int2ip(n) for n in range(first_ip, last_ip + 1)}
            except ValueError:
                raise APIError(
                    'Exclude IP\'s are expected to be in the form of '
                    '10.0.0.1,10.0.0.4 or 10.1.0.10-10.1.1.54 or both '
                    'comma-separated')

        ip_sets = (_parse(unicode(d)) for d in data.split(','))
        return reduce(operator.or_, ip_sets)

    def assign_ip_to_pod(self, pod_id, node_hostname=None):
        """
        Picks free pubic IP and assigns it to the specified pod
        :param pod_id: id of the pod IP should be assigned to
        :param node_hostname: optional node hostname. If specified only IP's
        from this node will be used
        :return: string representation of the picked IP
        """
        try:
            pod = Pod.query.get(pod_id)
        except sqlalchemy.exc.DataError:  # if pod_id is not uuid
            db.session.rollback()  # needed because of session saving exception
            pod = None
        if pod is None:
            raise APIError('Pod is not exists {0}'.format(pod_id))
        if pod.ip is not None:
            return str(pod.ip)
        ip = IPPool.get_free_host(as_int=True, node=node_hostname)
        if ip is None:
            raise NoFreeIPs()
        ip_pool = IPPool.get_network_by_ip(ip)
        pod_ip = PodIP(pod=pod, network=ip_pool.network, ip_address=ip)
        pod_ip.save()
        repr_ip = str(pod_ip)
        PodCollection().update(
            pod_id,
            {
                'command': 'change_config',
                'node': node_hostname,
                'public_ip': repr_ip,
            }
        )
        IpState.start(pod.id, ip)
        return repr_ip

    @staticmethod
    def get_mode():
        if AWS:
            return 'aws'
        if current_app.config['NONFLOATING_PUBLIC_IPS']:
            return 'non-floating'
        return 'floating'
