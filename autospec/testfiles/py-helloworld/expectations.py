"""
This file, expectations.py, defines expected test results and is not added to
the test source tarball.
"""
import os

buildreqs = ['pip', 'mock', 'requests', 'six', 'docutils', 'python']
license = 'GPL-3.0'

with open('testfiles/py-helloworld/spec-expectations', 'r') as spec:
    specfile = spec.read()
specfile = specfile.replace('{}', os.getcwd()).split('\n')

with open('testfiles/py-helloworld/conf-expectations', 'r') as conf:
    conffile = conf.read()
conffile = conffile.split('\n')

output_strings = []
