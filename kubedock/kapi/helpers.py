import json
import random
import requests
import string
from ..core import db
from ..pods.models import Pod
#from ..users.models import User
#from ..users.signals import user_get_setting, user_set_setting
from ..api import APIError
from ..utils import get_api_url
from flask import current_app


class KubeQuery(object):
    return_json = True

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
        if self.return_json:
            raise SystemExit(
                json.dumps(
                    {'status': 'ERROR',
                     'message': error_string}))
        else:
            raise SystemExit(error_string)

    @staticmethod
    def _make_url(res, ns=None):
        """
        Composes a full URL
        :param res: list -> list of URL path items
        """
        if res is not None:
            return get_api_url(*res, namespace=ns)
        return get_api_url(namespace=ns)

    def _return_request(self, req):
        try:
            if self.return_json:
                return req.json()
            return req.text
        except (ValueError, TypeError), e:
            raise APIError("Cannot process request: {0}".format(str(e)))

    def _get(self, res=None, params=None, ns=None):
        """
        GET request wrapper.
        :param res: list of URL path items
        :param params: dict -> request params
        """
        args = self._compose_args()
        if params:
            args['params'] = params
        return self._run('get', res, args, ns)

    def _post(self, res, data, rest=False, ns=None):
        args = self._compose_args(rest)
        args['data'] = data
        return self._run('post', res, args, ns)

    def _put(self, res, data, rest=False, ns=None):
        args = self._compose_args(rest)
        args['data'] = data
        return self._run('put', res, args, ns)

    def _del(self, res, ns=None):
        args = self._compose_args()
        return self._run('del', res, args, ns)

    def _run(self, act, res, args, ns):
        dispatcher = {
            'get': requests.get,
            'post': requests.post,
            'put': requests.put,
            'del': requests.delete
        }
        try:
            req = dispatcher.get(act, requests.get)(self._make_url(res, ns),
                                                    **args)
            return self._return_request(req)
        except requests.exceptions.ConnectionError, e:
            return self._raise_error(str(e))


class ModelQuery(object):

    def _fetch_pods(self, users=False, live_only=True):
        if users:
            if live_only:
                return db.session.query(Pod).join(Pod.owner).filter(Pod.status != 'deleted')
            return db.session.query(Pod).join(Pod.owner)
        if live_only:
            return db.session.query(Pod).filter(Pod.status != 'deleted')
        return db.session.query(Pod)

    def _check_pod_name(self, owner=None):
        if not hasattr(self, 'name'):
            return
        if owner is None:
            pod = Pod.query.filter_by(name=self.name).first()
        else:
            pod = Pod.query.filter_by(name=self.name, owner=owner).first()
        if pod:
            raise APIError("Conflict. Pod with name = '{0}' already exists. "
                           "Try another name.".format(self.name),
                           status_code=409)

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
    def replace_config(pod, data):
        """
        Replaces config in DB entirely with provided one
        :param data: dict -> config to be saved
        """
        db_pod = db.session.query(Pod).get(pod.id)
        try:
            db_pod.config = json.dumps(data)
            db.session.commit()
        except Exception:
            db.session.rollback()

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

    @staticmethod
    def _make_name_from_image(image):
        """
        Appends random part to image
        :param image: string -> image name
        """
        n = '-'.join(map((lambda x: x.lower()), image.split('/')))
        return "%s-%s" % (n, ''.join(
            random.sample(string.lowercase + string.digits, 10)))

    def merge_lists(self, list_1, list_2, key, replace=False):
        merged = {}
        for item in list_1 + list_2:
            item_key = item[key]
            if item_key in merged:
                if replace:
                    merged[item_key].update(item)
                else:
                    merged[item_key].update(item.items() + merged[item_key].items())
            else:
                merged[item_key] = item
        return merged.values()
