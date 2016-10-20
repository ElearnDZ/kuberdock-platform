# coding=utf-8
"""Tests for helper.py classes"""
import os
import unittest
from StringIO import StringIO
from tempfile import NamedTemporaryFile

import mock
import pytest
import responses

from .. import helper
from ..container import container

TEST_URL = 'http://localhost'
TEST_USER = 'user1'
TEST_PASSWORD = 'password1'


class TestHelperKubeQuery(unittest.TestCase):
    """Tests for KubeQuery class."""

    def _get_default_query(self):
        return helper.KubeQuery(url=TEST_URL, user=TEST_USER,
                                password=TEST_PASSWORD,
                                jsonify_errors=True)

    @responses.activate
    def test_get(self):
        """Test KubeQuery.get method"""
        query = self._get_default_query()
        path1 = '/path1/to/some/api'
        path2 = '/path2/to/some/api'
        responses.add(responses.GET, TEST_URL + path1,
                      body='{"error": "not found"}', status=404,
                      content_type='application/json')
        self.assertRaises(SystemExit, query.get, path1)

        body = '{"data": [1,2,3]}'
        responses.add(responses.GET, TEST_URL + path2,
                      body=body, status=200,
                      content_type='application/json',
                      match_querystring=True)
        res = query.get(path2)
        self.assertEqual(res, {u'data': [1, 2, 3]})

        token = 'qwerty'
        query.token = token
        body = '{"data": [3,4,5]}'
        responses.add(responses.GET, TEST_URL + path2 + '?token=' + token,
                      body=body, status=200,
                      content_type='application/json',
                      match_querystring=True)
        res = query.get(path2)
        self.assertEqual(res, {u'data': [3, 4, 5]})

    @responses.activate
    def test_post(self):
        """Test KubeQuery.post method"""
        query = self._get_default_query()
        token = '1324qewr'
        query.token = token
        path1 = '/path1/to/some/api'
        resp_body = '{"data": [1,2,3]}'
        req_data = '{"somekey": "somevalue"}'
        responses.add(responses.POST, TEST_URL + path1 + '?token=' + token,
                      body=resp_body, status=200,
                      content_type='application/json',
                      match_querystring=True)
        res = query.post(path1, req_data)
        self.assertEqual(res, {u'data': [1, 2, 3]})
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(responses.calls[0].request.body, req_data)

    @responses.activate
    def test_put(self):
        """Test KubeQuery.put method"""
        query = self._get_default_query()
        token = '1324qewrty'
        query.token = token
        path1 = '/path1/to/some/api'
        resp_body = '{"data": [1,2,3]}'
        req_data = '{"somekey": "somevalue"}'
        responses.add(responses.PUT, TEST_URL + path1 + '?token=' + token,
                      body=resp_body, status=200,
                      content_type='application/json',
                      match_querystring=True)
        res = query.put(path1, req_data)
        self.assertEqual(res, {u'data': [1, 2, 3]})
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(responses.calls[0].request.body, req_data)

    @responses.activate
    def test_delete(self):
        """Test KubeQuery.delete method"""
        query = self._get_default_query()
        token = '1324qewrtyui'
        query.token = token
        path1 = '/path1/to/some/api'
        resp_body = '{"data": [1,2,3]}'
        responses.add(responses.DELETE, TEST_URL + path1 + '?token=' + token,
                      body=resp_body, status=200,
                      content_type='application/json',
                      match_querystring=True)
        res = query.delete(path1)
        self.assertEqual(res, {u'data': [1, 2, 3]})


class TestParseConfig(unittest.TestCase):
    """Tests for configuration file parser"""

    VALID_CONFIG = "[global]" \
                   "url = https://127.0.0.1" \
                   "[defaults]" \
                   "registry = registry.hub.docker.com" \
                   "user = TrialUser" \
                   "password = TrialUser"

    INVALID_CONFIG = "url = https://127.0.0.1" \
                     "[defaults]" \
                     "registry = registry.hub.docker.com" \
                     "user = TrialUser" \
                     "password = TrialUser"

    def setUp(self):
        with NamedTemporaryFile('w', delete=False) as valid:
            with NamedTemporaryFile('w', delete=False) as invalid:
                valid.write(self.VALID_CONFIG)
                invalid.write(self.INVALID_CONFIG)
                self.invalid_path, self.valid_path = invalid.name, valid.name

    def tearDown(self):
        os.unlink(self.invalid_path)
        os.unlink(self.valid_path)

    def test_parse_valid_config(self):
        data = helper.parse_config(self.valid_path)
        self.assertTrue(isinstance(data, dict))

    def test_parse_invalid_config(self):
        self.assertRaises(SystemExit, helper.parse_config, self.invalid_path)


@mock.patch.object(helper, 'PrintOut')
@mock.patch.object(container.KuberDock, '_load')
@mock.patch.object(container.KuberDock, '_save')
@mock.patch('sys.stdout', new_callable=StringIO)
class TestEchoDecorator(unittest.TestCase):
    def test_bliss_json_true(self, _print, _save, _load, _printout):
        _printout.instantiated = False
        k = container.KuberDock(json=True)
        k.set()
        self.assertEqual('{"status": "OK"}\n', _print.getvalue())

    def test_bliss_json_false(self, _print, _save, _load, _printout):
        _printout.instantiated = True
        k = container.KuberDock(json=False)
        k.set()
        self.assertEqual('', _print.getvalue())

    def test_bliss_json_true_instantiated(self, _print, _save, _load,
                                          _printout):
        _printout.instantiated = True
        k = container.KuberDock(json=True)
        k.set()
        self.assertEqual('', _print.getvalue())

    def test_bliss_json_false_non_instantiated(self, _print, _save, _load,
                                               _printout):
        _printout.instantiated = False
        k = container.KuberDock(json=False)
        k.set()
        self.assertEqual('', _print.getvalue())


@pytest.fixture()
def print_out():
    return helper.PrintOut(wants_header=True)


class TestUnicodePrintOut(object):
    @pytest.mark.parametrize('s', [
        'Hello world',
        'Привет мир',
        u'Привет мир',
        ['Привет мир'],
        [u'Привет мир'],
        {'Бугага': 'Привет мир'},
        {u'Бугага': u'Привет мир'},
    ])
    def test_show(self, s, print_out):
        print_out.show(s)

    @pytest.mark.parametrize('s', [
        [
            {'name': 'Привет мир'},
            {'name': u'Привет мир'},
        ]
    ])
    def test_show_list(self, s, print_out):
        print_out.show_list(s)


if __name__ == '__main__':
    unittest.main()
