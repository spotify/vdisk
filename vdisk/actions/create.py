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


def action(ns):
    """
    Create base image with lvm.
    """
    if not ns.force and os.path.isfile(ns.image_path):
        raise Exception("path already exists: {0}".format(ns.image_path))

    with open(ns.image_path, "w") as f:
        f.truncate(ns.size.size)

    ns.preset.setup_disks()
