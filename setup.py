#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

if sys.argv[-1] == 'publish':
    os.system('python setup.py sdist upload')
    sys.exit()

readme = open('README.md').read()
history = open('HISTORY.rst').read().replace('.. :changelog:', '')

setup(
    name='xatmos',
    version='0.1.0',
    description='A GUI viewer for looking at EEtelluric transmission, TEXES orders, and identifying absorption lines.',
    long_description=readme + '\n\n' + history,
    author='Henry Roe',
    author_email='hroe@hroe.me',
    url='https://github.com/henryroe/xatmos',
    packages=[
        'xatmos',
    ],
    package_dir={'xatmos': 'xatmos'},
    package_data = {'xatmos': ['atmos.txt.gz', 'hitran*txt.gz', 'orders.txt']},
    include_package_data=True,
    install_requires=['numpy>=1.6.1',
                      'pandas',
                      'pyface',
                      'traits',
                      'traitsui',
                      'matplotlib'
    ],
    license='LICENSE.txt',
    zip_safe=False,
    keywords='xatmos',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
    ],
)
