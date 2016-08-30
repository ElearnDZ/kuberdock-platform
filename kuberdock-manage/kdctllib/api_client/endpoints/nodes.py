from ..base import ClientBase


class NodesClient(ClientBase):
    endpoint = '/nodes'

    def list(self):
        return self.transport.get(
            self._url()
        )

    def get(self, id):
        return self.transport.get(
            self._url(id)
        )

    def create(self, data):
        return self.transport.post(
            self._url(),
            json=data
        )

    def update(self, id, data):
        return self.transport.put(
            self._url(id),
            json=data
        )

    def delete(self, id):
        return self.transport.delete(
            self._url(id)
        )

    def check_host(self, hostname):
        return self.transport.get(
            self._url('checkhost', hostname)
        )
