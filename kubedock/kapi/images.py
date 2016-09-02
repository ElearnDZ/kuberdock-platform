# -*- coding: utf-8 -*-
import json
from itertools import chain
from collections import Mapping, defaultdict, namedtuple
from contextlib import contextmanager
from datetime import datetime
from urllib import urlencode
from urlparse import urlparse, parse_qsl, urlsplit

import re
import requests
from ..core import db
from ..exceptions import APIError
from ..pods.models import DockerfileCache, PrivateRegistryFailedLogin
from ..settings import DEFAULT_REGISTRY, DEFAULT_IMAGES_URL


# FIXME: private registries with self-signed certs
requests.packages.urllib3.disable_warnings(
    requests.packages.urllib3.exceptions.InsecureRequestWarning)

#: Minimum time in seconds to stop authentication attempts to a private
# registry after last failed login attempt
MIN_FAILED_LOGIN_PAUSE = 3

DOCKERHUB_V1_INDEX = 'https://index.docker.io'
DEFAULT_REGISTRY_HOST = urlparse(DEFAULT_REGISTRY).netloc

API_VERSION_HEADER = 'docker-distribution-api-version'

#: Timeout for requests to registries in seconds
REQUEST_TIMEOUT = 15.0

#: Timeout for ping requests to registries in seconds
PING_REQUEST_TIMEOUT = 5.0


class ImageNotAvailable(APIError):
    message_template = 'Image "{image}" is not available'

    def __init__(self, image=None, **kwargs):
        super(ImageNotAvailable, self).__init__(
            details=dict(image=image, **kwargs))


class CommandIsMissing(APIError):
    message_template = (
        'You need to specify CMD or ENTRYPOINT for container "{container}", '
        'because image "{image}" does not provide one.')

    def __init__(self, image=None, container=None, **kwargs):
        super(CommandIsMissing, self).__init__(
            details=dict(image=image, container=container, **kwargs))


class RegistryError(APIError):
    """
    Raised when the whole registry is not available.
    """
    message_template = (
        'It seems that the registry {registryHost} is not available now '
        '({status}). Try again later or contact your administrator for '
        'support.')
    status_code = 503

    def __init__(self, registry=DEFAULT_REGISTRY, status='', **kwargs):
        super(RegistryError, self).__init__(
            details=dict(registryHost=urlparse(registry).netloc,
                         registry=registry, status=status, **kwargs))


@contextmanager
def raise_registry_error(url=DEFAULT_REGISTRY):
    try:
        yield
    except (requests.exceptions.HTTPError,
            requests.exceptions.TooManyRedirects) as e:
        raise RegistryError(url, e.message)
    except requests.exceptions.Timeout:
        raise RegistryError(url, 'timeout error')
    except requests.exceptions.ConnectionError:
        raise RegistryError(url, 'connection error')


def check_registry_status(url=DEFAULT_IMAGES_URL, _v2=False):
    """
    Performs api check for registry health status.

    :params url: registry url
    :raises RegistryError: if registry is not available
    """
    url = urlsplit(url)._replace(path='/v2/' if _v2 else '/v1/_ping').geturl()

    with raise_registry_error(url):
        response = requests.get(url, timeout=PING_REQUEST_TIMEOUT,
                                verify=False)
        need_v2 = not _v2 and response.status_code == 404 and \
            response.headers.get(API_VERSION_HEADER) == 'registry/2.0'
        if need_v2:
            check_registry_status(url, _v2=True)
        elif response.status_code == 401:
            return  # user is not authorized, but registry is available
        else:
            response.raise_for_status()


def search_image(term, url=DEFAULT_IMAGES_URL, page=1, page_size=10):
    url = urlsplit(url)._replace(path='/v2/search/repositories').geturl()
    params = {'query': term, 'page_size': page_size, 'page': page}
    with raise_registry_error(url):
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT,
                                verify=False)
        response.raise_for_status()
        return response.json()


class APIVersionError(Exception):
    """Helper exception to raise on invalid API version in a docker registry"""
    pass


class DockerAuth(requests.auth.AuthBase):
    """Docker Registry v2 authentication + HTTP Basic Auth for private
    registry.

    """
    _bearer_pat = re.compile(r'bearer ', flags=re.IGNORECASE)

    def __init__(self, username=None, password=None):
        """
        Usage:
        DockerAuth('my-username', 'my-password')
        DockerAuth(username='my-username', password='my-password')
        DockerAuth(['my-username', 'my-password'])
        without credentials:
        DockerAuth(), DockerAuth(None), DockerAuth(None, None)
        """
        if hasattr(username, '__iter__') and password is None:
            # got one iterable
            username, password = username
        self.username, self.password = username, password
        self.num_401_calls = 0
        self.original_url = None

    def get_token(self, chal):
        """
        Try to complete the challenge.

        :param chal: challenge string
        :returns: token or None
        """
        url = urlparse(chal.pop('realm'))
        query = urlencode(dict(parse_qsl(url.query), **chal))
        url = url._replace(query=query).geturl()
        auth = None if self.username is None \
            else (self.username, self.password)
        response = requests.get(url, auth=auth, timeout=REQUEST_TIMEOUT)
        data = _json_or_none(response)
        if isinstance(data, dict):
            return data.get('token')

    def handle_401(self, response, **kwargs):
        s_auth = response.headers.get('www-authenticate')
        if not s_auth or self.num_401_calls > 0:
            return response

        seconds_to_wait = when_next_login_allowed(
            self.username, response.request.url)
        raise_api_error_to_login_pause(seconds_to_wait)
        self.num_401_calls += 1

        method = s_auth.split()[0].lower()
        if method in ('basic', 'bearer'):
            # Consume content and release the original connection
            # to allow our new request to reuse the same one.
            response.content
            response.raw.release_conn()
            prep = response.request.copy()

            if method == 'basic' and self.username is not None:
                # private registry
                prep = requests.auth.HTTPBasicAuth(
                    self.username, self.password)(prep)
            elif method == 'bearer':  # Docker Registry v2 authentication
                chal = requests.utils.parse_dict_header(
                    self._bearer_pat.sub('', s_auth, count=1))
                token = self.get_token(chal)
                if token is not None:
                    prep.headers['Authorization'] = 'Bearer {0}'.format(token)

            new_response = response.connection.send(prep, **kwargs)
            new_response.history.append(response)
            new_response.request = prep
            if new_response.status_code == requests.codes.unauthorized:
                save_failed_login(self.username, response.request.url)
            return new_response
        return response

    def __call__(self, request):
        request.register_hook('response', self.handle_401)
        return request


def save_failed_login(username, url):
    """Remember current user name and registry in failed logins table."""
    url = url or ''
    registry = urlparse(url).netloc
    if not(username and registry):
        return
    PrivateRegistryFailedLogin(
        login=username, registry=registry, created=datetime.utcnow()
    ).save()


def when_next_login_allowed(username, url):
    """Check last failed login for current username and registry was
    earlier than minimum allowed pause for login attempts.
    Returns number of seconds we should wait.

    """
    url = url or ''
    registry = urlparse(url).netloc
    if not (username and registry):
        return 0
    last_entry = PrivateRegistryFailedLogin.query.filter(
        PrivateRegistryFailedLogin.login == username,
        PrivateRegistryFailedLogin.registry == registry,
    ).order_by(PrivateRegistryFailedLogin.created.desc()).first()
    if not last_entry:
        return 0
    timediff = datetime.utcnow() - last_entry.created
    timediff = timediff.seconds + timediff.days * 24 * 60 * 60
    if timediff >= MIN_FAILED_LOGIN_PAUSE:
        return 0
    return MIN_FAILED_LOGIN_PAUSE - timediff


def raise_api_error_to_login_pause(seconds):
    """Raises API error if specified seconds is > 0."""
    if seconds:
        raise APIError(
            'To prevent blocking of the user name wait for {0} seconds '
            'before next login attempt.'.format(seconds),
            requests.codes.too_many_requests)


def docker_auth_v1(session, registry, repo, auth):
    """
    Docker Registry v1 authentication (using both token and session)

    :param session: requests.Session object
    :param registry: full registry address (https://quay.io)
    :param repo: repo name including "namespace" (library/nginx)
    :param auth: (username, password) or None
    :returns: True if auth was successful otherwise False
    """
    if registry == DEFAULT_REGISTRY:  # dockerhub have index on different host
        registry = DOCKERHUB_V1_INDEX
    username = None
    if auth and auth[0]:
        username = auth[0]
        seconds_to_wait = when_next_login_allowed(username, registry)
        raise_api_error_to_login_pause(seconds_to_wait)
    url = get_url(registry, 'v1/repositories', repo, 'images')
    response = session.get(url, auth=auth, headers={'x-docker-token': 'true'},
                           timeout=REQUEST_TIMEOUT)
    if response.status_code != 200:
        if response.status_code == requests.codes.unauthorized and username:
            save_failed_login(username, url)
        return False
    token = response.headers.get('x-docker-token')
    if token:
        session.headers['authorization'] = 'Token {0}'.format(token)
    return True


def get_url(base, *path):
    return urlparse(base)._replace(path='/'.join(path)).geturl()


def _json_or_none(response):
    try:
        return response.json()
    except ValueError:
        pass


def complement_registry(registry):
    if not urlparse(registry).scheme:
        registry = 'https://{0}'.format(registry)
    return registry.rstrip('/')


class Image(namedtuple('Image', ['full_registry', 'registry', 'repo', 'tag'])):
    """
    Represents parsed image url with common methods for Docker Registry API.

    Instance attributes:
        full_registry - registry url with schema and empty path,
            like "https://quay.io"
        registry - registry host, like "quay.io"
        repo - repository name, like "quay/redis"
        tag - tag name, like "latest"
    """
    pattern = re.compile(r'^(?:(.+(?:\..+?)+)\/)?(.+?)(?:\:(.+))?$')

    # Image inherits from immutable type (namedtuple),
    # so we use __new__ instead of __init__
    def __new__(cls, image):
        """
        Parse image url or copy parsed Image object.

        :param image: other Image object or image url string.
            May be in the following forms:
             - nginx[:tag] - for offical dockerhub images
             - username/nginx[:tag] - for user's images on dockerhub
             - some.hub.com/username/nginx[:tag] - for images on 3rd party
                 registries
            if tag is omitted, 'latest' will be used
        """
        if isinstance(image, Image):
            return super(Image, cls).__new__(cls, *image)
        else:
            # TODO: add digest support
            parsed = cls.pattern.match(image)
            if not parsed:
                raise APIError('invalid image url: {0}'.format(image))
            registry, repo, tag = parsed.groups()
            tag = tag or 'latest'
            if not registry or registry.endswith('docker.io'):
                registry = DEFAULT_REGISTRY_HOST
                full_registry = DEFAULT_REGISTRY
                if '/' not in repo:
                    repo = 'library/{0}'.format(repo)
            else:
                full_registry = complement_registry(registry)
            return super(Image, cls).__new__(
                cls, full_registry, registry, repo, tag)

    def __str__(self):
        full_registry, registry, repo, tag = self
        if self.is_dockerhub and repo.startswith('library/'):
            repo = repo[len('library/'):]

        url_format = '{repo}'
        if tag != 'latest':
            url_format += ':{tag}'
        if full_registry != DEFAULT_REGISTRY:
            url_format = '{registry}/' + url_format
        return url_format.format(registry=registry, repo=repo, tag=tag)

    @property
    def is_dockerhub(self):
        return self.registry.endswith('docker.io')

    @property
    def is_official(self):
        return self.is_dockerhub and self.repo.startswith('library/')

    @property
    def source_url(self):
        return (str(self) if not self.is_dockerhub else
                'hub.docker.com/r/' + self.repo if not self.is_official else
                'hub.docker.com/_/' + self.repo.replace('library/', '', 1))

    def _v2_request_image_info(self, auth, just_check=False, raise_=False):
        """Config request via V2 API
        Get info about image from manifest using Docker Registry API v2

        :param auth: (username, password) or None
        :param just_check: only check image availability, do not extract
            configuration
        :param raise_: raise APIVersionError or just return None
        :returns: full image info (True if just_check=True) or None
        :raise APIVersionError: for check requests - if registry doesn't
            support api v2
        """
        s = requests.Session()
        s.verify = False  # FIXME: private registries with self-signed certs

        url = get_url(self.full_registry, 'v2', self.repo, 'manifests',
                      self.tag)
        try:
            response = s.get(url, auth=DockerAuth(auth),
                             timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                version = response.headers.get(API_VERSION_HEADER)
                if raise_ and version != 'registry/2.0':
                    raise APIVersionError()
                return None

            if just_check:
                return True

            v2_data = _json_or_none(response)
            try:
                return json.loads(v2_data['history'][0]['v1Compatibility'])
            except (ValueError, KeyError, TypeError):
                pass
        except requests.RequestException:
            pass
        return None

    def _v1_request_image_info(self, auth, just_check=False):
        """Config request via V1 API
        Get info about image from image/json using Docker Registry API v1.

        :param auth: (username, password) or None
        :param just_check: only check image availability, do not extract
            configuration
        :returns: full image info (True if just_check=True) or None
        """
        registry, _, repo, tag = self
        s = requests.Session()
        s.verify = False  # FIXME: private registries with self-signed certs
        try:
            docker_auth_v1(s, registry, repo, auth)
            url = get_url(registry, 'v1/repositories', repo, 'tags', tag)
            response = s.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                image_id = _json_or_none(response)
                if not isinstance(image_id, basestring):
                    return None
                if just_check:
                    return True
                url = get_url(registry, 'v1/images', image_id, 'json')
                # get image info
                response = s.get(url, timeout=REQUEST_TIMEOUT)
                return _json_or_none(response)
        except requests.RequestException:
            pass
        return None

    def _request_image_info(self, auth=None):
        """
        Get info about image from image manifest using Docker Registry API v2
        or from image/json using Docker Registry API v1.

        :param auth: (username, password) or None
        :returns: full image info or None
        """
        return (self._v2_request_image_info(auth)
                or self._v1_request_image_info(auth))

    def _prepare_response(self, image_info, auth=None):
        """Create api response using raw container config from docker registry.

        :param image_info: raw data from docker registry api
            /v1/images/(image_id)/json or analogous from
            /v2/<name>/manifests/<reference> response.history[0].v1Compatibility
        :param auth: (username, password) or None
        :returns: simplified container config
        """
        raw_config = image_info['config']
        if not raw_config.get('Env'):
            raw_config['Env'] = []
        if not raw_config.get('ExposedPorts'):
            raw_config['ExposedPorts'] = []

        config = {
            'image': str(self),
            'sourceUrl': self.source_url,
            'command': ([] if raw_config.get('Entrypoint') is None else
                        raw_config['Entrypoint']),
            'args': [] if raw_config.get('Cmd') is None else raw_config['Cmd'],
            'env': [{'name': key, 'value': value} for key, value in
                    (line.split('=', 1) for line in raw_config['Env'])],
            'ports': [{'number': int(port), 'protocol': proto}
                      for port, proto
                      in (line.split('/', 1)
                          for line
                          in raw_config['ExposedPorts'])],
            'volumeMounts': ([] if raw_config.get('Volumes') is None else
                             raw_config['Volumes'].keys()),
            'workingDir': raw_config['WorkingDir'],
        }
        if auth is not None:
            config['secret'] = {'username': auth[0], 'password': auth[1]}
        return config

    def get_container_config(
            self, auth=None, refresh_cache=False, secrets=None):
        """
        Get container config from cache or registry

        :param auth: authentication data. Accepts None,
            [<username>, <password>], or
            {'username': <username>, <password>: <password>}
        :param refresh_cache: if True, then refresh cache no matter what
            timestamp does it have
        :param secrets: additional list of secrets to use with (or instead of)
            auth; each item must be a (username, password, registry) tuple.
        :return: dict which represents image configuration
        """
        if isinstance(auth, Mapping):
            auth = (auth.get('username'), auth.get('password'))
        additional_auth_set = set()
        if secrets is not None:
            additional_auth_set.update(
                (username, password)
                for username, password, registry in secrets
                if registry == self.full_registry)

        cache_enabled = auth is None and secrets is None
        if cache_enabled:
            cached_config = DockerfileCache.query.get(str(self))
            if not (refresh_cache
                    or cached_config is None
                    or cached_config.outdated):
                return cached_config.data

        # try to get image data using provided auth data
        # (or without auth) first, then using provided secrets
        for auth in chain([auth], additional_auth_set):
            image_info = self._request_image_info(auth)
            if image_info is not None and 'config' in image_info:
                data = self._prepare_response(image_info, auth)
                break
        else:
            check_registry_status(self.full_registry)
            raise APIError('Couldn\'t get the image')

        if cache_enabled:
            if cached_config is None:
                db.session.add(DockerfileCache(image=str(self), data=data,
                                               time_stamp=datetime.utcnow()))
            else:
                cached_config.data = data
                cached_config.time_stamp = datetime.utcnow()
            db.session.commit()
        return data

    def _check_availability(self, registries, fast=True):
        """
        Try to get image from registry.

        :param registries: mapping of registry to dict with bool 'v2_available'
            and list of secrets
        :param fast: if true, do not try to get full image config
        """
        registry = registries[self.full_registry]

        for auth in registry['auth']:
            # For now too many registries don't support
            # Docker Registry v2 API, so we'll try v1 first.
            image_info = self._v1_request_image_info(auth, just_check=fast)
            if image_info and (fast or 'config' in image_info):
                return True if fast else image_info['config']

            if registry['v2_available']:
                # v1 didn't work and v2 is available
                try:
                    image_info = self._v2_request_image_info(
                        auth, just_check=fast, raise_=True)
                    if image_info and (fast or 'config' in image_info):
                        return True if fast else image_info['config']
                except APIVersionError:
                    registry['v2_available'] = False

        check_registry_status(self.full_registry)
        raise ImageNotAvailable(self)

    def get_id(self, secrets=()):
        """
        Get image id from registry.

        :param secrets: list of secrets.
            Each secret must be iterable (username, password, registry)
        :returns: container config or None
        """
        auth_list = [(username, password)
                     for username, password, registry in secrets
                     if complement_registry(registry) == self.full_registry]
        for auth in auth_list + [None]:
            image_info = self._request_image_info(auth)
            if image_info is not None and 'id' in image_info:
                return image_info['id']

    @classmethod
    def check_containers(cls, containers, secrets=()):
        """Check if all images are available using provided credentials.

        Tries to check image availability without credentials and if it failed,
        will try all specified credentials for the registry until successful
        result.

        Also, if container doesn't specify neither CMD nor ENTRYPOINT, check
        that at least one of them is presented in image config.

        :param containers: list of containers
            each must have name and image and may have command and args
        :param secrets: list of secrets
            Each secret must be iterable (username, password, registry)
        :raises APIError: if some image is not available
        """
        registries = defaultdict(lambda: {'v2_available': True,
                                          'auth': [None]})
        for username, password, registry in secrets:
            registry = complement_registry(registry)
            registries[registry]['auth'].append((username, password))

        for container in containers:
            image = cls(container['image'])
            if not (container.get('args') or container.get('command')):
                # need extra check: image must have CMD or ENTRYPOINT
                image_data = image._check_availability(registries, fast=False)
                if not (image_data.get('Cmd') or image_data.get('Entrypoint')):
                    raise CommandIsMissing(image, container['name'])
            else:
                image._check_availability(registries)
