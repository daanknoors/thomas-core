#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup

setup(
    name='pybn',
    version='0.1',
    description='Very simple (almost naive ;) bayesian network implementation',
    url='https://github.com/mellesies/py-bn',
    author='Melle Sieswerda',
    author_email='m.sieswerda@iknl.nl',
    license='Apache 2.0',
    packages=['pybn'],
    python_requires='>= 3.6',
    install_requires=[
        'numpy',
        'pandas',
        'lark-parser',
        'termcolor',
        'networkx',
    ],
    zip_safe=False,
    test_suite='nose.collector',
    tests_require=['nose'],    
)