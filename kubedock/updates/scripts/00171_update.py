import subprocess
from subprocess import CalledProcessError
from kubedock.updates import helpers
from fabric.api import quiet


def upgrade(upd, with_testing, *args, **kwargs):
    try:
        upd.print_log('Check if firewalld installed and running')
        subprocess.check_call(['rpm', '-q', 'firewalld'])
        subprocess.check_call(['firewall-cmd', '--state'])
    except CalledProcessError:
        upd.print_log('Firewalld is not running, installing...')
        helpers.local("yum install -y firewalld")
        helpers.local("systemctl restart firewalld")
        helpers.local("systemctl reenable firewalld")
    upd.print_log('Adding Firewalld rules...')
    with quiet():
        helpers.local("rm -f /etc/firewalld/zones/public.xml")
        helpers.local("firewall-cmd --reload")
    helpers.local("firewall-cmd --permanent --zone=public --add-port=80/tcp")
    helpers.local("firewall-cmd --permanent --zone=public --add-port=443/tcp")
    helpers.local("firewall-cmd --permanent --zone=public --add-port=123/udp")
    helpers.local("firewall-cmd --permanent --zone=public --add-port=6443/tcp")
    helpers.local("firewall-cmd --permanent --zone=public --add-port=2379/tcp")
    helpers.local("firewall-cmd --permanent --zone=public --add-port=8123/tcp")
    helpers.local("firewall-cmd --permanent --zone=public --add-port=8118/tcp")
    helpers.local("firewall-cmd --reload")


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass

def upgrade_node(upd, with_testing, env, *args, **kwargs):
    pass


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    pass
