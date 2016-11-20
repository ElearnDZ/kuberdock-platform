import json
from urlparse import urljoin

import requests

from ... import exceptions


class Connect(object):
    def __init__(self, host, user, token):
        self.host = host
        self.user = user
        _token = ''.join(
            token.split())  # if token entered as multi-line string
        self.token = _token
        self.api_type = 'json-api'

    def _request(self, method, function, data=None):
        url_path = '{}/{}'.format(self.api_type, function)
        url = urljoin(self.host, url_path)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'WHM {user}:{token}'.format(
                user=self.user, token=self.token
            )
        }
        response = requests.request(
            method,
            url=url,
            data=data,
            headers=headers,
            verify=False
        )

        response.raise_for_status()
        return json.loads(response.content.decode('utf-8'))

    def post(self, *args, **kwargs):
        return self._request('POST', *args, **kwargs)

    def get(self, *args, **kwargs):
        return self._request('GET', *args, **kwargs)

    def raise_for_status(self, response):
        try:
            failures = [r for r in response['result'] if r['status'] != 1]
            if failures:
                message = '\n'.join(f['statusmsg'] for f in failures)
                raise exceptions.GenericPluginError(message, response['result'])
        except KeyError:
            raise exceptions.UnexpectedResponse(response=response)


class API(object):
    def __init__(self, host, user, token):
        self.connect = Connect(host, user, token)

    def zones(self):
        for zone in self.connect.get('listzones')['zone']:
            yield self.get_zone(zone['domain'])

    def get_zone(self, domain):
        response = self.connect.get('dumpzone', {'domain': domain})
        try:
            self.connect.raise_for_status(response)
            return Zone(name=domain, info=response, connect=self.connect)
        except exceptions.GenericPluginError as e:
            if e.response[0]['statusmsg'] == 'Zone does not exist.':
                raise exceptions.ZoneDoesNotExist(domain, e.response)
            raise


class Zone(object):
    def __init__(self, name, info, connect):
        self.name = name
        self.info = info
        self.connect = connect

    def records(self):
        # Need to understand why so complex path
        for record in self.info['result'][0]['record']:
            rec = Record(
                zone_name=self.name,
                connect=self.connect,
                **record
            )
            yield rec

    def add_a_record(self,
                     domain,
                     address,
                     record_class="IN",
                     record_type="A",
                     ttl=86400):
        return Record(
            zone_name=self.name,
            connect=self.connect,
            **{
                'address': address,
                'name': domain.split('.')[0],
                'class': record_class,
                'ttl': ttl,
                'type': record_type
            }
        ).add()

    def add_cname_record(self, domain, target, ttl=86400):
        return Record(
            zone_name=self.name,
            connect=self.connect,
            # ** is used here because class and type are reserverd keywords
            **{
                'cname': target,
                'name': domain.split('.')[0],
                'ttl': ttl,
                'class': 'IN',
                'type': 'CNAME',
            }
        ).add()


class Record(object):
    def __init__(self, zone_name, connect, **info):
        self.zone_name = zone_name
        self.connect = connect
        self.info = info

    def __setattr__(self, key, value):
        if key not in ['connect', 'info', 'zone_name']:
            self.info[key] = value
        else:
            super(Record, self).__setattr__(key, value)

    def __getattr__(self, item):
        return self.info[item]

    def add(self):
        new_info = self.info.copy()
        new_info['domain'] = self.zone_name
        response = self.connect.post('addzonerecord', data=new_info)
        self.connect.raise_for_status(response)
        return response

    def edit(self):
        new_info = self.info.copy()
        new_info['domain'] = self.zone_name
        response = self.connect.post('editzonerecord', data=new_info)
        self.connect.raise_for_status(response)
        return response

    def delete(self):
        assert self.zone_name, "Domain name should be define"
        assert self.info['Line'], "Line should be define"

        response = self.connect.post('removezonerecord', data={
            'zone': self.zone_name,
            'line': self.info['Line']
        })
        self.connect.raise_for_status(response)
        return response
