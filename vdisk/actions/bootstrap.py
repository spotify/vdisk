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
import logging

log = logging.getLogger(__name__)

from vdisk.helpers import mounted_loopback
from vdisk.helpers import available_lvm
from vdisk.helpers import mounted_device

from vdisk.externalcommand import ExternalCommand

debootstrap = ExternalCommand("debootstrap")


def action(ns):
    """
    Invoke debootstrap on an already created image.
    """
    if not os.path.isfile(ns.path):
        raise Exception("No such file: {0}".format(ns.path))

    if not os.path.isdir(ns.mountpoint):
        log.info("Creating mountpoint: {0}".format(ns.mountpoint))
        os.makedirs(ns.mountpoint)

    with mounted_loopback(ns.path):
        with available_lvm(ns.volume_group) as logical_volumes:
            with mounted_device(logical_volumes[0], ns.mountpoint):
                log.info("Installing on {0}".format(ns.mountpoint))
                debootstrap("--arch", ns.arch, ns.suite,
                            ns.mountpoint, ns.mirror)

    return 0
