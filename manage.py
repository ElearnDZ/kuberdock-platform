import os
import sys
import pytz
import logging
import string
import time
from random import choice
from datetime import datetime
import uuid
import json
import subprocess

from kubedock.api import create_app
from kubedock.kapi.nodes import create_node
from kubedock.validation import check_node_data
from kubedock.utils import APIError, UPDATE_STATUSES
from kubedock.core import db
from kubedock.models import User, Pod
from kubedock.billing.models import Package, Kube, PackageKube
from kubedock.rbac.fixtures import add_permissions
from kubedock.rbac.models import Role
from kubedock.system_settings.fixtures import add_system_settings
from kubedock.notifications.models import Notification
from kubedock.static_pages.fixtures import generate_menu
from kubedock.settings import (
    KUBERDOCK_INTERNAL_USER, NODE_CEPH_AWARE_KUBERDOCK_LABEL)
from kubedock.updates.models import Updates
from kubedock.nodes.models import Node, NodeFlag, NodeFlagNames
from kubedock.updates.kuberdock_upgrade import get_available_updates
from kubedock.updates.helpers import get_maintenance
from kubedock import tasks
from kubedock.kapi import licensing
from kubedock.kapi.pstorage import check_namespace_exists
from kubedock.kapi import ippool
from kubedock.kapi.node_utils import get_one_node

from flask.ext.script import Manager, Shell, Command, Option, prompt_pass
from flask.ext.script.commands import InvalidCommand
from flask.ext.migrate import Migrate, MigrateCommand, upgrade, stamp
from flask.ext.migrate import migrate as migrate_func

from sqlalchemy.orm.exc import NoResultFound

logging.getLogger("requests").setLevel(logging.WARNING)

WAIT_TIMEOUT = 1200  # seconds
WAIT_RETRY_DELAY = 5


class Creator(Command):
    option_list = (Option('password'),)

    def run(self, password):
        db.drop_all()
        db.create_all()

        # WARNING:
        # if you edit this method, make analogous changes in
        # kubedock.testutils.fixtures.initial_fixtures
        # TODO: merge two methods in one

        now = datetime.utcnow()
        now.replace(tzinfo=pytz.utc)
        available_updates = get_available_updates()
        if available_updates:
            last_upd = Updates.create(fname=available_updates[-1],
                                      status=UPDATE_STATUSES.applied,
                                      log='Applied at createdb stage.',
                                      start_time=now, end_time=now)
            db.session.add(last_upd)
        db.session.commit()

        # Create default packages and kubes
        # Package and Kube with id=0 are default
        # and must be undeletable (always present with id=0) for fallback
        k_internal = Kube(id=Kube.get_internal_service_kube_type(),
                          name='Internal service', cpu=.02, cpu_units='Cores',
                          memory=64, memory_units='MB', disk_space=1,
                          disk_space_units='GB', included_traffic=0)
        k1 = Kube(id=Kube.get_default_kube_type(),
                  name='Small', cpu=.05, cpu_units='Cores',
                  memory=16, memory_units='MB', disk_space=1,
                  disk_space_units='GB', included_traffic=0,
                  is_default=True)
        k2 = Kube(name='Standard', cpu=.25, cpu_units='Cores',
                  memory=64, memory_units='MB', disk_space=1,
                  disk_space_units='GB', included_traffic=0)
        k3 = Kube(name='High memory', cpu=.5, cpu_units='Cores',
                  memory=256, memory_units='MB', disk_space=2,
                  disk_space_units='GB', included_traffic=0)

        p1 = Package(id=0, name='Standard package', first_deposit=0,
                     currency='USD', period='month', prefix='$',
                     suffix=' USD', is_default=True)
        db.session.add(k_internal)
        PackageKube(package=p1, kube=k1, kube_price=0)
        PackageKube(package=p1, kube=k2, kube_price=0)
        PackageKube(package=p1, kube=k3, kube_price=0)

        add_system_settings()

        m1 = Notification(type='warning',
                          message='LICENSE_EXPIRED',
                          description='Your license has been expired.')
        m2 = Notification(type='warning',
                          message='NO_LICENSE',
                          description='License not found.')
        m3 = Notification(type='info',
                          message='CLN_NOTIFICATION',
                          description='')
        db.session.add_all([m1, m2, m3])

        db.session.commit()

        add_permissions()

        # Create all roles with users that has same name and password as role_name.
        # Useful to test permissions.
        # Delete all users from setup KuberDock. Only admin must be after install.
        # AC-228
        # for role in Role.all():
        #     u = User.filter_by(username=role.rolename).first()
        #     if u is None:
        #         u = User.create(username=role.rolename, password=role.rolename,
        #                         role=role, package=p, active=True)
        #         db.session.add(u)
        # db.session.commit()

        # Special user for convenience to type and login
        r = Role.filter_by(rolename='Admin').first()
        u = User.filter_by(username='admin').first()
        if u is None:
            u = User.create(username='admin', password=password, role=r, package=p1,
                            active=True)
            db.session.add(u)
        kr = Role.filter_by(rolename='User').first()
        ku = User.filter_by(username=KUBERDOCK_INTERNAL_USER).first()
        ku_passwd = uuid.uuid4().hex
        if ku is None:
            ku = User.create(username=KUBERDOCK_INTERNAL_USER,
                             password=ku_passwd, role=kr,
                             package=p1, first_name='KuberDock Internal',
                             active=True)
            # generate token immediately, to use it in node creation
            ku.get_token()
            db.session.add(ku)
        db.session.commit()

        generate_menu()

        # Fix packages id next val
        db.engine.execute("SELECT setval('packages_id_seq', 1, false)")

        stamp()


class Updater(Command):
    def run(self):
        migrate_func()
        upgrade()


class WaitTimeoutException(Exception):
    pass


class WaitTroubleException(Exception):
    pass


def wait_for_nodes(nodes_list, timeout):
    _timeout = time.time() + (timeout or WAIT_TIMEOUT)
    host_list = set(nodes_list)

    while host_list:
        if time.time() > _timeout:
            raise WaitTimeoutException()

        time.sleep(WAIT_RETRY_DELAY)

        for node_host in nodes_list:
            node = Node.get_by_name(node_host)
            status = get_one_node(node.id)['status']
            if status == 'troubles':
                raise WaitTroubleException()
            elif status == 'running':
                host_list.remove(node_host)


class NodeManager(Command):
    option_list = (
        Option('--hostname', dest='hostname', required=True),
        Option('--kube-type', dest='kube_type', type=int, required=True),
        Option('--do-deploy', dest='do_deploy', action='store_true'),
        Option('--wait', dest='wait', action='store_true'),
        Option('--timeout', dest='timeout', required=False, type=int),
        Option('-t', '--testing', dest='testing', action='store_true'),
    )

    def run(self, hostname, kube_type, do_deploy, wait, timeout, testing):
        if get_maintenance():
            raise InvalidCommand(
                'Kuberdock is in maintenance mode. Operation canceled'
            )
        try:
            check_node_data({'hostname': hostname, 'kube_type': kube_type})
            res = create_node(None, hostname, kube_type, do_deploy, testing)
        except APIError as e:
            print e.message
        except Exception as e:
            print e
        else:
            print res.to_dict()
            if wait:
                wait_for_nodes([hostname, ], timeout)


class WaitForNodes(Command):
    """Wait for nodes to become ready.
    """
    option_list = (
        Option('--nodes', dest='nodes', required=True),
        Option('--timeout', dest='timeout', required=False, type=int),
    )

    def run(self, nodes, timeout):
        nodes_list = nodes.split(',')
        wait_for_nodes(nodes_list, timeout)


def generate_new_pass():
    return ''.join(choice(string.digits + string.letters) for _ in range(10))


class ResetPass(Command):

    chars = string.digits + string.letters
    option_list = (
        Option('--generate', dest='generate', default=False,
               action='store_true'),
        Option('--set', dest='new_password', required=False),
    )

    def run(self, generate, new_password):
        print "Change password for admin."
        u = db.session.query(User).filter(User.username == 'admin').first()
        new_pass = None
        if generate:
            new_pass = generate_new_pass()
            print "New password: {}".format(new_pass)
        elif new_password:
            new_pass = new_password
        else:
            for i in range(3):
                first_attempt = prompt_pass("Enter new password")
                second_attempt = prompt_pass("Retype new password")
                if first_attempt == second_attempt:
                    new_pass = first_attempt
                    break
                print "Sorry, passwords do not match."
        if new_pass:
            u.password = new_pass
            db.session.commit()
            print "Password has been changed"


class NodeFlagCmd(Command):
    """Manage flags for a node"""
    option_list = (
        Option('-n', '--nodename', dest='nodename', required=True,
               help='Node host name'),
        Option('-f', '--flagname', dest='flagname', required=True,
               help='Flag name to change'),
        Option('--value', dest='value', required=False,
               help='Flag value to set'),
        Option('--delete', dest='delete', required=False, default=False,
               action='store_true', help='Delete the flag'),
    )

    def run(self, nodename, flagname, value, delete):
        node = Node.get_by_name(nodename)
        if not node:
            raise InvalidCommand(u'Node "{0}" not found'.format(nodename))
        if delete:
            NodeFlag.delete_by_name(node.id, flagname)
            print u'Node flag "{0}" was deleted'.format(flagname)
            return
        NodeFlag.save_flag(node.id, flagname, value)
        if flagname == NodeFlagNames.CEPH_INSTALLED:
            tasks.add_k8s_node_labels(
                node.hostname,
                {NODE_CEPH_AWARE_KUBERDOCK_LABEL: "True"}
            )
            check_namespace_exists(node.ip)
        print u'Node "{0}": flag "{1}" was set to "{2}"'.format(
            nodename, flagname, value)


class NodeInfoCmd(Command):
    """Manage flags for a node"""
    option_list = (
        Option('-n', '--nodename', dest='nodename', required=True,
               help='Node host name'),
    )

    def run(self, nodename):
        node = Node.get_by_name(nodename)
        if not node:
            raise InvalidCommand(u'Node "{0}" not found'.format(nodename))
        print json.dumps(node.to_dict())


class AuthKey(Command):
    """Returns auth key. Generates it if not created yet"""

    def run(self):
        try:
            key = licensing.get_auth_key()
        except APIError:
            key = licensing.generate_auth_key()
            subprocess.call(['chown', 'nginx', licensing.LICENSE_PATH])
        print key


class CreateIPPool(Command):
    """ Creates IP pool
    """
    option_list = (
        Option('-s', '--subnet', dest='subnet', required=True,
               help='Network with mask'),
        Option('-e', '--exclude', dest='exclude', required=False,
               help='Excluded ips'),
    )

    def run(self, subnet, exclude):
        ippool.IpAddrPool().create({
            'network': subnet.decode(),
            'autoblock': exclude
        })


class CreateUser(Command):
    """ Creates a new user
    """

    option_list = (
        Option('-u', '--username', dest='username', required=True,
               help='User name'),
        Option('-p', '--password', dest='password', required=False,
               help='User password'),
        Option('-r', '--rolename', dest='rolename', required=True,
               help='User role name'),
    )

    def run(self, username, password, rolename):
        try:
            role = Role.filter_by(rolename=rolename).one()
        except NoResultFound:
            raise InvalidCommand('Role with name `%s` not found' % rolename)

        if User.filter_by(username=username).first():
            raise InvalidCommand('User `%s` already exists' % username)

        if not password:
            password = generate_new_pass()
            print "New password: {}".format(new_pass)

        u = User.create(username=username, password=password, role=role,
                        active=True, package_id=0)
        db.session.add(u)
        db.session.commit()


class AddPredefinedApp(Command):
    """Adds a predefined app
    """

    option_list = (
        Option('-n', '--name', dest='name', required=True,
               help="Predefined app's name"),
        Option('-t', '--template', dest='template', required=True,
               help="Predefined app's template"),
        Option('-u', '--user', dest='username', required=False,
               help='User name'),
        Option('-o', '--origin', dest='origin', required=False,
               help='Origin'),
        Option('-f', '--no-validation', dest='no_validation',
               action='store_true'),
    )

    def run(self, name, template, username, origin, no_validation):
        from kubedock.kapi.predefined_apps import PredefinedApps

        if username is None:
            role = Role.filter_by(rolename='Admin').first()
            user = User.filter_by(role=role).first()
            if not user:
                raise InvalidCommand('No username was specified, so user with '
                                     'Admin role was searched but not found.')
        else:
            user = User.filter_by(username=username).first()
            if not user:
                raise InvalidCommand('User with `{0}` username not '
                                     'found'.format(username))

        try:
            with open(template, 'r') as tf:
                template_data = tf.read()
        except IOError as err:
            raise InvalidCommand("Can not load template: %s" % err)

        result = PredefinedApps(user).create(
            name=name,
            template=template_data,
            origin=origin or 'kuberdock',
            validate=not no_validation
        )
        print(result)

app = create_app(fake_sessions=True)
manager = Manager(app, with_default_commands=False)
directory = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                         'kubedock',
                         'updates',
                         'kdmigrations')
migrate = Migrate(app, db, directory)


def make_shell_context():
    return dict(app=app, db=db, User=User, Pod=Pod, Package=Package, Kube=Kube)

manager.add_command('shell', Shell(make_context=make_shell_context))
manager.add_command('db', MigrateCommand)
manager.add_command('createdb', Creator())
manager.add_command('updatedb', Updater())
manager.add_command('add_node', NodeManager())
manager.add_command('wait-for-nodes', WaitForNodes())
manager.add_command('reset-password', ResetPass())
manager.add_command('node-flag', NodeFlagCmd())
manager.add_command('node-info', NodeInfoCmd())
manager.add_command('auth-key', AuthKey())
manager.add_command('create-ip-pool', CreateIPPool())
manager.add_command('create-user', CreateUser())
manager.add_command('add-predefined-app', AddPredefinedApp())


if __name__ == '__main__':
    try:
        manager.run()
    except InvalidCommand as err:
        sys.stderr.write(str(err))
        sys.exit(1)
