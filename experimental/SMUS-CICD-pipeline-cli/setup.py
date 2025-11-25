"""SMUS CI/CD Pipeline CLI packaging setup."""

import os
from setuptools import setup, find_packages

# Read README for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Declare your non-python data files:
data_files = []
if os.path.exists("configuration"):
    for root, dirs, files in os.walk("configuration"):
        data_files.append(
            (
                os.path.relpath(root, "configuration"),
                [os.path.join(root, f) for f in files],
            )
        )

# Install requirements
install_requires = [
    "typer>=0.9.0",
    "pyyaml>=6.0",
    "boto3>=1.26.0",
    "botocore>=1.29.0",
    "jsonschema>=4.17.0",
    "rich>=13.0.0",
    "requests>=2.28.0",
]

# Development requirements
dev_requires = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "pytest-html>=3.1.0",
    "black>=23.0.0",
    "flake8>=6.0.0",
    "isort>=5.12.0",
    "mypy>=1.0.0",
    "safety>=2.3.0",
    "bandit>=1.7.0",
]

setup(
    name="smus-cicd-cli",
    version="1.0.0",
    author="AWS SageMaker Unified Studio Team",
    author_email="sagemaker-unified-studio@amazon.com",
    description="A CLI tool for managing CI/CD pipelines in SageMaker Unified Studio (SMUS)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker",
    project_urls={
        "Bug Tracker": "https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/issues",
        "Documentation": "https://github.com/aws/Unified-Studio-for-Amazon-Sagemaker/tree/main/docs",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=install_requires,
    extras_require={
        "dev": dev_requires,
    },
    entry_points={
        "console_scripts": [
            "smus-cli=smus_cicd.cli:app",
        ],
    },
    data_files=data_files,
    python_requires=">=3.8",
    keywords="sagemaker, unified-studio, cicd, pipeline, aws, data-science, mlops",
    include_package_data=True,
    zip_safe=False,
)
