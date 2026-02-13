import datajoint as dj


def add_schema(name: str, locals_: dict) -> dj.Schema:
    """Wrapper around the `datajoint.schema` decorator.

    Wrapper function around `datajoint.schema` that provides a decorator
    to associate the tables passed via locals with database's schema namespace.
    Schema object doesn't create a new schema and raises the error if it
    doesn't exist.

    Configuration is possible via `dj.config`. Current supported values are:
    * `dj.config['database.create_tables']`
    * `dj.config['database.database_prefix']`

    Args:
        name: existed schema's name
        locals_: namespace's variables

    Returns:
        dj.schema class instance used as decorator

    See Also:
        * Creating Schemas, https://docs.datajoint.org/python/v0.12/definition/01-Creating-Schemas.html
    """
    prefix = dj.config.get("database.database_prefix", None)

    if prefix is not None:
        name = f"{prefix}_{name}"

    return dj.Schema(name, locals_, create_tables=dj.config.get("database.create_tables", False))
