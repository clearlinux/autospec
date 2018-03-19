from setuptools import setup, find_packages

import sys, os
version = "1.2.0"

def readme():
    with open("README.rst") as f:
        return f.read()

setup(name="autospec",
      description="Automated creation of RPM packaging",
      long_description=readme(),
      version = version,
      license = "GPLv3",
      packages = ["autospec"],
      package_data = {
            '': ['*.pl', '*.dic'],
      },
      classifiers=[
            'Intended Audience :: Developers',
            'Topic :: Software Development :: Build Tools',
            'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
            # Python versions supported.
            'Programming Language :: Python :: 3 :: Only',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.2',
            'Programming Language :: Python :: 3.3',
            'Programming Language :: Python :: 3.4',
            'Programming Language :: Python :: 3.5',
            'Programming Language :: Python :: 3.6',
        ],
      include_package_data = True,
)
