
import sys
import os
from string import Template

import subprocess
import logging

import click
import tomlkit
from tomlkit.toml_file import TOMLFile

import pybee

CURRENT_WORK_DIR = os.path.abspath(os.getcwd())
DEFAULT_CONFIG_FILE = os.path.join(CURRENT_WORK_DIR, '.pyrunjvm.toml')

def is_str(v):
    if type(v) in (str, tomlkit.items.String):
        return True

    return False

class Context(object):
    def __init__(self, work_dir, config, env=None):
        self.work_dir = work_dir 
        self.dest_dir = os.path.join(work_dir, '.pyrunjvm')
        pybee.path.mkdir(self.dest_dir, True)

        self.config = config
        self.environ = {}
        self.environ.update(os.environ)

        default_env = config.get('env-default', None)
        if default_env:
            self.environ.update(default_env)

        if env:
            self.environ.update(env)

        self.jvm_arg_list = []

        jvm_opts = config.get('jvm_opts', None)
        if jvm_opts:
            self.jvm_arg_list.extend(jvm_opts)

    def get_env(self, name):
        value = self.environ.get(name, None)
        if value is None:
            return value

        if not is_str(value):
            return value

        return self.resolve_str_value(value, self.environ)


    def resolve_config_value(self, value):
        if not is_str(value):
            return value


        print('resolve config value')
        return self.resolve_str_value(value, self.config, **self.environ)

    def resolve_str_value(self, value, mapping, **kwds):
        old_v = value
        while True:
            if '$' not in old_v:
                return old_v 

            print('start template')
            t = Template(old_v)
            v = t.safe_substitute(mapping, **kwds)
            if old_v == v:
                return v

            old_v = v

        return None
            

class AbastApplication(object):
    def __init__(self, context):
        self.context = context

    def prepare_config(self):
        pass

    def pre_handle(self):
        pass

    def handle_project(self, project_config):
        pass

    def post_handle(self):
        pass

tomcat_context_xml_tpl = '''<?xml version="1.0" encoding="UTF-8"?>
<Context path="/{context_path}" docBase="{war_path}" />
'''


class TomcatApplication(AbastApplication):
    def __init__(self, context):
        self.context = context
        self.tomcat_config = None
        self.port = None
        self.shutdowm_port = None
        self.ajp_port = None

        self.tomcat_dir = os.path.join(
            self.context.dest_dir, 'tomcat'
            )
        self.conf_dir = os.path.join(self.tomcat_dir, 'conf')
        self.logs_dir = os.path.join(self.tomcat_dir, 'logs')
        self.work_dir = os.path.join(self.tomcat_dir, 'work')
        self.temp_dir = os.path.join(self.tomcat_dir, 'temp')
        self.tomcat_context_dir = os.path.join(
            self.conf_dir, 'Catalina', 'localhost'
        )

        self.src_tomcat_home_dir = None

    def prepare_config(self):

        self.port = self.context.get_env('TOMCAT_PORT', 8080)
        self.shutdowm_port = self.context.get_env('TOMCAT_SHUTDOWN_PORT', -1)
        self.ajp_port = self.context.get_env('TOMAT_AJP_PORT', -1)

        self.src_tomcat_home_dir = self.context.get_env('TOMCAT_HOME')
        if not self.src_tomcat_home_dir:
            pass


    def pre_handle(self):
        pybee.path.mkdir(self.tomcat_context_dir, True)
        pybee.path.mkdir(self.temp_dir)
        pybee.path.mkdir(self.work_dir)
        pybee.path.mkdir(self.logs_dir)

        pybee.path.copytree(
            os.path.join(self.src_tomcat_home_dir, 'conf'),
            self.conf_dir
        )

    def handle_project(self, project_config):
        context_path = project_config.get('context_path')
        exploded_war_path = project_config.get('exploded_war_path')

        exploded_war_path = self.context.resolve_config_value(exploded_war_path)

        m = {
            'context_path': context_path,
            'war_path': exploded_war_path
        }
        s = tomcat_context_xml_tpl.format(**m)
        out_file = os.path.join(self.tomcat_context_dir, '%s.xml' % context_path)
        pybee.path.write_file_with_encoding(out_file, s)


    def post_handle(self):
        pass


application_map = {
    'tomcat': TomcatApplication,
}


def load_tomlfile(f):
    toml = TOMLFile(f)
    return toml.read()


def load_env_file(f):
    content = load_tomlfile(f)
    return content.get('env', None)

def create_context(config_file):

    if not os.path.isabs(config_file):
        config_file = os.path.abspath(config_file)

    work_dir = os.path.dirname(config_file)

    env_file = os.path.join(work_dir, '.env.toml')

    config = load_tomlfile(config_file)
    print(config)
    print('')

    env = None
    if os.path.isfile(env_file):
        env = load_env_file(env_file)
        print(env)

    return Context(work_dir, config, env)


def create_application(context):
    app_type = context.resolve_config_value(
        context.config.get('app_type')
    )
    if app_type.endwith('.py'):
        pass

    if '.' in app_type:
        pass

    app_cls = application_map.get(app_type, None)
    if app_cls is None:
        return None

    return app_cls(context)

def build(context):
    build_config = context.config['build']
    clear_cmds = build_config.get('clear_cmds', None)
    if clear_cmds:
        execute_cmds(context, clear_cmds)

    build_cmds = build_config.get('build_cmds')
    execute_cmds(context, build_cmds)


def execute_cmds(context, cmds):
    for cmd in cmds:
        cmd = context.resolve_config_value(cmd)
        logging.debug('execute cmd %s', cmd)
        subprocess.check_call(cmd, shell=True)


def handle_projects(context, app):
    projects_config = context.config.get('projects')

    app.pre_handle()
    for pro_config in projects_config:
        app.handle_project(pro_config)

    app.post_handle()



def run_jvm(context):
    java_home = context.get_env('JAVA_HOME')
    java_bin = 'java'
    if java_home:
        java_bin = os.path.join(java_home, 'bin', 'java')

    jvm_cmd_list = [java_bin,]
    jvm_cmd_list.extend(context.jvm_arg_list)

    cmd = ' '.join(jvm_cmd_list)
    logging.debug('execute cmd: %s', cmd)
    subprocess.check_call(cmd, shell=True)


@click.command()
@click.option('-c', '--config', 'config_file', default=DEFAULT_CONFIG_FILE)
def main(config_file):

    context = create_context(config_file)

    v = context.get_env('JAVA_BIN')
    print(v)

    v = context.resolve_config_value('tomcat port is ${port}')
    print(v)

    app = create_application(context)

    app.prepare_config()

    build(context)

    handle_projects(context, app)

    run_jvm(context)


if __name__ == '__main__':
    main()