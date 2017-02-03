
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

from ... import kdclick

from ...kdclick.access import ADMIN
from ....api_client import APIError

# bit flags
_NOT_FORCE = 0
_FORCE_DELETE = 1
_FORCE_NOT_DELETE = 2


def _get_owner_from_dump(pod_dump):
    try:
        return pod_dump['owner']['username']
    except KeyError:
        raise Exception('Pod dump has unexpected structure. Cannot find '
                        'owner\'s username')


class _RestorePodCommand(object):
    def __init__(self, kdctl, io, pod_dump, owner, pv_backups_location,
                 pv_backups_path_template, force, max_tries):
        assert force in [_NOT_FORCE, _FORCE_DELETE, _FORCE_NOT_DELETE]
        self.kdctl = kdctl
        self.io = io
        self.pod_dump = pod_dump
        if owner is not None:
            self.owner = owner
        else:
            self.owner = _get_owner_from_dump(pod_dump)
        self.pv_backups_location = pv_backups_location
        self.pv_backups_path_template = pv_backups_path_template
        self.force = force
        self.max_tries = max_tries

    def __call__(self):
        return self._apply(try_number=0)

    def _apply(self, try_number):
        try:
            return self.kdctl.pods.restore(
                self.pod_dump, self.owner, self.pv_backups_location,
                self.pv_backups_path_template)
        except APIError as e:
            if self.force == _FORCE_NOT_DELETE or try_number >= self.max_tries:
                raise
            self._dispatch_errors(e)
            return self._apply(try_number + 1)

    def _dispatch_errors(self, error):
        e_type = error.json['type']
        if e_type == 'MultipleErrors':
            errors = [APIError(e)
                      for e in error.json['details']['errors']]
            for e in errors:
                self._dispatch_errors(e)
        elif e_type == 'PodNameConflict':
            self._try_delete_pod(error.json['details'])
        elif e_type == 'VolumeExists':
            self._try_delete_pv(error.json['details'])
        else:
            raise error

    def _try_delete_pod(self, pod_data):
        assert self.force in [_NOT_FORCE, _FORCE_DELETE]
        kdctl = self.kdctl
        io = self.io
        io.out_text('Pod with name "%s" already exists.' % pod_data['name'])
        if self.force == _NOT_FORCE:
            if not io.confirm('Do you want to delete this pod?'):
                kdclick.abort()
        io.out_text('Deleting...')
        pod_id = pod_data.get('id')
        kdctl.pods.delete(id=pod_id, owner=self.owner)
        io.out_text('Deleted')

    def _try_delete_pv(self, pv_data):
        assert self.force in [_NOT_FORCE, _FORCE_DELETE]
        kdctl = self.kdctl
        io = self.io
        io.out_text('Persistent volume with name "%s" already exists.'
                    % pv_data['name'])
        if self.force == _NOT_FORCE:
            if not io.confirm('Do you want to delete this persistent volume?'):
                kdclick.abort()
        io.out_text('Deleting...')
        pv_id = pv_data.get('id')
        kdctl.pstorage.delete(id=pv_id, owner=self.owner)
        io.out_text('Deleted')


def _check_params(io, force):
    if io.json_only and force == _NOT_FORCE:
        raise kdclick.UsageError(
            'In json-only mode one of --force-delete/--force-not-delete '
            'options must be specified')


def _max_tries_validation(ctx, param, value):
    conditions = [
        value is None or value >= 0
    ]
    if not all(conditions):
        raise kdclick.BadParameter('Value must be >= 0')
    if value == 0:
        return float('inf')
    return value


def _collect_force(force_delete, force_not_delete):
    # collect bit flags
    force = sum([
        (force_delete and _FORCE_DELETE),
        (force_not_delete and _FORCE_NOT_DELETE)
    ])

    # check if only one flag or no flags specified
    if force not in [_NOT_FORCE, _FORCE_DELETE, _FORCE_NOT_DELETE]:
        raise kdclick.UsageError('"force-delete" and "force-not-delete" '
                                 'are mutually exclusive options')

    # return result
    return force


@kdclick.command('restore', available_for=ADMIN)
@kdclick.data_argument('pod-dump')
@kdclick.option('--owner', required=False,
                help="Pod's owner name. If it is not provided, one will be "
                     "taken from pod's dump.")
@kdclick.option('--pv-backups-location', help='Url where backups are stored.')
@kdclick.option('--pv-backups-path-template',
                help='Template of path to backup at backups location. '
                     'Standard python template in form of '
                     '"some text with {some_key}". '
                     'Available keys are: owner_id, owner_name, '
                     'original_owner_id, original_owner_name, volume_name. '
                     'Default template is `/{owner_id}/{volume_name}.tar.gz`.')
@kdclick.option('--force-delete', is_flag=True,
                help='Force delete pods and persistent volumes.')
@kdclick.option('--force-not-delete', is_flag=True,
                help='Force NOT delete pods and persistent volumes.')
@kdclick.option('--max-tries', type=int, callback=_max_tries_validation,
                default=2, show_default=True,
                help='Maximal number of tries, 0 for infinity.')
@kdclick.pass_obj
def pod(obj, pod_dump, owner, pv_backups_location, pv_backups_path_template,
        force_delete, force_not_delete, max_tries):
    """Restore pod from dump"""
    kdctl = obj.kdctl
    io = obj.io
    force = _collect_force(force_delete, force_not_delete)
    _check_params(io, force)
    command = _RestorePodCommand(
        kdctl, io, pod_dump, owner, pv_backups_location,
        pv_backups_path_template, force, max_tries)
    return command()
