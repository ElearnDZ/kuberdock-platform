from flask import Blueprint, current_app, request

from kubedock.decorators import maintenance_protected
from kubedock.exceptions import APIError, BillingExc
from kubedock.login import auth_required
from kubedock.utils import KubeUtils
from kubedock.billing.models import Package, Kube
from kubedock.system_settings.models import SystemSettings
from kubedock.kapi.apps import PredefinedApp
from kubedock.kapi.podcollection import PodCollection
import json


billing = Blueprint('billing', __name__, url_prefix='/billing')


class WithoutBilling(APIError):
    message = 'Without billing'
    status_code = 404


def no_billing_data():
    return {
        'billing': 'No billing',
        'packages': [p.to_dict(with_kubes=True) for p in Package.query.all()],
        'default': {
            'kubeType': Kube.get_default_kube().to_dict(),
            'packageId': Package.get_default().to_dict(),
        }
    }


@billing.route('/info', methods=['GET'], strict_slashes=False)
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
def get_billing_info():
    data = KubeUtils._get_params()
    current_billing = SystemSettings.get_by_name('billing_type')
    if current_billing == 'No billing':
        return no_billing_data()
    billing = current_app.billing_factory.get_billing(current_billing)
    return billing.getkuberdockinfo(**data)


@billing.route('/paymentmethods', methods=['GET'], strict_slashes=False)
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
def payment_methods():
    current_billing = SystemSettings.get_by_name('billing_type')
    if current_billing == 'No billing':
        raise WithoutBilling()
    billing = current_app.billing_factory.get_billing(current_billing)
    return billing.getpaymentmethods()


@billing.route('/order', methods=['POST'], strict_slashes=False)
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
def order_product():
    data = KubeUtils._get_params()
    current_billing = SystemSettings.get_by_name('billing_type')
    if current_billing == 'No billing':
        raise WithoutBilling()
    billing = current_app.billing_factory.get_billing(current_billing)
    if data.get('pod'):
        data['referer'] = data['referer'] if 'referer' in data else ''
        return billing.orderpod(**data)
    return billing.orderproduct(**data)


@billing.route('/orderPodEdit', methods=['POST'], strict_slashes=False)
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
def order_edit():
    data = KubeUtils._get_params()
    data['pod'] = json.dumps(data['pod'])
    current_billing = SystemSettings.get_by_name('billing_type')
    if current_billing == 'No billing':
        raise WithoutBilling()
    billing = current_app.billing_factory.get_billing(current_billing)
    data['referer'] = data['referer'] if 'referer' in data else ''
    response = billing.orderpodedit(**data)
    if isinstance(response, basestring):
        raise BillingExc.InternalBillingError(
                    details={'message': response})
    if response.get('result') == 'error':
        raise APIError(response.get('message'))
    return response


@billing.route('/switch-app-package/<pod_id>/<int:plan_id>',
               methods=['POST'], strict_slashes=False)
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
def switch_app_package(pod_id, plan_id):
    current_billing = SystemSettings.get_by_name('billing_type')
    if current_billing == 'No billing':
        raise WithoutBilling()
    billing = current_app.billing_factory.get_billing(current_billing)
    owner = KubeUtils.get_current_user()

    old_pod = PodCollection(owner).get(pod_id, as_json=True)
    PredefinedApp.update_pod_to_plan(pod_id, plan_id, async=False)
    pod = PodCollection(owner).get(pod_id, as_json=True)

    data = KubeUtils._get_params()
    data['pod'] = pod
    data['oldPod'] = old_pod
    data['referer'] = data.get('referer') or ''

    return billing.orderswitchapppackage(**data)


@billing.route('/orderKubes', methods=['POST'], strict_slashes=False)
@auth_required
@maintenance_protected
@KubeUtils.jsonwrap
def order_kubes():
    data = KubeUtils._get_params()
    current_billing = SystemSettings.get_by_name('billing_type')
    if current_billing == 'No billing':
        raise WithoutBilling()
    billing = current_app.billing_factory.get_billing(current_billing)
    data['referer'] = data['referer'] if 'referer' in data else ''
    return billing.orderkubes(**data)


@billing.route('/orderapp/<int:template_id>/<int:plan_id>',
               methods=['POST'], strict_slashes=False)
# Currently this workflow does not imply authentication but we can force it
# @auth_required
@maintenance_protected
@KubeUtils.jsonwrap
def order_app(template_id, plan_id):
    data = KubeUtils._get_params()
    current_billing = SystemSettings.get_by_name('billing_type')
    if current_billing == 'No billing':
        raise WithoutBilling()
    app = PredefinedApp.get(template_id)
    filled = app.get_filled_template_for_plan(plan_id, data, as_yaml=True)
    pkgid = app._get_package().id
    billing = current_app.billing_factory.get_billing(current_billing)
    return billing.orderapp(pkgid=pkgid, yaml=filled, referer=request.referrer)
