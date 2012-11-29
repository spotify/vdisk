# Copyright (c) 2012 Spotify AB

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import os

from vdisk.helpers import entered_system
from vdisk.helpers import mounted_device

from vdisk.externalcommand import ExternalCommand


chroot = ExternalCommand("chroot")


def action(ns):
    if not os.path.isfile(ns.path):
        raise Exception("No such file: {0}".format(ns.path))

    puppet_env = dict()

    if ns.facts:
        for fact in ns.facts:
            try:
                key, value = fact.split("=", 2)
            except:
                raise Exception("Invalid fact: {0}".format(fact))

            puppet_env["FACTER_{0}".format(key)] = value

    with entered_system(ns.path, ns.volume_group, ns.mountpoint) as d:
        devices, logical_volumes, path = d

        puppetpath = "{0}/puppet".format(ns.mountpoint)

        if not os.path.isdir(puppetpath):
            os.makedirs(puppetpath)

        with mounted_device(ns.puppetpath, puppetpath, mount_bind=True):
            chroot(path, "puppet", *ns.puppetargs, env=puppet_env)

    return 0
