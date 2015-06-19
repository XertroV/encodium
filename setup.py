#!/usr/bin/env python

from setuptools import setup

setup(name='encodium',
      version='0.1.0',
      description='Yet another pure python serialization module',
      author='Kitten Tofu',
      author_email='kitten@eudemonia.io',
      url='http://eudemonia.io/encodium/',
      packages=['encodium'],
      install_requires=['bencodepy'],
     )
