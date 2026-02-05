import os
import warnings


"""
     The LoginUser class represents a user who is authorized to log into a database.

     DEPRECATED: Use datajoint.json or DJ_USER/DJ_PASS environment variables instead.
"""


class LoginUser:
    """Represents a user who is authorized to log into a database.

    DEPRECATED: This class is deprecated. Use datajoint.json configuration
    or DJ_USER/DJ_PASS environment variables instead.

    Attributes:
        user_name (str): The user's name.
        user_password (str): The user's password.
        db_host (str): The IP address of the server hosting the database.

    Properties:
        name (str): The user's name.
        password (str): The user's password.
        host (str): The IP address of the server hosting the database.

    """

    def __init__(self, user_name=None, user_password=None, db_host=None):
        warnings.warn(
            "LoginUser is deprecated. Use datajoint.json or DJ_USER/DJ_PASS env vars.",
            DeprecationWarning,
            stacklevel=2
        )
        self.user_name = user_name or os.environ.get("DJ_USER", "root")
        self.user_password = user_password or os.environ.get("DJ_PWD", "simple")
        self.db_host = (db_host or os.environ.get("DJ_HOST", "127.0.0.1")).replace('"', "")

    @property
    def name(self) -> str:
        """Returns the user's name."""
        return self.user_name

    @property
    def password(self) -> str:
        """Returns the user's password."""
        return self.user_password

    @property
    def host(self) -> str:
        """Returns the IP address of the server hosting the database."""
        return self.db_host
