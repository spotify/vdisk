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
import re
import logging

log = logging.getLogger(__name__)

from vdisk.helpers import copy_file
from vdisk.helpers import create_directory
from vdisk.helpers import install_packages
from vdisk.helpers import write_mounted

from vdisk.externalcommand import ExternalCommand

chroot = ExternalCommand("chroot")

APTITUDE_ENV = {
    "DEBIAN_FRONTEND": "noninteractive",
    "DEBCONF_NONINTERACTIVE_SEEN": "true",
    "LC_ALL": "C",
    "LANGUAGE": "C",
    "LANG": "C",
}


def action(ns):
    if not os.path.isfile(ns.image_path):
        raise Exception("Missing image file: {0}".format(ns.image_path))

    if ns.selections is None:
        ns.selections = os.path.join(ns.root, "selections", "default")

    if not os.path.isfile(ns.selections):
        raise Exception("Missing selections file: {0}".format(ns.selections))

    with ns.preset.entered_system() as d:
        devices, logical_volumes, mountpoint = d

        # find first device as soon as possible
        apt_env = dict(APTITUDE_ENV)

        log.info("Configuring apt")
        configure_base_system(ns, apt_env, mountpoint)

        log.info("Install selected packages")

        if ns.download:
            download_selections(ns, apt_env, mountpoint)
        else:
            install_selections(ns, apt_env, mountpoint)

        ns.preset.setup_boot(devices, mountpoint)

        log.info("Writing fstab")
        fstab = generate_fstab(ns)
        write_mounted(mountpoint, "etc/fstab", fstab)

        log.info("Writing real device.map")
        new_devicemap = generate_devicemap(ns, logical_volumes)
        write_mounted(mountpoint, "boot/grub/device.map", new_devicemap)

        manifest = ns.config.get("manifest")
        postinst = ns.config.get("postinst")

        if manifest:
            install_manifest(ns, manifest)

        if postinst:
            execute_postinst(ns, postinst)

        chroot(ns.mountpoint, "update-initramfs", "-u")

    return 0


def generate_sources(sources, default_components=["main"],
                     default_source_type="deb"):
    for name, opts in sources.items():
        comment = opts.get("comment")
        url = opts.get("url")
        suite = opts.get("suite")

        if url is None:
            raise Exception("'url' required for source {0}".format(name))

        if suite is None:
            raise Exception("'suite' required for source {0}".format(name))

        source_type = opts.get("source_type", default_source_type)
        components = opts.get("components", default_components)

        if comment:
            yield "# {0}: {1}".format(name, comment)
        else:
            yield "# {0}".format(name)

        yield "{0} {1} {2} {3}".format(
            source_type, url, suite, " ".join(components))


def configure_base_system(ns, apt_env, mountpoint):
    prepackages = ns.config.get("pre-packages")

    if prepackages:
        log.info("Installing pre-required packages")
        install_packages(ns, mountpoint, prepackages,
                         env=apt_env,
                         extra=["-y", "--force-yes"])

    sources = ns.config.get("sources")

    if sources:
        log.info("Writing sources.list")
        sourceslist = generate_sources(sources)
        write_mounted(mountpoint, "etc/apt/sources.list", sourceslist)

    log.info("Updating apt")
    chroot(mountpoint, ns.apt_get, "-y", "update", env=apt_env)

    packages = ns.config.get("packages")

    if packages:
        log.info("Installing required packages")
        install_packages(ns, mountpoint, packages,
                         env=apt_env,
                         extra=["-y", "--force-yes"])

    log.info("Updating apt")
    chroot(mountpoint, ns.apt_get, "-y", "update", env=apt_env)


def download_selections(ns, apt_env, mountpoint):
    with open(ns.selections) as f:
        log.info("Setting selections")
        chroot(mountpoint, ns.dpkg, "--set-selections", env=apt_env,
               input_fd=f)

    log.info("Downloading selections")
    chroot(mountpoint, ns.apt_get, "-y", "-u", "--download-only",
           "dselect-upgrade", env=apt_env)


def install_selections(ns, apt_env, mountpoint):
    with open(ns.selections) as f:
        log.info("Setting selections")
        chroot(mountpoint, ns.dpkg, "--set-selections", env=apt_env,
               input_fd=f)

    log.info("Installing selections")

    write_mounted(ns.mountpoint, "usr/sbin/policy-rc.d", ["exit 101"])
    chroot(mountpoint, 'chmod', '755', '/usr/sbin/policy-rc.d')
    chroot(mountpoint, ns.apt_get, "-y", "-u",
           "dselect-upgrade", env=apt_env)
    chroot(mountpoint, 'rm', '-f', '/usr/sbin/policy-rc.d')


def generate_fstab(ns):
    yield "# auto-generated fstab from vdisk"
    yield ("/dev/mapper/{0}-root /       ext4    "
           "noatime 0 1").format(ns.volume_group)
    yield ("/dev/mapper/{0}-swap none    swap    "
           "sw      0 0").format(ns.volume_group)


def generate_devicemap(ns, logical_volumes):
    yield "(hd0) /dev/sda"

    for i, logical_volume in enumerate(logical_volumes):
        yield "(hd0,{0}) {1}".format(i, logical_volume)


def install_manifest(ns, manifest):
    log.info("Installing files from manifest")

    for target_item in manifest:
        target = target_item.get("target")
        if target is None:
            raise Exception("Target must be specified in manifest configuration")
        target = re.sub('^/', '', target)

        owner = target_item.get("owner", "root")
        group = target_item.get("group", "root")
        mode = target_item.get("mode", 0644)
        ftype = target_item.get("type", "file")

        if ftype == "file":
            source = target_item.get("source")
            if source is None:
                raise Exception("source must be specified in manifest configuration")
            log.info("Installing {0} to /{1}".format(source, target))
            copy_file(ns, source, target, owner=owner, group=group, mode=mode)
        elif ftype == "directory":
            log.info("Creating directory /{0}".format(target))
            create_directory(ns, target, owner=owner, group=group, mode=mode)
        else:
            raise Exception("Uknown manifest type: {0} ({1})".format(ftype, target))


def execute_postinst(ns, postinst):
    for trigger in postinst:
        chroot(ns.mountpoint, ns.shell, "-c", trigger)
