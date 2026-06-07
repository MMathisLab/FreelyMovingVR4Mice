import os
import sys

from base_actions.utils.logger import Logger, config_logger
from base_actions.utils.login import LoginUser
from base_actions.utils.schema_config import connect_to_database


"""
    Script with different connection modes based on the number of input arguments:
    The address of database precised in the DJ_HOST env variable,
    If the password as the same as the name it can be used as the one input argument
    
    todo: authentication via file
"""


def connect(tag="", db_host=os.environ["DJ_HOST"]):
    """
    Connects to the database using the specified tag and database host.

    Args:
    tag (str): The prefix to use for the connection.
    db_host (str, optional): The database host to connect to.
    Defaults to the value of the "DJ_HOST" environment variable.

    """
    if len(sys.argv) > 2:
        name = sys.argv[2]

        if len(sys.argv) == 4:
            pwd = sys.argv[3]
        elif len(sys.argv) == 3:
            pwd = sys.argv[2]

        connect_to_database(
            LoginUser(user_name=name, user_password=pwd, db_host=db_host),
            prefix=tag,
            create_tables=True,
            # storage="app"
        )
    else:
        connect_to_database(
            LoginUser(
                user_name=os.environ["DJ_USER"],
                user_password=os.environ["DJ_PWD"],
                db_host=db_host,
            ),
            prefix=tag,
            create_tables=True,
            # storage="app"
        )
