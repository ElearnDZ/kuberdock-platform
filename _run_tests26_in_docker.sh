#!/usr/bin/env bash
IMAGE='tyzhnenko/centos6-test-base:v1'

docker run -v $(pwd):/appcloud:ro -w /appcloud $IMAGE /bin/bash -c \
"set -e;
 echo '###################### Setup requirements ######################';
 source /venv/bin/activate;
 pip install -r requirements-dev.txt;
 echo '######################## Run unit tests ########################';
 py.test -p no:cacheprovider -v \
    kuberdock-cli kuberdock-manage"
ret=$?

exit $ret
