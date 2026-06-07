import os

# Local dev defaults only — copy from .env.example and edit for your machine.
# Do not commit real production passwords here.
os.environ.setdefault("DJ_HOST", "127.0.0.1:3309")
os.environ.setdefault("DJ_USER", "root")
os.environ.setdefault("DJ_PWD", "change-me")
os.environ.setdefault("DJ_LAB", "mathis-lab")
os.environ.setdefault("GUI", "yes")
os.environ.setdefault("EMAIL", "no")
os.environ.setdefault("VR4MICE_EMAIL_RECIPIENTS", "mathislab")
os.environ.setdefault("IMG_SRC", "Imagingsource")
os.environ.setdefault("DJ_SUPPORT_FILEPATH_MANAGEMENT", "TRUE")
os.environ.setdefault("DJ_SUPPORT_ADAPTED_TYPES", "TRUE")
