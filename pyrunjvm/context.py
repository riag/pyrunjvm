
from string import Template
import os
import sys
import logging
import subprocess

import pybee

import tomlkit
from tomlkit.toml_file import TOMLFile

from .util import is_str
import jinja2
import io

class Project(object):
    def __init__(self, name, path, config):
        self.name = name
        self.path = path
        self.config = config

        self.jvm_arg_list = []

        self.log_file = None
        # Popen 对象
        self.proc = None


class Context(object):
    def __init__(self, platform, work_dir, config, env=None):
        self.platform = platform
        self.work_dir = work_dir 
        self.dest_dir = os.path.join(work_dir, '.pyrunjvm')

        self.no_config = False
        self.no_run = False

        self.project_list = []

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

        java_bin = self.get_env('JAVA_BIN')
        if java_bin is None:
            java_home = self.get_env('JAVA_HOME')
            if java_home:
                java_bin = os.path.join(java_home, 'bin', 'java')

        if java_bin is None:
            java_bin = 'java'

        self.java_bin = java_bin
        self.debug_port_info_list = []

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
    
    def create_project(self, project_config):
        path = project_config.get('path')
        name = os.path.dirname(path)
        name = project_config.get('name', name)
        p = Project(name, path, project_config)
        self.project_list.append(p)
        return p

    def gen_vscode_launch_file(self):
        '''
        vscode launch file format:
        https://code.visualstudio.com/Docs/editor/debugging#_compound-launch-configurations
        '''
        launch_tpl = '''{
  "version": "0.2.0",
  "configurations": [
      {% for info in debug_port_info_list %}
    {
      "type": "java",
      "request": "attach",
      "name": "{{ info.name }}",
      "port": {{ info.port }}
    }
    {% endfor %}
  ]
}
        '''
        p = os.path.join(self.dest_dir, 'launch.json')
        t = jinja2.Template(launch_tpl) 
        m = {
            "debug_port_info_list": self.debug_port_info_list
        }
        s = t.render(m)
        with io.open(p, 'w', encoding='UTF-8') as f:
            f.write(s)



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