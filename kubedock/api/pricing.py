from flask import Blueprint, current_app
from flask.views import MethodView

from ..core import db
from ..rbac import check_permission
from ..decorators import login_required_or_basic_or_token
from ..utils import KubeUtils, register_api, atomic
from ..users import User
from ..validation import check_pricing_api, package_schema, kube_schema, packagekube_schema
from ..billing.models import Package, Kube, PackageKube
from ..pods.models import Pod
from . import APIError


pricing = Blueprint('pricing', __name__, url_prefix='/pricing')


class PackageNotFound(APIError):
    message = 'Package not found'
    status_code = 404


class KubeNotFound(APIError):
    message = 'Kube not found'
    status_code = 404


class DuplicateName(APIError):
    pass


class DefaultKubeNotRemovable(APIError):
    pass


class OperationOnInternalKube(APIError):
    status_code = 403


class KubeInUse(APIError):
    pass


class PackageInUse(APIError):
    pass


# === PACKAGE ROUTINES ===


@pricing.route('/userpackage', methods=['GET'], strict_slashes=False)
@KubeUtils.jsonwrap
@login_required_or_basic_or_token
@check_permission('get', 'pods')
def get_user_kube_types():
    user = KubeUtils._get_current_user()
    user = User.query.filter_by(username=user.username).first()
    if user is None:
        raise APIError('No such user', 404, 'UserNotFound')
    # current_app.logger.debug(user.package.kubes)
    return {k.kube.name: k.kube.id for k in user.package.kubes}


class PackagesAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, login_required_or_basic_or_token]

    @check_permission('get', 'users')
    def get(self, package_id=None):
        if package_id is None:
            return [p.to_dict() for p in Package.query.all()]
        data = Package.query.get(package_id)
        if data is None:
            raise PackageNotFound()
        return data.to_dict()

    @atomic(APIError('Could not create package', 500), nested=False)
    @check_permission('create', 'users')
    def post(self):
        params = check_pricing_api(self._get_params(), package_schema)
        if Package.query.filter_by(name=params['name']).first() is not None:
            raise DuplicateName('Package with name \'{0}\' already exists'
                                .format(params['name']))
        package = Package(**params)
        db.session.add(package)
        db.session.flush()
        return package.to_dict()

    @atomic(APIError('Could not update package', 500), nested=False)
    @check_permission('edit', 'users')
    def put(self, package_id):
        package = Package.query.get(package_id)
        if package is None:
            raise PackageNotFound()
        params = check_pricing_api(self._get_params(), package_schema, update=True)

        if 'name' in params:
            duplicate = Package.query.filter(Package.name == params['name'],
                                             Package.id != package_id).first()
            if duplicate is not None:
                raise DuplicateName('Package with name \'{0}\' already exists'
                                    .format(params['name']))

        for key, value in params.iteritems():
            setattr(package, key, value)
        db.session.flush()
        return package.to_dict()

    @atomic(APIError('Could not delete package', 500), nested=False)
    @check_permission('delete', 'users')
    def delete(self, package_id):
        package = Package.query.get(package_id)
        if package is None:
            raise PackageNotFound()
        if package.users:
            raise PackageInUse('You have users with this package')
        PackageKube.query.filter_by(package_id=package_id).delete()
        db.session.delete(package)

register_api(pricing, PackagesAPI, 'packages', '/packages/', 'package_id', strict_slashes=False)


# === KUBE ROUTINES ===


class KubesAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, login_required_or_basic_or_token]

    @check_permission('get', 'users')
    def get(self, kube_id=None):
        if kube_id is None:
            return [i.to_dict() for i in Kube.public_kubes()]
        item = Kube.query.get(kube_id)
        if item is None:
            raise KubeNotFound()
        return item.to_dict()

    @check_permission('create', 'users')
    def post(self):
        params = self._get_params()
        return add_kube(params)

    @atomic(APIError('Could not update kube', 500), nested=False)
    @check_permission('edit', 'users')
    def put(self, kube_id):
        kube = Kube.query.get(kube_id)
        if kube is None:
            raise KubeNotFound()
        if not Kube.is_kube_editable(kube.id):
            raise OperationOnInternalKube('Kube type is not editable')
        data = check_pricing_api(self._get_params(), kube_schema, update=True)
        if 'name' in data:
            duplicate = Kube.get_by_name(data['name'], Kube.id != kube_id)
            if duplicate is not None:
                raise DuplicateName('Kube with name \'{0}\' already exists. '
                                    'Name should be unique'.format(data['name']))
        is_default = data.get('is_default', None)
        if is_default:
            _remove_is_default_kube_flags()
        elif kube.is_default and is_default is not None:
            raise DefaultKubeNotRemovable(
                'Setting "is_default" flag to false is forbidden. You can change '
                'default kube type by setting another kube type as default.')

        for key, value in data.items():
            setattr(kube, key, value)
        db.session.flush()
        return kube.to_dict()

    @atomic(APIError('Could not delete kube', 500), nested=False)
    @check_permission('delete', 'users')
    def delete(self, kube_id):
        kube = Kube.query.get(kube_id)
        if kube is None:
            raise KubeNotFound()
        if kube.is_default:
            raise DefaultKubeNotRemovable(
                'Deleting of default kube type is forbidden. '
                'Set another kube type as default and try again')
        if not Kube.is_kube_editable(kube.id):
            raise OperationOnInternalKube('Kube type is not editable')
        if kube.pods:
            raise KubeInUse('Some pods use this kube type')
        if kube.nodes:
            raise KubeInUse('Some nodes use this kube type')
        PackageKube.query.filter_by(kube_id=kube_id).delete()
        db.session.delete(kube)

register_api(pricing, KubesAPI, 'kubes', '/kubes/', 'kube_id', strict_slashes=False)


@atomic(APIError('Could not create kube', 500), nested=False)
def add_kube(data):
    data = check_pricing_api(data, kube_schema)
    if Kube.get_by_name(data['name']) is not None:
        raise DuplicateName('Kube type with name \'{0}\' already exists. '
                            'Name must be unique'.format(data['name']))

    kube = Kube(**data)
    if kube.is_default:
        # reset is_default flag for all kubes if new kube marked as default
        _remove_is_default_kube_flags()
    db.session.add(kube)
    db.session.flush()
    return kube.to_dict()


# === PACKAGE KUBE ROUTINES ===


@pricing.route('/packages/<int:package_id>/kubes-by-id', methods=['GET'],
               strict_slashes=False)
@KubeUtils.jsonwrap
@login_required_or_basic_or_token
@check_permission('get', 'users')
def get_package_kube_ids(package_id):
    package = Package.query.get(package_id)
    if package is None:
        raise PackageNotFound()
    return [kube.kube_id for kube in package.kubes]


@pricing.route('/packages/<int:package_id>/kubes-by-name', methods=['GET'],
               strict_slashes=False)
@KubeUtils.jsonwrap
@login_required_or_basic_or_token
@check_permission('get', 'users')
def get_package_kube_names(package_id):
    package = Package.query.get(package_id)
    if package is None:
        raise PackageNotFound()
    return [package_kube.kube.name for package_kube in package.kubes]


class PackageKubesAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, login_required_or_basic_or_token]

    @check_permission('get', 'users')
    def get(self, package_id, kube_id=None):
        package = Package.query.get(package_id)
        if package is None:
            raise PackageNotFound()
        if kube_id is None:
            return [dict(pk.kube.to_dict(), kube_price=pk.kube_price)
                    for pk in package.kubes]
        try:
            return (dict(pk.kube.to_dict(), kube_price=pk.kube_price)
                    for pk in package.kubes if pk.kube_id == int(kube_id)).next()
        except StopIteration:
            raise KubeNotFound()

    @atomic(APIError('Could not add kube type to package', 500), nested=False)
    @check_permission('create', 'users')
    def post(self, package_id):
        if Package.query.get(package_id) is None:
            raise PackageNotFound()
        params = self._get_params()
        if 'id' in params:
            params = check_pricing_api(params, packagekube_schema)
            kube_id = params['id']
            kube = Kube.query.get(kube_id)
            if kube is None:
                raise KubeNotFound()
            if not kube.is_public():
                raise OperationOnInternalKube(
                    'Kube type is not allowed to use it in packages')
        else:
            params = check_pricing_api(params, dict(kube_schema, **packagekube_schema))
            kube_id = add_kube({key: value for key, value in params.iteritems()
                                if key in kube_schema}, commit=False)['id']

        return _add_kube_type_to_package(package_id, kube_id, params['kube_price'])

    @atomic(APIError('Could not update kube type in package', 500), nested=False)
    @check_permission('edit', 'users')
    def put(self, package_id=None, kube_id=None):
        if Package.query.get(package_id) is None:
            raise PackageNotFound()
        kube = Kube.query.get(kube_id)
        if kube is None:
            raise KubeNotFound()
        if not kube.is_public():
            raise OperationOnInternalKube(
                'Kube type is not allowed to use it in packages')
        params = check_pricing_api(self._get_params(), packagekube_schema)

        return _add_kube_type_to_package(package_id, kube_id, params['kube_price'])

    @atomic(APIError('Could not remove kube type from package', 500), nested=False)
    @check_permission('delete', 'users')
    def delete(self, package_id, kube_id):
        package_kube = PackageKube.query.filter_by(package_id=package_id,
                                                   kube_id=kube_id).first()
        if package_kube is None:
            raise KubeNotFound('Kube type is not in the package')
        if User.query.filter(User.pods.any(Pod.kube == package_kube.kube),
                             User.package == package_kube.package).first():
            raise KubeInUse('Some users with this package have pods '
                            'with this kube type')
        db.session.delete(package_kube)

register_api(pricing, PackageKubesAPI, 'packagekubes',
             '/packages/<int:package_id>/kubes/', 'kube_id', strict_slashes=False)


def _add_kube_type_to_package(package_id, kube_id, kube_price):
    package_kube = PackageKube.query.filter_by(package_id=package_id, kube_id=kube_id).first()
    if package_kube is None:
        package_kube = PackageKube(package_id=package_id, kube_id=kube_id)
        db.session.add(package_kube)
    package_kube.kube_price = kube_price
    db.session.flush()
    return package_kube.to_dict()


def _remove_is_default_kube_flags():
    Kube.query.update({Kube.is_default: None}, synchronize_session='fetch')



@pricing.route('/license', methods=['GET'], strict_slashes=False)
@KubeUtils.jsonwrap
@login_required_or_basic_or_token
@check_permission('read', 'system_settings')
def get_license():
    return {
        'status': 'active',
        'expiration': '2020-12-31',
        'type': 'standard',
        'installationID': '1234567890abcdef',
        'platform': 'generic',
        'storage': 'ceph',
        'version':{
            'KuberDock': '0.4-13-4',
            'kubernetes': '1.0.3',
            'docker': '1.6.2'},
        'data': {
            'nodes': [10, 8],
            'cores': [48, 40],
            'memory': [512, 448],
            'containers': ['unlimited', 340],
            'pods': [220, 174],
            'apps': ['unlimited', 93],
            'persistentVolume': ['unlimited', 1332]}}
