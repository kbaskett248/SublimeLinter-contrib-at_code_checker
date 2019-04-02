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
from contextlib import contextmanager
import errno
import logging
import os
import platform
import re
import subprocess
import tempfile
import webbrowser

import sublime
import sublime_plugin

from SublimeLinter.lint import Linter, util

logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')

RING_MATCHER = re.compile(
    r"((.*?\\([^:\\\/\n]+?)\.Universe)\\([^:\\\/\n]+?)\.Ring)(?![^\\])",
    re.IGNORECASE)


def get_mtad_linter_path():
    """Return the path containing the mtad AT Code Checker executable.

    Return:
        str: Path containing at_code_checker.exe

    """
    return os.path.expandvars(os.path.join(
        "%PROGRAMFILES(X86)%", "MEDITECH", "M-AT Tools", "M-AT_Code_Checker"))


def get_bundled_linter_path():
    """Return the path that contains the bundled AT Code Checker executable.

    Return:
        str: Path that containat_code_checker.exe

    """
    return os.path.join(sublime.packages_path(),
                        'SublimeLinter-contrib-at_code_checker',
                        'at_code_checker')


def get_possible_paths():
    """Return possible paths for the linter."""
    yield ('mtad', get_mtad_linter_path())
    yield ('bundled', get_bundled_linter_path())


def bundled_warning():
    logger.warning(
        "Using bundled version of the AT Code Checker. This version is out "
        "of date. Please install the mtad version. Instructions can be "
        "found here: "
        "https://docs.google.com/document/d/1BQFGeg9pmIFmmQr2CPjIwRI_A4_LdhfRXwhWcJ3nM9s/edit")


def create_dir(dir_):
    """Make the directory if it doesn't exist. If it does, just eat exception."""
    try:
        os.makedirs(dir_)
        logger.debug("Creating directory %s", dir_)
    except OSError as err:
        if err.errno != errno.EEXIST:
            raise


def get_env(environ_name):
    """Return the value of the given environment variable."""
    temp = os.getenv(environ_name)
    if temp is None:
        if ('ProgramFiles' in environ_name) or ('ProgramW6432' in environ_name):
            temp = os.getenv('ProgramFiles')
    return temp


class At_code_checker(Linter):

    """Provides an interface to at_code_checker."""

    cmd = 'at_code_checker @'
    regex = (
        r"^(?P<filename>.+?) +(?P<line>\d+) : "
        r"(?P<message>(("
        r"(?P<warning>Subroutine|Line|Local variable|Do not call|List member|"
        r"Unusual result type,|Unknown formal doc keyword:|Avoid|"
        r"Button with no defined|Unassigned #Local|Use @OV rather than|"
        r"#Local|Double commas|Use message functions|There is a TODO or XXX)|"
        r"(?P<error>(Unknown M-AT function|Unknown attribute - [^ ]+? [^ ]+|"
        r"Undefined #Local|Un-referenced #Local|@HV without|"
        r"Too many translation arguments to|"
        r"System variable should only be modified by MIS or FOC utilities -))"
        r") "
        r"(?P<near>[^ (]+).*|.+))"
    )
    line_col_base = (1, 1)
    tempfile_suffix = 'atcc'
    error_stream = util.STREAM_BOTH
    defaults = {"selector": "source.focus"}

    Dir_Map = dict()

    LastIncludeMatch = None

    @classmethod
    def which(cls, cmd):
        """Return the path for the linter executable."""
        return cls.mtad_path(cmd) or cls.bundled_path(cmd)

    @staticmethod
    def mtad_path(cmd):
        linter_path = os.path.expandvars(os.path.join(
            "%PROGRAMFILES(X86)%", "MEDITECH", "M-AT Tools",
            "M-AT_Code_Checker", cmd + ".exe"))
        logger.debug('mtad path=%s', linter_path)
        if os.path.exists(linter_path):
            return linter_path
        else:
            return None

    @staticmethod
    def bundled_path(cmd):
        linter_path = os.path.join(get_bundled_linter_path(), cmd + '.exe')
        logger.debug('bundled_path=%s', linter_path)

        if not os.path.exists(linter_path):
            return None
        else:
            logger.warning("Using bundled version of the AT Code Checker. "
                           "This version is out of date. Please install the "
                           "mtad version. Instructions can be found here: "
                           "https://docs.google.com/document/d/"
                           "1BQFGeg9pmIFmmQr2CPjIwRI_A4_LdhfRXwhWcJ3nM9s/edit")
            return linter_path

    def split_match(self, match):
        """Extracts data from each error result returned from the command.

        Data is extracted using the regex. A tuple of data is returned.

        Arguments:
            match (re.Match): An re.Match object obtained by using the object's
                regex attribute and an error line

        Returns:
            tuple: match - the match object
                   line - the line on which the error occurred
                   col - the column on which the error occurred
                   error - Truthy value if the line indicates an error. Falsey
                        value otherwise.
                   warning - Truthy value if the line indicates a warning.
                        Falsey value otherwise.
                   message - Message text for the error or warning
                   near - Text value that the error is near. This text is
                        underlined when displayed.

        """
        match, line, col, error, warning, message, near = super().split_match(match)

        no_doc_index = message.find("has no :Doc")
        if no_doc_index > 0:
            error = False
            warning = "Warning"
            near = message[:no_doc_index].strip()
        elif message.startswith("@HV"):
            near = "@HV"

        if error:
            error = " "
        elif warning:
            warning = " "
        else:
            error = " "

        if (match is None) or match.group('filename').startswith('atcc-'):
            return match, line, col, error, warning, message, near

        temp_name = match.group('filename')
        if ((self.LastIncludeMatch is not None) and
                (self.LastIncludeMatch[0:2] == (self.filename, temp_name))):
            region = self.LastIncludeMatch[2]
        else:
            region = self.view.find(r"\s*File\s+" + temp_name, 0)
            self.LastIncludeMatch = (self.filename, temp_name, region)

        if region is not None:
            line = self.view.rowcol(region.begin())[0] + 1
            near = temp_name
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

        with self._make_temp_file(code) as temp_path:
            cmd = list(cmd)

            if '@' in cmd:
                cmd[cmd.index('@')] = temp_path
            else:
                cmd.append(temp_path)

            return self._communicate(cmd)

    @contextmanager
    def _make_temp_file(self, code):
        """A context manage to create a temp file for the linter to run on.

        Create a temp file with the same universe and ring as the current
        file, and write the specified code to it.

        When leaving the context manage, delete the file.

        Arguments:
            code: str: The code to write to the file

        Returns:
            str: The path to the temp file.

        """
        temp = None
        try:
            with tempfile.NamedTemporaryFile(prefix='atcc-',
                                             suffix='.focus',
                                             delete=False,
                                             dir=self.tmpdir()) as temp:

                logger.debug("'temp_file=%s", temp.name)

                if isinstance(code, str):
                    code = code.encode('utf-8')

                temp.write(code)
                temp.flush()
            yield temp.name
        finally:
            if temp:
                os.remove(temp.name)

    def tmpdir(self):
        """Return the temp file directory for the current file.

        A map is maintained from file path to temp file directory to improve
        performance.

        """
        dir_ = os.path.dirname(self.filename)
        try:
            path = At_code_checker.Dir_Map[dir_.lower()]
            if not os.path.isdir(path):
                create_dir(path)
        except KeyError:
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
        ring_mo = RING_MATCHER.match(self.filename)
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
                self._meditech_cache_root = os.path.join(
                    get_env('ALLUSERSPROFILE'), 'Application Data', 'Meditech')
            else:
                self._meditech_cache_root = os.path.join(
                    get_env('ALLUSERSPROFILE'), 'Meditech')
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
        """Run the configuration utility for AT Code Checker."""
        for type_, path in get_possible_paths():
            config_path = os.path.join(path, 'configuration.exe')

            if os.path.exists(config_path):
                subprocess.Popen(config_path)
                if type_ == 'bundled':
                    bundled_warning()
                break


class OpenWebPageCommand(sublime_plugin.WindowCommand):
    """Command to opens the specified url in the default browser."""

    def run(self, url=''):
        """Logic used when executing the command.

        Keyword Arguments:
            url (str): URL string to open.

        """
        if url:
            webbrowser.open(url)

    def is_visible(self, url=''):
        """Determine if the command should be visible.

        Keyword Arguments:
            url (str): URL string to open.

        Return:
            bool: True if the command should be visible. False otherwise.

        """
        return bool(url)
