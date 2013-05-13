# -*- coding: utf-8 -*-
# Copyright (c) 2013 Spotify AB
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

import os

from vdisk.externalcommand import ExternalCommand

chroot = ExternalCommand("chroot")


def action(ns):
    if not os.path.isfile(ns.image_path):
        raise Exception("No such file: {0}".format(ns.image_path))

    with ns.preset.entered_system() as d:
        path = d[2]
        exitcode, out, err = chroot(path, ns.shell, raise_on_exit=False)
        return exitcode
