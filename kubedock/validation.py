import re
import socket
import cerberus
import cerberus.errors
from copy import deepcopy
from distutils.util import strtobool
from sqlalchemy import func
import pytz

from .exceptions import APIError
from .predefined_apps.models import PredefinedApp
from .billing.models import Kube, Package, PackageKube
from .users.models import User
from .rbac.models import Role
from .system_settings.models import SystemSettings
from .settings import KUBERDOCK_INTERNAL_USER, AWS, CEPH
from .users.utils import strip_offset_from_timezone


SUPPORTED_VOLUME_TYPES = ['persistentDisk', 'localStorage']


class ValidationError(APIError):
    pass


# Coerce functions


def extbool(value):
    """Bool or string with values ('0', '1', 'true', 'false', 'yes') to bool.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, basestring):
        return bool(strtobool(value))
    raise TypeError('Invalid type. Must be bool or string')


"""
This schemas it's just a shortcut variables for convenience and reusability
"""
# ===================================================================
PATH_LENGTH = 512

container_image_name_schema = {
    'type': 'string',
    'empty': False,
    'required': True,
    'maxlength': 128,
    'regex': {
        'regex': r'^[a-zA-Z0-9_]+[a-zA-Z0-9/:_!.\-]*$',
        'message': 'image URL must be in format [registry/]image[:tag]',
    },
}

image_search_schema = {
    'type': 'string',
    'empty': False,
    'required': True,
    'maxlength': 128,
}

ascii_string = {
    'type': str, 'regex': {
        'regex': re.compile(ur'^[\u0000-\u007f]*$'),  # ascii range
        'message': 'must be an ascii string'}}

image_request_schema = {
    'image': dict(ascii_string, empty=False, required=True),
    'auth': {
        'type': dict,
        'required': False,
        'nullable': True,
        'schema': {
            'username': dict(ascii_string, empty=False, required=True),
            'password': dict(ascii_string, empty=False, required=True)
        },
    },
    'refresh_cache': {'coerce': bool},
}

# http://stackoverflow.com/questions/1418423/the-hostname-regex
hostname_regex = re.compile(
    r"^(?=.{1,255}$)[0-9A-Z](?:(?:[0-9A-Z]|-){0,61}[0-9A-Z])?"
    r"(?:\.[0-9A-Z](?:(?:[0-9A-Z]|-){0,61}[0-9A-Z])?)*\.?$", re.IGNORECASE)
hostname_schema = {
    'type': 'string',
    'empty': False,
    'required': True,
    'maxlength': 255,
    'regex': {
        'regex': hostname_regex,
        'message': 'invalid hostname'
    },
    'resolvable': True,
}


email_local_regex = re.compile(
    r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+"
    r"(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*\Z"  # dot-atom
    r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|'
    r'\\[\001-\011\013\014\016-\177])*"\Z)',  # quoted-string
    re.IGNORECASE)
email_domain_regex = re.compile(
    r'^(?=.{1,255}$)(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+'
    r'(?P<root>[A-Z0-9-]{2,63}(?<![-0-9]))\Z',
    re.IGNORECASE)
email_literal_regex = re.compile(
    # literal form, ipv4 or ipv6 address (SMTP 4.1.3)
    r'\[([A-f0-9:\.]+)\]\Z',
    re.IGNORECASE)

#: Restriction for environment variables names - uppercase letters, underscore,
# digits and must not start with digits.
# Do not compile it, because there is no support to deep copy of compiled
# regexps since 2.6, and this regex is participating in further deepcopy of
# schemas.
envvar_name_regex = {
    'regex': r'^[A-Za-z_]+[A-Za-z0-9_]*',
    'message': 'Latin letters, digits, undescores are expected only. '
               'Must not start with digit'
}

pdname_regex = {
    'regex': r'^[A-Za-z]+[A-Za-z0-9_\-]*',
    'message': 'Latin letters, digits, '
               'undescores and dashes are expected only. '
               'Must start with a letter'
}


# Kubernetes restriction, names must be dns-compatible
# pod_name = r"^(([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9])+$"
pod_name_schema = {
    'type': 'string',
    'empty': False,
    'maxlength': 63,    # kubernetes restriction (was)
    # 'regex': pod_name,
}


port_schema = {
    'type': 'integer',
    'min': 1,
    'max': 65535,
}
nullable_port_schema = deepcopy(port_schema)
nullable_port_schema['nullable'] = True


name_schema = {
    'type': 'string',
    'nullable': True,
    'maxlength': 25,
    'regex': {
        'regex': re.compile(r'^[^\W\d]{,25}$', re.U),
        'message': 'only alphabetic characters allowed'
    }
}

user_schema = {
    'username': {
        'type': 'username',
        'required': True,
        'empty': False,
        'unique_case_insensitive': User.username,
        'maxlength': 50,
        'regex': {
            'regex': re.compile(r'.*\D'),
            'message': 'Usernames containing digits only are forbidden.',
        }
    },
    'email': {
        'type': 'email',
        'required': True,
        'empty': False,
        'unique_case_insensitive': User.email,
        'maxlength': 50.
    },
    'password': {
        'type': 'string',
        'required': True,
        'empty': False,
        'maxlength': 25.
    },
    'first_name': name_schema,
    'last_name': name_schema,
    'middle_initials': name_schema,
    'rolename': {
        'type': 'string',
        'required': True,
        'empty': False,
        'maxlength': 64,
        'role_exists': True,
    },
    'package': {
        'type': 'string',
        'required': True,
        'empty': False,
        'maxlength': 64,
        'package_exists': True,
    },
    'active': {
        'type': 'boolean',
        'required': True,
        'coerce': extbool,
    },
    'suspended': {
        'type': 'boolean',
        'required': False,
        'coerce': extbool,
    },
    'timezone': {
        'type': 'string',
        'required': False,
        'allowed': pytz.common_timezones
    },
    'clientid': {
        'type': 'integer',
        'required': False
    },
}


args_list_schema = {'type': 'list', 'schema': {'type': 'string',
                                               'empty': False}}
env_schema = {'type': 'list', 'schema': {'type': 'dict', 'schema': {
    'name': {
        'type': 'string',
        'required': True,
        'empty': False,
        'maxlength': 255,
        'regex': envvar_name_regex
    },
    'value': {'type': 'string', 'required': True},
}}}
path_schema = {'type': 'string', 'maxlength': PATH_LENGTH}
protocol_schema = {'type': 'string', 'allowed': ['TCP', 'tcp', 'UDP', 'udp']}
kubes_qty_schema = {'type': 'integer', 'min': 1,
                    'max_kubes_per_container': True}
container_name_schema = {'type': 'string', 'empty': False, 'maxlength': 255}
pdsize_schema = {'type': 'integer', 'coerce': int, 'min': 1,
                 'pd_size_max': True}
pdname_schema = {'type': 'string', 'required': True, 'empty': False,
                 'maxlength': 36, 'regex': pdname_regex}
kube_type_schema = {'type': 'integer', 'coerce': int, 'kube_type_in_db': True}
volume_name_schema = {'type': 'string', 'coerce': str, 'empty': False,
                      'maxlength': 255}

update_pod_schema = {
    'command': {'type': 'string', 'allowed': ['start', 'stop', 'redeploy',
                                              'set']},
    'commandOptions': {
        'type': 'dict',
        'schema': {
            'wipeOut': {'type': 'boolean', 'nullable': True},
            'status': {'type': 'string', 'required': False,
                       'allowed': ['unpaid', 'stopped']},
            'name': pod_name_schema,
            'postDescription': {'type': 'string', 'nullable': True},
        }
    },

    # things that user allowed to change during pod's redeploy
    'containers': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'kubes': kubes_qty_schema,
                'name': dict(container_name_schema, required=True),
            }
        }
    }
}

new_pod_schema = {
    'name': dict(pod_name_schema, required=True),
    'podIP': {
        'type': 'ipv4',
        'nullable': True,
        'internal_only': True,
    },
    'replicas': {'type': 'integer', 'min': 0, 'max': 1},
    'kube_type': dict(kube_type_schema, kube_type_in_user_package=True,
                      kube_type_exists=True, required=True),
    'kuberdock_template_id': {
        'type': 'integer',
        'min': 0,
        'nullable': True,
        'template_exists': True,
    },
    'postDescription': {
        'type': 'string',
        'nullable': True,
    },
    'kuberdock_resolve': {'type': 'list', 'schema': {'type': 'string'}},
    'node': {
        'type': 'string',
        'nullable': True,
        'internal_only': True,
    },
    'restartPolicy': {
        'type': 'string', 'required': True,
        'allowed': ['Always', 'OnFailure', 'Never']
    },
    'dnsPolicy': {
        'type': 'string', 'required': False,
        'allowed': ['ClusterFirst', 'Default']
    },
    'status': {
        'type': 'string', 'required': False,
        'allowed': ['stopped', 'unpaid']
    },
    'volumes': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'name': dict(volume_name_schema, volume_type_required=False),
                'persistentDisk': {
                    'type': 'dict',
                    'nullable': True,
                    'pd_backend_required': False,
                    'schema': {
                        'pdName': pdname_schema,
                        'pdSize': pdsize_schema,
                        'used': {
                            'type': 'boolean',
                            'required': False,
                        }
                    }
                },
                'localStorage': {
                    'nullable': True,
                    'anyof': [
                        # {'type': 'boolean'},
                        {
                            'type': 'dict',
                            'schema': {
                                'path': {
                                    'type': 'string',
                                    'required': False,
                                    'nullable': False,
                                    'empty': False,
                                    'maxlength': PATH_LENGTH,
                                    # allowed only for kuberdock-internal
                                    'internal_only': True,
                                }
                            }
                        }
                    ]
                },
                # 'emptyDir': {
                #     'type': 'dict',
                #     'nullable': True
                # },
                # 'scriptableDisk': {
                #     'type': 'dict',
                #     'nullable': True
                # },
                # 'awsElasticBlockStore': {
                #     'type': 'dict',
                #     'nullable': True
                # },
                # 'gitRepo': {
                #     'type': 'dict',
                #     'nullable': True
                # },
                # 'glusterfs': {
                #     'type': 'dict',
                #     'nullable': True
                # },
                # 'iscsi': {
                #     'type': 'dict',
                #     'nullable': True
                # },
                # 'nfs': {
                #     'type': 'dict',
                #     'nullable': True
                # },
                # 'secret': {
                #     'type': 'dict',
                #     'nullable': True
                # },
            },
        }
    },
    'containers': {
        'type': 'list',
        'minlength': 1,
        'required': True,
        'schema': {
            'type': 'dict',
            'schema': {
                'sourceUrl': {'type': 'string', 'required': False},
                'lifecycle': {
                    'type': 'dict',
                    'required': False
                },
                'readinessProbe': {
                    'type': 'dict',
                    'required': False
                },
                'command': args_list_schema,
                'args': args_list_schema,
                'kubes': kubes_qty_schema,
                'image': container_image_name_schema,
                'name': container_name_schema,
                'env': env_schema,
                'ports': {
                    'type': 'list',
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'containerPort': dict(port_schema, required=True),
                            # null if not public
                            'hostPort': dict(port_schema, nullable=True),
                            'isPublic': {'type': 'boolean'},
                            'protocol': protocol_schema,
                        }
                    }
                },
                'volumeMounts': {
                    'type': 'list',
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'mountPath': {
                                'type': 'string',
                                'maxlength': PATH_LENGTH,
                            },
                            'name': {
                                'type': 'string',
                                'has_volume': True,
                            },
                        },
                    }
                },
                'workingDir': path_schema,
                "terminationMessagePath": {
                    'type': 'string',
                    'maxlength': PATH_LENGTH,
                    'nullable': True
                },
                'secret': {
                    'type': 'dict',
                    'nullable': True,
                    'schema': {
                        'username': {'type': 'string', 'nullable': True},
                        'password': {'type': 'string', 'nullable': True},
                    }
                }
            }
        }
    }
}


pd_schema = {
    'name': pdname_schema,
    'size': dict(pdsize_schema, required=True),
}


# billing

positive_float_schema = {'coerce': float, 'min': 0}
positive_integer_schema = {'coerce': int, 'min': 0}
positive_non_zero_integer_schema = {'coerce': int, 'min': 1}
billing_name_schema = {'type': 'string', 'maxlength': 64,
                       'required': True, 'empty': False}

kube_name_schema = {
    'type': 'string',
    'maxlength': 25,
    'required': True,
    'empty': False,
    'regex': {
        'regex': r'^[A-Za-z0-9]+[A-Za-z0-9 ]*$',
        'message': 'Name may contain Latin alphabet letters, digits, spaces '
                   'and should not start with a space'
    }
}

package_schema = {
    'name': billing_name_schema,
    'first_deposit': positive_float_schema,
    'currency': {'type': 'string', 'maxlength': 16, 'empty': False},
    'period': {'type': 'string', 'maxlength': 16, 'empty': False,
               'allowed': ['hour', 'month', 'quarter', 'annual']},
    'prefix': {'type': 'string', 'maxlength': 16},
    'suffix': {'type': 'string', 'maxlength': 16},
    'price_ip': positive_float_schema,
    'price_pstorage': positive_float_schema,
    'price_over_traffic': positive_float_schema,
    'is_default': {'type': 'boolean', 'coerce': extbool, 'required': False},
    'count_type': {'type': 'string', 'maxlength': 5, 'required': False,
                   'allowed': ['payg', 'fixed']},
}

kube_schema = {
    'name': kube_name_schema,
    'cpu': {'coerce': float, 'min': 0.01, 'max': 9.99, 'required': True},
    'memory': {'coerce': int, 'min': 1, 'max': 99999, 'required': True},
    'disk_space': {'coerce': int, 'min': 1, 'max': 999, 'required': True},
    'included_traffic': {
        'coerce': int, 'min': 0, 'max': 99999, 'required': True
    },
    'cpu_units': {'type': 'string', 'maxlength': 32, 'empty': False,
                  'allowed': ['Cores']},
    'memory_units': {'type': 'string', 'maxlength': 3, 'empty': False,
                     'allowed': ['MB']},
    'disk_space_units': {'type': 'string', 'maxlength': 3, 'empty': False,
                         'allowed': ['GB']},
    'is_default': {'type': 'boolean', 'coerce': extbool, 'required': False}
}

packagekube_schema = {
    'kube_price': dict(positive_float_schema, required=True),
    'id': positive_integer_schema
}

cpu_multiplier_schema = {
    'coerce': float, 'min': 1, 'max': 100
}

memory_multiplier_schema = {
    'coerce': float, 'min': 1, 'max': 100
}

app_package_schema = {
    'name': {
        'type': 'string',
        'empty': False,
        'required': True,
        'maxlength': 32,
    },
    'recommended': {
        'type': 'boolean',
        'coerce': extbool,
    },
    'goodFor': {
        'type': 'string',
        'maxlength': 64,
    },
    'publicIP': {
        'type': 'boolean',
        'coerce': extbool,
    },
    'pods': {
        'type': 'list',
        'maxlength': 1,  # we don't support multiple pods in one app yet
        'schema': {
            'type': 'dict',
            'schema': {
                'name': dict(pod_name_schema, required=True),
                'kubeType': kube_type_schema,
                'containers': {
                    'type': 'list',
                    'empty': False,
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'name': container_name_schema,
                            'kubes': kubes_qty_schema,
                        },
                    },
                },
                'persistentDisks': {
                    'type': 'list',
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'name': volume_name_schema,
                            'pdSize': pdsize_schema,
                        },
                    },
                },
            },
        },
    },
}
predefined_apps_kuberdock_schema = {
    'preDescription': {'type': 'string'},
    'postDescription': {'type': 'string'},
    'packageID': {
        'type': 'integer',
        'coerce': int,
        'package_id_exists': True,
    },
    'appPackages': {
        'type': 'list',
        'required': True,
        'empty': False,
        'maxlength': 4,
        'schema': {
            'type': 'dict',
            'schema': app_package_schema,
        },
    }
}
predefined_app_schema = {
    'kuberdock': {
        'type': 'dict',
        'required': True,
        'schema': predefined_apps_kuberdock_schema,
    }
}


node_schema = {'hostname': hostname_schema, 'kube_type': kube_type_schema}


ippool_schema = {
    'network': {'type': 'string'},
    'autoblock': {
        'type': 'string',
        'nullable': True,
        'regex': {
            'regex': re.compile(r'^(?:(?:\s*\d+(?:-\d+)?\s*,)*'
                                r'(?:\s*\d+(?:-\d+)?\s*))?$'),
            'message': 'Exclude IP\'s are expected to be in the form of 5,6,7 '
                       'or 6-134 or both comma-separated',
        },
    },
    'node': {
        'type': 'string',
        'nullable': True,
        # Optional because schema should be the same both when
        # NONFLOATING_PUBLIC_IPS is either True and False.
        'required': False,
    },
}


# ===================================================================


class V(cerberus.Validator):
    """
    This class is for all custom and our app-specific validators and types,
    implement any new here.
    """
    # TODO: add readable error messages for regexps in old schemas
    type_map = {str: 'string',
                int: 'integer',
                float: 'float',
                bool: 'boolean',
                dict: 'dict',
                list: 'list',
                # None: 'string'  # you can use `None` to set the default type
                set: 'set'}

    def __init__(self, *args, **kwargs):
        self.user = kwargs.get('user')
        super(V, self).__init__(*args, **kwargs)

    def validate_schema(self, schema):
        """
        Little hack to allow us to use sandard python types
        (or anything at all) for type validation.
        Just map it to some string in self.type_map
        """
        for value in schema.itervalues():
            vtype = value.get('type')
            if not vtype:
                continue
            if isinstance(vtype, (list, tuple)):
                value['type'] = [
                    self.type_map.get(typeentry, typeentry)
                    for typeentry in vtype
                ]
            else:
                value['type'] = self.type_map.get(vtype, vtype)
        return super(V, self).validate_schema(schema)

    def _api_validation(self, data, schema, **kwargs):
        validated = self.validated(data, schema, **kwargs)
        if validated is None:
            raise ValidationError(self.errors)
        return validated

    def _validate_regex(self, re_obj, field, value):
        """
        The same as original Validator._validate_regex, but can accept
        pre-compiled regex as a parameter or a regex-object:
        {'regex': <pattern or compiled regex>,
        'message': <custom error message>}

        Examples:

        'regex': r'^[A-Za-z]*$'
        'regex': re.compile(r'^[A-Z]*$', re.IGNORECASE)
        'regex': {'regex': r'^[A-Za-z]*$',
                  'message': 'should contain letters of Latin alphabet only'}
        'regex': {'regex': re.compile(r'^[A-Z]*$', re.IGNORECASE),
                  'message': 'should contain letters of Latin alphabet only'}
        """
        if not isinstance(value, basestring):
            return

        message = u'value "{value}" does not match regex "{regex}"'
        if isinstance(re_obj, dict):
            message = re_obj['message'].decode('utf-8')
            re_obj = re_obj['regex']

        if isinstance(re_obj, basestring):
            re_obj = re.compile(re_obj)

        if not re_obj.match(value):
            self._error(field, message.format(value=value,
                                              regex=re_obj.pattern))

    def _validate_type_email(self, field, value):
        super(V, self)._validate_type_string(field, value)

        if not value or '@' not in value:
            self._error(field, 'invalid email address (there is no @ in it)')
            return

        user_part, domain_part = value.rsplit('@', 1)

        if not email_local_regex.match(user_part):
            self._error(field, 'invalid email address (local part)')

        try:
            domain_part = domain_part.encode('idna')
        except (TypeError, UnicodeError):
            self._error(field, 'invalid email address (domain part)')

        if domain_part.endswith('.web'):
            self._error(field, 'invalid email address (domain part)')

        if email_domain_regex.match(domain_part):
            return

        literal_match = email_literal_regex.match(domain_part)
        if literal_match:
            ip_address = literal_match.group(1)
            try:
                socket.inet_pton(socket.AF_INET, ip_address)
                return
            except socket.error:
                pass
        self._error(field, 'invalid email address (domain part)')

    def _validate_internal_only(self, internal_only, field, value):
        if internal_only and self.user != KUBERDOCK_INTERNAL_USER:
            self._error(field, 'not allowed')

    def _validate_template_exists(self, exists, field, value):
        if exists:
            if value is None:
                return
            templ = PredefinedApp.query.get(value)
            if not templ:
                self._error(field,
                            'There is no template with such template_id')

    def _validate_kube_type_exists(self, exists, field, value):
        if exists:
            kube = Kube.query.get(value)
            if kube is None:
                self._error(field, 'Pod can\'t be created, because cluster has '
                                   'no kube type with id "{0}", please contact '
                                   'administrator.'.format(value))
            elif not kube.available:
                self._error(field, 'Pod can\'t be created, because cluster has '
                                   'no nodes with "{0}" kube type, please '
                                   'contact administrator.'.format(kube.name))

    def _validate_kube_type_in_user_package(self, exists, field, value):
        if exists and self.user:
            if self.user == KUBERDOCK_INTERNAL_USER and \
                    value == Kube.get_internal_service_kube_type():
                return
            package = User.get(self.user).package
            if value not in [k.kube_id for k in package.kubes]:
                self._error(field,
                            "Pod can't be created, because your package "
                            "\"{0}\" does not include kube type with id "
                            "\"{1}\"".format(package.name, value))

    def _validate_kube_type_in_db(self, exists, field, value):
        if exists:
            kube = Kube.query.get(value)
            if not kube:
                self._error(field, 'No such kube_type: "{0}"'.format(value))
            elif not kube.is_public() and self.user != KUBERDOCK_INTERNAL_USER:
                self._error(field, 'Forbidden kube type: "{0}"'.format(value))

    def _validate_pd_backend_required(self, pd_backend_required, field, value):
        if pd_backend_required and not (AWS or CEPH):
            self._error(field, 'persistent storage backend wasn\'t configured')

    def _validate_type_ipv4(self, field, value):
        try:
            socket.inet_pton(socket.AF_INET, value)
        except socket.error:
            self._error(field, 'Invalid ipv4 address')

    def _validate_type_strnum(self, field, value):
        try:
            float(value)
        except ValueError:
            self._error(field, '{0} should be string or number'.format(field))

    def _validate_resolvable(self, resolvable, field, value):
        if resolvable:
            try:
                socket.gethostbyname(value)
            except socket.error:
                self._error(field,
                            "Can't be resolved. "
                            "Check /etc/hosts file for correct Node records")

    def _validate_has_volume(self, has_volume, field, value):
        # Used in volumeMounts
        if has_volume:
            if not self.document.get('volumes'):
                self._error(field,
                            'Volume is needed, but no volumes are described')
                return
            vol_names = [v.get('name', '') for v in self.document['volumes']]
            if value not in vol_names:
                self._error(
                    field,
                    'Volume "{0}" is not defined in volumes list'.format(
                        value))

    def _validate_volume_type_required(self, vtr, field, value):
        # Used in volumes list
        if vtr:
            for vol in self.document['volumes']:
                if vol.keys() == ['name']:
                    self._error(field, 'Volume type is required for volume '
                                       '"{0}"'.format(value))
                    return
                for k in vol.keys():
                    if k not in SUPPORTED_VOLUME_TYPES + ['name']:
                        self._error(field,
                                    'Unsupported volume type "{0}"'.format(k))

    def _validate_pd_size_max(self, exists, field, value):
        if exists:
            max_size = SystemSettings.get_by_name('persitent_disk_max_size')
            if max_size and int(value) > int(max_size):
                self._error(field, (
                    'Persistent disk size must be less or equal '
                    'to "{0}" GB').format(max_size))

    def _validate_max_kubes_per_container(self, exists, field, value):
        if exists:
            max_size = SystemSettings.get_by_name('max_kubes_per_container')
            if max_size and int(value) > int(max_size):
                self._error(field, (
                    'Container cannot have more than {0} kubes.'.format(
                        max_size)))

    def _validate_package_exists(self, exists, field, value):
        if exists:
            if Package.by_name(value) is None:
                self._error(field, "Package doesn't exist")

    def _validate_package_id_exists(self, exists, field, value):
        if exists:
            if Package.query.get(int(value)) is None:
                self._error(field, 'Package with id "{0}" doesn\'t exist'.format(value))


def check_int_id(id):
    try:
        int(id)
    except ValueError:
        raise APIError('Invalid id')


def check_image_search(searchkey):
    validator = V()
    if not validator.validate(
            {'searchkey': searchkey},
            {'searchkey': image_search_schema}):
        raise ValidationError(validator.errors['searchkey'])


def check_image_request(params):
    V()._api_validation(params, image_request_schema)


def check_node_data(data):
    V(allow_unknown=True)._api_validation(data, node_schema)
    if is_ip(data['hostname']):
        raise ValidationError('Please add nodes by hostname, not by ip')


def is_ip(addr):
    try:
        socket.inet_pton(socket.AF_INET, addr)
    except socket.error:
        return False
    else:
        return True


def check_hostname(hostname):
    validator = V()
    if not validator.validate({'Hostname': hostname},
                              {'Hostname': hostname_schema}):
        raise APIError(validator.errors)
    if is_ip(hostname):
        raise APIError('Please, enter hostname, not ip address.')


def check_change_pod_data(data):
    data = V(allow_unknown=True)._api_validation(data, update_pod_schema)
    # TODO: with cerberus 0.10, just use "purge_unknown" option
    return {'command': data.get('command'),
            'commandOptions': data.get('commandOptions') or {},
            'containers': [{'name': c.get('name'), 'kubes': c.get('kubes')}
                           for c in data.get('containers') or []]}


def check_new_pod_data(data, user=None):
    validator = V(user=None if user is None else user.username)
    if not validator.validate(data, new_pod_schema):
        raise APIError(validator.errors)


def check_internal_pod_data(data, user=None):
    validator = V(user=None if user is None else user.username)
    if not validator.validate(data, new_pod_schema):
        raise APIError(validator.errors)
    kube_type = data.get('kube_type', Kube.get_default_kube_type())
    if Kube.get_internal_service_kube_type() != kube_type:
        raise APIError('Internal pod must be of type {0}'.format(
            Kube.get_internal_service_kube_type()))


def check_system_settings(data):
    validator = V()
    name = data.get('name', '')
    value = data.get('value', '')

    # Purely cosmetic issue: forbid leading '+'
    if name in ['persitent_disk_max_size', 'cpu_multiplier',
                'memory_multiplier', 'max_kubes_per_container']:
        if not re.match(r'[0-9]', value):
            fmt = 'Value for "{0}" is expected to start with digits'
            raise APIError(fmt.format(' '.join(name.split('_')).capitalize(),))

    if name in ['persitent_disk_max_size', 'max_kubes_per_container']:
        if not validator.validate({'value': value},
                                  {'value': positive_non_zero_integer_schema}):
            fmt = 'Incorrect value for "{0}" limit'
            raise APIError(fmt.format(' '.join(name.split('_')).capitalize(),))
    elif name == 'cpu_multiplier':
        if not validator.validate({'value': value},
                                  {'value': cpu_multiplier_schema}):
            raise APIError('Incorrect value for CPU multiplier')
    elif name == 'memory_multiplier':
        if not validator.validate({'value': value},
                                  {'value': memory_multiplier_schema}):
            raise APIError('Incorrect value for Memory multiplier')


class UserValidator(V):
    """Validator for user api"""

    username_regex = {
        'regex': re.compile(r'^[A-Z0-9](?:[A-Z0-9_-]{0,23}[A-Z0-9])?$',
                            re.IGNORECASE),
        'message': 'Username should contain only Latin letters and '
                   'Numbers and must not be more than 25 characters in length'
    }

    def __init__(self, *args, **kwargs):
        self.id = kwargs.get('id')
        super(UserValidator, self).__init__(*args, **kwargs)

    def _validate_unique_case_insensitive(self, model_field, field, value):
        model = model_field.class_

        taken_query = model.query.filter(
            func.lower(model_field) == func.lower(value)
        )
        if self.id is not None:  # in case of update
            taken_query = taken_query.filter(model.id != self.id)
        if taken_query.first() is not None:
            self._error(field, 'has already been taken')

    def _validate_role_exists(self, exists, field, value):
        if exists:
            if Role.by_rolename(value) is None:
                self._error(field, "Role doesn't exists")

    def validate_user(self, data, update=False):
        data = _clear_timezone(data, ['timezone'])
        data = self._api_validation(data, user_schema, update=update)
        # TODO: with cerberus 0.10, just use "purge_unknown" option
        data = {key: value for key, value in data.iteritems()
                if key in user_schema}
        return data

    def _validate_type_username(self, field, value):
        """Validates username by username_regex and email validator"""
        if self.username_regex['regex'].match(value):
            return

        super(UserValidator, self)._validate_type_email(field, value)

        if 'username' in self.errors:
            self._error(field, self.username_regex['message'])


def _clear_timezone(data, keys):
    """Clears timezone fields - removes UTC offset from timezone string:
    Europe/London (+000) -> Europe/London
    """
    if not data:
        return data
    for key in keys:
        if key in data:
            data[key] = strip_offset_from_timezone(data[key])
    return data


def check_pricing_api(data, schema, *args, **kwargs):
    validated = V(allow_unknown=True)._api_validation(data, schema,
                                                      *args, **kwargs)
    # purge unknown
    data = {field: value for field, value in validated.iteritems()
            if field in schema}
    return data
