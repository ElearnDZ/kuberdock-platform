import logging
import re
import socket
import time
from contextlib import contextmanager
from itertools import count, islice

from colorama import Fore, Style

NO_FREE_IPS_ERR_MSG = 'There are no free public IP-addresses, contact ' \
                      'KuberDock administrator'

LOG = logging.getLogger(__name__)


def ssh_exec(ssh, cmd, timeout=None, check_retcode=True):
    LOG.debug("{}Calling SSH: '{}'{}".format(Style.DIM, cmd, Style.RESET_ALL))
    _, out, err = ssh.exec_command(cmd, timeout=timeout)
    ret_code = out.channel.recv_exit_status()
    out, err = out.read().strip(), err.read().strip()

    msg_parts = [
        (Fore.GREEN, 'RetCode: ', str(ret_code)),
        (Fore.YELLOW, '=== StdOut ===\n', out),
        (Fore.RED, '=== StdErr ===\n', err)]
    msg = '\n'.join('{}{}{}'.format(c, n, v) for c, n, v in msg_parts if v)

    LOG.debug(msg + Style.RESET_ALL)
    if check_retcode and ret_code != 0:
        raise NonZeroRetCodeException(
            stdout=out, stderr=err, ret_code=ret_code)
    return ret_code, out, err


class PublicPortWaitTimeoutException(Exception):
    pass


class StatusWaitException(Exception):
    pass


class UnexpectedKubectlResponse(Exception):
    pass


class NonZeroRetCodeException(Exception):
    def __init__(self, message='', stdout=None, stderr=None, ret_code=None):
        self.stdout, self.stderr, self.ret_code = stdout, stderr, ret_code
        super(NonZeroRetCodeException, self).__init__(message)

    def __str__(self):
        return '\n'.join([self.message, self.stdout, self.stderr])


def wait_net_port(ip, port, timeout, try_interval=2):
    LOG.debug("Waiting for {0}:{1} to become available.".format(ip, port))
    end = time.time() + timeout
    while time.time() < end:
        try:
            s = socket.create_connection((ip, port), timeout=5)
        except socket.timeout:
            # cannot connect after timeout
            continue
        except socket.error as ex:
            # cannot connect immediately (e.g. no route)
            # wait timeout before next try
            LOG.debug("Wait cycle msg: {0}".format(repr(ex)))
            time.sleep(try_interval)
            continue
        else:
            # success!
            s.close()
            return
    raise PublicPortWaitTimeoutException()


def kube_type_to_int(kube_type):
    int_types = {
        "Tiny": 0,
        "Standard": 1,
        "High memory": 2,
    }
    return int_types[kube_type]


def assert_eq(actual, expected):
    if actual != expected:
        raise AssertionError("Values are not equal\n"
                             "Expected: {0}\n"
                             "Actual  : {1}".format(expected, actual))


def assert_in(item, sequence):
    if item not in sequence:
        raise AssertionError("Item '{0}' not in '{1}'".format(
            item, sequence
        ))


@contextmanager
def assert_raises(exc, text):
    try:
        yield
    except exc as e:
        assert re.search(text, str(e)) is not None


def merge_dicts(*dictionaries):
    """
    Merge a given number of dicts to the single one. If there are duplicate
    keys between the dictionaries then the value is taken from dictionary
    which has a higher priority. Priorities increase from the left to the right
    """
    result = {}
    for dictionary in dictionaries:
        result.update(dictionary)
    return result


def pod_factory(image, **create_kwargs):
    """
    A helper function which returns a factory function. It is then used to
    create a given amount of pods with unique names because POD names should be
    unique in KD. Also it is possible to specify some default arguments
    passed to the actual create_pod function but nevertheless it's possible
    to override them each time you create a pod

    :param cluster: an instance of KDIntegrationTestAPI
    :param image: the desired image name which will be used for pods
    :param create_kwargs: arguments (except image and name) which will passed
    through to the cluster's create_pod(...) method
    :return: a list of created pod instances
    """
    name_generator = ('{}_{}'.format(image, i) for i in count())

    def _factory(cluster, num=1, **override_kwargs):
        params = merge_dicts(create_kwargs, override_kwargs)
        names = islice(name_generator, num)
        return [cluster.create_pod(image, n, **params) for n in names]

    return _factory


def center_text_message(message, width=120, fill_char='-'):
    """
    Returns a string where the message is centered relative to the specified
    width filling the empty space around text with the given character

    :param message: string
    :param width: width of the screen
    :param fill_char: char to use for filling blanks
    :return: formatted message
    """
    message = ' {} '.format(message)
    return '{{:{}^{}}}'.format(fill_char, width).format(message)


def retry(f, tries=3, interval=1, _raise=True, *f_args, **f_kwargs):
    """
    Retries given func call specified n times

    :param f: callable
    :param tries: number of retries
    :param interval: sleep interval between retries
    :param _raise: re-raise function exception when retries done
    :param f_args: callable args
    :param f_kwargs: callable kwargs
    :return:
    """
    while tries > 0:
        tries -= 1
        try:
            return f(*f_args, **f_kwargs)
        except Exception as ex:
            LOG.debug("Retry failed with exception: {0}".format(repr(ex)))
            if tries > 0:
                LOG.debug("{0} retries left".format(tries))
                time.sleep(interval)
            else:
                if _raise:
                    raise
