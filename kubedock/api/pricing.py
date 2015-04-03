from flask import Blueprint, request, jsonify, current_app
from sqlalchemy.exc import IntegrityError, InvalidRequestError

from ..billing import Package
from ..core import db
from ..rbac import check_permission
from ..utils import login_required_or_basic
from ..users import User
from ..pods import Pod
from ..billing.models import Package, Kube
from ..stats import StatWrap5Min
from collections import defaultdict
import time
import datetime
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from . import APIError


pricing = Blueprint('pricing', __name__, url_prefix='/pricing')

@pricing.route('/packages', methods=['POST'], strict_slashes=False)
@login_required_or_basic
def create_package():
    data = {}
    defaults = {'kube_id': 0, 'currency': 'USD', 'period': 'hour', 'default': False}
    for attr in 'name', 'kube_id', 'amount', 'currency', 'period':
        data[attr] = request.form.get(attr, defaults.get(attr))
        if data[attr] is None:
            return jsonify({
                'status': 'ERROR',
                'message': "attribute '{0}' is expected to be set".format(attr,)
            })
    try:
        package = Package(**data)
        db.session.add(package)
        db.session.commit()
    except (IntegrityError, InvalidRequestError):
        db.session.rollback()
        return jsonify({
            'status': 'ERROR',
            'message': "Package '{0}' already exists!".format(data['name'],)
        })
    return jsonify({'status': 'OK', 'data': data})


@pricing.route('/kubes', methods=['GET'], strict_slashes=False)
@pricing.route('/kubes/<int:kube_id>', methods=['GET'])
@login_required_or_basic
def get_kube(kube_id=None):
    if kube_id is None:
        data = [i.to_dict() for i in db.session.query(Kube).all()]
    else:
        item = db.session.query(Kube).get(kube_id)
        if item is None:
            raise APIError('Kube not found', 404)
        data = item.to_dict()
    return jsonify({'status': 'OK', 'data': data})


@pricing.route('/kubes', methods=['POST'], strict_slashes=False)
@login_required_or_basic
def create_kube():
    data = {}
    defaults = {'cpu': 0, 'cpu_units': 'MHz', 'memory': 0, 'memory_units': 'MB',
                'disk_space': 0, 'total_traffic': 0, 'default': False}
    for attr in ('name',  'cpu', 'cpu_units', 'memory', 'memory_units',
                 'disk_space', 'total_traffic'):
        data[attr] = request.form.get(attr, defaults.get(attr))
        if data[attr] is None:
            return jsonify({
                'status': 'ERROR',
                'message': "attribute '{0}' is expected to be set".format(attr,)
            })
    try:
        kube = Kube(**data)
        db.session.add(kube)
        db.session.commit()
        data['id'] = kube.id
    except (IntegrityError, InvalidRequestError):
        db.session.rollback()
        return jsonify({
            'status': 'ERROR',
            'message': "Kube '{0}' already exists!".format(data['name'],)
        })
    return jsonify({'status': 'OK', 'data': data})

@pricing.route('/kubes/<int:kube_id>', methods=['PUT'])
@login_required_or_basic
def update_kube(kube_id):
    conv = {'cpu': float, 'memory': int}
    item = db.session.query(Kube).get(kube_id)
    if item is None:
        raise APIError('Kube not found', 404)
    if request.json is not None:
        data = request.json
    else:
        data = request.form
    for key, value in data.items():
        if hasattr(item, key):
            setattr(item, key, conv.get(key, str)(value))
    db.session.commit()
    return jsonify({'status': 'OK'});


@pricing.route('/kubes/<int:kube_id>', methods=['DELETE'])
@login_required_or_basic
def delete_kube(kube_id):
    item = db.session.query(Kube).get(kube_id)
    if item is None:
        raise APIError('Kube not found', 404)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'status': 'OK'});