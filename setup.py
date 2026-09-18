"""
A small Python module to read/write PFM (Portable Float Map) images
"""

import pathlib

from setuptools import find_packages, setup

here = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (here / "README.md").read_text(encoding="utf-8")

setup(
    name="justpfm",
    version="1.0.0",
    description="Read and write PFM files",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MartinPeris/justPFM",
    author="Martin Peris Martorell",
    author_email="cosmoperis@gmail.com",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Image Processing",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Programming Language :: Python :: 3 :: Only",
    ],
    keywords="pfm, portable, float, map",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.10, <4",
    install_requires=["numpy"],
    extras_require={
        "dev": ["check-manifest"],
        "test": ["pytest", "pytest-cov", "hypothesis==6.168.0"],
    },
    project_urls={
        "Bug Reports": "https://github.com/MartinPeris/justPFM/issues",
        "Source": "https://github.com/MartinPeris/justPFM",
    },
)
