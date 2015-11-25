#!/bin/true
#
# commitmessage.py - part of autospec
# Copyright (C) 2015 Intel Corporation
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# objective
#
# heuristics to find a git commit message
#
#

import config
import tarball
import subprocess

commitmessage = ""

cves = set()
have_cves = 0
cvestring = "";
    
    
def new_cve(str):
    global cvestring;
    global have_cves
    global cves
    
    cves.add(str)
    have_cves = 1;
    cvestring = cvestring + " " + str
    
def guess_commit_message():
    global cvestring
    global have_cves
     
    # default commit messages before we get too smart
    if config.old_version != None and config.old_version != tarball.version:
        commitmessage = "Autospec creation for update from version " + config.old_version + " to version " + tarball.version + "\n\n"
    else:
        if have_cves > 0:
          commitmessage = "Fix for " + cvestring + "\n\n"
        else:
          commitmessage = "Autospec creation for version " + tarball.version + "\n\n"
          
          
    if have_cves > 0:
        commitmessage = commitmessage + "CVEs fixed in this build: " + cvestring + "\n\n"
        
        

    print("Guessed commit message:")
    print(commitmessage)
    with open("commitmsg", "w") as file:
      file.write(var)
  