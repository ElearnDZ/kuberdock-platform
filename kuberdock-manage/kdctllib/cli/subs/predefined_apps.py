
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

from functools import wraps

from .. import kdclick
from ..kdclick.access import ADMIN, USER
from ..utils import SimpleCommand, SimpleCommandWithIdNameArgs


@kdclick.group('predefined-apps', available_for=(ADMIN, USER))
@kdclick.pass_obj
def pa(obj):
    """Commands for predefined applications management"""
    obj.executor = obj.kdctl.predefined_apps


def id_decorator(fn):
    @kdclick.option('--id', help='Id of required predefined application')
    @kdclick.option('--name', help='Use it to specify name instead of id')
    @kdclick.required_exactly_one_of('id', 'name')
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


@pa.command(available_for=(ADMIN, USER))
@kdclick.option('--file-only', is_flag=True)
@kdclick.pass_obj
class List(SimpleCommand):
    """List existing predefined applications"""
    pass


@pa.command(available_for=(ADMIN, USER))
@id_decorator
@kdclick.option('--file-only', is_flag=True)
@kdclick.pass_obj
class Get(SimpleCommandWithIdNameArgs):
    """Get existing predefined application"""
    pass


@pa.command(available_for=ADMIN)
@kdclick.data_argument('template', type=kdclick.types.text)
@kdclick.option('--name', required=True, help='Application name.')
@kdclick.option('--origin', required=False, help='Origin of application.')
@kdclick.option('--validate', is_flag=True,
                help='Provide if validation is needed.')
@kdclick.pass_obj
class Create(SimpleCommand):
    """Create new predefined application"""
    pass


@pa.command(available_for=ADMIN)
@id_decorator
@kdclick.data_argument('template', type=kdclick.types.text)
@kdclick.option('--validate', is_flag=True,
                help='Provide if validation is needed.')
@kdclick.pass_obj
class Update(SimpleCommandWithIdNameArgs):
    """Update existing predefined application"""
    pass


@pa.command(available_for=ADMIN)
@id_decorator
@kdclick.pass_obj
class Delete(SimpleCommandWithIdNameArgs):
    """Delete existing predefined application"""
    pass


@pa.command('validate-template', available_for=ADMIN)
@kdclick.data_argument('template', type=kdclick.types.text)
@kdclick.pass_obj
class ValidateTemplate(SimpleCommand):
    """Validate template of predefined application"""
    corresponding_method = 'validate_template'


@pa.command('create-pod', available_for=ADMIN)
@kdclick.argument('template-id')
@kdclick.argument('plan-id')
@kdclick.data_argument('data')
@kdclick.option('--owner')
@kdclick.pass_obj
class CreatePod(SimpleCommand):
    """Create pod from template"""
    corresponding_method = 'create_pod'


@pa.command('create-pod', available_for=USER)
@kdclick.argument('template-id')
@kdclick.argument('plan-id')
@kdclick.data_argument('data')
@kdclick.pass_obj
class CreatePod(SimpleCommand):
    """Create pod from template"""
    corresponding_method = 'create_pod'
