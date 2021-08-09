
import os
import pkg_resources

from .util import random_port, mkdir,rmtree,write_file_with_encoding,render_by_jinja_template
import shutil
import asyncio
import subprocess
import sys

class DebugPortInfo(object):
    def __init__(self, name, port):
        self.name = name
        self.port = port

class AbastApplication(object):
    def __init__(self, context):
        self.context = context

    def prepare_config(self):
        pass

    def build_project(self, project_config):
        pass

    def pre_handle(self):
        pass

    def handle_project(self, project_config):
        pass

    def post_handle(self):
        pass

    def run(self, **kwargs):
        pass

class TomcatProxy(object):
    def __init__(self, context, proxy_config):
        self.enable = proxy_config.get('enable')
        self.ip = context.get_env('TOMCAT_PROXY_IP', '127.0.0.1')
        self.http_port = context.get_env('TOMCAT_PROXY_HTTP_PORT', '80')
        self.https_port = context.get_env('TOMCAT_PROXY_HTTPS_PORT', '443')

        if self.ip:
            self.ip = self.ip.replace('.', '\\.')

class TomcatApplication(AbastApplication):

    TOMCAT_CONTEXT_XML_TPL = '''<?xml version="1.0" encoding="UTF-8"?>
    <Context path="{context_path}" docBase="{war_path}" reloadable="true"/>
    '''

    def __init__(self, context):
        self.context = context
        self.tomcat_config = None
        self.tomcat_proxy = None
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

        self.debug_port = self.context.get_env('JVM_DEBUG_PORT', 50899, int)
        self.jvm_arg_list = []
        if context.jvm_arg_list:
            self.jvm_arg_list.extend(context.jvm_arg_list)
        self.jvm_arg_list.append('-Xdebug') 
        self.jvm_arg_list.append(
            '-Xrunjdwp:transport=dt_socket,server=y,suspend=n,address=127.0.0.1:%d' % self.debug_port
        )

        self.context.debug_port_info_list.append(DebugPortInfo('debug tomcat', self.debug_port))

    def prepare_config(self):

        self.tomcat_config = self.context.config.get('tomcat')
        self.tomcat_proxy = TomcatProxy(self.context, self.tomcat_config.get('proxy'))

        self.port = self.context.get_env('TOMCAT_PORT', 8080, int)
        self.shutdowm_port = self.context.get_env('TOMCAT_SHUTDOWN_PORT', -1, int)
        self.ajp_port = self.context.get_env('TOMAT_AJP_PORT', -1, int)
        self.redirect_port = self.context.get_env('TOMCAT_REDIRECT_PORT', -1, int)

        self.src_tomcat_home_dir = self.context.get_env('TOMCAT_HOME')
        if not self.src_tomcat_home_dir:
            print('please define env variable TOMCAT_HOME')
            return False

        return True

    def pre_handle(self):
        if self.context.no_config:
            return

        mkdir(self.tomcat_context_dir, True)
        mkdir(self.temp_dir)
        mkdir(self.work_dir)
        mkdir(self.logs_dir)

        rmtree(self.conf_dir)

        shutil.copytree(
            os.path.join(self.src_tomcat_home_dir, 'conf'),
            self.conf_dir, dirs_exist_ok=True
        )

        use_port_list = [self.debug_port , self.port,]
        if self.shutdowm_port < 1 :
            if not self.context.enable_psutil:
                print("psutil is not enable, please use fixed port for tomcat shutdown port")
                sys.exit(-1)

            self.shutdowm_port = random_port(use_port_list)
            use_port_list.append(self.shutdowm_port)

        if self.ajp_port < 1:
            if not self.context.enable_psutil:
                print("psutil is not enable, please use fixed port for tomcat ajp port")
                sys.exit(-1)

            self.ajp_port = random_port(use_port_list)
            use_port_list.append(self.ajp_port)

        if self.redirect_port < 1:
            if not self.context.enable_psutil:
                print("psutil is not enable, please use fixed port for tomcat redirect port")
                sys.exit(-1)

            self.redirect_port = random_port(use_port_list)
            use_port_list.append(self.redirect_port)


    def handle_project(self, project_config):
        if self.context.no_config:
            return

        project_path = project_config.get('path')
        context_path = project_config.get('context_path')
        exploded_war_path = project_config.get('exploded_war_path')

        context_path = self.context.resolve_config_value(context_path)
        exploded_war_path = self.context.resolve_config_value(exploded_war_path)

        if not context_path.startswith('/'):
            context_path = '/%s' % context_path

        m = {
            'context_path': context_path,
            'war_path': exploded_war_path
        }
        s = self.TOMCAT_CONTEXT_XML_TPL.format(**m)
        p = context_path[1:]
        p = p.replace('/', '#')
        out_file = os.path.join(self.tomcat_context_dir, '%s.xml' % p)
        write_file_with_encoding(out_file, s)


    def post_handle(self):
        context = self.context
        if not context.no_config:
            tpl = pkg_resources.resource_filename(__name__, 'config/tomcat/server.xml')
            m = {
                'PORT': self.port,
                'SHUTDOWN_PORT': self.shutdowm_port,
                'REDIRECT_PORT': self.redirect_port,
                'AJP_PORT': self.ajp_port,
                'Proxy': self.tomcat_proxy
            }
            render_by_jinja_template(
                tpl,
                os.path.join(self.conf_dir, 'server.xml'),
                'utf-8', m
            )

        self.jvm_arg_list.append('-Djava.awt.headless=true')
        self.jvm_arg_list.append(
            "-Djava.util.logging.config.file=%s" % os.path.join(self.conf_dir, 'logging.properties')
            )
        self.jvm_arg_list.append("-Djava.util.logging.manager=org.apache.juli.ClassLoaderLogManager")

        #self.jvm_arg_list.append("-D\"com.sun.management.jmxremote\"= ")
        #self.jvm_arg_list.append("-D\"com.sun.management.jmxremote.port\"=%d" % tomact_jmx_port)
        #self.jvm_arg_list.append("-D\"com.sun.management.jmxremote.ssl\"=false")
        #self.jvm_arg_list.append("-D\"com.sun.management.jmxremote.authenticate\"=false")

        self.jvm_arg_list.append("-Djava.rmi.server.hostname=127.0.0.1")
        self.jvm_arg_list.append("-Djdk.tls.ephemeralDHKeySize=2048")
        self.jvm_arg_list.append("-Djava.protocol.handler.pkgs=org.apache.catalina.webresources")

        class_path_list = []
        class_path_list.append(
            os.path.join(self.src_tomcat_home_dir, "bin", "bootstrap.jar")
            )
        class_path_list.append(
            os.path.join(self.src_tomcat_home_dir, "bin", "tomcat-juli.jar")
            )
        self.jvm_arg_list.append('-classpath')
        self.jvm_arg_list.append('%s' % os.pathsep.join(class_path_list))

        # self.jvm_arg_list.append('-classpath')
        # self.jvm_arg_list.append(
        #      os.path.join(self.src_tomcat_home_dir, "bin", "bootstrap.jar")
        # )

        # self.jvm_arg_list.append('-classpath')
        # self.jvm_arg_list.append(
        #      os.path.join(self.src_tomcat_home_dir, "bin", "tomcat-juli.jar")
        # )

        self.jvm_arg_list.append("-Dcatalina.base=%s" % self.tomcat_dir)
        self.jvm_arg_list.append("-Dcatalina.home=%s" % self.src_tomcat_home_dir)
        self.jvm_arg_list.append("-Djava.io.tmpdir=%s" % self.temp_dir)
        self.jvm_arg_list.append("org.apache.catalina.startup.Bootstrap")
        self.jvm_arg_list.append("start")


    def run(self, **kwargs):
        jvm_cmd_list = [self.context.java_bin,]
        jvm_cmd_list.extend(self.jvm_arg_list)

        kwargs['env'] = self.context.environ

        cmd = ' '.join(jvm_cmd_list)
        if kwargs.get('shell', None) is None:
            kwargs['shell'] = True

        log_file = os.path.join(self.context.logs_dir, 'tomcat.log')

        print(f'execute cmd: {cmd}')
        print('')
        print('log file is %s' % log_file)

        if self.context.no_run:
            return

        with open(log_file, 'w') as f:
            kwargs['stdout'] = f
            kwargs['stderr'] = f
            subprocess.check_call(jvm_cmd_list, **kwargs)

        print('')
        print('stop')

class FlatJarConfig(object):
    def __init__(self):
        self.name = ''
        self.project_path = ''
        self.jar_path = ''
        self.jvm_arg_list = []
        self.debug_port = None
        self.log_file_name = ''


class FlatJarApplication(AbastApplication):
    def __init__(self, context):
        super().__init__(context)

        self.logs_dir = os.path.join(self.context.dest_dir, 'logs')
        self.flatjar_config_list = []

    def prepare_config(self):
        return True

    def build_project(self, project_config):
        clear_cmds = project_config.get('clear_cmds', None)
        if clear_cmds:
            self.context.execute_cmds(clear_cmds)

        build_cmds = project_config.get('build_cmds')
        if build_cmds:
            self.context.execute_cmds(build_cmds)

    def pre_handle(self):
        if self.context.no_config:
            return

        mkdir(self.logs_dir)

    def handle_project(self, project_config):

        project_path = project_config.get('path')
        name = os.path.basename(project_path)
        jar_path = project_config.get('jar_path')
        jar_path = self.context.resolve_config_value(jar_path)
        jvm_arg_list = project_config.get('jvm_opts')
        debug_port = project_config.get('debug_port')
        debug_port = self.context.resolve_config_value(debug_port)

        print(f"debug port: is ${debug_port}")

        if debug_port and type(debug_port) is str:
            debug_port = int(debug_port)

        c = FlatJarConfig()
        c.name = name
        c.project_path = project_path
        c.jar_path = jar_path
        c.jvm_arg_list = jvm_arg_list
        c.debug_port = debug_port
        c.log_file_name = project_config.get('log_file_name')
        if not c.log_file_name:
            c.log_file_name = f'{name}.log'

        self.flatjar_config_list.append(c)

        if c.debug_port and c.debug_port > 0:
            di = DebugPortInfo(f'debug {name}', c.debug_port)
            self.context.debug_port_info_list.append(di)

    def post_handle(self):
        pass

    async def run_flatjar(self, config:FlatJarConfig):
        p = os.path.join(self.logs_dir, config.log_file_name)
        with open(p, 'w') as log_file:
            jvm_args = []
            if self.context.jvm_arg_list:
                jvm_args.extend(self.context.jvm_arg_list)
            if config.jvm_arg_list:
                jvm_args.extend(config.jvm_arg_list)

            if config.debug_port and config.debug_port > 0:
                jvm_args.append('-Xdebug') 
                jvm_args.append(
                    '-Xrunjdwp:transport=dt_socket,server=y,suspend=n,address=127.0.0.1:%d' % config.debug_port
                )

            cmd_list = [self.context.java_bin, ]
            if jvm_args:
                cmd_list.extend(jvm_args)

            cmd_list.append('-jar')
            cmd_list.append(config.jar_path)

            cmd = ' '.join(cmd_list)

            cwd = os.path.join(self.context.work_dir, config.project_path)

            print(f'cwd is {cwd}')
            print(f'execute cmd: {cmd}')
            print('')
            print(f'log file is {p}')

            proc = await asyncio.create_subprocess_shell(
                cmd, 
                stdout=log_file,
                stderr=log_file,
                cwd = cwd,
                env = self.context.environ
            )
            await proc.wait()
            print(f"{config.name} is stop")


    def run(self, **kwargs):
        if self.context.no_run:
            return

        ct_list = []
        if sys.platform == 'win32':
            asyncio.set_event_loop(asyncio.ProactorEventLoop())

        loop = asyncio.get_event_loop()
        for config in self.flatjar_config_list:
            ct = self.run_flatjar(config)
            print('')
            ct_list.append(ct)

        loop.run_until_complete(asyncio.gather(*ct_list))
        loop.close()

application_map = {
    'tomcat': TomcatApplication,
    'flatjar': FlatJarApplication,
}


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
