
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

import operator
import logging
import random
from collections import defaultdict
from ipaddress import IPv4Address

import oca
from oca import OpenNebulaException
from xmlrpclib import ProtocolError

from tests_integration.lib.exceptions import OpenNebulaError, NotEnoughFreeIPs
from tests_integration.lib.timing import log_timing, log_timing_ctx
from tests_integration.lib.utils import log_begin, log_end

LOG = logging.getLogger(__name__)


class NebulaIPPool(object):
    def __init__(self, client):
        self.client = client
        self.reserved = defaultdict(set)

    @property
    @log_timing
    def pool(self):
        try:
            p = oca.VirtualNetworkPool(self.client, preload_info=True)
            # Filter flag possible values:
            # -3: Connected user's resources
            # -2: All resources
            # -1: Connected user's and his group's resources
            p.info(filter=-2, range_start=-1, range_end=-1)
            return p
        except ProtocolError:
            raise OpenNebulaError('Could not retrieve info from OpenNebula')

    def get_free_ip_list(self, net):
        # type: (oca.VirtualNetworkPool) -> list[str]
        """
        Returns the set of free IP addresses in the given network

        :param net: oca.VirtualNetworkPool
        :return: a set of IPv4 addresses
        """
        ip_list, used_ip_list = set(), set()

        for r in net.address_ranges:
            start_ip = int(IPv4Address(unicode(r.ip)))
            end_ip = start_ip + r.size

            for ip in range(start_ip, end_ip):
                ip_list.add(str(IPv4Address(ip)))
            for lease in r.leases:
                used_ip_list.add(lease.ip)

        free_ips = list(ip_list - used_ip_list)
        random.shuffle(free_ips)
        return free_ips

    @log_timing
    def reserve_ips(self, network_name, count):
        # type: (str, int) -> list[str]
        """
        Tries to hold the given amount of given IP addresses of a network
        Automatically retries if IP were concurrently taken. Raises if there
        are not enough IP addresses

        :param network_name: the name of a network in OpenNebula
        :param count: number of IPs to hold
        :return: a set of reserved IPv4 addresses
        """

        def reserve_ips(ips, net):
            """
            Tries to reserve a random free IP. Retries if any OpenNebula
            related problem occurs. If ips set is empty or became empty
            during the while loop consider there is not enough IPs

            :return: reserved IP
            """
            while ips:
                ip = ips.pop()
                LOG.debug("Trying to hold IP: {}".format(ip))
                try:
                    with log_timing_ctx("net.hold({})".format(ip)):
                        net.hold(ip)
                    return ip
                except (OpenNebulaException, ProtocolError) as e:
                    # It's not possible to distinguish if that was an
                    # arbitrary API error or the IP was concurrently
                    # reserved. We'll consider it's always the latter case
                    LOG.debug("Trouble while holding IP {}:\n{}\nTrying the "
                              "next available IP.".format(ip, repr(e)))

            raise NotEnoughFreeIPs(
                'The number of free IPs became less than requested during '
                'reservation')

        LOG.debug("Getting free IP list from OpenNebula")
        net = self.pool.get_by_name(network_name)
        ips = self.get_free_ip_list(net)
        LOG.debug("Got {} IPs".format(len(ips)))
        if len(ips) < count:
            raise NotEnoughFreeIPs(
                '{} net has {} free IPs but {} requested'.format(network_name,
                                                                 len(ips),
                                                                 count))

        LOG.debug("Starting reservation of {} IP addresses.".format(count))
        for _ in range(count):
            ip = reserve_ips(ips, net)
            self.reserved[network_name].add(ip)

        LOG.debug("Done reservation of {} IP addresses: {}".format(
            count, self.reserved[network_name]))

        return self.reserved[network_name]

    @log_timing
    def free_reserved_ips(self):
        """
        Tries to release all IPs reserved within this class object instance
        """
        LOG.debug("Starting release of IP addresses: {}".format(self.reserved))
        for net_name, ip_set in self.reserved.items():
            net = self.pool.get_by_name(net_name)
            for ip in ip_set:
                LOG.debug("Trying to release IP: {}".format(ip))
                try:
                    with log_timing_ctx("net.release({})".format(ip)):
                        net.release(ip)
                except (OpenNebulaException, ProtocolError) as e:
                    LOG.debug("Trouble while releasing IP {}:\n{}\nTrying the "
                              "next one".format(ip, repr(e)))
        LOG.debug("Done release of IP addresses.")

    @property
    def reserved_ips(self):
        return reduce(operator.or_, self.reserved.values())

    @classmethod
    def factory(cls, url, username, password):
        # type: (str, str, str) -> NebulaIPPool
        client = oca.Client('{}:{}'.format(username, password), url)
        return cls(client)

    @log_timing
    def store_reserved_ips(self, ip):
        """
        Store information about reserved IPs by a VM given it's IP

        This information is needed for a GC script, which removes old VMs.
        The script should also release IPs which were reserved in this
        class. It will use this info saved here to extract a list of IPs
        it should release
        """
        vm = self._get_vm_by_ip(ip)
        reserved_ips = ','.join(self.reserved_ips)
        vm.update('RESERVED_IPS="{}"'.format(reserved_ips))

    def _get_vm_by_ip(self, ip):
        # type: (str) -> oca.VirtualMachine
        vm_pool = oca.VirtualMachinePool(self.client)
        vm_pool.info()
        for vm in vm_pool:
            if ip in (n.ip for n in vm.template.nics):
                return vm
        raise OpenNebulaException('VM {} not found'.format(ip))
