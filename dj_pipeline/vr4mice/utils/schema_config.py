import datajoint as dj


def connect_to_database(user=None, prefix=None, create_tables=None, storage=None):
    """
    Connects to database using DataJoint 2.0's auto-configuration.

    Configuration loads automatically from:
    1. Environment variables (DJ_HOST, DJ_USER, DJ_PASS)
    2. .secrets/datajoint.json
    3. datajoint.json

    Args (all optional - override datajoint.json if provided):
        user: LoginUser object (deprecated, for backward compatibility)
        prefix: Schema prefix (overrides database.database_prefix)
        create_tables: Whether to create tables (overrides database.create_tables)
        storage: Ignored (deprecated)
    """
    # Override config if parameters provided (backward compatibility)
    if prefix is not None:
        dj.config['database.database_prefix'] = prefix
    if create_tables is not None:
        dj.config['database.create_tables'] = create_tables
    if user is not None:
        dj.config["database.host"] = user.host
        dj.config["database.user"] = user.name
        dj.config["database.password"] = user.password

    return dj.conn()


def get_schema(name, _locals):
    """
    Returns a DataJoint schema object for the given name.

    Args:
    name (str): The name of the schema to create.
    _locals (dict): A dictionary containing the local variables in the calling function's namespace.

    Returns:
    dj.Schema: A DataJoint schema object.

    Notes:
    - This function assumes that DataJoint has already been imported and configured.
    - The _locals argument is necessary to properly define the schema and
        should be passed in as locals() from the calling function.
    - The create_tables argument is set by default to SchemaConfig.create_tables(),
        which is defined in the SchemaConfig class.
    - The schema name is generated using SchemaConfig.get_schema_key(name).
    """

    return dj.Schema(
        SchemaConfig.get_schema_key(name),
        _locals,
        create_tables=SchemaConfig.create_tables(),
    )


class SchemaConfig:
    """
    A class that contains configuration information for DataJoint schemas.

    Methods:
    - get_schema_key(key): Returns the schema key for a given key,
        using the database prefix defined in dj.config["database.database_prefix"].
    - create_tables(): Returns the value of dj.config["database.create_tables"],
        which determines whether the schema object will create tables on the database if they don't already exist.

    Notes:
    - This class assumes that DataJoint has already been imported and configured.
    - The get_schema_key() method is used to generate schema keys that include a prefix,
        which can be useful for distinguishing schemas in the same database.
    - The create_tables() method determines
        whether the schema object will create tables on the database if they don't already exist.
    """

    @staticmethod
    def get_schema_key(key):
        return str(dj.config['database.database_prefix']) + str(key)

    @staticmethod
    def create_tables():
        return dj.config['database.create_tables']
