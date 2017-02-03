
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

from ..base import ClientBase


class StatsClient(ClientBase):
    endpoint = '/stats'

    def pod(self, pod_id):
        return self.transport.get(self._url('pods', pod_id))

    def container(self, pod_id, container_id):
        return self.transport.get(self._url(
            'pods', pod_id, 'containers', container_id))

    def node(self, node_id):
        return self.transport.get(self._url('nodes', node_id))
