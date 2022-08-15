from setuptools import find_packages, setup

import codetype

DESCRIPTION = """Tool for improving typing speed and accuracy while "programming"!"""
LONG_DESCRIPTION = DESCRIPTION

INSTALL_REQUIRES = [
    "click",
    "numpy",
    "validators",
    "requests",
    "colour",
    "rich",
    "textual==0.1.18",
]

setup(
    name="codetype",
    version="0.1",
    author="Jacob J",
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    packages=find_packages(exclude=["tests"]),
    license="MIT",
    install_requires=INSTALL_REQUIRES,
    extras_require={
        "dev": [
            "black",
            "flake8",
            "jupyter",
            # "pydocstyle",
            # "pytest",
            # "pytest-coverage",
            # "tox",
        ],
    },
    entry_points={
        "console_scripts": [
            "ctt = codetype.cli:cli",
        ]
    },
)
