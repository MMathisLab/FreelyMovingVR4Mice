import os


"""
     The LoginUser class represents a user who is authorized to log into a database.
"""


class LoginUser:

    """Represents a user who is authorized to log into a database.

    Attributes:
        user_name (str): The user's name.
        user_password (str): The user's password.
        db_host (str): The IP address of the server hosting the database.

    Methods:
        __init__(self, user_name=os.environ["DJ_USER"], user_password=os.environ["DJ_PWD"],
                 db_host=os.environ["DJ_HOST"])
            Initializes a LoginUser instance with values from environment variables, or with
            default values if no arguments are provided.

    Properties:
        name (str): The user's name.
        password (str): The user's password.
        host (str): The IP address of the server hosting the database.

    """

    def __init__(self, local=True):
        self.user_name = "root"
        self.user_password = "simple"
        self.db_host = "127.0.0.1"  # os.environ["DJ_HOST"]

    def __init__(self, db_host=os.environ["DJ_HOST"]):
        self.user_name = "root"
        self.user_password = "simple"
        self.db_host = db_host.replace('"', "")

    def __init__(
        self,
        user_name=os.environ["DJ_USER"],
        user_password=os.environ["DJ_PWD"],
        db_host=os.environ["DJ_HOST"],
    ):
        self.user_name = user_name
        self.user_password = user_password
        self.db_host = db_host.replace('"', "")

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
