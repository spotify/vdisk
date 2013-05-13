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
import logging

log = logging.getLogger(__name__)

from vdisk.externalcommand import ExternalCommand

debootstrap = ExternalCommand("debootstrap")


def action(ns):
    """
    Invoke debootstrap on an already created image.
    """
    if not os.path.isfile(ns.image_path):
        raise Exception("No such file: {0}".format(ns.image_path))

    if not os.path.isdir(ns.mountpoint):
        log.info("Creating mountpoint: {0}".format(ns.mountpoint))
        os.makedirs(ns.mountpoint)

    # deboostrap managed dev and proc magically.
    with ns.preset.entered_system(mount_proc=False, mount_dev=False) as d:
        devices, logical_volumes, mountpoint = d
        log.info("Installing on {0}".format(mountpoint))
        debootstrap("--arch", ns.arch, ns.suite, mountpoint, ns.mirror)

    return 0
