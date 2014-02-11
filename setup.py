#!/usr/bin/env python

import os
from setuptools import setup, find_packages


VERSION_PY = os.path.join(os.path.dirname(__file__), "blockade/version.py")

# this execs blockade/version.py on it's own and brings __version__ into this
# package. Ugliness is to support both Python 2 and 3.
__version__ = None
with open(VERSION_PY) as f:
    code = compile(f.read(), VERSION_PY, "exec")
    exec(code)
assert __version__, "Failed to get version from %s" % (VERSION_PY)

requires = [
    "clint",
    "docker-py",
    "pyyaml"
]

tests_require = requires + [
    'coverage',
    'mock',
    'nose',
]

with open('README.md') as f:
    readme = f.read()

setup(
    name='blockade',
    version=__version__,
    description='Blockade: network fault testing with Docker',
    long_description=readme + '\n\n',
    author='David LaBissoniere',
    author_email='david@labisso.com',
    url="https://kazoo.readthedocs.org",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requires,
    tests_require=tests_require,
    extras_require={
        'test': tests_require,
    },
    entry_points={
        'console_scripts': [
            'blockade=blockade.cli:main'
        ]
    },
    zip_safe=False,
    classifiers=(
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7'
    ),
)
