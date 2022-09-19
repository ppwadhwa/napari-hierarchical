from ._controller import controller


def napari_get_reader(path):
    if isinstance(path, list):
        if len(path) != 1:
            return None
        path = path[0]
    if controller.can_read_image(path):
        return _reader_function
    return None


def _reader_function(path):
    controller.read_image(path)
    return [(None,)]
