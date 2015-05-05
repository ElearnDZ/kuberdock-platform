Version: 0.1
Name: kuberdock
Summary: KuberDock
Release: 34%{?dist}.cloudlinux
Group: Applications/System
BuildArch: noarch
License: CloudLinux Commercial License
URL: http://www.cloudlinux.com
Source0: %{name}-%{version}.tar.bz2

Requires: nginx
Requires: influxdb
Requires: redis
Requires: postgresql-server
Requires: fabric
Requires: etcd == 2.0.9-1.el7.centos
Requires: kubernetes >= 0.15.0-4.el7.centos.1
Requires: flannel >= 0.3.0
Requires: dnsmasq >= 2.66
# For semanage:
Requires: policycoreutils-python >= 2.2
Requires: python-uwsgi
Requires: python-cerberus >= 0.7.2
Requires: python-flask >= 0.10.1
Requires: python-flask-assets >= 0.10
Requires: python-flask-influxdb >= 0.1
Requires: python-flask-login >= 0.2.11
Requires: python-flask-mail >= 0.9.1
Requires: python-flask-sqlalchemy >= 2.0
Requires: python-jinja2 >= 2.7.2
Requires: python-markupsafe >= 0.23
Requires: python-sqlalchemy >= 0.9.7-3
Requires: python-unidecode >= 0.04.16
Requires: python-werkzeug >= 0.9.6-1
Requires: python-werkzeug-doc >= 0.9.6
Requires: python-amqp >= 1.4.5
Requires: python-anyjson >= 0.3.3
Requires: python-argparse >= 1.2.1
Requires: python-billiard >= 3.3.0.18
Requires: python-blinker >= 1.3
Requires: python-celery >= 3.1.15
Requires: python-ecdsa >= 0.11
Requires: python-gevent >= 1.0
Requires: python-greenlet >= 0.4.2
Requires: python-influxdb >= 0.1.13
Requires: python-itsdangerous >= 0.24
Requires: python-ipaddress >= 1.0.7
Requires: python-kombu >= 3.0.23
Requires: python-nose >= 1.3.0
Requires: python-paramiko >= 1.12.4
Requires: python-psycopg2 >= 2.5.4
Requires: python-redis >= 2.10.3
Requires: python-requests >= 2.4.3
Requires: python-simple-rbac >= 0.1.1
Requires: python-sse >= 1.2
Requires: python-webassets >= 0.10.1
Requires: python-wsgiref >= 0.1.2
Requires: python-psycogreen >= 1.0

# AutoReq: 0
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

%description
Kuberdock

%prep
%setup -n %{name}-%{version}

%build

%install
rm -rf %{buildroot}
%{__install} -d %{buildroot}%{_defaultdocdir}/%{name}-%{version}/
mkdir -p %{buildroot}/var/opt/kuberdock
mkdir -p %{buildroot}%{_sysconfdir}/uwsgi/vassals
mkdir -p %{buildroot}%{_sysconfdir}/nginx/conf.d/
mkdir -p %{buildroot}%{_sysconfdir}/nginx/ssl/
mkdir -p %{buildroot}/var/log/kuberdock
cp -r * %{buildroot}/var/opt/kuberdock
%{__install} -D -m 0644 conf/kuberdock.ini %{buildroot}%{_sysconfdir}/uwsgi/vassals/kuberdock.ini
%{__install} -D -m 0644 conf/kuberdock-ssl.conf %{buildroot}%{_sysconfdir}/nginx/conf.d/kuberdock-ssl.conf
%{__install} -D -m 0644 conf/kuberdock.conf %{buildroot}%{_sysconfdir}/sysconfig/kuberdock/kuberdock.conf


%clean
rm -rf %{buildroot}

%posttrans

%define sslcert %{_sysconfdir}/nginx/ssl/kubecert.crt
%define sslkey %{_sysconfdir}/nginx/ssl/kubecert.key

%post
umask 077

if [ ! -f %{sslkey} ] ; then
%{_bindir}/openssl genrsa -rand /proc/apm:/proc/cpuinfo:/proc/dma:/proc/filesystems:/proc/interrupts:/proc/ioports:/proc/pci:/proc/rtc:/proc/uptime 1024 > %{sslkey} 2> /dev/null
fi

FQDN=`hostname`
if [ "x${FQDN}" = "x" ]; then
   FQDN=localhost.localdomain
fi

if [ ! -f %{sslcert} ] ; then
cat << EOF | %{_bindir}/openssl req -new -key %{sslkey} \
         -x509 -days 365 -set_serial $RANDOM \
         -out %{sslcert} 2>/dev/null
--
SomeState
SomeCity
SomeOrganization
SomeOrganizationalUnit
${FQDN}
root@${FQDN}
EOF
fi

# Even if SELinux disabled, we set labels for future
semanage fcontext -a -t httpd_sys_content_t /var/opt/kuberdock/kubedock/frontend/static\(/.\*\)\?
restorecon -Rv /var/opt/kuberdock/kubedock/frontend/static

%files
%defattr(-,root,root)
%attr (-,nginx,nginx) /var/opt/kuberdock
%attr (-,nginx,nginx) /var/log/kuberdock
%dir %{_sysconfdir}/nginx/ssl
%config %{_sysconfdir}/nginx/conf.d/kuberdock-ssl.conf
%config %{_sysconfdir}/uwsgi/vassals/kuberdock.ini
%attr (-,nginx,nginx) %config(noreplace) %{_sysconfdir}/sysconfig/kuberdock/kuberdock.conf

%changelog
* Wed Apr 29 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Andrey Lukyanov <alukyanov@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com> 0.1-34
- AC-292 Node saves install log and shows it if in troubles state.
- Design fixes AC: 266, 279, 281, 288, 299
- Design fixes AC: 271, 276, 279, 297, 312, 31
- Remove manifests from kubelet config as we no longer use them
- AC-262: Run service pods as KuberDock Internal user
- Reworked WHMCS API

* Mon Apr 27 2015 Igor Savenko <bliss@cloudlinux.com> 0.1-33
- Added preliminary persistent storage implementation

* Mon Apr 27 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Andrey Lukyanov <alukyanov@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com>, Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.1-32
- Show true container state on container page
- Add node troubles reason
- Last small gevent related fixes
- Fix for no node condition
- Fix typo in deploy.sh with externalIPs feature.
- Change to generateName in services
- Design fixes AC: 270, 275, 279, 280, 284, 285, 286, 287
- Added persistent drive script

* Fri Apr 24 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Andrey Lukyanov <alukyanov@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com> 0.1-31
- gevent fixes
- deploy.sh improvemets

* Mon Apr 22 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Andrey Lukyanov <alukyanov@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com>, Alex Tishin <atishin@cloudlinux.com> 0.1-30
- multiports
- bugfixes

* Mon Apr 20 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com> 0.1-29
- Add full style to container page tabs
- AC-218, AC-211 add style to variables page & fix style in others pages in container template
- Add style to last step in add pod template

* Fri Apr 17 2015 Stanislav Sergiienko <ssergiienko@cloudlinux.com>, Andrey Lukyanov <alukyanov@cloudlinux.com>, Igor Savenko <bliss@cloudlinux.com> 0.1-28
- SELinux fixes
- AC-217 (SSH-key generation)
- kube-public-ip fix, show count of kubes of pod,
  added price and kubes into validation scheme (added new type strnum)
   

* Thu Apr 16 2015 Oleg Bednarskiy <obednarsky@cloudlinux.com>, Andrey Lukyanov <alukyanov@cloudlinux.com> 0.1-27
- Merge "AC-202: Default page for admin and user roles"
- set_public_ip fix, next redirect on login fix, 401 status code fix
- Add new design to add pod template, fix some bugs in settings,
  create new templates in container page
- Introduce new desgn login page

* Wed Apr 15 2015 Igor Savenko <bliss@cloudlinux.com> 0.1-26
- First release

