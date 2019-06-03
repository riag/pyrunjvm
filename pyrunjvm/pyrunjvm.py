
import sys
import os
from string import Template

import subprocess
import logging
import pkg_resources
import random
import psutil

import click
import tomlkit
from tomlkit.toml_file import TOMLFile

import pybee

CURRENT_WORK_DIR = os.path.abspath(os.getcwd())
DEFAULT_CONFIG_FILE = os.path.join(CURRENT_WORK_DIR, '.pyrunjvm.toml')

MAX_PORT = 65535

def get_in_use_ports():
    sconns = psutil.net_connections()
    port_list = []
    for s in sconns:
        p = s.laddr.port
        if p in port_list:
            continue
        port_list.append(p)

    return port_list

def random_port(use_port_list=[]):
    port_list = get_in_use_ports()
    while True:
        port_list = []

        x = random.choice((5, 6))
        port_list.append(str(x))

        if x == 5:
            x = random.choice(range(2, 10))
            port_list.append(str(x))
        else:
            x = random.choice(range(0, 6))
            port_list.append(str(x))

        numbers = range(0, 10)
        for i in range(0, 3):
            x = random.choice(numbers)
            port_list.append(str(x))

        port = int(''.join(port_list))
        if port > MAX_PORT:
            continue

        if port in port_list or port in use_port_list:
            continue

        return port


def get_platform():
    p = sys.platform
    if p != 'linux':
        return p

    # todo


def is_str(v):
    if type(v) in (str, tomlkit.items.String):
        return True

    return False

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
        self.redirect_port = self.context.get_env('TOMCAT_REDIRECT_PORT', -1)

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

        use_port_list = [self.context.debug_port , self.port,]
        if self.shutdowm_port < 1:
            self.shutdowm_port = random_port(use_port_list)
            use_port_list.append(self.shutdowm_port)

        if self.ajp_port < 1:
            self.ajp_port = random_port(use_port_list)
            use_port_list.append(self.ajp_port)

        if self.redirect_port < 1:
            self.redirect_port = random_port(use_port_list)
            use_port_list.append(self.redirect_port)


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
        tpl = pkg_resources.resource_filename(__name__, 'config/tomcat/server.xml')
        m = {
            'PORT': self.port,
            'SHUTDOWN_PORT': self.shutdowm_port,
            'REDIRECT_PORT': self.redirect_port,
            'AJP_PORT': self.ajp_port,
        }
        pybee.sed.render_by_jinja_template(
            tpl, 
            os.path.join(self.conf_dir, 'server.xml'),
            'utf-8', m
        )

        context = self.context
        context.jvm_arg_list.append(
            "-D\"java.util.logging.config.file\"=\"%s\"" % os.path.join(self.conf_dir, 'logging.properties')
            )
        context.jvm_arg_list.append("-D\"java.util.logging.manager\"=org.apache.juli.ClassLoaderLogManager")

        #context.jvm_arg_list.append("-D\"com.sun.management.jmxremote\"= ")
        #context.jvm_arg_list.append("-D\"com.sun.management.jmxremote.port\"=%d" % tomact_jmx_port)
        #context.jvm_arg_list.append("-D\"com.sun.management.jmxremote.ssl\"=false")
        #context.jvm_arg_list.append("-D\"com.sun.management.jmxremote.authenticate\"=false")

        context.jvm_arg_list.append("-D\"java.rmi.server.hostname\"=127.0.0.1")
        context.jvm_arg_list.append("-D\"jdk.tls.ephemeralDHKeySize\"=2048")
        context.jvm_arg_list.append("-D\"java.protocol.handler.pkgs\"=\"org.apache.catalina.webresources\"")

        class_path_list = []
        class_path_list.append(
            os.path.join(self.src_tomcat_home_dir, "bin", "bootstrap.jar")
            )
        class_path_list.append(
            os.path.join(self.src_tomcat_home_dir, "bin", "tomcat-juli.jar")
            )
        context.jvm_arg_list.append('-classpath')
        context.jvm_arg_list.append('"%s"' % os.pathsep.join(class_path_list))

        context.jvm_arg_list.append("-D\"catalina.base\"=\"%s\"" % self.tomcat_dir)
        context.jvm_arg_list.append("-D\"catalina.home\"=\"%s\"" % self.src_tomcat_home_dir)
        context.jvm_arg_list.append("-D\"java.io.tmpdir\"=\"%s\"" % self.temp_dir)
        context.jvm_arg_list.append("org.apache.catalina.startup.Bootstrap")
        context.jvm_arg_list.append("start")



application_map = {
    'tomcat': TomcatApplication,
}


def load_tomlfile(f):
    toml = TOMLFile(f)
    return toml.read()


def load_env_file(f, platform):
    content = load_tomlfile(f)
    logging.debug('env config file content:')
    logging.debug(content)
    environ = {}
    env = content.get('env', None)
    if env:
        environ.update(env)

    platform_content = content.get('platform', None)
    if platform_content is None:
        return environ
    p = platform_content.get(platform, None)
    if p is None:
        return environ

    env = p.get('env' , None)
    if env:
        environ.update(env)

    return environ

def create_context(config_file):

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


def create_application(context):
    app_type = context.resolve_config_value(
        context.config.get('app_type')
    )
    if app_type.endswith('.py'):
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
    java_bin = context.get_env('JAVA_BIN')
    if java_bin is None:
        java_home = context.get_env('JAVA_HOME')
        if java_home:
            java_bin = os.path.join(java_home, 'bin', 'java')

    if java_bin is None:
        java_bin = 'java'

    jvm_cmd_list = [java_bin,]
    jvm_cmd_list.extend(context.jvm_arg_list)

    cmd = ' '.join(jvm_cmd_list)
    logging.debug('execute cmd: %s', cmd)
    subprocess.check_call(cmd, shell=True)


@click.command()
@click.option('-c', '--config', 'config_file', default=DEFAULT_CONFIG_FILE)
def main(config_file):

    rootLogger = logging.getLogger()
    rootLogger.setLevel(logging.DEBUG)

    context = create_context(config_file)

    app = create_application(context)

    app.prepare_config()

    build(context)

    handle_projects(context, app)

    run_jvm(context)


if __name__ == '__main__':
    main()