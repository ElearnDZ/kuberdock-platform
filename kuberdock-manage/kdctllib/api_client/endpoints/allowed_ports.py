
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


class AllowedPortsClient(ClientBase):
    endpoint = '/allowed-ports'

    def list(self):
        return self.transport.get(self._url())

    def open(self, port, protocol):
        json = {
            'port': port,
            'protocol': protocol,
        }
        return self.transport.post(self._url(), json=json)

    def close(self, port, protocol):
        return self.transport.delete(self._url(port, protocol))
