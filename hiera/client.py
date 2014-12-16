#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Python client for Hiera hierachical database."""

from __future__ import print_function, unicode_literals

import logging
import os
import os.path
import subprocess
import json

import hiera.exc

__all__ = ('HieraClient',)


class HieraClient(object):
    __doc__ = __doc__

    def __init__(self, config_filename, hiera_binary='hiera', **kwargs):
        """Create a new instance with the given settings.

        Key value params passed into this will be added to the environment when
        running the hiera client. For example, (environment='developer',
        osfamily='Debian') as keyword args to __init__ would result in hiera
        calls like this:

          hiera --config <config_filename> <key> environment=developer \
            osfamily=Debian

        :param config_filename: Path to the hiera configuration file.
        :param hiera_binary: Path to the hiera binary. Defaults to 'hiera'.
        """
        self.config_filename = config_filename
        self.hiera_binary = hiera_binary
        self.environment = kwargs

        self._validate()
        logging.debug('New Hiera instance: {0}'.format(self))

    def __repr__(self):
        """String representations of Hiera instance."""
        def kv_str(key):
            """Takes an instance attribute and returns a string like:
            'key=value'
            """
            return '='.join((key, repr(getattr(self, key, None))))

        params_list = map(kv_str,
                          ['config_filename', 'hiera_binary', 'environment'])
        params_string = ', '.join(params_list)
        return '{0}({1})'.format(self.__class__.__name__, params_string)

    def get(self, key_name, lookup_type=None):
        """Request the given key from hiera.

        Returns the string version of the key when successful.

        Raises :class:`hiera.exc.HieraError` if the key does not exist or there
        was an error invoking hiera. Raises
        :class:`hiera.exc.HieraNotFoundError` if the hiera CLI binary could not
        be found.

        :param key_name: string key
        :rtype: str value for key or None
        """

        try:
            value = self._hiera(key_name, lookup_type)

        except hiera.exc.HieraError:
            if lookup_type is None:
                value = ''
            elif lookup_type == dict:
                value = dict()
            elif lookup_type == list:
                value = []

        return value


    def _command(self, key_name, lookup_type=None):
        """Returns a hiera command list that is suitable for passing to
        subprocess calls.

        :param key_name:
        :rtype: list that is hiera command
        """

        lookup_cmd = None

        if lookup_type is not None:
            lookup_cmd = "--%s" % { list: 'array', dict: 'hash' }[lookup_type]

        cmd = [self.hiera_binary,
               '--config', self.config_filename,
               key_name]

        if lookup_cmd is not None:
            cmd.insert(1, lookup_cmd)

        cmd.extend(map(lambda *env_var: '='.join(*env_var),
                       self.environment.iteritems()))
        return cmd

    def _to_dict_or_list(self, string):
        """Converts a ruby hash to json"""

        string = string.replace('\n','')
        to_json_cmd = ['ruby', '-e', 'require "json"; puts JSON.generate(%s)' % string]
        json_output = subprocess.check_output(to_json_cmd, env=os.environ, stderr=subprocess.STDOUT)
        return json.loads(json_output)


    def _hiera(self, key_name, lookup_type=None):
        """Invokes hiera in a subprocess with the instance environment to query
        for the given key.

        Returns the string version of the key when successful.

        Raises HieraError if the key does not exist or there was an error
        invoking hiera. Raises HieraNotFoundError if the hiera CLI binary could
        not be found.

        :param key_name: string key
        :param lookup_type: lookup type = None, list or dict
        :rtype: str value for key or None
        """
        hiera_command = self._command(key_name, lookup_type)
        output = None
        try:
            output = subprocess.check_output(
                hiera_command,
                env=os.environ,
                stderr=subprocess.STDOUT)

            if lookup_type is not None:
                output = self._to_dict_or_list(output)

        except OSError as ex:
            raise hiera.exc.HieraNotFoundError(
                'Could not find hiera binary at: {0}'.format(
                    self.hiera_binary))
        except subprocess.CalledProcessError as ex:
            raise hiera.exc.HieraError(
                'Failed to retrieve key {0}. exit code: {1} '
                'message: {2} console output: {3}'.format(
                    key_name, ex.returncode, ex.message, ex.output))
        else:
            if isinstance(output, basestring):
                output = output.strip()

            if not output:
                return None
            else:
                return output

    def _validate(self):
        """Validate the instance attributes. Raises HieraError if issues are
        found.
        """
        if not os.path.isfile(self.config_filename):
            raise hiera.exc.HieraError(
                'Hiera configuration file does not exist '
                'at: {0}'.format(self.config_filename))
