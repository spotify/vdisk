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

import logging
import os
import subprocess as sp

log = logging.getLogger(__name__)


class ExternalCommandException(Exception):
    def __init__(self, exitcode, message):
        self.exitcode = exitcode
        super(ExternalCommandException, self).__init__(message)


class _PrefixedExternalCommand(object):
    def __init__(self, external_command, *prefix_args):
        self.external_command = external_command
        self.prefix_args = prefix_args

    def prefix(self, *prefix_args):
        return _PrefixedExternalCommand(self, *prefix_args)

    def __call__(self, *args, **kw):
        args = list(self.prefix_args) + list(args)
        return self.external_command.__call__(*args, **kw)


class ExternalCommand(object):
    def __init__(self, binary):
        self.binary = binary

    def prefix(self, *prefix_args):
        """
        Create a callable which prefixes the command invication.

        This is useful for commands which have a common re-occurence of certain
        arguments.
        """

        return _PrefixedExternalCommand(self, *prefix_args)

    def __call__(self, *args, **opts):
        raise_on_exit = opts.get("raise_on_exit", True)
        split_output = opts.get("split_output", True)
        capture = opts.get("capture", False)
        remove_empty = opts.get("remove_empty", False)
        env = opts.get("env")
        input_fd = opts.get("input_fd")

        args = [self.binary] + map(str, args)

        log.debug("command: {0}".format(" ".join(args)))

        kwargs = dict()

        if env:
            new_env = dict(os.environ)
            new_env.update(env)
            kwargs["env"] = new_env

        if input_fd:
            kwargs["stdin"] = input_fd

        if capture:
            kwargs["stdout"] = sp.PIPE
            kwargs["stderr"] = sp.PIPE

        try:
            p = sp.Popen(args, **kwargs)
        except Exception:
            log.error("Exception thrown when executing: %s" % " ".join(args))
            raise

        if capture:
            stdout, stderr = p.communicate()
        else:
            stdout, stderr = (None, None)

        exitcode = p.wait()

        if capture and split_output:
            stdout = stdout.split(os.linesep)
            stderr = stderr.split(os.linesep)

            if remove_empty:
                strip = lambda s: s.strip()
                stdout = filter(bool, map(strip, stdout))
                stderr = filter(bool, map(strip, stderr))

        if raise_on_exit and exitcode != 0:
            raise ExternalCommandException(
                exitcode,
                "{0}: subprocess returned non-zero exit code".format(
                    " ".join(args)))

        return exitcode, stdout, stderr
