
import psutil
import tomlkit
import random

def is_str(v):
    if type(v) in (str, tomlkit.items.String):
        return True

    return False

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