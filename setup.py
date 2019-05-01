#!/usr/bin/env python

import sys
import os
from setuptools import setup, find_packages
from blockade import __version__

with open("requirements.txt") as fh:
    requires = fh.readlines()

with open("test-requirements.txt") as fh:
    tests_require = requires + fh.readlines()

with open('README.rst') as f:
    readme = f.read()
with open('CHANGES.rst') as f:
    changes = f.read()

setup(
    name='embargo',
    version=__version__,
    description='Embargo: network fault testing with Docker',
    long_description=readme + '\n\n' + changes + '\n\n',
    author='David LaBissoniere',
    author_email='david@labisso.com',
    url="https://github.com/dgraph-io/embargo",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requires,
    tests_require=tests_require,
    extras_require={
        'test': tests_require,
    },
    entry_points={
        'console_scripts': [
            'embargo=blockade.cli:main'
        ]
    },
    zip_safe=False,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7'
    ],
)
