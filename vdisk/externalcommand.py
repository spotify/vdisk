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
import logging
import os
import subprocess as sp

log = logging.getLogger(__name__)


class ExternalRunError(Exception):
    def __init__(self, exitcode, message):
        self.exitcode = exitcode
        super(ExternalRunError, self).__init__(message)


class ExternalCommand(object):
    def __init__(self, binary):
        self.binary = binary

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
            raise ExternalRunError(
                exitcode,
                "{0}: subprocess returned non-zero exit code".format(
                    " ".join(args)))

        return exitcode, stdout, stderr
