from flask import Blueprint
from flask.views import MethodView
from ..utils import login_required_or_basic_or_token, KubeUtils, register_api
from ..utils import maintenance_protected
from ..kapi.podcollection import PodCollection
from ..validation import check_new_pod_data


podapi = Blueprint('podapi', __name__, url_prefix='/podapi')


class PodsAPI(KubeUtils, MethodView):
    decorators = [KubeUtils.jsonwrap, KubeUtils.pod_permissions, KubeUtils.pod_start_permissions,
                  login_required_or_basic_or_token]

    def get(self, pod_id):
        #params = self._get_params()
        user = self._get_current_user()
        return PodCollection(user).get(as_json=False)

    @maintenance_protected
    def post(self):
        user = self._get_current_user()
        params = self._get_params()
        check_new_pod_data(params, user)
        return PodCollection(user).add(params)

    @maintenance_protected
    def put(self, pod_id):
        user = self._get_current_user()
        params = self._get_params()
        #check_change_pod_data(params)
        pods = PodCollection(user)
        return pods.update(pod_id, params)

    @maintenance_protected
    def delete(self, pod_id):
        user = self._get_current_user()
        pods = PodCollection(user)
        return pods.delete(pod_id)
register_api(podapi, PodsAPI, 'podapi', '/', 'pod_id', strict_slashes=False)
