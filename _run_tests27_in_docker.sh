#!/usr/bin/env bash
build_number=${BUILD_NUMBER:-local_$(echo $RANDOM | tr '[0-9]' '[a-zA-Z]')}
project="appcloudunittest${build_number}"
compose="docker-compose -f tests27-compose.yml -p ${project}"

$compose build
$compose run --rm appcloud /bin/bash -c \
"set -e;
 echo 'Waiting for postgres 5432 port';
 timeout 30 bash -c 'until nmap --open -p5432 postgres | grep open; do echo \"Waiting..\"; sleep 1; done;'
 echo '###################### Setup requirements ######################';
 source /venv/bin/activate;
 pip install -r requirements.txt -r requirements-dev.txt;
 echo '######################## Run unit tests ########################';
 py.test -v \
    --cov-config .coveragerc \
    --cov-report xml:/artifacts/cov.xml \
    --cov-report html:/artifacts/htmlcov \
    --cov-report term \
    --cov=kubedock \
    --cov=kuberdock-cli \
    --cov=kuberdock-manage \
    kubedock kuberdock-cli kuberdock-manage node_storage_manage"
ret=$?

$compose down --rmi local -v
exit $ret
