
import os
import pkg_resources
import logging

import pybee
from .util import random_port

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

    def prepare_config(self):

        self.tomcat_config = self.context.config.get('tomcat')
        self.tomcat_proxy = TomcatProxy(self.context, self.tomcat_config.get('proxy'))

        self.port = self.context.get_env('TOMCAT_PORT', 8080)
        self.shutdowm_port = self.context.get_env('TOMCAT_SHUTDOWN_PORT', -1)
        self.ajp_port = self.context.get_env('TOMAT_AJP_PORT', -1)
        self.redirect_port = self.context.get_env('TOMCAT_REDIRECT_PORT', -1)

        self.src_tomcat_home_dir = self.context.get_env('TOMCAT_HOME')
        if not self.src_tomcat_home_dir:
            logging.error('please define env variable TOMCAT_HOME')
            return False

        return True

    def pre_handle(self):
        if self.context.no_config:
            return

        pybee.path.mkdir(self.tomcat_context_dir, True)
        pybee.path.mkdir(self.temp_dir)
        pybee.path.mkdir(self.work_dir)
        pybee.path.mkdir(self.logs_dir)

        pybee.path.rmtree(self.conf_dir)

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
        pybee.path.write_file_with_encoding(out_file, s)


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
            pybee.sed.render_by_jinja_template(
                tpl,
                os.path.join(self.conf_dir, 'server.xml'),
                'utf-8', m
            )

        context.jvm_arg_list.append('-D"java.awt.headless"=true')
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
