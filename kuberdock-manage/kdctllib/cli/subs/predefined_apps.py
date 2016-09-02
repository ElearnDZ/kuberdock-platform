from functools import wraps

from .. import kdclick
from ..kdclick.access import ADMIN
from ..utils import SimpleCommand, SimpleCommandWithIdNameArgs


@kdclick.group('predefined-apps',
               help='Commands for predefined applications management.',
               available_for=ADMIN)
@kdclick.pass_obj
def pa(obj):
    obj.executor = obj.kdctl.predefined_apps


def id_decorator(fn):
    @kdclick.option('--id', help='Id of required predefined application')
    @kdclick.option('--name', help='Use it to specify name instead of id')
    @kdclick.required_exactly_one_of('id', 'name')
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


@pa.command()
@kdclick.option('--file-only', is_flag=True)
@kdclick.pass_obj
class List(SimpleCommand):
    pass


@pa.command()
@id_decorator
@kdclick.option('--file-only', is_flag=True)
@kdclick.pass_obj
class Get(SimpleCommandWithIdNameArgs):
    pass


@pa.command()
@kdclick.data_argument('template', type=kdclick.types.text)
@kdclick.option('--name', required=True, help='Application name.')
@kdclick.option('--origin', required=False, help='Origin of application.')
@kdclick.option('--validate', is_flag=True,
                help='Provide if validation is needed.')
@kdclick.pass_obj
class Create(SimpleCommand):
    pass


@pa.command()
@id_decorator
@kdclick.data_argument('template', type=kdclick.types.text)
@kdclick.option('--validate', is_flag=True,
                help='Provide if validation is needed.')
@kdclick.pass_obj
class Update(SimpleCommandWithIdNameArgs):
    pass


@pa.command()
@id_decorator
@kdclick.pass_obj
class Delete(SimpleCommandWithIdNameArgs):
    pass


@pa.command('validate-template')
@kdclick.data_argument('template', type=kdclick.types.text)
@kdclick.pass_obj
class ValidateTemplate(SimpleCommand):
    corresponding_method = 'validate_template'
