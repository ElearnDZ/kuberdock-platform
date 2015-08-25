import os
import shutil
import json
import logging
import operator
import requests
import ConfigParser
import collections
import warnings

from requests.auth import HTTPBasicAuth


class NullHandler(logging.Handler):
    def emit(self, record):
        pass


class KubeQuery(object):
    CONNECT_TIMEOUT = 3
    READ_TIMEOUT = 15

    def _compose_args(self):
        args = {
            'auth': HTTPBasicAuth(
                getattr(self, 'user', 'user'),
                getattr(self, 'password', 'password'))}
            #'timeout': (self.CONNECT_TIMEOUT, self.READ_TIMEOUT)}
        if self.url.startswith('https'):
            args['verify'] = False
        return args

    def _raise_error(self, error_string):
        if self.json:
            raise SystemExit(json.dumps({'status': 'ERROR', 'message': error_string}))
        else:
            raise SystemExit(error_string)

    def _make_url(self, res):
        token = getattr(self, 'token', None)
        token = '?token=%s' % token if token is not None else ''
        if res is not None:
            return self.url + res + token
        return self.url + token

    def _return_request(self, req):
        try:
            return req.json()
        except (ValueError, TypeError):
            return req.text

    def _get(self, res=None, params=None):
        args = self._compose_args()
        if params:
            args['params'] = params
        return self._run('get', res, args)

    def _post(self, res, data, rest=False):
        args = self._compose_args()
        args['data'] = data
        if rest:
            args['headers'] = {'Content-type': 'application/json',
                               'Accept': 'text/plain'}
        return self._run('post', res, args)

    def _put(self, res, data):
        args = self._compose_args()
        args['data'] = data
        args['headers'] = {'Content-type': 'application/json',
                           'Accept': 'text/plain'}
        return self._run('put', res, args)

    def _del(self, res):
        args = self._compose_args()
        return self._run('del', res, args)

    def _run(self, act, res, args):
        dispatcher = {
            'get': requests.get,
            'post': requests.post,
            'put': requests.put,
            'del': requests.delete
        }
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                req = dispatcher.get(act, 'get')(self._make_url(res), **args)
                return self._return_request(req)
        except requests.exceptions.ConnectionError, e:
            return self._raise_error(str(e))


class PrintOut(object):

    def __getattr__(self, attr):
        if attr == '_WANTS_HEADER':
            return False
        if attr == '_FIELDS':
            return (('name', 32),)
        if attr == '_INDENT':
            return 4
        raise AttributeError("'{0}' object has no attribute '{1}'".format(
            self.__class__.__name__, attr))

    def _list(self, data):
        if self.json:
            self._print_json(data)
        else:
            self._print(data)

    def _show(self, data):
        if self.json:
            self._print_json(data)
        else:
            self._r_print(data)

    @staticmethod
    def _print_json(data):
        try:
            print json.dumps(data)
        except (ValueError, TypeError):
            print json.dumps({'status': 'ERROR', 'message': 'Unparseable format'})

    def _print(self, data):
        if isinstance(data, collections.Mapping):
            self._list_data(data)
        elif isinstance(data, collections.Iterable):
            if self._WANTS_HEADER:
                self._print_header()
            for item in data:
                self._list_data(item)
        else:
            raise SystemExit("Unknown format")

    def _r_print(self, data, offset=0):
        if isinstance(data, dict):
            for k, v in sorted(data.items(), key=operator.itemgetter(0)):
                if isinstance(v, (list, dict)):
                    print "{0}{1}:".format(' ' * (self._INDENT * offset), k)
                    self._r_print(v, offset+1)
                else:
                    print '{0}{1}: {2}'.format(
                        ' ' * (self._INDENT * offset), k, v)
        elif isinstance(data, list):
            for item in data:
                self._r_print(item, offset)
        elif isinstance(data, basestring):
            print '{0}{1}'.format(' ' * (self._INDENT * offset), data)
        else:
            raise SystemExit("Unknown format")

    def _print_header(self):
        fmt = ''.join( ['{{{0}:<{1[1]}}}'.format(i, v)
                for i, v in enumerate(self._FIELDS)])
        print fmt.format(*[i[0].upper() for i in self._FIELDS])

    def _list_data(self, data):
        if self._FIELDS is None:
            self._FIELDS = list((k, 32) for k, v in data.items())
        fmt = ''.join(['{{{0[0]}:<{0[1]}}}'.format(i) for i in self._FIELDS])
        print fmt.format(**data)

    @staticmethod
    def _unwrap(data):
        try:
            return data['data']
        except KeyError:
            return data


def make_config(args):
    create_user_config(args)
    excludes = ['call', 'config']
    config = parse_config(os.path.expanduser(args.config))
    for k, v in vars(args).items():
        if k in excludes:
            continue
        if v is not None:
            config[k] = v

    return config


def parse_config(path):
    data = {}
    conf = ConfigParser.ConfigParser()
    conf.optionxform = str
    configs = conf.read(path)
    if len(configs) == 0:   # no configs found
        raise SystemExit(
            "Config '{0}' not found. Try to specify a custom one with option '--config'".format(path))
    for section in conf.sections():
        data.update(dict(conf.items(section)))
    return data


def create_user_config(args):
    path = os.path.expanduser(args.config)
    default_path = os.path.expanduser('~/.kubecli.conf')
    old_default_path = '/etc/kubecli.conf'

    if not os.path.exists(default_path):
        print('Default config was not found: {0}'.format(default_path))
        conf = ConfigParser.ConfigParser()
        conf.optionxform = str
        if os.path.exists(path):
            print('Saving specified config as default...')
            conf.read(path)
        elif os.path.exists(old_default_path):
            print('Default config path was changed. Saving {0} as {1}...'
                  ''.format(old_default_path, default_path))
            conf.read(old_default_path)
        else:
            raise SystemExit("Config '{0}' not found. Try to specify a custom "
                             "one with option '--config'".format(path))
        conf.set('defaults', 'user', args.user)
        conf.set('defaults', 'password', args.password)
        conf.set('defaults', 'token', args.token)
        with open(default_path, 'wb') as config:
            conf.write(config)
