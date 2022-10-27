import importlib

from setuptools import find_packages, setup

# Load version.py without importing __init__.py and it's dependencies
# https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
spec = importlib.util.spec_from_file_location("version", "universalasync/version.py")
version_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(version_module)

setup(
    name="universalasync",
    packages=find_packages(),
    version=version_module.VERSION,
    license="MIT",
    description="A library to help automate the creation of universal python libraries",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="MrNaif2018",
    author_email="chuff184@gmail.com",
    url="https://github.com/bitcartcc/universalasync",
    keywords=["async", "await", "bitcartcc", "universal", "sync", "asyncio", "asynctosync", "synctoasync"],
    install_requires=[],
    package_data={"universalasync": ["py.typed"]},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
