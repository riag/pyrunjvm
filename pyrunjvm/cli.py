import os
import sys
import logging
import click
import subprocess

from .env import load_env_file
from .context import create_context
from .application import create_application
import pyrunjvm

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
@click.option('--no-config', is_flag=True)
@click.option('--no-build', is_flag=True)
@click.option('--no-run', is_flag=True)
@click.option('--version', 'print_version', is_flag=True)
def main(config_file, no_config, no_build, no_run, print_version):

    rootLogger = logging.getLogger()
    rootLogger.setLevel(logging.DEBUG)

    platform = sys.platform

    logging.info('platform : %s', platform)
    logging.info('work dir : %s', CURRENT_WORK_DIR)
    logging.info(f'no config: {no_config}')
    logging.info(f'no build: {no_build}')
    logging.info(f'no run: {no_run}')

    if print_version:
        logging.info('version: %s', pyrunjvm.__version__)
        return

    env_file = os.path.join(CURRENT_WORK_DIR, '.env.toml')
    env = load_env_file(env_file, platform)

    context = create_context(
        platform, CURRENT_WORK_DIR, config_file, env
        )
    if context is None:
        return

    context.no_config = no_config
    context.no_run = no_run

    app = create_application(context)

    if not app.prepare_config():
        return

    if not no_build:
        build(context)

    handle_projects(context, app)

    context.run()

if __name__ == '__main__':
    main()
