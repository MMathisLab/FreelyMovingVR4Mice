import os
import sys
import json
import argparse
import subprocess
import tkinter as tk
from tkinter import Tk
from tkinter import filedialog
from pathlib import Path


# Function to create conda environment and install dependencies
def create_conda_env(env_name="vr4mice", verbose=False):

    print(f"Creating conda environment: {env_name}") if verbose else None
    # Create the conda environment
    subprocess.call(f"conda create --name {env_name} python=3.10.12", shell=True)
    print("Environment created.") if verbose else None

    # Activate the conda environment
    activate_precommand = f"conda run -n {env_name} "

    # Install dependencies
    print("Installing dependencies...") if verbose else None

    # Install the mlagents_envs package
    subprocess.call(
        activate_precommand + "pip install ./ext_modules/mlagents_envs-1.0.0.tar.gz",
        shell=True,
    )

    # Install the mlagents package
    subprocess.call(
        activate_precommand + "pip install ./ext_modules/mlagents-1.0.0.tar.gz",
        shell=True,
    )

    # Install the vr4mice package
    subprocess.call(activate_precommand + "pip install ../", shell=True)
    print("Dependencies installed.") if verbose else None


# Function to prompt user for build directory path
def get_path(purpose=""):
    # Hide the main tkinter window
    Tk().withdraw()

    # Display a quick dialogue explaining the purpose of the selected directory
    tk.messagebox.showinfo(
        "Select Directory",
        f"Select directory for: {purpose}",
    )

    # Open a directory navigator and get the selected path
    build_path = filedialog.askdirectory(title="Select Directory")
    build_path = Path(build_path).absolute()  # get absolute path
    if not os.path.isdir(build_path):
        raise ValueError(f"Invalid directory: {build_path}")
    return build_path


# Function to save build path to config.json
def save_to_config(file_path):
    # Load the existing config data
    with open(file_path, "r") as file:
        config = json.load(file)

    # Update the necessary key-value pairs
    for config_path in config.keys():
        if config_path.find("path"):
            # print(config_path)
            config[config_path] = str(get_path(config_path))

    # Save the updated config data
    with open(file_path, "w") as file:
        json.dump(config, file)

    print(f"Build path saved to {file_path}")


# Function to parse command line arguments
def parse_arguments():
    # Create the argument parser
    parser = argparse.ArgumentParser(
        description="--- HELP TO SETUP TASK ENVIRONMENT ---"
    )

    # Add arguments
    parser.add_argument(
        "--env_name",
        type=str,
        help="Name of conda environment",
        required=False,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Toggle verbose output",
        required=False,
    )

    # Parse the arguments
    args = parser.parse_args()
    arguments = {"env_name": "vr4mice", "verbose": False}

    # Access the arguments
    if args.env_name:
        arguments["env_name"] = args.env_name
        # print(f"Conda environment name: {args.env_name}")
    if args.verbose:
        arguments["verbose"] = args.verbose
        # print("Verbose output enabled")

    return arguments


# main
def main():
    args = parse_arguments()
    create_conda_env(args["env_name"], args["verbose"])

    # config_file_path = Path("task_config.json")
    # save_to_config(config_file_path)


if __name__ == "__main__":
    main()
