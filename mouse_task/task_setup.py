import os
import sys
import json
import argparse

# import platform
import subprocess
import tkinter as tk
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from pathlib import Path


# Function to create conda environment and install dependencies
def create_env(env_name="vr4mice", verbose=False):
    """Creates a conda environment for the vr4mice task and installs required dependencies.

    Parameters
    ----------
    env_name : str, optional
        name of the conda environment to be created, by default "vr4mice"
    verbose : bool, optional
        whether the output of this function should be verbose or not, by default False
    """
    print(f"Creating conda environment: {env_name}") if verbose else None

    # Create the conda environment
    subprocess.run(f"conda create --name {env_name} python=3.10.12", shell=True)
    print("Environment created.") if verbose else None

    # Activate the conda environment
    activate_precommand = f"conda run -n {env_name} "
    github_repo_link = "https://github.com/AdaptiveMotorControlLab/ml-agents.git"

    print("Installing dependencies...") if verbose else None

    # Install ml-agents dependencies
    subprocess.run(
        f"git clone --branch release_21_fix_macOS {github_repo_link} ../../ml-agents",
        shell=True,
    )
    subprocess.run(
        activate_precommand + "pip install ../../ml-agents/ml-agents-envs",
        shell=True,
    )
    subprocess.run(
        activate_precommand + "pip install ../../ml-agents/ml-agents",
        shell=True,
    )

    # Install the vr4mice package
    subprocess.run(activate_precommand + "pip install ../", shell=True)
    print("Dependencies installed.") if verbose else None


# Function to prompt user for build directory path
def get_path():
    """Retrieve a directory path from the user.

    Parameters
    ----------
    purpose : str, optional
        information about what the directory should contain, by default ""

    Returns
    -------
    str
        the path selected by the user

    Raises
    ------
    ValueError
        raises error if the selected path is not a directory
    """
    # Hide the main tkinter window
    tk.Tk().withdraw()

    # Display a quick dialogue explaining the purpose of the selected directory
    tk.messagebox.showinfo(
        "Select Unity game",
        f"Select the built unity game",
    )

    # Open a directory navigator and get the selected path
    build_path = filedialog.askopenfilename(title="Select Unity Game")

    if build_path:
        return Path(build_path).absolute()
    else:
        raise ValueError("No build was selected. Try again.")


# Function to save build path to config.json
def save_config(file_path):
    """Prompts the user to select a directory and saves the path to the specified config file.

    Parameters
    ----------
    file_path : str
        path to config file
    """

    final_build_path = str(get_path())

    if file_path.exists():
        # Load  config data
        with open(file_path, "r") as file:
            config = json.load(file)

        # Update the necessary key-value pairs
        for config_path in config.keys():
            if config_path == "ar_env_unity_absolute_path":
                config[config_path] = final_build_path
    else:
        # Create the config data
        config = {"ar_env_unity_absolute_path": str(final_build_path)}

    # Save the config data
    with open(file_path, "w") as file:
        json.dump(config, file)

    print(f"Build path saved to {file_path}")


# Function to parse command line arguments
def parse_arguments():
    """Parses the command-line arguments that are passed when running the script

    Returns
    -------
    list
        list containing the arguments passed to the script

    Raises
    ------
    ValueError
        if both config_only and env_only are set to True
    UserWarning
        if env_name is specified when config_only is set to True
    """
    # Create the argument parser
    parser = argparse.ArgumentParser(
        description="--- HELP TO SETUP TASK ENVIRONMENT ---"
    )

    # Add arguments
    # env_name
    parser.add_argument(
        "--env_name",
        type=str,
        help="Name of conda environment",
        required=False,
    )

    # verbose
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Toggle verbose output",
        required=False,
    )

    # config_only
    parser.add_argument(
        "--config_only",
        action="store_true",
        help="Tells the script to only update the config file without creating a conda environment",
        required=False,
    )

    # env_only
    parser.add_argument(
        "--env_only",
        action="store_true",
        help="Tells the script to only create a conda environment without updating the config file",
        required=False,
    )

    # Parse the arguments
    args = parser.parse_args()
    arguments = {
        "env_name": "vr4mice",
        "verbose": False,
        "config_only": False,
        "env_only": False,
        "all": True,
    }

    # Access the arguments
    if args.env_name:
        arguments["env_name"] = args.env_name
        # print(f"Conda environment name: {args.env_name}")
    if args.verbose:
        arguments["verbose"] = args.verbose
        # print("Verbose output enabled")
    if args.config_only:
        arguments["config_only"] = args.config_only
        arguments["all"] = False
        # print("Config file only")
    if args.env_only:
        arguments["env_only"] = args.env_only
        arguments["all"] = False
        # print("Environment only")

    if args.config_only and args.env_only:
        raise ValueError("Cannot have both config_only and env_only set to True")

    if args.config_only and args.env_name:
        raise UserWarning(
            "Doesn't make sense to specify environment name when config_only is set to True."
        )

    return arguments


def preliminary_check():
    """Asks the user if he/she already has already built the Unity game.
    If yes, the script will proceed to the setup of the configuration .json file.
    If no, the scrpit will stop and configuration will be set.

    Returns
    -------
    bool
        True if the user has already built the Unity game, False otherwise
    """

    question = "Have you already built the Unity game and have the executable stored in a directory on your machine?"

    root = tk.Tk()
    root.withdraw()
    answer = messagebox.askquestion(title="Question", message=question, icon="warning")
    root.destroy()
    if answer == "yes":
        return True
    else:
        return False


# main
def main():
    args = parse_arguments()

    if args["env_only"] or args["all"]:
        # print("- - - - - - ENV - - - - - -")
        create_env(args["env_name"], args["verbose"])

    if args["config_only"] or args["all"]:
        # print("- - - - - CONFIG - - - - -")
        answer = preliminary_check()
        if not answer:
            raise RuntimeError(
                "In order to save configuration paths, you need to already have the directory containing the built Unity game."
            )
        save_config(Path("./task_config.json"))


if __name__ == "__main__":
    main()
