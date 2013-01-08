#!/usr/bin/python
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
import sys
import argparse
import logging
import yaml

__version__ = (0, 2, 0)
__version_string__ = ".".join(map(str, __version__))

from vdisk.actions.install import action as action_install
from vdisk.actions.create import action as action_create
from vdisk.actions.bootstrap import action as action_bootstrap
from vdisk.actions.enter import action as action_enter
from vdisk.actions.puppet import action as action_puppet

log = logging.getLogger(__name__)


class sizeunit(object):
    units = {
        't': 10 ** 13,
        'g': 10 ** 9,
        'm': 10 ** 6,
        'k': 10 ** 3,
        'T': 2 ** 40,
        'G': 2 ** 30,
        'M': 2 ** 20,
        'K': 2 ** 10,
        'b': 1,
    }

    DEFAULT_UNIT = 'B'

    def __init__(self, string):
        self.size = self._parse_size(string)

    def _parse_size(self, string):
        unit = string[-1]
        conversion = self.units.get(unit)

        if conversion is not None:
            return int(string[:-1]) * conversion

        return int(string)


def read_config(path):
    if not os.path.isfile(path):
        raise Exception("Missing configuration: {0}".format(path))

    with open(path) as f:
        return yaml.load(f)


def setup_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--version", action="version",
                        version="vdisk " + __version_string__)
    parser.add_argument("--root",
                        metavar="<dir>",
                        help="Root directory of project, default: {default}",
                        default=os.getcwd())

    parser.add_argument("--log-level", default=logging.INFO,
                        metavar="<level>",
                        help=("Set log level, valid values are: "
                              "DEBUG, INFO, ERROR. Default: INFO"),
                        type=lambda l: getattr(logging, l.upper(),
                                               logging.INFO))
    parser.add_argument("-V", "--volume-group",
                        metavar="<name>",
                        help="Name of volume group, default: VolGroup00",
                        default="VolGroup00")
    parser.add_argument("-m", "--mountpoint",
                        metavar="<dir>",
                        help="Mount point for disk images, default: tmp/mount",
                        default="tmp/mount")
    parser.add_argument("-S", "--shell",
                        metavar="<bin>",
                        help="Shell to use in chroot, default: /bin/sh",
                        default="/bin/sh")
    parser.add_argument("-A", "--apt-get", dest="apt_get",
                        metavar="<bin>",
                        help="Apt get to use in chroot, default: apt-get",
                        default="apt-get")
    parser.add_argument("-D", "--dpkg", dest="dpkg",
                        metavar="<bin>",
                        help="Dpkg to use in chroot, default: apt-get",
                        default="dpkg")
    parser.add_argument("-G", "--gem",
                        metavar="<bin>",
                        help="Gem to use in chroot, default: gem",
                        default="gem")
    parser.add_argument("-M", "--mirror",
                        metavar="<url>",
                        default="http://ftp.se.debian.org/debian",
                        help=("Installation mirror, default: "
                              "http://ftp.se.debian.org/debian"))

    parser.add_argument("-c", "--config",
                        metavar="<config>",
                        help="vdisk configuration",
                        default=None)
    parser.add_argument("path",
                        metavar="<image>",
                        help="Path to image")

    actions = parser.add_subparsers()

    create = actions.add_parser("create",
                                help="Create a new disk image")

    create.add_argument("-s", "--size",
                        help="Size of image, default: 8G",
                        metavar="<size>",
                        default=sizeunit("8G"),
                        type=sizeunit)
    create.add_argument("-f", "--force",
                        help="Force creation, even if file exists",
                        default=False,
                        action="store_true")
    create.set_defaults(action=action_create)

    bootstrap = actions.add_parser("bootstrap",
                                   help=("bootstrap a new disk image w/ "
                                         "debootstrap"))
    bootstrap.add_argument("-S", "--suite", default="squeeze",
                           help="Installation suite, default: squeeze")
    bootstrap.add_argument("-A", "--arch", default="amd64",
                           help="Installation architecture, default: amd64")
    bootstrap.set_defaults(action=action_bootstrap)

    install = actions.add_parser("install",
                                 help=("Install packages and selections into "
                                       "a disk image"))
    install.add_argument("selections",
                         metavar="<file>",
                         nargs='?',
                         help="List of selections",
                         default=None)
    install.add_argument("-d", "--download",
                         help="Only download the selections, don't install.",
                         default=False,
                         action="store_true")
    install.set_defaults(action=action_install)

    enter = actions.add_parser("enter",
                               help="Open a shell into a disk image")

    enter.set_defaults(action=action_enter)

    puppet = actions.add_parser("puppet",
                                help="Run puppet inside a disk image")
    puppet.add_argument("puppetpath",
                        metavar="<dir>",
                        help="Path to puppet modules")
    puppet.add_argument("-F", "--fact", dest="facts", action='append',
                        metavar="<name>=<value>",
                        help="Override puppet facts")
    puppet.add_argument("puppetargs",
                        metavar="<puppet-args...>",
                        help="Arguments passed into puppet",
                        nargs=argparse.REMAINDER)

    puppet.set_defaults(action=action_puppet)

    return parser


def main(args):
    logging.basicConfig(level=logging.INFO)
    parser = setup_argument_parser()
    ns = parser.parse_args(args)
    logging.getLogger().setLevel(ns.log_level)

    if os.getuid() != 0:
        log.error("vdisk uses loopback mounting, and needs to be run as root")
        return -1

    if ns.config is None:
        ns.config = os.path.join(ns.root, "vdisk.yaml")

    ns.config = read_config(ns.config)
    return ns.action(ns)


def entry():
    sys.exit(main(sys.argv[1:]))
