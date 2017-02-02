
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

from kubedock.kapi.helpers import Services
from kubedock.kapi.podutils import raise_if_failure
from kubedock.settings import AWS

PUBLIC_SVC_TYPE = 'public'


def get_service_provider():
    if AWS:
        return LoadBalanceService()
    else:
        return ExternalIPsService()


class LoadBalanceService(Services):
    """Return Services that response for ingress public addresses"""

    def __init__(self):
        super(LoadBalanceService, self).__init__(PUBLIC_SVC_TYPE)

    def get_template(self, pod_id, ports, annotations=None):
        template = super(LoadBalanceService, self).get_template(
            pod_id, ports, annotations)

        template['spec']['type'] = 'LoadBalancer'
        return template

    @staticmethod
    def get_public_dns(service):
        if service['spec']['type'] == 'LoadBalancer':
            ingress = service['status']['loadBalancer'].get('ingress', [])
            if ingress and 'hostname' in ingress[0]:
                hostname = ingress[0]['hostname']
                return hostname

    def get_pods_public_dns(self, services):
        svc = {}
        for pod, s in services.iteritems():
            public_dns = self.get_public_dns(s)
            if public_dns:
                svc[pod] = public_dns
        return svc

    def get_dns_all(self):
        svc = self.get_all()
        return [self.get_public_dns(s) for s in svc]

    def get_dns_by_pods(self, pods):
        svc = self.get_by_pods(pods)
        return self.get_pods_public_dns(svc)

    def get_dns_by_user(self, user_id):
        svc = self.get_by_user(user_id)
        return self.get_pods_public_dns(svc)


class ExternalIPsService(Services):

    def __init__(self):
        super(ExternalIPsService, self).__init__(PUBLIC_SVC_TYPE)

    @staticmethod
    def get_publicIP(service):
        try:
            return service['spec']['externalIPs'][0]
        except (KeyError, IndexError):
            return None

    def set_publicIP(self, service, publicIP):
        if publicIP:
            service['spec']['externalIPs'] = [publicIP]
        return service

    def update_publicIP(self, service, publicIP=None):
        """Update publicIP in service
        :param service: service to update
        :param publicIP: new publicIP for service
        :return: updated service
        """
        name = service['metadata']['name']
        namespace = service['metadata']['namespace']
        data = {'spec': {'externalIPs': [publicIP]}}
        rv = self.patch(name, namespace, data)
        raise_if_failure(rv, "Couldn't patch service publicIP")
        return rv

    def get_pods_publicIP(self, services):
        svc = {}
        for pod, s in services.iteritems():
            publicIP = self.get_publicIP(s)
            if publicIP:
                svc[pod] = publicIP
        return svc

    def get_publicIP_all(self):
        svc = self.get_all()
        return [self.get_publicIP(s) for s  in svc]

    def get_publicIP_by_pods(self, pods):
        svc = self.get_by_pods(pods)
        return self.get_pods_publicIP(svc)

    def get_publicIP_by_user(self, user_id):
        svc = self.get_by_user(user_id)
        return self.get_pods_publicIP(svc)
