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

from vdisk.helpers import mounted_device

from vdisk.externalcommand import ExternalCommand


chroot = ExternalCommand("chroot")


def action(ns):
    if not os.path.isfile(ns.image_path):
        raise Exception("No such file: {0}".format(ns.image_path))

    puppet_env = dict()

    if ns.facts:
        for fact in ns.facts:
            try:
                key, value = fact.split("=", 2)
            except:
                raise Exception("Invalid fact: {0}".format(fact))

            puppet_env["FACTER_{0}".format(key)] = value

    with ns.preset.entered_system() as d:
        devices, logical_volumes, mountpoint = d

        puppetpath = "{0}/puppet".format(ns.mountpoint)

        if not os.path.isdir(puppetpath):
            os.makedirs(puppetpath)

        with mounted_device(ns.puppetpath, puppetpath, mount_bind=True):
            chroot(mountpoint, "puppet", *ns.puppetargs, env=puppet_env)

    return 0
