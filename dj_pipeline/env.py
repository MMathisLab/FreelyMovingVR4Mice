"""
Project-specific environment variable defaults.

NOTE: Database configuration (DJ_HOST, DJ_USER, DJ_PWD) is now handled by
datajoint.json and .secrets/datajoint.json - do NOT set them here.
"""
import os

# Project-specific settings (not handled by DataJoint 2.0)
os.environ.setdefault("DJ_LAB", "lab_name")
os.environ.setdefault("GUI", "gui_mode")
os.environ.setdefault("EMAIL", "True")
os.environ.setdefault("VR4MICE_EMAIL_RECIPIENTS", "mathislab")
os.environ.setdefault("IMG_SRC", "Imagingsource")

# DataJoint feature flags
os.environ.setdefault("DJ_SUPPORT_FILEPATH_MANAGEMENT", "TRUE")
os.environ.setdefault("DJ_SUPPORT_ADAPTED_TYPES", "TRUE")
