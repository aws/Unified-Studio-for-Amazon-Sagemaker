"""SMUS CI/CD Pipeline CLI packaging setup."""

import os
from setuptools import setup, find_packages

# Declare your non-python data files:
data_files = []
if os.path.exists("configuration"):
    for root, dirs, files in os.walk("configuration"):
        data_files.append(
            (os.path.relpath(root, "configuration"), [os.path.join(root, f) for f in files])
        )

# Install requirements
install_requires = [
    "typer>=0.9.0",
    "pyyaml>=6.0",
    "boto3>=1.26.0",
    "requests>=2.28.0",
]

setup(
    name="smus-cicd-cli",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=install_requires,
    entry_points={
        "console_scripts": [
            "smus-cli=smus_cicd.cli:app",
        ],
    },
    data_files=data_files,
    python_requires=">=3.8",
)
