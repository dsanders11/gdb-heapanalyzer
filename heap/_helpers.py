"""Collection of small helper functions"""

def create_singleton(name):
    """Helper function to create a singleton class"""

    type_dict = {'__slots__': (), '__str__': lambda self: name, '__repr__': lambda self: name}

    return type(name, (object,), type_dict)()