"""
This file, expectations.py, defines expected test results and is not added to
the test source tarball.
"""
import os

buildreqs = ['xz',
             'gcc-dev32',
             'gcc-libgcc32',
             'gcc-libstdc++32',
             'glibc-dev32',
             'glibc-libc32']

license = 'GPL-3.0'
with open('tests/testfiles/c-helloworld-32/spec-expectations', 'r') as spec:
    specfile = spec.read()
specfile = specfile.replace('{}', os.getcwd()).split('\n')

with open('tests/testfiles/c-helloworld-32/conf-expectations', 'r') as conf:
    conffile = conf.read()
conffile = conffile.split('\n')

output_strings = []
