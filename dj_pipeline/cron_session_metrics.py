import os
import argparse
from base_actions.connect import connect

connect(tag="", db_host=os.environ["DJ_HOST"])


from vr4mice.utils.logger import Logger

logger = Logger.get_logger()


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Script to handle AWS or local execution."
    )
    parser.add_argument(
        "--aws", action="store_true", help="Enable AWS-specific execution."
    )
    args = parser.parse_args()

    try:
        from vr4mice.schema import session_metrics

        session_metrics.SessionMetrics().populate()

    except Exception as e:
        logger.error(f"An error occurred in populate_decision_making.populate: {e}")


if __name__ == "__main__":
    main()
