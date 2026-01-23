import datajoint as dj

# Module-level configuration for schema settings
# Used instead of dj.config custom keys for DJ 2.0 compatibility
_schema_prefix = ""
_create_tables = True


def connect_to_database(user, prefix="", create_tables=True, storage="/storage"):
    """
    Connects to a database using DataJoint.

    Args:
    user (User): A User object that contains the necessary information to connect to the database,
                such as the host, name, and password.
    prefix (str, optional): A prefix to add to the schema name. Defaults to "".
    create_tables (bool, optional): Whether to create tables if they don't exist. Defaults to True.
    storage (str, optional): The location of the storage directory. Defaults to "/storage".

    Raises:
    ConnectionError: If the connection to the database fails.

    Notes:
    - This function assumes that DataJoint has already been imported and configured.
    - The user argument is expected to be a User object with attributes host, name, and password.
    - The prefix argument is useful if you want to add a prefix to the schema name to distinguish it from other schemas in the same database.
    - The create_tables argument is useful if you want to create tables in the database if they don't already exist.
    - The location argument is the location of the storage directory where DataJoint will store data files.
    """

    dj.config["stores"] = {  # todo: + surgery_images from mice
        # read-only store
        # "data": {
        #    "protocol": "file",
        #    "location": storage,
        #    "stage": storage
        # },
    }

    global _schema_prefix, _create_tables
    _schema_prefix = prefix
    _create_tables = create_tables

    dj.config["database.host"] = user.host
    dj.config["database.user"] = user.name
    dj.config["database.password"] = user.password

    dj.conn()


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
        using the schema prefix defined in dj.config["database.misc.schema_prefix"].
    - create_tables(): Returns the value of dj.config["database.misc.create_tables"],
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
        return str(_schema_prefix) + str(key)

    @staticmethod
    def create_tables():
        return _create_tables
