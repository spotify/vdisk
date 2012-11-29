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

from vdisk.externalcommand import ExternalCommand

from vdisk.helpers import mounted_loopback
from vdisk.helpers import available_lvm

parted = ExternalCommand("parted")
lvm = ExternalCommand("lvm")
mkfs_ext4 = ExternalCommand("mkfs.ext4")
mkswap = ExternalCommand("mkswap")


def action(ns):
    """
    Create base image with lvm.
    """
    if not ns.force and os.path.isfile(ns.path):
        raise Exception("path already exists: {0}".format(ns.path))

    with open(ns.path, "w") as f:
        f.truncate(ns.size.size)

    parted("-s", "--", ns.path,
           "mklabel", "gpt")
    parted("-s", "--", ns.path,
           "mkpart", "no-fs", "1", "2",
           "set", "1", "bios_grub", "on")
    parted("-s", "--", ns.path,
           "mkpart", "primary", "2", "-1",
           "set", "2", "lvm", "on")
    parted("-s", "--", ns.path, "print")

    with mounted_loopback(ns.path) as devices:
        for loop_device, subdevices in devices.items():
            if len(subdevices) < 2:
                log.warning("Ignoring {0}: too few partitions")
                continue

            lvm("pvcreate", subdevices[1])
            lvm("vgcreate", ns.volume_group, subdevices[1])
            lvm("lvcreate", "-L", "7G", "-n", "root", ns.volume_group)
            lvm("lvcreate", "-l", '100%FREE', "-n", "swap", ns.volume_group)

            with available_lvm(ns.volume_group) as logical_volumes:
                log.info("formatting logical volumes")
                mkfs_ext4(logical_volumes[0])
                mkswap("-f", logical_volumes[1])

    return 0
