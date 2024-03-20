import setuptools

setuptools.setup(
    name="base_actions",
    install_requires=[
        "datajoint",
        "opencv-python-headless",
        "gitpython",
        "numpy",
        "scipy",
        "matplotlib",
        "tifffile",
    ],
    extras_require={
        "docs": ["numpydoc", "jupyter-book", "ghp-import"],
    },
    packages=setuptools.find_packages(),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    entry_points="""[console_scripts]
            unset=unset:main""",
)
