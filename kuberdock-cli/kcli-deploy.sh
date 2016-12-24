#!/bin/bash

FLANNEL_CONFIG=/etc/sysconfig/flanneld
PROXY_CONFIG=/etc/kubernetes/config
PROXY_CONFIG_ARGS=/etc/kubernetes/proxy
GLOBAL_KCLI_CONFIG=/etc/kubecli.conf
KCLI_CONFIG=.kubecli.conf
DEPLOY_LOG_FILE=/var/log/kuberdock_client_deploy.log
EXIT_MESSAGE="Installation error. Install log saved to $DEPLOY_LOG_FILE"


if [ $USER != "root" ];then
    echo "Superuser privileges required" | tee -a $DEPLOY_LOG_FILE
    exit 1
fi


tty -s
if [ $? -ne 0 ];then
    read -s -r KD_PASSWORD
fi


show_help() {
    echo "-U|--upgrade          : Upgrade kuberdock packages"
    echo "-u|--user             : Specify kuberdock admin username (if not specified 'admin' is used)"
    echo "-t|--testing          : Use testing repositories"
    echo "-k|--kuberdock        : Specify KuberDock master hostname or IP address (if not specified '127.0.0.1' is used)"
    echo "-i|--ip-address       : Ip v4 address to use in calico-node"
    echo "-h|--help             : Show this help"
    echo "--local-kcli          : Filename of local package to install for upgrade kuberdock-cli."
    echo "--local-plugin        : Filename of local package to install for upgrade kuberdock-plugin."
    exit 0
}


do_and_log() {
    "$@" 2>&1 | tee -a $DEPLOY_LOG_FILE
    temp=$PIPESTATUS
    if [ $temp -ne 0 ];then
      echo $EXIT_MESSAGE
      exit $temp
    fi
}


log_errors() {
    echo "Doing $@" >> $DEPLOY_LOG_FILE
    "$@" 2> >(tee -a $DEPLOY_LOG_FILE)
    temp=$PIPESTATUS
    if [ $temp -ne 0 ];then
      echo $EXIT_MESSAGE
      exit $temp
    fi
}


yum_wrapper() {
    if [ -z "$TESTING" ];then
        log_errors yum --enablerepo=kube-client $@
    else
        log_errors yum --enablerepo=kube-client --enablerepo=kube-client-testing $@
    fi
}


enable_epel() {
  rpm --import https://dl.fedoraproject.org/pub/epel/RPM-GPG-KEY-EPEL-7
  rpm -q epel-release &> /dev/null || yum_wrapper -y install epel-release

  # Clean metadata once again if it's outdated after time sync with ntpd
  yum -d 1 --disablerepo=* --enablerepo=epel clean metadata

  # sometimes certificates can be outdated and this could cause
  # EPEL https metalink problems
  do_and_log yum -y --disablerepo=epel upgrade ca-certificates
  do_and_log yum -y --disablerepo=epel install yum-utils
  yum-config-manager --save --setopt timeout=60.0
  yum-config-manager --save --setopt retries=30

  _get_epel_metadata() {
    # download metadata only for EPEL repo
    yum -d 1 --disablerepo=* --enablerepo=epel clean metadata
    yum -d 1 --disablerepo=* --enablerepo=epel makecache fast
  }

  for _retry in $(seq 5); do
    echo "Attempt $_retry to get metadata for EPEL repo ..."
    _get_epel_metadata && return || sleep 10
  done
  do_and_log _get_epel_metadata
}


remove_flannel() {
    if [ "$VER" == "7" ];then
        do_and_log systemctl stop flanneld
        do_and_log systemctl disable flanneld
    else
        do_and_log service flanneld stop
        do_and_log chkconfig flanneld off
    fi

    yum_wrapper -y remove flannel

    rm -f "$FLANNEL_CONFIG"
}


register_host() {
    REGISTER_INFO=$(kcli kubectl register 2>&1)
    if [ $? -ne 0 ];then
        echo $REGISTER_INFO | grep -iq "already registered"
        if [ $? -ne 0 ];then
            echo "Could not register host in KuberDock. Check hostname, username and password and try again. Quitting."
            exit 1
        else
            echo "Already registered"
        fi
    else
        echo "Done"
    fi
}


install_calico() {
    if [ -z "$KD_HOST" ];then
        KD_HOST=$(grep url /etc/kubecli.conf | cut -d= -f2 | xargs echo | sed 's/^https\?:\/\///')
    fi

    # Probably Plesk already has installed docker
    if [ -z $(rpm -qa docker-engine) ]; then
        if [ "$VER" == "7" ];then
            yum_wrapper -y install docker
            do_and_log systemctl enable docker
            do_and_log systemctl start docker
        else
            # Explicitly enable EPEL repo in case if it already installed
            # but disabled by administrator
            yum_wrapper -y install --enablerepo=epel docker-io
            do_and_log chkconfig docker on
            do_and_log service docker start
        fi
    fi

    yum_wrapper -y install calicoctl-0.22.0

    # Separate pull command helps to prevent timeout bugs in calicoctl (AC-4679)
    # during deploy process under heavy IO (slow dev clusters).
    # If it's not enough we could add few retries with sleep here
    CALICO_NODE_IMAGE="kuberdock/calico-node:0.22.0-rh2"
    echo "Pulling Calico node image..."
    docker pull "$CALICO_NODE_IMAGE" > /dev/null
    time sync
    #sleep 10   # even harder workaround
    echo "Starting Calico node..."
    if mount | grep /tmp | grep noexec > /dev/null; then
        mount /tmp -o remount,exec
        echo "Directory /tmp was remount with exec flag"
    fi
    # In case of ambiguity we can force calico to register host with
    # envvar HOSTNAME="$SOME_HOSTNAME"
    if [ -z "$SELF_IP" ]; then
        ETCD_AUTHORITY="$KD_HOST:8123" do_and_log /opt/bin/calicoctl node --node-image="$CALICO_NODE_IMAGE"
    else
        ETCD_AUTHORITY="$KD_HOST:8123" do_and_log /opt/bin/calicoctl node --ip="$SELF_IP" --node-image="$CALICO_NODE_IMAGE"
    fi

    # wait for calico routes to bring up
    # TODO looks like this workaround is not needed after all fixes and may be
    # safely removed after few iterations of KD with Calico (KD 1.5.0)
    #sleep 20

    echo "Re-registering host again with network running..."
    register_host
}


check_calico() {
    if ! rpm -q docker >> /dev/null; then
        return 1
    fi
    if ! docker ps | grep kuberdock/calico-node >> /dev/null; then
        return 1
    fi
    return 0
}


switch_to_calico() {
    if rpm -q flannel >> /dev/null; then
        remove_flannel
    fi
    install_calico
}


upgrade() {
    yum_wrapper -y update kubernetes-proxy ${KCLI_PACKAGE} ${PLUGIN_PACKAGE}

    sed -i "s/^#\?KUBE_PROXY_ARGS=.*$/KUBE_PROXY_ARGS=\"--proxy-mode userspace\"/" $PROXY_CONFIG_ARGS
    do_and_log service kube-proxy restart

    check_calico || switch_to_calico

    exit 0
}


VER=$(cat /etc/redhat-release|sed -e 's/[^0-9]//g'|cut -c 1)

TEMP=$(getopt -o k:u:i:th,U -l kuberdock:,user:,ip-address:,local-kcli:,local-plugin:,testing,help,upgrade -n 'kcli-deploy.sh' -- "$@")
eval set -- "$TEMP"
# default values
KCLI_PACKAGE=kuberdock-cli
PLUGIN_PACKAGE=kuberdock-plugin

while true;do
    case "$1" in
        -k|--kuberdock)
            KD_HOST=$2;shift 2;
        ;;
        -u|--user)
            KD_USER=$2;shift 2;
        ;;
        -t|--testing)
            TESTING=true;shift;
        ;;
        -i|--ip-address)
            SELF_IP=$2;shift 2;
        ;;
        -h|--help)
            show_help;break
        ;;
         -U|--upgrade)
            DO_UPGRADE=true;shift;
        ;;
        --local-kcli)
            KCLI_PACKAGE=$2;shift 2;
        ;;
        --local-plugin)
            PLUGIN_PACKAGE=$2;shift 2;
        ;;
        --) shift;break;
    esac
done

if [ "$DO_UPGRADE" ];then
    upgrade
fi

if [ -z "$KD_HOST" ];then
    read -r -p "Enter KuberDock host name or IP address: " KD_HOST
    if [ -z "$KD_HOST" ];then
        KD_HOST="127.0.0.1"
    else
        KD_HOST=$(echo $KD_HOST|sed 's/^https\?:\/\///')
    fi
fi

if [ -z "$KD_USER" ];then
    read -r -p "Enter KuberDock admin username: " KD_USER
    if [ -z "$KD_USER" ];then
        KD_USER="admin"
    fi
fi

if [ -z "$KD_PASSWORD" ];then
    read -s -r -p "Enter KuberDock admin password: " KD_PASSWORD
    echo
    if [ -z "$KD_PASSWORD" ];then
        KD_PASSWORD="admin"
    fi
fi

cat > /etc/yum.repos.d/kube-client-cloudlinux.repo << EOF
[kube-client]
name=kube-client
baseurl=http://repo.cloudlinux.com/kuberdock-client/\$releasever/\$basearch
enabled=0
gpgcheck=1
gpgkey=http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
EOF

cat > /etc/yum.repos.d/kube-client-testing-cloudlinux.repo << EOF
[kube-client-testing]
name=kube-client-testing
baseurl=http://repo.cloudlinux.com/kuberdock-client-testing/\$releasever/\$basearch
enabled=0
gpgcheck=1
gpgkey=http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
EOF

do_and_log rpm --import http://repo.cloudlinux.com/cloudlinux/security/RPM-GPG-KEY-CloudLinux
enable_epel

yum_wrapper -y install ${KCLI_PACKAGE}
yum_wrapper -y install ${PLUGIN_PACKAGE}

sed -i -e "/^url/ {s|[ \t]*\$||}" -e "/^url/ {s|[^/]\+$|$KD_HOST|}" $GLOBAL_KCLI_CONFIG

KD_URL="https://$KD_HOST"
TOKEN=$(curl -s -k --connect-timeout 1 --user "$KD_USER:$KD_PASSWORD" "$KD_URL/api/auth/token"|tr -d " \t\r\n")
echo $TOKEN|grep -qi token
if [ $? -eq 0 ];then
    TOKEN=$(echo $TOKEN|sed "s/.*\"token\":\"\(.*\)\".*/\1/I")
    KCLI_CONFIG_PATH="$HOME/$KCLI_CONFIG"
    cat > $KCLI_CONFIG_PATH << EOF
[global]
url = $KD_URL

[defaults]
# token to talk to kuberdock
token = $TOKEN
# default registry to pull docker images from
registry = registry.hub.docker.com
EOF
    chmod 0600 $KCLI_CONFIG_PATH
else
    echo "Could not get token from KuberDock."
    echo "Check KuberDock host connectivity, username and password correctness"
    exit 1
fi

echo -n "Registering host in KuberDock... "
register_host

yum_wrapper -y install kubernetes-proxy
# TODO AC-4871: move to kube-proxy dependencies
yum_wrapper -y install conntrack-tools

yum_wrapper -y install at

install_calico


# looks like userspace mode works fine too, but maybe cPanel will conflicts
# with some iptables rules?
sed -i "s/^#\?KUBE_PROXY_ARGS=.*$/KUBE_PROXY_ARGS=\"--proxy-mode iptables\"/" $PROXY_CONFIG_ARGS

sed -i "s/^KUBE_MASTER=.*$/KUBE_MASTER=\"--master=http:\/\/$KD_HOST:8118\"/" $PROXY_CONFIG

if [ "$VER" == "7" ];then
    do_and_log systemctl enable kube-proxy
    do_and_log systemctl start kube-proxy
    do_and_log systemctl enable atd
    do_and_log systemctl start atd
else
    do_and_log chkconfig kube-proxy on
    do_and_log service kube-proxy start
    do_and_log chkconfig atd on
    do_and_log service atd start
fi
