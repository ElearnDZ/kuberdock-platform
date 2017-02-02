
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

import json
import os

from ... import kdclick
from ...kdclick.access import ADMIN
from ...utils import file_utils


@kdclick.command(available_for=ADMIN)
@kdclick.argument('pod-id')
@kdclick.pass_obj
def dump(obj, **params):
    """Dump pod"""
    return obj.executor.dump(**params)


@kdclick.command('batch-dump', available_for=ADMIN)
@kdclick.option('--owner', required=False,
                help='If specified, only pods of this user will be dumped')
@kdclick.option('--target-dir', required=False,
                type=kdclick.Path(dir_okay=True, file_okay=False,
                                  resolve_path=True),
                help='If specified, pod dumps will be saved there '
                     'in the following structure: '
                     '<target_dir>/<owner_id>/<pod_id>')
@kdclick.pass_obj
def batch_dump(obj, owner=None, target_dir=None):
    """Batch dump pods"""
    result = obj.executor.batch_dump(owner)
    if target_dir is None:
        return result
    else:
        dumps = result['data']
        if dumps is None:
            dumps = []
        _save_batch_dump_result(obj, dumps, target_dir)


def _save_batch_dump_result(obj, dumps, target_dir):
    """Saves dumps to <target_dir>/<owner_id>/<pod_id>"""
    for dump in dumps:
        owner_id = dump['owner']['id']
        pod_id = dump['pod_data']['id']
        target_dir0 = os.path.join(target_dir, str(owner_id))
        file_utils.ensure_dir(target_dir0)
        target_file = os.path.join(target_dir0, str(pod_id))
        with open(target_file, 'w') as f:
            json.dump(dump, f, indent=4, sort_keys=True)
        obj.io.out_text('Saved %s' % target_file)
