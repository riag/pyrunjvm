
from string import Template
import os
import logging

import pybee

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


def create_context(config_file, env):

    platform = sys.platform
    logging.info('platform : %s', platform)

    if not os.path.isabs(config_file):
        config_file = os.path.abspath(config_file)

    work_dir = os.path.dirname(config_file)

    env_file = os.path.join(CURRENT_WORK_DIR, '.env.toml')

    config = load_tomlfile(config_file)
    logging.debug('config file content:')
    logging.debug(config)

    env = None
    if os.path.isfile(env_file):
        env = load_env_file(env_file, platform)
        logging.debug(env)

    return Context(
        platform, CURRENT_WORK_DIR, 
        config, env)