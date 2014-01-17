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

from vdisk.externalcommand import ExternalCommand
from vdisk.helpers import mounted_loopback
from vdisk.helpers import available_lvm
from vdisk.helpers import entered_system
from vdisk.helpers import find_first_device
from vdisk.helpers import mounted_device

log = logging.getLogger(__name__)


class EC2Preset(object):
    parted = ExternalCommand("parted")
    lvm = ExternalCommand("lvm")
    mkfs_ext4 = ExternalCommand("mkfs.ext4")
    mkswap = ExternalCommand("mkswap")

    def __init__(self, ns):
        self.image_path = ns.image_path
        self.volume_group = ns.volume_group
        self.root_size = ns.root_size
        self.mountpoint = ns.mountpoint

    def setup_disks(self):
        """
        pv-grub depends on mbr and a separate non-lvm boot partition.
        """
        parted = self.parted.prefix("-s", "--", self.image_path)

        parted("mklabel", "msdos")

        parted(
            "mkpart", "primary", "1", "512",
            "set", "1", "boot", "on"
        )
        parted(
            "mkpart", "primary", "512", "-1",
            "set", "2", "lvm", "on"
        )

        parted("print")

        with mounted_loopback(self.image_path) as devices:
            for loop_device, partitions in devices.items():
                if len(partitions) < 2:
                    log.warning("Ignoring {0}: too few partitions")
                    continue

                self.mkfs_ext4(partitions[0])

                self.lvm(
                    "pvcreate", partitions[1])
                self.lvm(
                    "vgcreate", self.volume_group, partitions[1])
                self.lvm(
                    "lvcreate", "-L", self.root_size.formatted,
                    "-n", "root", self.volume_group)
                self.lvm(
                    "lvcreate", "-l", '100%FREE', "-n", "swap",
                    self.volume_group)

                with available_lvm(self.volume_group) as lv:
                    log.info("formatting logical volumes")
                    self.mkfs_ext4(lv['root'])
                    self.mkswap("-f", lv['swap'])

    def _extra_mounts(self):
        def __ec2_extra_mounts(devices, logical_volumes):
            first_device, partitions = find_first_device(devices)

            return mounted_device(
                partitions[0], "{0}/boot".format(self.mountpoint))

        return [__ec2_extra_mounts]

    def entered_system(self, **kw):
        return entered_system(
            self.image_path,
            self.volume_group,
            self.mountpoint,
            extra_mounts=self._extra_mounts(), **kw)

    def setup_boot(self, devices, path):
        """
        we need /boot/boot/grub/menu.lst since pv-grub
        checks /boot/grub/menu.lst on (hd0,0) partition
        """
        log.info("Creating a relative symlink /boot/boot -> .")
        os.symlink('.', "{0}/boot/boot".format(self.mountpoint))
