
import os
import logging

import tomlkit
from tomlkit.toml_file import TOMLFile


def load_env_file(f, platform):
    if not os.path.isfile(f):
        return None
    toml = TOMLFile(f)
    content = toml.read()
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