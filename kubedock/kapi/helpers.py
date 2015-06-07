import ipaddress
import json
import random
import re
import requests
import string
from .. import signals
from ..core import db
from ..pods.models import Pod, PodIP
#from ..users.models import User
#from ..users.signals import user_get_setting, user_set_setting
from ..billing.models import Kube
from ..api import APIError
from ..utils import get_api_url

from flask import current_app

class KubeQuery(object):
    return_json=True

    @staticmethod
    def _compose_args(rest=False):
        """
        Adds request args
        :param rest: bool
        :return: dict -> args dict to be included to request
        """
        args = {}
        if rest:
            args['headers'] = {'Content-Type': 'application/json'}
        return args

    def _raise_error(self, error_string):
        """
        Raises an error
        :param error_string: string
        """
        if self._json:
            raise SystemExit(
                json.dumps(
                    {'status': 'ERROR',
                     'message': error_string}))
        else:
            raise SystemExit(error_string)

    @staticmethod
    def _make_url(res, use_v3=False, ns=None):
        """
        Composes a full URL
        :param res: list -> list of URL path items
        """
        kw = {'use_v3': use_v3, 'namespace': ns}
        if res is not None:
            return get_api_url(*res, **kw)
        return get_api_url(**kw)

    def _return_request(self, req):
        try:
            if self.return_json:
                return req.json()
            return req.text
        except (ValueError, TypeError), e:
            raise APIError("Cannot process request: {0}".format(str(e)))

    def _get(self, res=None, params=None, use_v3=False, ns=None):
        """
        GET request wrapper.
        :param res: list of URL path items
        :param params: dict -> request params
        """
        args = self._compose_args()
        if params:
            args['params'] = params
        return self._run('get', res, args, use_v3, ns)

    def _post(self, res, data, rest=False, use_v3=False, ns=None):
        args = self._compose_args(rest)
        args['data'] = data
        return self._run('post', res, args, use_v3, ns)

    def _put(self, res, data, rest=False, use_v3=False, ns=None):
        args = self._compose_args(rest)
        args['data'] = data
        return self._run('put', res, args, use_v3, ns)

    def _del(self, res, use_v3=False, ns=None):
        args = self._compose_args()
        return self._run('del', res, args, use_v3, ns)

    def _run(self, act, res, args, use_v3, ns):
        dispatcher = {
            'get': requests.get,
            'post': requests.post,
            'put': requests.put,
            'del': requests.delete
        }
        try:
            req = dispatcher.get(act, requests.get)(self._make_url(res, use_v3, ns), **args)
            return self._return_request(req)
        except requests.exceptions.ConnectionError, e:
            return self._raise_error(str(e))


class ModelQuery(object):

    def _fetch_pods(self, users=False, live_only=True):
        if users:
            if live_only:
                return db.session.query(Pod).join(Pod.owner).filter(Pod.status!='deleted')
            return db.session.query(Pod).join(Pod.owner)
        if live_only:
            return db.session.query(Pod).filter(Pod.status!='deleted')
        return db.session.query(Pod)



    def _check_pod_name(self, owner=None):
        if not hasattr(self, 'name'):
            return
        if owner is None:
            pod = Pod.query.filter_by(name=self.name).first()
        else:
            pod = Pod.query.filter_by(name=self.name, owner=owner).first()
        if pod:
            raise APIError(
                "Conflict. Pod with name = '{0}' already exists. "
                       "Try another name.".format(self.name),
                       status_code=409)

    def _allocate_ip(self, pod_id=None, ip=None):
        if pod_id is None:
            if hasattr(self, 'id'):
                pod_id = self.id
            else:
                raise TypeError('pod_id should be specified')
        if hasattr(self, 'public_ip'):
            ip = self.public_ip
        signals.allocate_ip_address.send([pod_id, ip])

    def _free_ip(self, ip=None):
        if hasattr(self, 'public_ip'):
            ip = self.public_ip
        if ip is not None:
            podip = PodIP.filter_by(
                ip_address=int(ipaddress.ip_address(ip)))
            pod = podip.first().pod
            pod_config = json.loads(pod.config)
            pod_config.pop('public_ip', None)
            for container in pod_config['containers']:
                for port in container['ports']:
                    port.pop('isPublic', None)
            pod.config = json.dumps(pod_config)
            podip.delete()

    def _save_pod(self, obj):
        kube_type = getattr(obj, 'kube_type', 0)
        pod = Pod(name=obj.name, config=json.dumps(vars(obj)), id=obj.id, status='stopped')
        kube = db.session.query(Kube).get(kube_type)
        if kube is None:
            kube = db.session.query(Kube).get(0)
        pod.kube = kube
        pod.owner = self.owner
        try:
            db.session.add(pod)
            db.session.commit()
            return pod
        except Exception, e:
            current_app.logger.debug(e)
            db.session.rollback()

    def _mark_pod_as_deleted(self, pod_id):
        p = db.session.query(Pod).get(pod_id)
        if p is not None:
            p.name += '__' + ''.join(random.sample(string.lowercase + string.digits, 8))
            p.status = 'deleted'
        db.session.commit()

    def get_config(self, param=None, default=None):
        db_pod = db.session.query(Pod).get(self.id)
        if param is None:
            return json.loads(db_pod.config)
        return json.loads(db_pod.config).get(param, default)

    @staticmethod
    def _update_pod_config(pod, **attrs):
        db_pod = db.session.query(Pod).get(pod.id)
        try:
            data = json.loads(db_pod.config)
            data.update(attrs)
            db_pod.config = json.dumps(data)
            db.session.commit()
        except Exception:
            db.session.rollback()


class Utilities(object):

    @staticmethod
    def _raise(message, code=409):
        raise APIError(message, status_code=code)

    def _raise_if_failure(self, return_value, message=None):
        """
        Raises error if return value has key 'status' and that status' value
        neither 'success' nor 'working' (which means failure)
        :param return_value: dict
        :param message: string
        """
        pass
        #if message is None:
        #    message = 'An error occurred'
        #status = return_value.get('status')
        #if status is not None and status.lower() not in ['success', 'working']:
        #    self._raise(message)

    def _make_dash(self, limit=None):
        """
        Substitutes certain symbols for dashes to make DNS-compatible string
        """
        data = '-'.join(re.split(r'[\s\\/\[\|\]{}\(\)\._]+', self.name))
        if limit is None:
            return data
        return data[:limit]

    def _make_sid(self):
        sid = ''.join(
            map((lambda x: x.lower()), re.split(r'[\s\\/\[\|\]{}\(\)\._]+',
                self.name)))
        sid += ''.join(random.sample(string.lowercase + string.digits, 20))
        return sid

    @staticmethod
    def _make_name_from_image(image):
        """
        Appends random part to image
        :param image: string -> image name
        """
        n = '-'.join(map((lambda x: x.lower()), image.split('/')))
        return "%s-%s" % (n, ''.join(
            random.sample(string.lowercase + string.digits, 10)))

    def merge_lists(self, l1, l2, key, replace=False):
        merged = {}
        for item in l1+l2:
            if item[key] in merged:
                if replace is False:
                    merged[item[key]].update(dict(item.items() + merged[item[key]].items()))
                else:
                    merged[item[key]].update(item)
            else:
                merged[item[key]] = item
        return [val for (_, val) in merged.items()]
