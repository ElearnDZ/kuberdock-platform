import ipaddress

from ..pods.models import IPPool, PodIP
from ..api import APIError

class IpAddrPool(object):
    
    def get(self, net=None):
        if net is None:
            return [p.to_dict() for p in IPPool.all()]
        rv = IPPool.filter_by(network=net).first()
        if rv is not None:
            return rv.to_dict()
        
    def get_free(self):
        return IPPool.get_free_host()
    
    def create(self, data):
        try:
            network = ipaddress.ip_network(data.get('network'))
            if IPPool.filter_by(network=str(network)).first():
                raise APIError('Network {0} already exists'.format(str(network)))
            autoblock = map(str, self._parse_autoblock(data.get('autoblock')))
            pool = IPPool(network=str(network))
            block_list = [int(ipaddress.ip_address(unicode(i)))
                for i in map(str, network.hosts()) if i[i.rfind('.')+1:] in autoblock]
            pool.block_ip(block_list)
            pool.save()
            return {'network': str(network), 'autoblock': block_list}
        except ValueError, e:
            raise APIError(str(e))

    def update(self, network, params):
        net = IPPool.filter_by(network=network).first()
        if net is None:
            raise APIError("Network '{0}' does not exist".format(network))
        block_ip = params.get('block_ip')
        if block_ip:
            net.block_ip(block_ip)
        unblock_ip = params.get('unblock_ip')
        if unblock_ip:
            net.unblock_ip(unblock_ip)
        unbind_ip = params.get('unbind_ip')
        if unbind_ip:
            self.unbind_address(unbind_ip)
        return net.to_dict()
    
    def unbind_address(self, addr):
        ip = PodIP.filter_by(ip_address=int(ipaddress.ip_address(addr))).first()
        if ip:
            ip.delete()
    
    def delete(self, network):
        network = str(ipaddress.ip_network(network))
        if not IPPool.filter_by(network=network).first():
            raise APIError("Network '{0}' does not exist".format(network))
        pods_count = PodIP.filter_by(network=network).count()
        if pods_count > 0:
            raise APIError("You cannot delete this network '{0}' while "
                            "some of IP-addresses of this network were "
                            "assigned to Pods".format(network))
        for obj in PodIP.filter_by(network=network):
            obj.delete()
        for obj in IPPool.filter_by(network=network):
            obj.delete()

    def _parse_autoblock(self, data):
        blocklist = set()
        if not data:
            return blocklist
        for num in [i.strip() for i in data.split(',')]:
            if num.isdigit():
                blocklist.add(int(num))
                continue
            try:
                f, l = map(int, num.split('-'))
                blocklist.update(set(range(f, l+1)))
            except ValueError:
                continue
        return blocklist