
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

from flask import Blueprint, request, current_app

from datetime import datetime

from kubedock.decorators import maintenance_protected
from kubedock.exceptions import (
    APIError,
    RegisteredHostError,
    RegisteredHostExists,
)
from kubedock.login import auth_required
from kubedock.core import db
from kubedock.kapi.nginx_utils import update_nginx_proxy_restriction
from kubedock.kapi.network_policies import get_rhost_policy
from kubedock.nodes.models import RegisteredHost
from kubedock.utils import Etcd, KubeUtils, atomic, find_remote_host_tunl_addr
from kubedock.settings import ETCD_NETWORK_POLICY_HOSTS

hosts = Blueprint('hosts', __name__, url_prefix='/hosts')


@hosts.route('/register', methods=['POST'])
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
def create_host():
    user = KubeUtils.get_current_user()
    if not user.is_administrator():
        raise APIError('Insufficient permissions level', 403,
                       type='PermissionDenied')
    ip = request.environ.get('REMOTE_ADDR')
    return register_host(ip)


@atomic(nested=False)
def register_host(ip):
    current_app.logger.info('REGISTERING REMOTE HOST IN KD NETWORK, IP: {}'
                            .format(ip))
    host = RegisteredHost.query.filter_by(host=ip).first()
    if host and host.tunnel_ip:
        raise RegisteredHostExists()
    if not host:
        # First registration
        host = RegisteredHost(host=ip, time_stamp=datetime.now())
        db.session.add(host)
        db.session.flush()
        update_nginx_proxy_restriction()
        return {'ip': ip}

    tunl_ip, err = find_remote_host_tunl_addr(ip)
    if err:
        current_app.logger.error(err)
        raise RegisteredHostError(details={'message': err})
    if not tunl_ip:
        # This is a case for second registration when calico node is not
        # ready and does't have tunnel ip yet
        raise RegisteredHostError(
            details={'message': 'Calico network is not ready yet '
                                'for {0}'.format(ip)}
        )

    host.tunnel_ip = tunl_ip
    policy = get_rhost_policy(ip, tunl_ip)
    current_app.logger.debug('GENERATED POLICY FOR REMOTE HOST IS: {}'
                             .format(policy))
    policy_hosts = Etcd(ETCD_NETWORK_POLICY_HOSTS)
    policy_hosts.put(ip, value=policy)
    return {'ip': ip}
