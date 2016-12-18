import json
import operator
import random
import string
import types
import uuid
from functools import reduce
from hashlib import md5

import ipaddress
from datetime import datetime
from flask import current_app
from sqlalchemy.dialects import postgresql

from ..core import db
from ..exceptions import NoFreeIPs, PodExists
from ..kapi import pd_utils
from kubedock import utils
from ..models_mixin import BaseModelMixin
from ..settings import DOCKER_IMG_CACHE_TIMEOUT, KUBERDOCK_INTERNAL_USER
from ..users.models import User


class Pod(BaseModelMixin, db.Model):
    """
    Notes:
        Status of pod is taken from kubernetes if it possible or from database.
        If pod is running, it exists in kubernetes, if it stopped, it exists in
        database only. So pod in database can has only statuses ['stopped',
        'deleted', 'unpaid', 'pending']. If pod is running, it's status is
        taken from kubernetes. It's historically.
    """
    __tablename__ = 'pods'
    __table_args__ = (db.UniqueConstraint('name', 'owner_id'),)

    id = db.Column(postgresql.UUID, primary_key=True, nullable=False)
    name = db.Column(db.String(length=255))
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    kube_id = db.Column(db.Integer, db.ForeignKey('kubes.id'))
    # Not a foreignkey because templates may be deleted at any time
    template_id = db.Column(db.Integer, nullable=True)
    template_version_id = db.Column(db.Integer, nullable=True)
    template_plan_name = db.Column(db.String(24), nullable=True)
    config = db.Column(db.Text)
    direct_access = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(length=32), default='unknown')
    unpaid = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return "<Pod(id='{}', name='{}', owner_id='{}', kubes='{}', " \
               "config='{}', status='{}')>" \
            .format(self.id, self.name.encode('ascii', 'replace'),
                    self.owner_id, self.kubes, self.config, self.status)

    @property
    def kubes(self):
        return sum(
            [c.get('kubes', 1) for c in self.get_dbconfig('containers')]
        )

    @property
    def kubes_detailed(self):
        return {c.get('name'): c.get('kubes', 1)
                for c in self.get_dbconfig('containers')}

    def get_limits(self, container=None):
        if container is None:
            kubes = self.kubes
        else:
            containers = self.get_dbconfig('containers')
            try:
                kubes = (c.get('kubes', 1) for c in containers
                         if c.get('name') == container).next()
            except StopIteration:
                return None
        return self.kube.to_limits(kubes)

    @property
    def is_deleted(self):
        return self.status == 'deleted'

    @property
    def containers_count(self):
        return len(json.loads(self.config).get('containers', []))

    @property
    def price_per_hour(self):
        if self.kube is None:
            return 0
        return self.kubes * self.kube.price

    @property
    def namespace(self):
        try:
            config = json.loads(self.config)
            if 'namespace' in config:
                return config['namespace']
        except Exception, e:
            current_app.logger.warning('Pod.namespace failed: {0}'.format(e))
        return 'default'

    @property
    def has_local_storage(self):
        """
        Check pod config for local storage

        :returns: True or False
        :rtype: bool
        """
        volumes = self.get_dbconfig('volumes', [])
        if len(volumes) > 0:
            return ('annotation' in volumes[0] and
                    'localStorage' in volumes[0]['annotation'])
        return False

    @property
    def is_default_ns(self):
        return self.namespace == 'default'

    @property
    def is_service_pod(self):
        return (self.owner.username == KUBERDOCK_INTERNAL_USER)

    @property
    def pinned_node(self):
        """
        Check if pod is pinned to a node (local storage or fixed IP pools).

        :returns: node hostname or None
        :rtype: str or None
        """
        hostname = self.get_dbconfig('node', None)
        if self.has_local_storage or self.has_fixed_public_ip:
            # TODO: The initial idea was to return nodes.models.Node instance
            # here. However this caused a problem with circular(cyclic)
            # imports.
            return hostname
        return None

    @property
    def has_fixed_public_ip(self):
        return (current_app.config['FIXED_IP_POOLS'] and
                self.ip is not None)

    def delete(self):
        self.name += '__' + ''.join(
            random.sample(string.lowercase + string.digits, 8))
        self.status = 'deleted'

    # Such name to distinguish from non-db Pod's get_config() method
    def get_dbconfig(self, param=None, default=None):
        if param is None:
            return json.loads(self.config)
        return json.loads(self.config).get(param, default)

    def set_dbconfig(self, conf, save=True):
        self.config = json.dumps(conf)
        if save:
            self.save()
        return self

    @classmethod
    def check_name(cls, name, owner_id, pod_id=None, generate_new=False,
                   max_retries=5):
        query = cls.query.filter(
            cls.name == name,
            cls.owner_id == owner_id
        )
        if pod_id is not None:
            query = query.filter(cls.id != pod_id)
        duplicate = query.first()
        if duplicate:
            if generate_new:
                new_name = '{}-{}'.format(name,
                                          utils.randstr(3, string.digits))
                retries = max_retries
                while retries > 0:
                    try:
                        return cls.check_name(new_name, owner_id, pod_id)
                    except PodExists:
                        new_name = '{}-{}'.format(
                            name,
                            utils.randstr(3, string.digits))
                        retries -= 1
            raise PodExists(name=name, id_=duplicate.id)
        return name

    def get_volumes_size(self):
        return {pd['persistentDisk']['pdName']:
                pd['persistentDisk']['pdSize']
                for pd in self.get_dbconfig('volumes_public', [])
                if pd.get('persistentDisk')}

    def to_dict(self):
        return dict(
            id=self.id,
            name=self.name,
            kube=self.kube.to_dict(),
            owner=self.owner.to_dict(),
            config=self.get_dbconfig(),
            status=self.status,
            direct_acces=self.direct_access)


class ImageCache(db.Model):
    __tablename__ = 'image_cache'

    query = db.Column(db.String(255), primary_key=True, nullable=False)
    data = db.Column(postgresql.JSON, nullable=False)
    time_stamp = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return ("<ImageCache(query='{}', data='{}', time_stamp='{}'')>"
                .format(self.query, self.data, self.time_stamp))

    @property
    def outdated(self):
        return (datetime.utcnow() - self.time_stamp) > DOCKER_IMG_CACHE_TIMEOUT


class DockerfileCache(db.Model):
    __tablename__ = 'dockerfile_cache'

    image = db.Column(db.String(255), primary_key=True, nullable=False)
    data = db.Column(postgresql.JSON, nullable=False)
    time_stamp = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return "<DockerfileCache(image='{}', data='{}', time_stamp='{}'')>" \
            .format(self.image, self.data, self.time_stamp)

    @property
    def outdated(self):
        return (datetime.utcnow() - self.time_stamp) > DOCKER_IMG_CACHE_TIMEOUT


def _page(page, pages):
    if page is None or page < 1:
        page = 1
    elif page > pages:
        page = pages
    return page


def _ip_network_hosts(obj, page=None):
    """
    Returns a portion of IP addresses based on page parameter.
    :returns: IP addresses
    :rtype: iterator (AC-3531)
    Previous rtype was a generator
    """
    pages = obj.pages()
    page = _page(page, pages)
    net_ip = obj.network_address + (page - 1) * 2 ** obj.page_bits
    net_pl = obj.max_prefixlen - obj.page_bits if pages > 1 else obj.prefixlen
    network = ipaddress.ip_network(u'{0}/{1}'.format(net_ip, net_pl))
    # This method used to return _BaseNetwork.hosts() generator,
    # however the default implementation would skip network and
    # broadcast addresses, which made the final IP pool short of
    # two IP addresses.  As of AC-3531 fix, now it returns
    # the _BaseNetwork.__iter__() instead, which does not skip any addresses.
    return iter(network)


def _ip_network_iterpages(obj):
    return xrange(1, obj.pages() + 1)


def _ip_network_pages(obj):
    suf_len = obj.max_prefixlen - obj.prefixlen
    pages = 2 ** (suf_len - obj.page_bits) if suf_len > obj.page_bits else 1
    return pages


def ip_network(network):
    ip_net_obj = ipaddress.ip_network(network)
    ip_net_obj.page_bits = 8
    ip_net_obj.hosts = types.MethodType(_ip_network_hosts, ip_net_obj)
    ip_net_obj.iterpages = types.MethodType(_ip_network_iterpages, ip_net_obj)
    ip_net_obj.pages = types.MethodType(_ip_network_pages, ip_net_obj)
    return ip_net_obj


class IPPool(BaseModelMixin, db.Model):
    __tablename__ = 'ippool'

    network = db.Column(db.String, primary_key=True, nullable=False)
    ipv6 = db.Column(db.Boolean, default=False)
    blocked_list = db.Column(db.Text, nullable=True)
    node_id = db.Column(db.ForeignKey('nodes.id'), nullable=True)
    node = db.relationship('Node', backref='ippool')

    def __repr__(self):
        return self.network

    def iterpages(self):
        return ip_network(self.network).iterpages()

    def get_blocked_set(self, as_int=False):
        network = ip_network(self.network)

        blocked_set = set()
        try:
            blocked_set = self._to_ip_set(
                json.loads(self.blocked_list or "[]"),
                int if as_int else str)
            blocked_set = filter(lambda x: ipaddress.ip_address(x) in network,
                                 blocked_set)
        except Exception as e:
            current_app.logger.warning("IPPool.get_blocked_set failed: "
                                       "{0}".format(e))
        return set(blocked_set)

    def _to_ip_set(self, ip, format=int):
        """Convert singular IP or IP iterable in IP set

        :param ip: ip string ('128.0.0.1'), ip as a number (2130706433),
            or ip iterable (['128.0.0.1', 2130706434, 2130706435])
        :param format: ip format in returned set (int by default)
        :returns: set of IPs
        """
        if not isinstance(ip, (tuple, list, set)):
            ip = [ip]
        return set(format(ipaddress.ip_address(ip_)) for ip_ in ip)

    def block_ip(self, ip):
        """
        Blocks given IP or a an IP set
        :param ip: either a single ip or an iterable of ips
        :return: number of blocked ip addresses
        """
        current_set = self.get_blocked_set(as_int=True)
        new_set = current_set | self._to_ip_set(ip)
        self.blocked_list = json.dumps(list(new_set))
        return len(new_set) - len(current_set)

    def unblock_ip(self, ip):
        """
        Unblocks given IP or an IP set
        :param ip: either a single ip or an iterable of ips
        :return: number of unblocked ip addresses
        """
        current_set = self.get_blocked_set(as_int=True)
        new_set = current_set - self._to_ip_set(ip)
        self.blocked_list = json.dumps(list(new_set))
        return len(current_set) - len(new_set)

    def hosts(self, as_int=None, exclude=None, allowed=None, page=None):
        """
        Return IPv4Network object or list of IPs (long) or list of IPs (string)
        :param as_int: Return list of IPs (long)
        :param exclude: Exclude IP from IP list (list, tuple, str, int)
        :return: IPv4Network or list
        """
        network = self.network
        if not self.ipv6 and network.find('/') < 0:
            network = u'{0}/32'.format(network)
        network = ip_network(unicode(network))
        hosts = list(network.hosts(page=page)) or [network.network_address]
        if exclude:
            if isinstance(exclude, (basestring, int)):
                hosts = [h for h in hosts if int(h) != int(exclude)]
            elif isinstance(exclude, (list, tuple)):
                hosts = [h for h in hosts
                         if int(h) not in [int(ex) for ex in exclude]]
        if as_int:
            hosts = [int(h) for h in hosts]
        else:
            hosts = [str(h) for h in hosts]
        return hosts

    def free_hosts(self, as_int=None, page=None):
        ip_list = [pod.ip_address
                   for pod in PodIP.filter_by(network=self.network)]
        ip_list = list(set(ip_list) | self.get_blocked_set(as_int=True))
        _hosts = self.hosts(as_int=as_int, exclude=ip_list, page=page)
        return _hosts

    def busy_and_block(self):
        network = ip_network(self.network)
        ip_list = [pod.ip_address
                   for pod in PodIP.filter_by(network=self.network)]
        blocked_list = self.get_blocked_set(as_int=True)
        blocked_list = filter(lambda x: ipaddress.ip_address(x) in network,
                              blocked_list)
        return list(set(ip_list) | set(blocked_list))

    def host_count(self):
        network = self.network
        if not self.ipv6 and network.find('/') < 0:
            network = u'{0}/32'.format(network)
        network = ip_network(unicode(network))
        suf_len = network.max_prefixlen - network.prefixlen
        return 2 ** suf_len

    def free_hosts_and_busy(self, as_int=None, page=None):
        pods = PodIP.filter_by(network=self.network)
        allocated_ips = {int(pod): pod.get_pod() for pod in pods}
        blocked_ips = self.get_blocked_set(as_int=True)
        hosts = self.hosts(as_int=True, page=page)

        def get_ip_state(ip, pod):
            if pod:
                return 'busy'
            if ip in blocked_ips:
                return 'blocked'
            return 'free'

        def get_ip_info(ip):
            pod = allocated_ips.get(ip)
            state = get_ip_state(ip, pod)
            return ip if as_int else str(ipaddress.ip_address(ip)), pod, state

        return [get_ip_info(ip) for ip in hosts]

    @property
    def is_free(self):
        for page in self.iterpages():
            if len(self.free_hosts(as_int=True, page=page)) > 0:
                return True
        return False

    def get_first_free_host(self, as_int=None):
        for page in self.iterpages():
            free_hosts = self.free_hosts(as_int=as_int, page=page)
            if free_hosts:
                return free_hosts[0]
        return None

    @classmethod
    def get_network_by_ip(cls, ip_address):
        ip_address = ipaddress.ip_address(ip_address)
        for net in cls.all():
            network = ip_network(net.network)
            for page in network.iterpages():
                hosts = (list(network.hosts(page=page)) or
                         [network.network_address])
                if ip_address in hosts:
                    return net
        return None

    def main_info_dict(self):
        data = {
            'id': self.network,
            'network': self.network,
            'ipv6': self.ipv6,
            'node': None if self.node is None else self.node.hostname,
            'free_host_count': self.host_count() - len(self.busy_and_block()),
        }
        return data

    def to_dict(self, include=None, exclude=None, page=None):
        free_hosts_and_busy = self.free_hosts_and_busy(page=page)
        pages = ip_network(self.network).pages()
        page = _page(page, pages)
        data = dict(
            id=self.network,
            network=self.network,
            ipv6=self.ipv6,
            free_hosts=self.free_hosts(page=page),
            blocked_list=list(self.get_blocked_set()),
            node=None if self.node is None else self.node.hostname,
            allocation=free_hosts_and_busy,
            page=page,
            pages=pages,
        )
        return data

    @classmethod
    def has_public_ips(cls):
        for n in cls.all():
            if n.is_free:
                return True
        return False

    @classmethod
    def get_free_host(cls, as_int=None, node=None, ip=None):
        """Return free host if available.
        :param as_int: return ip as long int
        :param node: if set, get free host only for this node
        :param ip: if set, first try to check if this ip available, if not,
        then return any other available ip
        :return: ip address, as str or int, depends on  as_int value

        """
        if ip:
            network = cls.get_network_by_ip(ip)
            if network and network.is_ip_available(ip, node):
                return int(ipaddress.ip_address(ip)) if as_int else ip
        if node is None:
            networks = cls.all()
        else:
            networks = cls.filter(cls.node.has(hostname=node))
        for n in networks:
            free_host = n.get_first_free_host(as_int=as_int)
            if free_host is not None:
                return free_host
        raise NoFreeIPs()

    def is_ip_available(self, ip, node_hostname=None):
        """Check if ip available
        param ip: ip to check
        type ip: str
        param node_hostname: if set, check if ip available only on this node
        return: True of False

        """
        node = self.node.hostname if self.node else None
        if node and node_hostname and node_hostname != node:
            return False
        pages = (self.free_hosts(page=p) for p in self.iterpages())
        return ip in reduce(operator.add, pages)


class PodIP(BaseModelMixin, db.Model):
    __tablename__ = 'podip'

    pod_id = db.Column(postgresql.UUID, db.ForeignKey('pods.id'),
                       primary_key=True, nullable=False)
    pod = db.relationship(Pod, backref=db.backref('ip', uselist=False))
    network = db.Column(db.ForeignKey('ippool.network'))
    ip_address = db.Column(db.BigInteger, nullable=False)

    def __str__(self):
        return str(ipaddress.ip_address(self.ip_address))

    def __int__(self):
        return self.ip_address

    def get_pod(self):
        return Pod.query.get(self.pod_id).name

    def to_dict(self, include=None, exclude=None):
        ip = self.ip_address
        return dict(
            id=self.pod_id,
            pod_id=self.pod_id,
            network=self.network.network,
            ip_address_int=ip,
            ip_address=ipaddress.ip_address(ip)
        )


class PersistentDiskStatuses(object):
    #: Drive was created in database and waits for creation in storage backend
    PENDING = 0
    #: Drive was created in DB and in storage backend
    CREATED = 1
    #: Drive must be deleted from storage backend
    TODELETE = 2
    #: Drive was deleted from backend storage. If it will be recreated, then
    # disk state must be changed to CREATED
    DELETED = 3


class PersistentDisk(BaseModelMixin, db.Model):
    __tablename__ = 'persistent_disk'
    __table_args__ = (
        db.UniqueConstraint('drive_name'),
        db.UniqueConstraint('name', 'owner_id'),
    )

    id = db.Column(db.String(32), primary_key=True, nullable=False)
    drive_name = db.Column(db.String(64), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    owner_id = db.Column(db.ForeignKey('users.id'), nullable=False)
    owner = db.relationship(User, backref='persistent_disks')
    size = db.Column(db.Integer, nullable=False)
    pod_id = db.Column(postgresql.UUID, db.ForeignKey('pods.id'),
                       nullable=True)
    state = db.Column(db.Integer, default=PersistentDiskStatuses.PENDING,
                      nullable=False)
    pod = db.relationship(Pod, backref='persistent_disks')
    # Optional binding of PD to a particular node. Now is only used for 'local
    # storage' backend
    node_id = db.Column(db.ForeignKey('nodes.id'), nullable=True)

    def __init__(self, *args, **kwargs):
        super(PersistentDisk, self).__init__(*args, **kwargs)
        if self.drive_name is None:
            owner = self.owner if self.owner is not None else self.owner_id
            self.drive_name = pd_utils.compose_pdname(self.name, owner)
        if self.id is None:
            self.id = md5(self.drive_name).hexdigest()

    def __str__(self):
        return 'PersistentDisk(drive_name={0}, name={1}, owner={2}, ' \
               'size={3}, pod={4})' \
            .format(self.drive_name, self.name, self.owner, self.size,
                    self.pod)

    @classmethod
    def take(cls, pod_id, drives):
        """Tries to bind given drives to the pod.
        Returns list of drive names which were binded to the pod and dict with
        drives that already binded to another pod.
        If there are any drives binded to another pod, then does not bind
        any free drives to the target pod.

        """
        db.session.expire_all()
        current_app.logger.debug(
            "Locking drives %s for pod id %s", drives, pod_id)
        all_drives = cls.filter(
            cls.drive_name.in_(drives)).with_for_update().all()
        current_app.logger.debug(
            "LOCKED drives %s for pod id %s", drives, pod_id)

        free = [item for item in all_drives if
                item.pod_id is None]
        now_taken = []

        taken_by_another = [
            item for item in all_drives
            if (item.pod_id is not None and item.pod_id != pod_id)]

        if not taken_by_another:
            for drive in free:
                drive.pod_id = pod_id
            now_taken = free

        current_app.logger.debug(
            "Releasing drives %s for pod id %s", drives, pod_id)
        db.session.commit()
        current_app.logger.debug(
            "RELEASED drives %s for pod id %s", drives, pod_id)
        return now_taken, taken_by_another

    @classmethod
    def free(cls, pod_id):
        return cls.filter_by(pod_id=pod_id).update(
            {cls.pod_id: None},
            synchronize_session=False
        )

    @classmethod
    def free_drives(cls, drives):
        if not drives:
            return
        cls.filter(cls.drive_name.in_(drives)).update(
            {cls.pod_id: None},
            synchronize_session=False
        )

    def to_dict(self):
        return dict(id=self.id,
                    drive_name=self.drive_name,
                    name=self.name,
                    owner=self.owner.username,
                    size=self.size,
                    pod=self.pod_id,
                    in_use=self.pod_id is not None)

    @classmethod
    def _increment_drive_name(cls, pd):
        """Finds drive_name with postfix '_i', where 'i' is the smallest number
        for which there is no existing drive_names in database.
        It is needed for auto creation of new PD while old one with the same
        name is in deleting process.
        """
        base_drivename = pd_utils.compose_pdname(pd.name, pd.owner_id)
        # escape existing symbols %, _ for like clause in selection
        name_for_like_search = base_drivename.replace(
            '_', '\\_').replace('%', '\\%')
        existing_drives = cls.query.filter(
            cls.drive_name.like('{}\\_%'.format(name_for_like_search)),
            cls.name == pd.name,
            cls.owner_id == pd.owner_id,
            cls.state != PersistentDiskStatuses.DELETED
        )
        max_number = 0
        for item in existing_drives:
            try:
                number = int(item.drive_name.split('_')[-1])
                if number > max_number:
                    max_number = number
            except (ValueError, TypeError):
                pass
        return '{0}_{1}'.format(base_drivename, max_number + 1)

    @classmethod
    def mark_todelete(cls, drive_id):
        """Marks PD for deletion. Also creates a new one PD with the same
        'name' and owner, but with different physical 'drive_name'. It is
        needed for possibility to fast relaunch the pod right after PD
        deletion. If we will use the same physical drive name, then we have
        to wait until old drive will be actually deleted.
        """
        pd = cls.query.filter(cls.id == drive_id, cls.pod_id.is_(None)).first()
        if not pd or pd.state == PersistentDiskStatuses.TODELETE:
            return
        new_drive_name = cls._increment_drive_name(pd)
        old_name = pd.name
        # change name for deleting PD to prevent conflict of uniques and
        # to hide PD from search by name
        pd.name = uuid.uuid4().hex
        pd.state = PersistentDiskStatuses.TODELETE
        db.session.flush()
        new_pd = cls(
            drive_name=new_drive_name, name=old_name, owner_id=pd.owner_id,
            size=pd.size, state=PersistentDiskStatuses.DELETED
        )
        db.session.add(new_pd)
        db.session.commit()
        return new_pd

    @classmethod
    def get_todelete_query(cls):
        return db.session.query(cls).filter(
            cls.state == PersistentDiskStatuses.TODELETE
        )

    @classmethod
    def get_all_query(cls, include_deleted=False):
        query = db.session.query(cls)
        if not include_deleted:
            query = query.filter(
                ~cls.state.in_([PersistentDiskStatuses.TODELETE,
                                PersistentDiskStatuses.DELETED])
            )
        return query

    @classmethod
    def bind_to_node(cls, pod_id, node_id):
        """Binds all PD's to the given node if PD's are not already binded to
        any node and belong to a given pod.
        """
        db.session.query(cls).filter(
            cls.pod_id == pod_id, cls.node_id.is_(None)
        ).update(
            {cls.node_id: node_id},
            synchronize_session=False
        )

    @classmethod
    def get_by_node_id(cls, node_id):
        """Returns all PersistentDisk binded to a given node.
        :param node_id: identifier if a Node model
        :return: SQLAlchemy query
        """
        return cls.query.filter(cls.node_id == node_id)


class PrivateRegistryFailedLogin(BaseModelMixin, db.Model):
    """Stores time for last failed login attempts to private registries.
    It's a simple workaround to prevent blocking from a registry. It may occur
    when we frequently tried to login to a registry with the same name, and all
    attempts was failed. At the moment hub.docker.com blocks by name + IP if
    there were simultaneous failed login attempts.
    Just remember last failed login for name + registry here and do not allow
    next login attempt before some pause.

    """
    __tablename__ = 'private_registry_failed_login'

    login = db.Column(db.String(255), primary_key=True, nullable=False)
    registry = db.Column(db.String(255), primary_key=True, nullable=False)
    created = db.Column(db.DateTime, primary_key=True, nullable=False)
