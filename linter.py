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
import subprocess
import tempfile

import sublime
import sublime_plugin

from SublimeLinter.lint import Linter, util

try:
    from Focus.src.Managers.RingFileManager import RingFileManager
    FILE_MANAGER = RingFileManager.getInstance()
    FocusImported = True
except ImportError:
    FocusImported = False

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

class At_code_checker(Linter):

    """Provides an interface to at_code_checker."""

    syntax = ('m-at', 'focus')
    cmd = 'at-code-checker @'
    regex = (
        r'^.+? +(?P<line>\d+) : '
        r'(?P<message>(((?P<warning>Subroutine|Line|Local variable)|(?P<error>(Unknown M-AT function|Unknown attribute - [^ ]+ [^ ]+))) (?P<near>[^ ]+).*|.+))'
    )
    line_col_base = (1, 1)
    tempfile_suffix = 'atcc'
    error_stream = util.STREAM_BOTH
    selectors = {}
    defaults = {}

    @classmethod
    def which(cls, cmd):
        """Return the path for the linter executable."""
        linter_path = os.path.join(get_linter_path(), 'at_code_checker.exe')

        if not os.path.exists(linter_path):
            return None
        else:
            return linter_path

    # def tmpfile(self, cmd, code, suffix=''):
    #     """Run an external executable using a temp file to pass code and return its output."""
    #     return At_code_checker.tmpfilehelper(
    #         cmd,
    #         code,
    #         suffix or self.get_tempfile_suffix(),
    #         output_stream=self.error_stream,
    #         env=self.env,
    #         dir_=os.path.basename(self.filename))

    def tmpfile(self, cmd, code, suffix=''):
        """
        Return the result of running an executable against a temporary file containing code.

        It is assumed that the executable launched by cmd can take one more argument
        which is a filename to process.

        The result is a string combination of stdout and stderr.
        If env is not None, it is merged with the result of create_environment.

        """

        f = None
        suffix = suffix or self.get_tempfile_suffix()

        print('temp_dir = %s' % self.get_temp_dir())

        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, 
                                             delete=False, 
                                             dir=self.get_temp_dir()) as f:
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

    def get_temp_dir(self):
        if 'SoloFocus' in self.filename:
            return os.path.dirname(self.filename)
        elif not FocusImported:
            return None
        else:
            # ring_file = FILE_MANAGER.get_ring_file(self.view)
            # print('ring_file = %s' % ring_file)
            # print('ring_object = %s' % ring_file.ring_object)
            # if (ring_file is None) or (ring_file.ring_object is None):
            #     return None
            # partial = ring_file.ring_object.partial_path(self.filename)
            # print('partial = %s' % partial)
            # try:
            #     cache_path = ring_file.ring_object.cache_path
            # except AttributeError:
            #     return None
            # if not os.path.exists(cache_path):
            #     return None
            # path = os.path.join(ring_file.ring_object.cache_path, partial)
            # print('path = %s' % path)
            # dir_ = os.path.dirname(path)
            # print('dir_ = %s' % dir_)
            # try:
            #     create_dir(dir_)
            #     return dir_
            # except Exception:
            #     pass
            
            return None


class ConfigureCodeCheckerCommand(sublime_plugin.ApplicationCommand):
    """Runs the built-in configuration utility for AT Code Checker."""

    def run(self):

        configuration_path = os.path.join(get_linter_path(), 'configuration.exe')

        if os.path.exists(configuration_path):
            subprocess.Popen(configuration_path)