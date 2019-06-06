import os
import sys
import logging
import click
import subprocess

from .env import load_env_file
from .context import create_context
from .application import create_application

CURRENT_WORK_DIR = os.path.abspath(os.getcwd())
DEFAULT_CONFIG_FILE = os.path.join(CURRENT_WORK_DIR, '.pyrunjvm.toml')

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

@click.command()
@click.option('-c', '--config', 'config_file', default=DEFAULT_CONFIG_FILE)
def main(config_file):

    rootLogger = logging.getLogger()
    rootLogger.setLevel(logging.DEBUG)

    platform = sys.platform

    logging.info('platform : %s', platform)

    env_file = os.path.join(CURRENT_WORK_DIR, '.env.toml')
    env = load_env_file(env_file, platform)

    context = create_context(
        platform, CURRENT_WORK_DIR, config_file, env
        )
    if context is None:
        return

    app = create_application(context)

    if not app.prepare_config():
        return

    build(context)

    handle_projects(context, app)

    context.run()

if __name__ == '__main__':
    main()