from mock import mock

from kubedock.pods import models as pods_models
from kubedock.pods.models import IPPool
from kubedock.testutils.testcases import APITestCase

TEST_POD_DATA = {
    'containers': [
        {
            'image': 'nginx',
            'ports': [
                {
                    'isPublic': True
                }
            ]
        }
    ]
}


@mock.patch('kubedock.kapi.licensing.is_valid', lambda *a, **kw: True)
@mock.patch('kubedock.kapi.podcollection.PodCollection._get_namespaces',
            mock.Mock())
@mock.patch('kubedock.kapi.podcollection.PodCollection._get_pods',
            mock.Mock())
@mock.patch('kubedock.kapi.podcollection.PodCollection._merge',
            mock.Mock())
class TestBilling(APITestCase):
    url = '/billing'

    def setUp(self):
        super(TestBilling, self).setUp()
        pods_models.MASTER_IP = '192.168.254.1'

    @mock.patch('kubedock.kapi.apps.dispatch_kind', mock.Mock())
    @mock.patch('kubedock.kapi.apps.check_new_pod_data', mock.Mock(
        return_value=TEST_POD_DATA))
    @mock.patch('kubedock.api.billing.PredefinedApp.get')
    @mock.patch('kubedock.system_settings.models.SystemSettings.get_by_name',
                mock.Mock(return_value='WHMCS'))
    @mock.patch('kubedock.billing.resolver.BillingFactory.get_billing')
    def test_no_free_ips(self,
                         get_billing, app):
        billing = mock.Mock()
        get_billing.return_value = billing
        billing.orderapp.return_value = {}
        url = '/'.join([self.url, 'orderapp/3/0'])
        resonse = self.open(url, method='POST')
        self.assertAPIError(resonse, 400, 'APIError')
        self.assertEqual(resonse.json['data'], 'There is a problem with a '
                                               'package you trying to buy. '
                                               'Please, try again or contact'
                                               ' support team.')

        # add free ip
        IPPool(network='192.168.122.60/30').save()

        resonse = self.open(url, method='POST')
        self.assert200(resonse)
        billing.orderapp.assert_called_once_with(
            pkgid=app()._get_package().id,
            yaml=app().get_filled_template_for_plan(),
            referer=None)
