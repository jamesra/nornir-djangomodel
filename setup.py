'''
Created on Aug 30, 2013

@author: u0490822
'''




# from ez_setup import use_setuptools
# from setuptools import setup, find_packages
import os
import glob

from ez_setup import use_setuptools

if __name__ == '__main__':
    use_setuptools()

    from setuptools import setup, find_packages

    packages = find_packages()

    install_requires = ["nornir_volumemodel>=1.2.0",
                        "nornir_imageregistration>=1.2.0"]

    dependency_links = ["git+http://github.com/nornir/nornir-imageregistration#egg=nornir_imageregistration-1.2.0",
                        "git+http://github.com/nornir/nornir-volumemodel#egg=nornir_volumemodel-1.2.0"]

    scripts = None

    classifiers = ['Programming Language :: Python :: 3.4',
                   'Topic :: Scientific/Engineering']

    setup(name='nornir_djangomodel',
          classifiers=classifiers,
          version='1.2.0',
          description="Django web model for Nornir",
          author="James Anderson",
          author_email="James.R.Anderson@utah.edu",
          url="https://github.com/nornir/nornir-djangomodel",
          packages=packages,
          scripts=scripts,
          test_suite='test',
          install_requires=install_requires,
          dependency_links=dependency_links)