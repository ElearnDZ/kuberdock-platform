from flask import Blueprint, request, jsonify
from ..rbac import check_permission
from ..decorators import login_required_or_basic_or_token
from ..decorators import maintenance_protected
from ..validation import check_int_id, check_node_data, check_hostname
from ..billing import Kube
from . import APIError
from ..kapi import nodes as kapi_nodes
from ..kapi import node_utils


nodes = Blueprint('nodes', __name__, url_prefix='/nodes')


@nodes.route('/', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get', 'nodes')
def get_list():
    return jsonify({
        'status': 'OK',
        'data': node_utils.get_nodes_collection()
    })


@nodes.route('/<node_id>', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('get', 'nodes')
def get_one_node(node_id):
    check_int_id(node_id)
    data = node_utils.get_one_node(node_id)
    return jsonify({'status': 'OK', 'data': data})


@nodes.route('/', methods=['POST'])
@login_required_or_basic_or_token
@check_permission('create', 'nodes')
@maintenance_protected
def create_item():
    data = request.json
    check_node_data(data)
    kube = Kube.query.get(data.get('kube_type', Kube.get_default_kube_type()))
    if kube is None:
        raise APIError('Unknown kube type')
    hostname = data['hostname']
    dbnode = kapi_nodes.create_node(None, hostname, kube.id)
    data['id'] = dbnode.id
    return jsonify({'status': 'OK', 'data': data})


@nodes.route('/<node_id>', methods=['PUT'])
@login_required_or_basic_or_token
@check_permission('edit', 'nodes')
@maintenance_protected
def put_item(node_id):
    check_int_id(node_id)
    data = request.json
    check_node_data(data)
    ip = data['ip']
    hostname = data['hostname']
    kapi_nodes.edit_node_hostname(node_id, ip, hostname)
    return jsonify({'status': 'OK', 'data': data})


@nodes.route('/<int:node_id>', methods=['PATCH'])
@login_required_or_basic_or_token
@check_permission('delete', 'nodes')
@maintenance_protected
def patch_item(node_id):
    data = request.json
    command = data.get('command')
    if command is None:
        raise APIError('No command has been send')
    if command != 'delete':
        raise APIError('Unsupported command')
    node = kapi_nodes.mark_node_as_being_deleted(node_id)
    kapi_nodes.delete_node(node=node)
    return jsonify({'status': 'OK', 'data': {'status': 'deletion'}})


@nodes.route('/<node_id>', methods=['DELETE'])
@login_required_or_basic_or_token
@check_permission('delete', 'nodes')
@maintenance_protected
def delete_item(node_id):
    check_int_id(node_id)
    kapi_nodes.delete_node(node_id)
    return jsonify({'status': 'OK'})


@nodes.route('/checkhost/', methods=['GET'])
@nodes.route('/checkhost/<hostname>', methods=['GET'])
def check_host(hostname=''):
    check_hostname(hostname)
    return jsonify({'status': 'OK'})


@nodes.route('/redeploy/<node_id>', methods=['GET'])
@login_required_or_basic_or_token
@check_permission('redeploy', 'nodes')
@maintenance_protected
def redeploy_item(node_id):
    check_int_id(node_id)
    kapi_nodes.redeploy_node(node_id)
    return jsonify({'status': 'OK'})
