from flask import Blueprint

from .utils import use_kwargs
from ..kapi import allowed_ports as kapi_allowed_ports
from ..login import auth_required
from ..rbac import check_permission
from ..utils import KubeUtils
from ..validation import V, ValidationError, port_schema, protocol_schema


allowed_ports = Blueprint('allowed-ports', __name__,
                          url_prefix='/allowed-ports')


@allowed_ports.route('/', methods=['GET'])
@auth_required
@check_permission('get', 'allowed-ports')
@KubeUtils.jsonwrap
def get_ports():
    return kapi_allowed_ports.get_ports()


@allowed_ports.route('/', methods=['POST'])
@auth_required
@check_permission('create', 'allowed-ports')
@KubeUtils.jsonwrap
@use_kwargs({'port': dict(port_schema, required=True),
             'protocol': dict(protocol_schema, required=True)})
def set_port(port, protocol):
    kapi_allowed_ports.set_port(port, protocol)


@allowed_ports.route('/<int:port>/<protocol>', methods=['DELETE'])
@auth_required
@check_permission('delete', 'allowed-ports')
@KubeUtils.jsonwrap
def del_port(port, protocol):
    v = V()
    if not v.validate({'port': port, 'protocol': protocol},
                      {'port': port_schema, 'protocol': protocol_schema}):
        raise ValidationError(v.errors)
    kapi_allowed_ports.del_port(port, protocol)
