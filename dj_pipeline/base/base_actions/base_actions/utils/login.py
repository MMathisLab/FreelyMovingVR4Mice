import os


"""
     The LoginUser class represents a user who is authorized to log into a database.
"""


class LoginUser:
    """Represents a user who is authorized to log into a database."""

    def __init__(self, user_name=None, user_password=None, db_host=None):
        self.user_name = user_name if user_name is not None else os.environ["DJ_USER"]
        self.user_password = (
            user_password if user_password is not None else os.environ["DJ_PWD"]
        )
        self.db_host = (db_host if db_host is not None else os.environ["DJ_HOST"]).replace(
            '"', ""
        )

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
