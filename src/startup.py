from .service import Server, ALL_SERVERS

instances: list[Server] = []

def setup_instances() -> list[Server]:
    for server in ALL_SERVERS:
        instances.append(server())

    return instances
