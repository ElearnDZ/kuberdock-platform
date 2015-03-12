import ipaddress
from flask import Blueprint, request, jsonify

from . import APIError
from ..core import db, check_permission
from ..utils import login_required_or_basic
from ..pods.models import IPPool, PodIP


ippool = Blueprint('ippool', __name__, url_prefix='/ippool')


@check_permission('get', 'ippool')
def get_networks_collection():
    return [u.to_dict() for u in IPPool.all()]


@ippool.route('/', methods=['GET'])
@login_required_or_basic
def get_list():
    return jsonify({'status': 'OK', 'data': get_networks_collection()})


@ippool.route('/hasPublicIPs', methods=['GET'])
@login_required_or_basic
def has_public_ips():
    return jsonify({'status': 'OK' if IPPool.has_public_ips() else 'NO'})


@ippool.route('/<network>', methods=['GET'])
@login_required_or_basic
@check_permission('get', 'ippool')
def get_one_network(network):
    if network == 'all':
        return jsonify({'status': 'OK', 'data': get_networks_collection()})
    # Suppose our IDs are integers only
    net = IPPool.filter_by(network=network).first()
    if net is None:
        raise APIError("Network {0} doesn't exists".format(network))
    return jsonify({'status': 'OK', 'data': net.to_dict()})


@ippool.route('/', methods=['POST'])
@login_required_or_basic
@check_permission('create', 'ippool')
def create_item():
    data = request.json
    if data is None:
        data = dict(request.form)
    for key in data.keys():
        if type(data[key]) is list and len(data[key]) == 1:
            data[key] = data[key][0]
    try:
        network = str(ipaddress.ip_network(unicode(data['network'])))
        if IPPool.filter_by(network=network).first():
            raise Exception("Network '{0}' already exist".format(network))
        pool = IPPool.create(network=network)
        pool.save()
        return jsonify({'status': 'OK', 'data': pool.to_dict()})
    except KeyError:
        raise APIError('Network is not defined')
    except Exception, e:
        db.session.rollback()
        raise APIError("An error was occured: '{0}'".format(e))


@ippool.route('/', methods=['DELETE'])
@login_required_or_basic
@check_permission('delete', 'ippool')
def delete_item():
    data = request.json
    if data is None:
        data = dict(request.form)
    try:
        network = str(ipaddress.ip_network(unicode(data['network'][0])))
        if not IPPool.filter_by(network=network).first():
            raise Exception("Network '{0}' does not exist".format(network))
        pods_count = PodIP.filter_by(network=network).count()
        if pods_count > 0:
            raise Exception("You cannot delete this network '{0}' while "
                            "some of IP-addresses of this network were "
                            "assigned to Pods".format(network))
        for obj in PodIP.filter_by(network=network):
            obj.delete()
        for obj in IPPool.filter_by(network=network):
            obj.delete()
        return jsonify({'status': 'OK'})
    except KeyError:
        raise APIError('Network is not defined')
    except Exception, e:
        raise APIError("An error was occured: '{0}'".format(e))