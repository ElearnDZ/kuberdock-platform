from kubedock.core import db
from .models import Resource, Role, Permission


ROLES = (
    # rolename, is_internal
    ("Admin", False),
    ("User", False),
    ("LimitedUser", False),
    ("TrialUser", False),
)

resources = {
    'users': ('create', 'get', 'edit', 'delete', 'auth_by_another'),
    'nodes': ('create', 'get', 'edit', 'delete', 'redeploy'),
    'pods': ('create', 'get', 'edit', 'delete'),
    'yaml_pods': ('create',),
    'ippool': ('create', 'get', 'edit', 'delete', 'view'),
    'notifications': ('create', 'get', 'edit', 'delete'),
    'system_settings': ('read', 'read_private', 'write', 'delete'),
    'images': ('get', 'isalive'),
    'predefined_apps': ('create', 'get', 'edit', 'delete'),
    'pricing': ('create', 'get', 'edit', 'delete', 'get_own'),
    'timezone': ('get',),
}

permissions_base = {
    (resource, action): False
    for resource, actions in resources.iteritems() for action in actions
}
permissions = {
    'Admin': dict(permissions_base, **{
        ('users', 'create'): True,
        ('users', 'get'): True,
        ('users', 'edit'): True,
        ('users', 'delete'): True,
        ('users', 'auth_by_another'): True,
        ('nodes', 'create'): True,
        ('nodes', 'get'): True,
        ('nodes', 'edit'): True,
        ('nodes', 'delete'): True,
        ('nodes', 'redeploy'): True,
        ('ippool', 'create'): True,
        ('ippool', 'get'): True,
        ('ippool', 'edit'): True,
        ('ippool', 'delete'): True,
        ('ippool', 'view'): True,
        ('notifications', 'create'): True,
        ('notifications', 'get'): True,
        ('notifications', 'edit'): True,
        ('notifications', 'delete'): True,
        ('system_settings', 'read'): True,
        ('system_settings', 'read_private'): True,
        ('system_settings', 'write'): True,
        ('system_settings', 'delete'): True,
        ('images', 'get'): True,
        ('images', 'isalive'): True,
        ('predefined_apps', 'create'): True,
        ('predefined_apps', 'get'): True,
        ('predefined_apps', 'edit'): True,
        ('predefined_apps', 'delete'): True,
        ('pricing', 'get'): True,  # packages, kube types
        ('pricing', 'get_own'): True,
        ('pricing', 'edit'): True,
        ('pricing', 'create'): True,
        ('pricing', 'delete'): True,
        ('timezone', 'get'): True,
    }),
    'User': dict(permissions_base, **{
        ('pods', 'create'): True,
        ('pods', 'get'): True,
        ('pods', 'edit'): True,
        ('pods', 'delete'): True,
        ('yaml_pods', 'create'): True,
        ('system_settings', 'read'): True,
        ('images', 'get'): True,
        ('images', 'isalive'): True,
        ('pricing', 'get_own'): True,  # packages, kube types
        ('timezone', 'get'): True,
    }),
}
permissions['LimitedUser'] = dict(permissions['User'], **{
    ('pods', 'create'): False,
})
permissions['TrialUser'] = dict(permissions['User'], **{
    # ...
})

RESOURCES = resources.keys()
PERMISSIONS = [
    (resource, role, action, allowed)
    for role, perms in permissions.iteritems()
    for (resource, action), allowed in perms.iteritems()
]


def add_roles(roles=()):
    for r in roles:
        if not Role.filter(Role.rolename == r[0]).first():
            role = Role.create(rolename=r[0], internal=r[1])
            role.save()


def delete_roles(roles=()):
    """ Delete roles with its permissions
    """
    for role_name in roles:
        role = Role.filter(Role.rolename == role_name).first()
        if role:
            Permission.filter(Permission.role == role).delete()
            db.session.commit()
            role.delete()


def add_resources(resources=()):
    for res in resources:
        if not Resource.filter(Resource.name == res).first():
            resource = Resource.create(name=res)
            resource.save()


def delete_resources(resources=()):
    """ Delete resources with its permissions
    """
    for resource_name in resources:
        resource = Resource.filter(Resource.name == resource_name).first()
        if resource:
            Permission.filter(Permission.resource == resource).delete()
            db.session.commit()
            resource.delete()


def _add_permissions(permissions=()):
    for res, role, perm, allow in permissions:
        resource = Resource.query.filter_by(name=res).first()
        role = Role.query.filter_by(rolename=role).first()
        if role and resource:
            exist = Permission.filter(Permission.role == role). \
                filter(Permission.resource == resource). \
                filter(Permission.allow == allow). \
                filter(Permission.name == perm).first()
            if not exist:
                permission = Permission.create(
                    resource_id=resource.id,
                    role_id=role.id, name=perm, allow=allow)
                permission.save()


def add_permissions(roles=None, resources=None, permissions=None):
    if not roles:
        roles = ROLES
    if not resources:
        resources = RESOURCES
    if not permissions:
        permissions = PERMISSIONS
    add_roles(roles)
    add_resources(resources)
    _add_permissions(permissions)


if __name__ == '__main__':
    add_permissions()
