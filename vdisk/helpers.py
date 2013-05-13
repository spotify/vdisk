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
import shutil
import contextlib
import logging

log = logging.getLogger(__name__)

from vdisk.externalcommand import ExternalCommand

losetup = ExternalCommand("losetup")
kpartx = ExternalCommand("kpartx")
lvm = ExternalCommand("lvm")
udevadm = ExternalCommand("udevadm")
mount = ExternalCommand("mount")
umount = ExternalCommand("umount")
chroot = ExternalCommand("chroot")


@contextlib.contextmanager
def mounted_loopback(path, partition_pattern="/dev/mapper/{0}"):
    """
    Mount the specified path as loopback devices.

    There is a small chance that some system resources are not properly
    released, in which case one of the functions in the finally clause might
    throw an exception.
    """
    devices = {}
    exitcode, out, err = losetup("--show", "-f", path, capture=True)

    loop = out[0]

    try:
        exitcode, out, err = kpartx("-v", "-a", loop, capture=True,
                                    remove_empty=True)
    except:
        losetup("-d", path)
        yield

    udevadm("settle")

    for line in out:
        parts = line.split()
        partition = partition_pattern.format(parts[2])
        devices.setdefault(loop, []).append(partition)

    try:
        yield devices
    finally:
        for path, partitions in devices.items():
            kpartx("-d", path)
            losetup("-d", path)


@contextlib.contextmanager
def available_lvm(volume_group):
    lvm("vgchange", "-a", "y", volume_group)
    udevadm("settle")

    exitcode, out, err = lvm("lvdisplay", "-c", volume_group,
                             capture=True, remove_empty=True)

    logical_volumes = dict()

    for line in out:
        parts = line.split(":")
        device = parts[0]
        name = device.split('/')[-1]
        logical_volumes[name] = device

    try:
        yield logical_volumes
    finally:
        lvm("vgchange", "-a", "n", volume_group)
        udevadm("settle")


@contextlib.contextmanager
def mounted_device(device, mountpoint, **opts):
    args = []

    if not os.path.isdir(mountpoint):
        os.makedirs(mountpoint)

    mount_type = opts.get("mount_type")

    if mount_type:
        args.extend(["-t", mount_type])

    mount_bind = opts.get("mount_bind", False)

    if mount_bind:
        args.extend(["--bind"])

    args.extend([device, mountpoint])

    mount(*args)

    udevadm("settle")

    try:
        yield
    finally:
        umount(mountpoint)


@contextlib.contextmanager
def entered_system(path, volume_group, mountpoint, **kw):
    extra_mounts = kw.pop("extra_mounts", None)
    mount_proc = kw.pop("mount_proc", True)
    mount_dev = kw.pop("mount_dev", True)

    with mounted_loopback(path) as devices:
        with available_lvm(volume_group) as lv:
            mounts = [
                mounted_device(lv['root'], mountpoint),
            ]

            if mount_proc:
                mounts.append(
                    mounted_device(
                        "null", "{0}/proc".format(mountpoint),
                        mount_type="proc")
                )

            if mount_dev:
                mounts.append(
                    mounted_device(
                        "/dev", "{0}/dev".format(mountpoint),
                        mount_bind=True)
                )

            # mount boot if available.
            if 'boot' in lv:
                mounts.append(
                    mounted_device(lv['boot'], "{0}/boot".format(mountpoint)))

            if extra_mounts:
                mounts.extend(m(devices, lv) for m in extra_mounts)

            with contextlib.nested(*mounts):
                yield devices, lv, mountpoint


def install_packages(ns, path, packages, env=None, extra=[]):
    """
    Install the specified packages.

    Expects packages to be a dict with keys matching the suites the packages
    should be installed from, to a value which is a list of packages.
    """

    for suite, packages in packages.items():
        for package in packages:
            log.info("Installing {0} from suite {1}".format(package, suite))

            args = list(extra)

            if suite != "default":
                args.extend(["-t", suite])

            args.extend(["-y", "install", package])

            chroot(path, ns.apt_get, *args, env=env)


def find_first_device(devices):
    for (device, partitions) in sorted(devices.items()):
        return device, partitions

    raise Exception("No device found: {0!r}".format(devices))


def copy_file(ns, source, target, owner="root", group="root", mode=0644):
    source_path = os.path.join(ns.root, source)
    target_path = os.path.join(ns.mountpoint, target)
    abs_target_path = os.path.join("/", target)

    if not os.path.isfile(source_path):
        raise Exception("Source path is not a file: {0}".format(source_path))

    shutil.copy(source_path, target_path)

    chroot(ns.mountpoint, "chown", "{0}:{1}".format(owner, group),
           abs_target_path)

    chroot(ns.mountpoint, "chmod", oct(mode), abs_target_path)


def create_directory(ns, target, owner="root", group="root", mode=0755):
    target_path = os.path.join(ns.mountpoint, target)
    abs_target_path = os.path.join("/", target)

    if not os.path.isdir(target_path):
        os.mkdir(target_path, mode)

    chroot(ns.mountpoint, "chown", "{0}:{1}".format(owner, group),
           abs_target_path)


def write_mounted(mountpoint, path, lines):
    with open(os.path.join(mountpoint, path), "w") as f:
        for line in lines:
            print >>f, line


def generate_devicemap(devices):
    for i, (device, partitions) in enumerate(sorted(devices.items())):
        yield "(hd{0}) {1}".format(i, device)

        for s, partition in enumerate(partitions):
            yield "(hd{0},{1}) {2}".format(i, s, partition)
