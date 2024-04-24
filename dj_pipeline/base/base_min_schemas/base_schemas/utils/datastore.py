import datajoint as dj


def add_store(key: str, value: dict):
    """Add a data store to the datajoint configuration.
    See https://docs.datajoint.org/python/admin/5-blob-config.html#external
    for full documentation on the configuration options. Calling this function
    is equivalent to setting the config via `dj.config['stores'][key]=value`,
    but ensures that the `'stores'` dictionary is created if needed.
    """

    if "stores" not in dj.config:
        dj.config["stores"] = {}
    dj.config["stores"][key] = value
