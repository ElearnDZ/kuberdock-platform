from .. import kdclick
from ..kdclick.access import ADMIN, USER
from ..utils import SimpleCommand


@kdclick.group(available_for=(ADMIN, USER))
@kdclick.pass_obj
def images(obj):
    """Commands for docker images management"""
    obj.executor = obj.kdctl.images


@images.command()
@kdclick.argument('search-key')
@kdclick.option('-p', '--page', type=int, help='Page to display')
@kdclick.option('-R', '--REGISTRY', type=int,
                help='Registry to search in. By default dockerhub is used')
@kdclick.pass_obj
class Search(SimpleCommand):
    """Search image by search key"""
    pass
