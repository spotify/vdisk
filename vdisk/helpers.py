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
import sys
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
def mounted_loopback(path, subdevice_pattern="/dev/mapper/{0}"):
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
        subdevice = subdevice_pattern.format(parts[2])
        devices.setdefault(loop, []).append(subdevice)

    try:
        yield devices
    except:
        log.error("exception thrown", exc_info=sys.exc_info())
    finally:
        for path, subdevices in devices.items():
            kpartx("-d", path)
            losetup("-d", path)


@contextlib.contextmanager
def available_lvm(volume_group):
    lvm("vgchange", "-a", "y", volume_group)
    udevadm("settle")

    exitcode, out, err = lvm("lvdisplay", "-c", volume_group,
                             capture=True, remove_empty=True)

    logical_volumes = list()

    for line in out:
        parts = line.split(":")
        logical_volumes.append(parts[0])

    try:
        yield logical_volumes
    except:
        log.error("exception thrown", exc_info=sys.exc_info())
    finally:
        lvm("vgchange", "-a", "n", volume_group)
        udevadm("settle")


@contextlib.contextmanager
def mounted_device(device, mountpoint, **opts):
    args = []

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
    except:
        log.error("exception thrown", exc_info=sys.exc_info())
    finally:
        umount(mountpoint)


@contextlib.contextmanager
def entered_system(path, volume_group, mountpoint):
    with mounted_loopback(path) as devices:
        with available_lvm(volume_group) as logical_volumes:
            mounts = contextlib.nested(
                mounted_device(logical_volumes[0], mountpoint),
                mounted_device("null", "{0}/proc".format(mountpoint),
                               mount_type="proc"),
                mounted_device("/dev", "{0}/dev".format(mountpoint),
                               mount_bind=True))

            with mounts:
                yield devices, logical_volumes, mountpoint


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
    for (device, subdevices) in sorted(devices.items()):
        return device

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

    os.mkdir(target_path, mode)

    chroot(ns.mountpoint, "chown", "{0}:{1}".format(owner, group),
           abs_target_path)
