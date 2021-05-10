
import tomlkit
import random
import os
import shutil
import io
import jinja2

def is_str(v):
    if type(v) in (str, tomlkit.items.String):
        return True

    return False

MAX_PORT = 65535

def get_in_use_ports():
    import psutil
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

def mkdir(path, recursive=False, **kwargs):
    if recursive:
        os.makedirs(path, exist_ok=True, **kwargs)
    else:
        if os.path.isdir(path):
            return
        os.mkdir(path, **kwargs)

# 这里只删除目录下的文件和目录
# 不删除根目录
def rmtree(path):
    p_list = os.listdir(path)
    for p in p_list:
        m = os.path.join(path, p)
        if os.path.isfile(m):
            os.unlink(m)
        else:
            shutil.rmtree(m)

def write_file_with_encoding(path, text, encoding='UTF-8'):
    with io.open(path, 'w', encoding=encoding) as f:
            f.write(text)

def read_text_file(fpath, encoding='UTF-8'):
    with io.open(fpath, 'r', encoding=encoding) as f:
        return f.read()

def render_str_by_jinja_template(text, *mapping, **kwds):
    t = jinja2.Template(text)
    return t.render(*mapping, **kwds)


def render_by_jinja_template(
        tmp_path, out_path, encoding='UTF-8',
        mapping=None, **kwds):

    text = read_text_file(tmp_path, encoding)
    s = render_str_by_jinja_template(text, mapping, **kwds)
    write_file_with_encoding(out_path, s, encoding)