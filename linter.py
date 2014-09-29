#
# linter.py
# Linter for SublimeLinter3, a code checking framework for Sublime Text 3
#
# Written by kbaskett
# Copyright (c) 2014 kbaskett
#
# License: MIT
#

"""This module exports the At_code_checker plugin class."""
import errno
import os
import platform
import re
import subprocess
import tempfile

import sublime
import sublime_plugin

from SublimeLinter.lint import Linter, util

ring_matcher = re.compile(
    r"((.*?\\([^:\\\/\n]+?)\.Universe)\\([^:\\\/\n]+?)\.Ring)(?![^\\])",
    re.IGNORECASE)


def get_linter_path():
    return os.path.join(sublime.packages_path(),
                        'SublimeLinter-contrib-at_code_checker',
                        'at_code_checker')


def create_dir(dir):
    """Make the directory if it doesn't exist. If it does, just eat exception."""
    print("Creating dir " + dir)
    try:
        os.makedirs(dir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def get_env(environ_name):
    """Return the value of the given environment variable."""
    temp = os.getenv(environ_name)
    if (temp is None):
        if ('ProgramFiles' in environ_name) or ('ProgramW6432' in environ_name):
            temp = os.getenv('ProgramFiles')
    return temp


class At_code_checker(Linter):

    """Provides an interface to at_code_checker."""

    syntax = ('m-at', 'focus')
    cmd = 'at-code-checker @'
    regex = (
        r"^(?P<filename>.+?) +(?P<line>\d+) : "
        r"(?P<message>(("
        r"(?P<warning>Subroutine|Line|Local variable|Do not call|List member|"
        r"Unusual result type,|Unknown formal doc keyword:|Avoid|"
        r"Button with no defined)|"
        r"(?P<error>(Unknown M-AT function|Unknown attribute - [^ ]+? [^ ]+))"
        r") "
        r"(?P<near>[^ (]+).*|.+))"
    )
    line_col_base = (1, 1)
    tempfile_suffix = 'atcc'
    error_stream = util.STREAM_BOTH
    selectors = {}
    defaults = {}

    Dir_Map = dict()

    LastIncludeMatch = None

    @classmethod
    def which(cls, cmd):
        """Return the path for the linter executable."""
        linter_path = os.path.join(get_linter_path(), 'at_code_checker.exe')

        if not os.path.exists(linter_path):
            return None
        else:
            return linter_path

    def split_match(self, match):
        match, line, col, error, warning, message, near = super().split_match(match)
        if (match is None) or match.group('filename').endswith('.atcc'):
            return match, line, col, error, warning, message, near

        fname = match.group('filename')
        if ((self.LastIncludeMatch is not None) and
                (self.LastIncludeMatch[0:2] == (self.filename, fname))):
            region = self.LastIncludeMatch[2]
        else:
            region = self.view.find(r"\s*File\s+" + fname, 0)
            self.LastIncludeMatch = (self.filename, fname, region)

        if region is not None:
            line = self.view.rowcol(region.begin())[0] + 1
            near = fname
            return match, line, col, error, warning, message, near
        else:
            return match, None, None, None, None, None, None

    def tmpfile(self, cmd, code, suffix=''):
        """
        Return the result of running an executable against a temporary file containing code.

        This is overridden since the location of the temp folder varies based
        on the file.

        It is assumed that the executable launched by cmd can take one more argument
        which is a filename to process.

        The result is a string combination of stdout and stderr.
        If env is not None, it is merged with the result of create_environment.

        """

        # Don't run for DataDefs or !DictionarySource
        if 'DataDefs' in self.filename:
            return ''
        elif '!DictionarySource' in self.filename:
            return ''

        f = None

        suffix = suffix or self.get_tempfile_suffix()

        # print('temp_dir = %s' % self.tmpdir())

        try:
            with tempfile.NamedTemporaryFile(suffix=suffix,
                                             delete=False,
                                             dir=self.tmpdir()) as f:
                if isinstance(code, str):
                    code = code.encode('utf-8')

                f.write(code)
                f.flush()

            print('temp_file = ', f.name)

            cmd = list(cmd)

            if '@' in cmd:
                cmd[cmd.index('@')] = f.name
            else:
                cmd.append(f.name)

            out = util.popen(cmd, output_stream=util.STREAM_STDOUT, extra_env=self.env)

            if out:
                out = out.communicate()
                return util.combine_output(out)
            else:
                return ''
        finally:
            if f:
                os.remove(f.name)

    def tmpdir(self):
        """Return the temp file directory for the current file.

        A map is maintained from file path to temp file directory to improve
        performance.

        """
        dir_ = os.path.dirname(self.filename)
        try:
            path = At_code_checker.Dir_Map[dir_.lower()]
            # print('No need to recalculate')
        except KeyError:
            # print('recalculating temp dir')
            path = self.get_temp_dir()
            At_code_checker.Dir_Map[dir_.lower()] = path
        finally:
            return path

    def get_temp_dir(self):
        """Compute and return the temp directory for the current file.

        As long as the file is in a valid M-AT ring structure, the temp
        directory is in the ring's temporary cache directory. Otherwise, the
        default temp directory is returned.

        """
        base = tempfile.gettempdir()
        ring_mo = ring_matcher.match(self.filename)
        if not ring_mo:
            return base

        universe = ring_mo.group(3) + '.Universe'
        ring = ring_mo.group(4) + '.Ring'
        if 'SoloFocus' in self.filename:
            ring += '.Local'

        temp_dir = self.meditech_pgmsource_cache(universe, ring)
        if not os.path.exists(temp_dir):
            if os.path.exists(os.path.dirname(temp_dir)):
                try:
                    create_dir(temp_dir)
                except OSError:
                    return base
            else:
                return base

        codebase = os.path.basename(os.path.dirname(self.filename))
        temp_dir = os.path.join(temp_dir, codebase)

        try:
            create_dir(temp_dir)
        except OSError:
            return base
        else:
            return temp_dir

    @property
    def meditech_cache_root(self):
        """Return the root of the Meditech cache."""
        result = None
        try:
            result = self._meditech_cache_root
        except AttributeError:
            version = int(platform.win32_ver()[1].split('.', 1)[0])
            if (version <= 5):
                self._meditech_cache_root = os.path.join(get_env('ALLUSERSPROFILE'),
                                                'Application Data',
                                                'Meditech')
            else:
                self._meditech_cache_root = os.path.join(get_env('ALLUSERSPROFILE'),
                                                'Meditech')
            result = self._meditech_cache_root
        finally:
            return result

    def meditech_pgmsource_cache(self, universe, ring):
        """Return the PgmSource cache for the given universe and ring."""
        return os.path.join(self.meditech_cache_root, universe, ring, '!AllUsers',
                            'Sys', 'PgmCache', 'Ring', 'PgmSource')


class ConfigureCodeCheckerCommand(sublime_plugin.ApplicationCommand):
    """Runs the built-in configuration utility for AT Code Checker."""

    def run(self):

        configuration_path = os.path.join(get_linter_path(), 'configuration.exe')

        if os.path.exists(configuration_path):
            subprocess.Popen(configuration_path)
