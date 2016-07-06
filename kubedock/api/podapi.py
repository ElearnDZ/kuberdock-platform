from flask import Blueprint
from flask.views import MethodView

from kubedock.api.utils import use_kwargs
from ..decorators import maintenance_protected
from ..exceptions import PermissionDenied
from ..kapi.podcollection import PodCollection, PodNotFound
from ..login import auth_required
from ..pods.models import Pod
from ..rbac import check_permission
from ..system_settings.models import SystemSettings
from ..utils import KubeUtils, register_api
from ..validation import check_new_pod_data, check_change_pod_data, \
    owner_optional_schema

podapi = Blueprint('podapi', __name__, url_prefix='/podapi')


schema = {'owner': owner_optional_schema}


class PodsAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, KubeUtils.pod_start_permissions,
                  auth_required]

    @use_kwargs(schema)
    def get(self, pod_id, owner=None):
        current_user = self.get_current_user()
        owner = owner or current_user

        check_permission('get', 'pods', user=owner).check()
        if owner != current_user:
            check_permission('get_non_owned', 'pods').check()

        return PodCollection(owner).get(pod_id, as_json=False)

    @maintenance_protected
    @use_kwargs(schema, allow_unknown=True)
    def post(self, owner=None, **params):
        current_user = self.get_current_user()
        owner = owner or current_user

        check_permission('create', 'pods', user=owner).check()
        if owner != current_user:
            check_permission('create_non_owned', 'pods').check()

        params = check_new_pod_data(params, owner)
        return PodCollection(owner).add(params)

    @maintenance_protected
    @use_kwargs({}, allow_unknown=True)
    def put(self, pod_id, **params):
        current_user = self.get_current_user()
        db_pod = Pod.query.get(pod_id)
        if db_pod is None:
            raise PodNotFound()
        owner = db_pod.owner

        check_permission('edit', 'pods', user=owner)
        if owner != current_user:
            check_permission('edit_non_owned', 'pods').check()

        data = check_change_pod_data(params)

        privileged = False
        if current_user.is_administrator():
            privileged = True  # admin interacts with user's pod

        billing_type = SystemSettings.get_by_name('billing_type').lower()
        if billing_type != 'no billing' and current_user.fix_price \
                and not privileged:
            command = data.get('command')
            command_options = data.get('commandOptions')
            if command == 'set' and 'status' in command_options \
                    and command_options['status'] != db_pod.status:
                # fix-price user is not allowed to change paid/unpaid status
                # and start pod directly, only through billing system
                raise PermissionDenied(
                    'Direct requests are forbidden for fixed-price users.')
            kubes = db_pod.kubes_detailed
            for container in data.get('containers', []):
                if container.get('kubes') is not None:
                    kubes[container['name']] = container['kubes']
            if command == 'redeploy' and db_pod.kubes != sum(kubes.values()):
                # fix-price user is not allowed to upgrade pod
                # directly, only through billing system
                raise PermissionDenied(
                    'Direct requests are forbidden for fixed-price users.')

        pods = PodCollection(owner)
        return pods.update(pod_id, data)

    patch = put

    @maintenance_protected
    @use_kwargs(schema)
    def delete(self, pod_id, owner=None):
        current_user = self.get_current_user()
        owner = owner or current_user

        check_permission('delete', 'pods', user=owner).check()
        if owner != current_user:
            check_permission('delete_non_owned', 'pods').check()

        pods = PodCollection(owner)
        return pods.delete(pod_id)


register_api(podapi, PodsAPI, 'podapi', '/', 'pod_id', strict_slashes=False)


@podapi.route('/<pod_id>/<container_name>/update', methods=['GET'],
              strict_slashes=False)
@auth_required
@KubeUtils.jsonwrap
@check_permission('get', 'pods')
def check_updates(pod_id, container_name):
    user = KubeUtils.get_current_user()
    return PodCollection(user).check_updates(pod_id, container_name)


@podapi.route('/<pod_id>/<container_name>/update', methods=['POST'],
              strict_slashes=False)
@auth_required
@KubeUtils.jsonwrap
@check_permission('get', 'pods')
def update_container(pod_id, container_name):
    user = KubeUtils.get_current_user()
    return PodCollection(user).update_container(pod_id, container_name)


@podapi.route('/<pod_id>/direct_access', methods=['GET'],
              strict_slashes=False)
@auth_required
@KubeUtils.jsonwrap
@check_permission('get', 'pods')
def access_container(pod_id):
    user = KubeUtils.get_current_user()
    return PodCollection(user).direct_access(pod_id)
