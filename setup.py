import setuptools

setuptools.setup(
    name = "vr4mice",
    version = "0.0.1",
    author = "M. Mathis Lab Members",
    author_email = "mathis@rowland.harvard.edu",
    description = " Tasks and GUI to run experiments controlled by Teensy & Arduino microcontrollers",
    url = "https://github.com/MMathisLab/FreelyMovingVR4Mice",
    python_requires = '>=3.5, <3.11',
    install_requires = [
    'numpy>=1.16.0',
    'ruamel.yaml>=0.15.0',
    'pyserial',
    'mlagents-envs==0.14.0',
    'opencv-python'],
    extras_require={
        "docs": ["numpydoc", "jupyter-book","ghp-import"],
        "deeplabcut": ["deeplabcut[tf]"],
    },
    packages = setuptools.find_packages(),
    package_data = {'teensyexp' : ['cfg/*']},
    include_package_data = True,
    entry_points = {'console_scripts' : ['vr4mice=vr4mice:main']}
)
