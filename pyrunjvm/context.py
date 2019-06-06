
from string import Template
import os
import sys
import logging
import subprocess

import pybee

import tomlkit
from tomlkit.toml_file import TOMLFile

from .util import is_str

class Context(object):
    def __init__(self, platform, work_dir, config, env=None):
        self. platform = platform
        self.work_dir = work_dir 
        self.dest_dir = os.path.join(work_dir, '.pyrunjvm')

        pybee.path.mkdir(self.dest_dir, True)

        self.config = config
        self.environ = {}
        self.environ.update(os.environ)

        default_env = config.get('env', None)
        if default_env:
            self.environ.update(default_env)

        if env:
            self.environ.update(env)

        
        self.environ['WORK_DIR'] = work_dir

        self.jvm_arg_list = []

        jvm_opts = config.get('jvm_opts', None)
        if jvm_opts:
            self.jvm_arg_list.extend(jvm_opts)

        self.debug_port = self.get_env('JVM_DEBUG_PORT', 50899)

        self.jvm_arg_list.append('-Xdebug') 
        self.jvm_arg_list.append(
            '-Xrunjdwp:transport=dt_socket,server=y,suspend=n,address=127.0.0.1:%d' % self.debug_port
        )

    def get_env(self, name, default=None):
        value = self.environ.get(name, None)
        if value is None:
            value = default

        if not is_str(value):
            return value

        return self.resolve_str_value(value, self.environ)


    def resolve_config_value(self, value):
        if not is_str(value):
            return value

        return self.resolve_str_value(value, self.config, **self.environ)

    def resolve_str_value(self, value, mapping, **kwds):
        old_v = value
        while True:
            if '$' not in old_v:
                return old_v 

            t = Template(old_v)
            v = t.safe_substitute(mapping, **kwds)
            if old_v == v:
                return v

            old_v = v

        return None

    def run(self, **kwargs):
        java_bin = self.get_env('JAVA_BIN')
        if java_bin is None:
            java_home = self.get_env('JAVA_HOME')
            if java_home:
                java_bin = os.path.join(java_home, 'bin', 'java')

        if java_bin is None:
            java_bin = 'java'

        jvm_cmd_list = [java_bin,]
        jvm_cmd_list.extend(self.jvm_arg_list)

        cmd = ' '.join(jvm_cmd_list)
        logging.debug('execute cmd: %s', cmd)
        if kwargs.get('shell', None) is None:
            kwargs['shell'] = True
        subprocess.check_call(cmd, **kwargs)


def create_context(platform, work_dir, config_file, env):
    if not os.path.isfile(config_file):
        logging.error("config file %s is not exist", config_file)
        return None

    if not os.path.isabs(config_file):
        config_file = os.path.abspath(config_file)

    toml = TOMLFile(config_file)
    config = toml.read()
    logging.debug('config file content:')
    logging.debug(config)

    return Context(
        platform, work_dir, 
        config, env)