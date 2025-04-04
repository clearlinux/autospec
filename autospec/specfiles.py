#!/usr/bin/python3
#
# specfile.py - part of autospec
# Copyright (C) 2016 Intel Corporation
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
# Write spec file
#

import os
import re
import time
import types
from collections import OrderedDict

import git
from jinja2 import Environment
from jinja2.loaders import DictLoader
from util import _file_write, open_auto

AVX2_CFLAGS = "-march=x86-64-v3"
AVX2_LCFLAGS = "-march=x86-64-v3"
AVX2_LFLAGS = "-Wl,-z,x86-64-v3"
AVX512_CFLAGS = "-march=x86-64-v4 -mprefer-vector-width=512"
AVX512_FCFLAGS = "-march=x86-64-v4 -mprefer-vector-width=256"
AVX512_LCFLAGS = "-march=x86-64-v4"
AVX512_LFLAGS = "-Wl,-z,x86-64-v4"
APX_CFLAGS = "-march=x86-64-v4 -mapxf"
APX_LCFLAGS = "-march=x86-64-v4"
APX_LFLAGS = "-Wl,-z,x86-64-v4"


class Specfile(object):
    """Holds data and methods needed to write the spec file."""

    def __init__(self, url, version, name, release, config, requirements, content):
        """Add default information for specfile template."""
        self.url = url
        self.version = version
        self.name = name
        self.release = release
        self.config = config
        self.requirements = requirements
        self.content = content
        self.specfile = None
        self.source_index = {}
        self.default_sum = ""
        self.hashes = dict()
        self.licenses = []
        self.license_files = []
        self.packages = OrderedDict()
        self.default_desc = ""
        self.locales = []
        self.build_dirs = dict()  # Build directories, indexed by source URL
        self.tests_config = ""
        self.excludes = []
        self.file_maps = {}
        self.keyid = ""
        self.email = ""
        self.extra_cmake = config.extra_cmake + " " + " ".join(requirements.extra_cmake)
        self.extra_cmake_openmpi = config.extra_cmake_openmpi + " " + " ".join(requirements.extra_cmake_openmpi)
        self.setuid = []

    def write_spec(self):
        """Write spec file."""
        spec_path = f"{os.path.join(self.config.download_path, self.name)}.spec"
        self.specfile = open_auto(spec_path, "w")
        self.specfile.write_strip = types.MethodType(_file_write, self.specfile)

        # last chance to sanitize url for template and build types
        if self.config.urlban:
            clean_url = re.sub(self.config.urlban, "localhost", self.url)
            # Duplicate prefixes entry before we change the url
            self.content.prefixes[clean_url] = self.content.prefixes.get(self.url)
            self.url = clean_url

        template_path = f"{spec_path}.template"

        if os.path.isfile(template_path):
            # make templates have a template build pattern
            self.config.default_pattern = "template"
        # spec file comment header
        self.write_comment_header()

        if os.path.isfile(template_path):
            with open_auto(template_path) as tfile:
                template_content = tfile.read()
            template = Environment(loader=DictLoader({'spec': template_content})).get_template('spec')
            kw = {
                'package_name': self.name,
                'package_version': self.version,
                'package_url': self.url,
                'package_release': self.release,
            }
            self.specfile.write(template.render(**kw))
            self.specfile.write_strip('\n')
            self.specfile.close()
            # return specfile type built so autospec knows how to
            # handle build results (template should only builds once)
            return "template"

        if self.config.config_opts.get('keepstatic'):
            self._write("%define keepstatic 1\n")

        # general package header
        self.write_nvr()
        self.write_sources()
        self.write_summary()
        self.write_license()

        self.write_main_subpackage_requires()
        self.write_buildreq()
        self.write_strip_command()
        self.write_debug_command()
        self.write_patch_header()

        # main package extra content
        self.write_description()
        self.write_files_header()

        # build instructions
        self.write_buildpattern()

        # scriplets
        self.write_scriplets()

        # %files
        self.write_files()
        self.write_lang_files()

        self.specfile.close()

        # return specfile type built so autospec knows how to
        # handle build results (generate has multiple builds)
        return "generate"

    def write_comment_header(self):
        """Write comment header to spec file."""
        self._write("#\n")
        self._write("# This file is auto-generated. DO NOT EDIT\n")
        self._write("# Generated by: autospec.py\n")
        self._write(f"# Using build pattern: {self.config.default_pattern}\n")
        tag, commit = git.get_autospec_info()
        self._write(f"# autospec version: {tag}\n")
        self._write(f"# autospec commit: {commit}\n")
        self._write("#\n")

        # if package was verified, write public key information
        if self.keyid:
            sig_msg = "# Source0 file verified with key 0x{}".format(self.keyid)
            if self.email:
                sig_msg += " ({})".format(self.email)

            self._write_strip(sig_msg)
            self._write_strip("#")

    def write_nvr(self):
        """Write name, version, and release information."""
        self._write("Name     : {}\n".format(self.name))
        self._write("Version  : {}\n".format(self.version))
        self._write("Release  : {}\n".format(str(self.release)))
        self._write("URL      : {}\n".format(self.url))
        self._write("Source0  : {}\n".format(self.url))

    def write_sources(self):
        """Append additional source files.

        Append systemd unit files, gcov, and additional source tarballs are the currently supported file types.
        """
        count = 0
        for source in sorted(self.config.sources["unit"] + self.config.sources["archive"]
                             + self.config.sources["tmpfile"] + self.config.sources["sysuser"] + self.config.sources["gcov"]): # NOQA
            count += 1
            self.source_index[source] = count
            if self.config.urlban:
                source = re.sub(self.config.urlban, "localhost", source)
            self._write("Source{0}  : {1}\n".format(count, source))

        # if package is verified, include the signature in the source tarball
        if self.keyid and self.config.signature:
            # We'll need gnupg to verify the signature. Need to add it here so it's ready before write_buildreq
            self.requirements.add_buildreq("gnupg")

            count += 1
            self._write_strip(f"Source{count}  : {self.config.signature}")
            self.config.signature_macro = f"%{{SOURCE{count}}}"

            # Also include the public key in the source tarball.
            count += 1
            self._write_strip(f"Source{count}  : {self.keyid}.pkey")
            self.config.pkey_macro = f"%{{SOURCE{count}}}"

        for source in self.config.extra_sources:
            count += 1
            self._write("Source{0}  : {1}\n".format(count, source[0]))

    def write_summary(self):
        """Write package summary to spec file."""
        if len(self.default_sum.strip()) < 1:
            self.default_sum = "No summary provided"
        self._write("Summary  : {}\n".format(self.default_sum.strip()))
        self._write("Group    : Development/Tools\n")

    def write_license(self):
        """Write license information to spec file."""
        self._write("License  : {}\n".format(" ".join(sorted(self.licenses))))

    def write_main_subpackage_requires(self):
        """Write subpackage build requirements."""
        for pkg in sorted(self.packages):
            if pkg == "autostart" and self.config.config_opts.get('no_autostart'):
                continue
            if pkg.startswith("extras-"):
                continue
            if pkg in ["ignore", "main", "dev", "active-units", "extras",
                       "lib32", "dev32", "doc", "examples", "abi", "staticdev",
                       "staticdev32", "tests"]:
                continue
            # honor requires_ban for manual overrides
            if "{}-{}".format(self.name, pkg) in self.requirements.banned_requires.get(None, []):
                continue
            self._write("Requires: {}-{} = %{{version}}-%{{release}}\n".format(self.name, pkg))

        for pkg in sorted(self.requirements.requires.get(None, [])):
            self._write("Requires: {}\n".format(pkg))

    def write_buildreq(self):
        """Write build requirements."""
        for req in sorted(self.requirements.buildreqs):
            self._write("BuildRequires : {}\n".format(req))

    def write_strip_command(self):
        """Write commands to prevent stripping binary if requested."""
        if self.config.config_opts['nostrip'] or not self.config.config_opts['full-debug-info']:
            self._write("# Suppress stripping binaries\n")
            self._write("%define __strip /bin/true\n%define debug_package %{nil}\n")

    def write_debug_command(self):
        """Write commands to prevent debug info generation if requested."""
        if self.config.config_opts['nodebug']:
            self._write("# Suppress generation of debuginfo\n")
            self._write("%global debug_package %{nil}\n")

    def write_patch_header(self):
        """Write patch list header."""
        # First loop will set this to 0 when we start. Second loop adds one
        # and picks up from where first loop left off.
        count = -1
        # Write the patches for the primary version as given in Makefile
        for count, patch in enumerate(self.config.patches):
            self._write("Patch{0}: {1}\n".format(count + 1, patch.split()[0]))
        # Write the version-specific patches
        for version in self.config.verpatches:
            for count, patch in enumerate(self.config.verpatches[version], start=count + 1):
                self._write("Patch{0}: {1}\n".format(count + 1, patch.split()[0]))

    def write_description(self):
        """Write package description."""
        self._write("\n%description\n{}\n".format(self.default_desc.strip()))

    def write_files_header(self):
        """Write file headers to spec file."""
        groups = {}
        groups["dev"] = "Development"
        groups["bin"] = "Binaries"
        groups["lib"] = "Libraries"
        groups["doc"] = "Documentation"
        groups["data"] = "Data"
        groups["services"] = "Systemd services"

        deps = {}
        deps["dev"] = ["lib", "bin", "data"]
        deps["doc"] = ["man", "info"]
        deps["examples"] = ["dev"]
        deps["dev32"] = ["lib32", "bin", "data", "dev"]
        deps["bin"] = ["data", "libexec", "config", "setuid", "attr", "license", "services", "filemap"]
        deps["lib"] = ["data", "libexec", "license", "filemap"]
        deps["libexec"] = ["config", "license", "filemap"]
        deps["lib32"] = ["data", "license"]
        deps["python"] = ["python3"]
        deps["python3"] = ["filemap"]
        if "services" in self.packages:
            if service_reqs := self.requirements.requires.get("services"):
                service_reqs.add("systemd")
            else:
                self.requirements.requires["services"] = set(["systemd"])
        if self.config.config_opts.get('dev_requires_extras'):
            deps["dev"].append("extras")
        if self.config.config_opts.get('openmpi'):
            deps["dev"].append("openmpi")
        for k, v in self.file_maps.items():
            if "requires" in v:
                deps[k] = v['requires']

        # migration workaround; if we have a python3 package
        # we add an artificial python package

        if ("python3" in self.packages) and ("python" not in self.packages):
            self.packages["python"] = set()

        provides = {}
        provides["dev"] = ["devel"]

        for pkg in sorted(self.packages):
            if pkg in ["ignore", "main"]:
                continue

            self._write("\n%package {}\n".format(pkg))
            self._write("Summary: {} components for the {} package.\n"
                        .format(pkg, self.name))
            if pkg in groups:
                self._write("Group: {}\n".format(groups[pkg]))
            else:
                self._write("Group: Default\n")

            for dep in deps.get(pkg, []):
                # honor requires_ban for manual overrides
                if f"{self.name}-{dep}" in self.requirements.banned_requires.get(pkg, []):
                    continue
                if dep in self.packages:
                    self._write("Requires: {}-{} = %{{version}}-%{{release}}\n".format(self.name, dep))

            for prov in provides.get(pkg, []):
                self._write("Provides: {}-{} = %{{version}}-%{{release}}\n".format(self.name, prov))

            if pkg in ("dev", "perl", "tests"):
                self._write("Requires: {} = %{{version}}-%{{release}}\n".format(self.name))

            if pkg in ("staticdev", "staticdev32"):
                self._write("Requires: {}-dev = %{{version}}-%{{release}}\n".format(self.name))

            if pkg == "python":
                if self.name != self.name.lower():
                    self._write("Provides: {}-python\n".format(self.name.lower()))

            if pkg == "python3":
                self._write("Requires: python3-core\n")
                if self.requirements.pypi_provides:
                    self._write(f"Provides: pypi({self.requirements.pypi_provides})\n")

            for req in sorted(self.requirements.requires.get(pkg, [])):
                self._write(f"Requires: {req}\n")

            for prov in sorted(self.requirements.provides.get(pkg, [])):
                self._write(f"Provides: {prov}\n")

            self._write("\n%description {}\n".format(pkg))
            self._write("{} components for the {} package.\n".format(pkg, self.name))
            self._write("\n")

    def write_buildpattern(self):
        """Write build pattern to spec file."""
        self._write_strip("\n")
        pattern_method = getattr(self, 'write_{}_pattern'.format(self.config.default_pattern))
        if pattern_method:
            pattern_method()

        self.write_source_installs()
        self.write_service_restart()
        self.write_exclude_deletes()
        self.write_install_append()
        # elf move is last is copying content already
        # installed bits to their individual buildroots
        # maybe need a new install_append_last file
        # eventually though
        self.write_elf_move()

    def write_scriplets(self):
        """Write post and pre scripts to spec file."""
        for pkg in sorted(self.packages):
            if pkg in ["ignore", "main", "locales"]:
                continue
            for script in ["post", "pre"]:
                content = self.config.read_conf_file("{}.{}".format(script, pkg))
                if content:
                    self._write("\n%{0} {1}\n".format(script, pkg))
                    content = ['{}\n'.format(line) for line in content]
                    self.specfile.writelines(content)

    def write_files(self):
        """Write %files section to spec file."""
        self._write("\n%files\n")
        self._write("%defattr(-,root,root,-)\n")
        if "main" in self.packages:
            for filename in sorted(self.packages["main"]):
                self._write("{}\n".format(self.quote_filename(filename)))

        for pkg in sorted(self.packages):
            if pkg in ["ignore", "main", "locales"]:
                continue

            self._write("\n%files {}\n".format(pkg))
            if pkg in ["doc", "license", "man", "info"]:
                self._write("%defattr(0644,root,root,0755)\n")
            else:
                self._write("%defattr(-,root,root,-)\n")
            for filename in sorted(self.packages[pkg]):
                self._write("{}\n".format(self.quote_filename(filename)))

    def write_lang_files(self):
        """Write lang files to spec."""
        if not self.locales:
            return

        self._write("\n%files locales")
        for lang in self.locales:
            self._write(" -f {}.lang".format(lang))

        self._write("\n%defattr(-,root,root,-)\n\n")

    def write_lang_c(self, export_epoch=False):
        """Write C language pattern."""
        self._write_strip("%build")
        self.write_build_prepend_once()
        self.write_build_prepend()
        self.write_proxy_exports()
        self._write_strip("export LANG=C.UTF-8")
        if export_epoch:
            # time.time() returns a float, but we only need second-precision
            self._write_strip("export SOURCE_DATE_EPOCH={}".format(int(time.time())))
        if self.config.config_opts['asneeded']:
            self._write_strip("unset LD_AS_NEEDED\n")

    def write_proxy_exports(self):
        """Write proxy exports to localhost to block build/check calls to internet."""
        self._write_strip("export http_proxy=http://127.0.0.1:9/")
        self._write_strip("export https_proxy=http://127.0.0.1:9/")
        self._write_strip("export no_proxy=localhost,127.0.0.1,0.0.0.0")

    def write_make_line(self, build32=False):
        """Write make line to spec file."""
        if self.config.make_prepend:
            self._write_strip("## make_prepend content")
            for line in self.config.make_prepend:
                self._write_strip("{}\n".format(line))
            self._write_strip("## make_prepend end")
        if self.config.make_command:
            make = self.config.make_command
        elif self.config.config_opts['use_ninja']:
            make = "ninja"
        else:
            make = "make"
        if build32:
            self._write_strip("{} {} {} {}".format(make, self.config.parallel_build, self.config.extra_make, self.config.extra32_make))
        else:
            self._write_strip("{} {} {}".format(make, self.config.parallel_build, self.config.extra_make))

    def write_install_openmpi(self):
        """Write make install line (openmpi) to spec file."""
        self._write_strip('module load openmpi')
        make_string = '%make_install_openmpi'
        self._write_strip("{} {}".format(make_string, self.config.extra_make_install))
        self._write_strip('module unload openmpi')

    def write_cmake_line_openmpi(self):
        """Write cmake line (openmpi) to spec file."""
        if self.config.config_opts['use_ninja']:
            cmake_type = "Ninja"
        else:
            cmake_type = "Unix Makefiles"
        cmake_string = f"cmake -G '{cmake_type}' -DCMAKE_INSTALL_PREFIX=$MPI_ROOT -DCMAKE_INSTALL_SBINDIR=$MPI_BIN \\\n" \
                       '-DCMAKE_INSTALL_LIBDIR=$MPI_LIB -DCMAKE_INSTALL_INCLUDEDIR=$MPI_INCLUDE -DLIB_INSTALL_DIR=$MPI_LIB \\\n' \
                       '-DBUILD_SHARED_LIBS:BOOL=ON -DLIB_SUFFIX=64 \\\n' \
                       '-DCMAKE_AR=/usr/bin/gcc-ar -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_RANLIB=/usr/bin/gcc-ranlib \\\n'
        self._write_strip("{} {} {}".format(cmake_string, self.config.cmake_srcdir, self.extra_cmake_openmpi))

    def write_prep(self):
        """Write prep section to spec file."""
        self._write_strip("%prep")
        if self.keyid and self.config.signature:
            self._write_strip("mkdir .gnupg")
            self._write_strip("chmod 700 .gnupg")
            self._write_strip(f"gpg --homedir .gnupg --import {self.config.pkey_macro}")
            self._write_strip(f"gpg --homedir .gnupg --status-fd 1 --verify {self.config.signature_macro} %{{SOURCE0}} > gpg.status")
            self._write_strip(f"grep -E '^\\[GNUPG:\\] (GOODSIG|EXPKEYSIG) {self.keyid}' gpg.status")
        self.write_prep_prepend()
        if self.config.default_pattern == 'R':
            prefix = self.content.tarball_prefix
            self._write_strip("%setup -q -n " + prefix)
        else:
            prefix = self.content.prefixes[self.url]
            if not prefix:
                prefix = os.path.splitext(os.path.basename(self.url))[0]
                self._write_strip("%setup -q -c -n " + prefix)
            else:
                self._write_strip("%setup -q -n " + prefix)
            for archive in self.config.sources["archive"]:
                # Handle various archive types
                extract_cmd = 'tar xf {}'
                if archive.endswith('.zip'):
                    extract_cmd = 'unzip -q {}'
                if archive.endswith('.bz2') and not archive.endswith('.tar.bz2'):
                    extract_cmd = 'bzcat {0} > $(basename "{0}" .bz2)'
                if archive.endswith('.zst'):
                    if archive.endswith('.tar.zst'):
                        extract_cmd = 'tar -I zstd xf {}'
                    else:
                        extract_cmd = 'zstd -dqc {0} > $(basename "{0}" .zst)'
                self._write_strip('cd %{_builddir}')
                archive_file = os.path.basename(archive)
                if self.config.archive_details.get(archive + "prefix"):
                    self._write_strip(extract_cmd.format('%{_sourcedir}/' + archive_file))
                else:
                    # The archive doesn't have a prefix inside, so we have
                    # to create it, then extract the archive under the
                    # created directory, itself beneath BUILD
                    fake_prefix = os.path.splitext(os.path.basename(archive))[0]
                    self._write_strip("mkdir -p {}".format(fake_prefix))
                    self._write_strip("cd {}".format(fake_prefix))
                    self._write_strip(extract_cmd.format('%{_sourcedir}/' + archive_file))

            self._write_strip('cd %{_builddir}/' + prefix)

        for archive, destination in zip(self.config.sources["archive"], self.config.sources["destination"]):
            if destination.startswith(':'):
                continue
            if self.config.archive_details[archive + "prefix"] == self.content.tarball_prefix:
                print("Archive {} already unpacked in {}; ignoring destination"
                      .format(archive, self.content.tarball_prefix))
            else:
                self._write_strip("mkdir -p {}"
                                  .format(destination))

                # Here again, if the archive file has a top-level prefix
                # directory, we simply use it. If not, we have to figure
                # out where we extracted the files instead.
                archive_prefix = self.config.archive_details[archive + "prefix"]
                if not archive_prefix:
                    # Make it up
                    archive_prefix = os.path.splitext(os.path.basename(archive))[0]
                self._write_strip("cp -r %{{_builddir}}/{0}/. %{{_builddir}}/{1}/{2}"
                                  .format(archive_prefix,
                                          self.content.tarball_prefix,
                                          destination))
        self.apply_patches()

        # setup cargo.toml vendoring if needed
        if self.config.cargo_vendors:
            if self.config.subdir:
                self._write_strip("pushd " + self.config.subdir)
            self._write_strip("mkdir -p .cargo")
            self._write_strip(f"echo '\n{self.config.cargo_vendors}' >> .cargo/config.toml")
            if self.config.subdir:
                self._write_strip("popd")

        self.write_copy_prepend()

        if self.config.config_opts['32bit']:
            self._write_strip("pushd ..")
            self._write_strip("cp -a {} build32".format(self.content.tarball_prefix))
            self._write_strip("popd")
        if self.config.config_opts['use_avx2']:
            self._write_strip("pushd ..")
            self._write_strip("cp -a {} buildavx2".format(self.content.tarball_prefix))
            self._write_strip("popd")
        if self.config.config_opts['use_avx512']:
            self._write_strip("pushd ..")
            self._write_strip("cp -a {} buildavx512".format(self.content.tarball_prefix))
            self._write_strip("popd")
        if self.config.config_opts['use_apx']:
            self._write_strip("pushd ..")
            self._write_strip("cp -a {} buildapx".format(self.content.tarball_prefix))
            self._write_strip("popd")
        if self.config.config_opts['openmpi']:
            self._write_strip("pushd ..")
            self._write_strip("cp -a {} build-openmpi".format(self.content.tarball_prefix))
            self._write_strip("popd")
        self._write_strip("\n")

    def write_32bit_exports(self):
        """Write 32bit only env exports."""
        self._write_strip('export PKG_CONFIG_PATH="/usr/lib32/pkgconfig:/usr/share/pkgconfig"')
        self._write_strip('ASFLAGS="${CLEAR_INTERMEDIATE_ASFLAGS}${CLEAR_INTERMEDIATE_ASFLAGS:+ }--32"')
        self._write_strip('CFLAGS="${CLEAR_INTERMEDIATE_CFLAGS}${CLEAR_INTERMEDIATE_CFLAGS:+ }-m32 -mstackrealign"')
        self._write_strip('CXXFLAGS="${CLEAR_INTERMEDIATE_CXXFLAGS}${CLEAR_INTERMEDIATE_CXXFLAGS:+ }-m32 -mstackrealign"')
        self._write_strip('LDFLAGS="${CLEAR_INTERMEDIATE_LDFLAGS}${CLEAR_INTERMEDIATE_LDFLAGS:+ }-m32 -mstackrealign"')

    def write_variables(self):
        """Write variable exports to spec file."""
        flags = []
        arch = os.uname()[4]

        # Clear ships with a patch in GCC that allows ignoring the -Werror
        # compilation flag if this environment variable is set.  -Werror
        # is a useful flag for the upstream package maintainers, but is
        # a source of headaches for downstream users.
        self._write_strip("export GCC_IGNORE_WERROR=1\n")

        if self.config.config_opts['use_clang']:
            self._write_strip("export CC=clang\n")
            self._write_strip("export CXX=clang++\n")
            self._write_strip("export LD=ld.gold\n")
            self._write_strip("CLEAR_INTERMEDIATE_CFLAGS=${CLEAR_ORIG_CFLAGS/ -Wa,/ -fno-integrated-as -Wa,}")
            self._write_strip("CLEAR_INTERMEDIATE_CXXFLAGS=${CLEAR_ORIG_CXXFLAGS/ -Wa,/ -fno-integrated-as -Wa,}")
            lto = "-flto"
        else:
            lto = "-flto=auto"

        if self.config.config_opts['optimize_size']:
            if self.config.config_opts['use_clang']:
                flags.extend(["-Os", "-ffunction-sections", "-fdata-sections"])
            else:
                flags.extend(["-Os", "-ffunction-sections", "-fdata-sections", "-fno-semantic-interposition"])
        if self.config.config_opts['security_sensitive']:
            flags.append("-fstack-protector-strong")
            if arch == 'x86_64':
                flags.append("-fzero-call-used-regs=used")
        if self.config.config_opts['insecure_build']:
            self._write_strip('CLEAR_INTERMEDIATE_CFLAGS="-O3 -g -fopt-info-vec "\n')
        if self.config.config_opts['conservative_flags']:
            self._write_strip('CLEAR_INTERMEDIATE_CFLAGS="-O2 -g -Wp,-D_FORTIFY_SOURCE=2 '
                              "-fexceptions -fstack-protector "
                              "--param=ssp-buffer-size=32 -Wformat "
                              "-Wformat-security -Wno-error "
                              "-Wl,-z,max-page-size=0x4000 "
                              '-march=westmere"\n')
            self._write_strip("CLEAR_INTERMEDIATE_CXXFLAGS=$CLEAR_INTERMEDIATE_CFLAGS\n")
            self._write_strip('CLEAR_INTERMEDIATE_FFLAGS="-O2 -g -Wp,-D_FORTIFY_SOURCE=2 '
                              "-fexceptions -fstack-protector "
                              "--param=ssp-buffer-size=32 "
                              "-Wno-error "
                              "-Wl,-z,max-page-size=0x4000 "
                              '-march=westmere"\n')
            self._write_strip("CLEAR_INTERMEDIATE_FCFLAGS=$CLEAR_INTERMEDIATE_FFLAGS\n")
        if self.config.config_opts['funroll-loops']:
            if self.config.config_opts['use_clang']:
                flags.extend(["-O3"])
            else:
                flags.extend(["-fno-semantic-interposition", "-falign-functions=32"])
        if not self.config.config_opts['full-debug-info'] and not self.config.config_opts['use_clang']:
            flags.extend(["-gno-variable-location-views", "-gno-column-info", "-femit-struct-debug-baseonly", "-fdebug-types-section", "-gz=zstd", "-g1"])
        if self.config.default_pattern != 'qmake' or self.config.default_pattern != 'qmake6':
            if self.config.config_opts['use_lto']:
                flags.extend(["-O3", lto, "-ffat-lto-objects"])
                if self.config.config_opts['use_clang']:
                    self._write_strip("export AR=llvm-ar\n")
                    self._write_strip("export RANLIB=llvm-ranlib\n")
                    self._write_strip("export NM=llvm-nm\n")
                else:
                    self._write_strip("export AR=gcc-ar\n")
                    self._write_strip("export RANLIB=gcc-ranlib\n")
                    self._write_strip("export NM=gcc-nm\n")
            else:
                flags.extend(["-fno-lto"])
        if self.config.config_opts['fast-math']:
            flags.extend(["-ffast-math", "-ftree-loop-vectorize"])
        if self.config.config_opts['pgo']:
            flags.extend(["-O3"])
        if self.content.gcov_file:
            flags = list(filter((lto).__ne__, flags))
            flags.extend(["-O3", "-fauto-profile=%{{SOURCE{0}}}".format(self.source_index[self.config.sources["gcov"][0]])])
        if flags or self.config.config_opts['broken_c++']:
            flags = sorted(list(set(flags)))
            self._write_strip('CLEAR_INTERMEDIATE_CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {0} "\n'.format(" ".join(flags)))
            self._write_strip('CLEAR_INTERMEDIATE_FCFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {0} "\n'.format(" ".join(flags)))
            self._write_strip('CLEAR_INTERMEDIATE_FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {0} "\n'.format(" ".join(flags)))
            # leave the export CXXFLAGS line open in case
            self._write('CLEAR_INTERMEDIATE_CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {0} '.format(" ".join(flags)))
            if self.config.config_opts['broken_c++']:
                self._write('-std=gnu++98')
            # close the open quote from CXXFLAGS export and add newline
            self._write('"\n')

        if self.config.profile_payload and self.config.profile_payload[0]:
            genflags = []
            useflags = []
            genflags.extend(["-fprofile-generate", "-fprofile-dir=/var/tmp/pgo", "-fprofile-update=atomic"])
            useflags.extend(["-fprofile-use", "-fprofile-dir=/var/tmp/pgo", "-fprofile-correction"])

            self._write_strip('export CFLAGS_GENERATE="$CLEAR_INTERMEDIATE_CFLAGS {0} "\n'.format(" ".join(genflags)))
            self._write_strip('export FCFLAGS_GENERATE="$CLEAR_INTERMEDIATE_FCFLAGS {0} "\n'.format(" ".join(genflags)))
            self._write_strip('export FFLAGS_GENERATE="$CLEAR_INTERMEDIATE_FFLAGS {0} "\n'.format(" ".join(genflags)))
            self._write_strip('export CXXFLAGS_GENERATE="$CLEAR_INTERMEDIATE_CXXFLAGS {0} "\n'.format(" ".join(genflags)))
            self._write_strip('export LDFLAGS_GENERATE="$CLEAR_INTERMEDIATE_LDFLAGS {0} "\n'.format(" ".join(genflags)))

            self._write_strip('export CFLAGS_USE="$CLEAR_INTERMEDIATE_CFLAGS {0} "\n'.format(" ".join(useflags)))
            self._write_strip('export FCFLAGS_USE="$CLEAR_INTERMEDIATE_FCFLAGS {0} "\n'.format(" ".join(useflags)))
            self._write_strip('export FFLAGS_USE="$CLEAR_INTERMEDIATE_FFLAGS {0} "\n'.format(" ".join(useflags)))
            self._write_strip('export CXXFLAGS_USE="$CLEAR_INTERMEDIATE_CXXFLAGS {0} "\n'.format(" ".join(useflags)))
            self._write_strip('export LDFLAGS_USE="$CLEAR_INTERMEDIATE_LDFLAGS {0} "\n'.format(" ".join(useflags)))

        self._write_strip('CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS"\n')
        self._write_strip('CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS"\n')
        self._write_strip('FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS"\n')
        self._write_strip('FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS"\n')
        self._write_strip('ASFLAGS="$CLEAR_INTERMEDIATE_ASFLAGS"\n')
        self._write_strip('LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS"\n')

    def write_check(self):
        """Write check section to spec file."""
        if self.tests_config and not self.config.config_opts['skip_tests']:
            self._write_strip("%check")
            self._write_strip("export LANG=C.UTF-8")
            self.write_proxy_exports()
            self._write_strip(self.tests_config)
            self._write_strip("\n")

    def write_license_files(self):
        """Install all license files for this package."""
        if len(self.license_files) > 0:
            self._write_strip("mkdir -p %{buildroot}/usr/share/package-licenses/" + self.name)
            for lfile in self.license_files:
                file2 = self.hashes[lfile]
                # Use the absolute path to the source license file b/c we don't know for sure where we are
                lfile = lfile.replace(self.version, "%{version}")
                self._write_strip("cp " + "%{_builddir}/" + lfile + " %{buildroot}/usr/share/package-licenses/" + self.name + "/" + file2 + " || :\n")

    def write_profile_payload(self, pattern=None):
        """Write the profile_payload specified for this package."""
        if not self.config.profile_payload:
            return
        use_subdir = True
        init = ""
        post = ""
        if pattern == "configure":
            init = f"{self.get_profile_generate_flags()}" \
                   f"%configure " \
                   f"{self.config.disable_static} " \
                   f"{self.config.extra_configure} " \
                   f"{self.config.extra_configure64}"
        elif pattern == "configure_ac":
            init = f"{self.get_profile_generate_flags()}" \
                   f"%reconfigure " \
                   f"{self.config.disable_static} " \
                   f"{self.config.extra_configure} " \
                   f"{self.config.extra_configure64}"
        elif pattern == "autogen":
            init = f"{self.get_profile_generate_flags()}" \
                   f"%autogen " \
                   f"{self.config.disable_static} " \
                   f"{self.config.extra_configure} " \
                   f"{self.config.extra_configure64}"
        elif pattern == "cmake":
            use_subdir = False
            init = f"{self.get_profile_generate_flags()}"
            post = f"{self.get_profile_use_flags()}"
        elif pattern == "make":
            init = f"{self.get_profile_generate_flags()}"
            post = f"{self.get_profile_use_flags()}"
        if use_subdir and self.config.subdir:
            self._write_strip("pushd " + self.config.subdir)
        if init:
            self._write_strip(init)
        self.write_make_line()
        if use_subdir and self.config.subdir:
            self._write_strip("popd")
        self._write_strip("\n")
        self._write_strip("\n".join(self.config.profile_payload))
        if not self.config.make_command:
            self._write_strip("\nmake clean\n")
        if post:
            self._write_strip(post)

    def write_make_install(self):
        """Write install section to spec file for make builds."""
        self._write_strip("%install")
        self.write_variables()
        # time.time() returns a float, but we only need second-precision
        self._write_strip("export SOURCE_DATE_EPOCH={}".format(int(time.time())))
        self._write_strip("rm -rf %{buildroot}")
        self.write_install_prepend()

        self.write_license_files()

        self._write_strip("export GOAMD64=v2")
        if self.config.config_opts['32bit']:
            self._write_strip("pushd ../build32/" + self.config.subdir)
            self._write_strip("%make_install32 {} {}".format(self.config.extra_make_install,
                                                             self.config.extra_make32_install))
            self._write_strip("if [ -d  %{buildroot}/usr/lib32/pkgconfig ]")
            self._write_strip("then")
            self._write_strip("    pushd %{buildroot}/usr/lib32/pkgconfig")
            self._write_strip("    for i in *.pc ; do ln -s $i 32$i ; done")
            self._write_strip("    popd")
            self._write_strip("fi")
            self._write_strip("if [ -d %{buildroot}/usr/share/pkgconfig ]")
            self._write_strip("then")
            self._write_strip("    pushd %{buildroot}/usr/share/pkgconfig")
            self._write_strip("    for i in *.pc ; do ln -s $i 32$i ; done")
            self._write_strip("    popd")
            self._write_strip("fi")
            self._write_strip("popd")

        if self.config.config_opts['use_avx2']:
            self._write_strip("GOAMD64=v3")
            self._write_strip("pushd ../buildavx2/" + self.config.subdir)
            self._write_strip("%s_v3 %s\n" % (self.config.install_macro, self.config.extra_make_install))
            self._write_strip("popd")

        if self.config.config_opts['use_avx512']:
            self._write_strip("GOAMD64=v4")
            self._write_strip("pushd ../buildavx512/" + self.config.subdir)
            self._write_strip("%s_v4 %s\n" % (self.config.install_macro, self.config.extra_make_install))
            self._write_strip("popd")

        if self.config.config_opts['use_apx']:
            self._write_strip("GOAMD64=v3")
            self._write_strip("pushd ../buildapx/" + self.config.subdir)
            self._write_strip("%s_va %s\n" % (self.config.install_macro, self.config.extra_make_install))
            self._write_strip("popd")

        if self.config.config_opts['openmpi']:
            self._write_strip("GOAMD64=v3")
            self._write_strip("pushd ../build-openmpi/" + self.config.subdir)
            self.write_install_openmpi()
            self._write_strip("popd")

        if self.config.subdir:
            self._write_strip("pushd " + self.config.subdir)

        self._write_strip("GOAMD64=v2")
        self._write_strip("%s %s\n" % (self.config.install_macro, self.config.extra_make_install))

        if self.config.subdir:
            self._write_strip("popd")

        self.write_find_lang()

    def write_prep_prepend(self):
        """Write out any custom supplied commands at the start of the %prep section."""
        if self.config.prep_prepend:
            self._write_strip("## prep_prepend content")
            for line in self.config.prep_prepend:
                self._write_strip("{}\n".format(line))
            self._write_strip("## prep_prepend end")

    def write_copy_prepend(self):
        """Write out any custom supplied commands prior to creating source copies for avx, etc builds."""
        if self.config.copy_prepend:
            self._write_strip("## copy_prepend content")
            for line in self.config.copy_prepend:
                self._write_strip("{}\n".format(line))
            self._write_strip("## copy_prepend end")

    def write_build_prepend(self):
        """Write out any custom supplied commands at the start of the %build section and every build type."""
        if self.config.build_prepend:
            self._write_strip("## build_prepend content")
            for line in self.config.build_prepend:
                self._write_strip("{}\n".format(line))
            self._write_strip("## build_prepend end")

    def write_build_prepend_once(self):
        """Write out any custom supplied commands once at the start of the %build section."""
        if self.config.build_prepend_once:
            self._write_strip("## build_prepend_once content")
            for line in self.config.build_prepend_once:
                self._write_strip("{}\n".format(line))
            self._write_strip("## build_prepend_once end")

    def write_build_append(self):
        """Write out any custom supplied commands at the end of the %build section."""
        if self.config.build_append:
            self._write_strip("## build_append content")
            for line in self.config.build_append:
                self._write_strip("{}\n".format(line))
            self._write_strip("## build_append end")

    def write_install_prepend(self):
        """Write out any custom supplied commands at the start of the %install section."""
        if self.config.install_prepend:
            self._write_strip("## install_prepend content")
            for line in self.config.install_prepend:
                self._write_strip("{}\n".format(line))
            self._write_strip("## install_prepend end")

    def write_install_append(self):
        """Write out any custom supplied commands at the very end of the %install section."""
        if self.config.install_append:
            self._write_strip("## install_append content")
            for line in self.config.install_append:
                self._write_strip("{}\n".format(line))
            self._write_strip("## install_append end")

    def write_elf_move(self):
        """Write out elf-move for alternate build roots."""
        skips = ""
        for setuid in self.setuid:
            skips = f"{skips} --skip-path {setuid}"
        if self.config.config_opts['use_avx2']:
            self._write_strip('/usr/bin/elf-move.py avx2 %{buildroot}-v3 %{buildroot} %{buildroot}/usr/share/clear/filemap/filemap-%{name}' + skips)
        if self.config.config_opts['use_avx512']:
            self._write_strip('/usr/bin/elf-move.py avx512 %{buildroot}-v4 %{buildroot} %{buildroot}/usr/share/clear/filemap/filemap-%{name}' + skips)
        if self.config.config_opts['use_apx']:
            self._write_strip('/usr/bin/elf-move.py apx %{buildroot}-va %{buildroot} %{buildroot}/usr/share/clear/filemap/filemap-%{name}' + skips)

    def write_exclude_deletes(self):
        """Write out deletes for excluded files."""
        if self.excludes:
            self._write_strip("## Remove excluded files")
        for exclude in self.excludes:
            self._write_strip(f"rm -f %{{buildroot}}*{exclude}")

    def write_service_restart(self):
        """Enable configured units to be restarted with clr-service-restart."""
        if self.config.service_restart:
            self._write_strip("## service_restart content")
            installdir = "%{buildroot}/usr/share/clr-service-restart"
            self._write_strip("mkdir -p {}".format(installdir))
            for unit in self.config.service_restart:
                basename = os.path.basename(unit)
                self._write_strip("ln -s {} {}".format(unit, os.path.join(installdir, basename)))
            self._write_strip("## service_restart end")

    def write_source_installs(self):
        """Write out installs from SourceX lines."""
        if len(self.config.sources["unit"]) != 0:
            self._write_strip("mkdir -p %{buildroot}/usr/lib/systemd/system")
            for unit in self.config.sources["unit"]:
                self._write_strip("install -m 0644 %{{SOURCE{0}}} %{{buildroot}}/usr/lib/systemd/system/{1}"
                                  .format(self.source_index[unit], unit))
        if len(self.config.sources["tmpfile"]) != 0:
            self._write_strip("mkdir -p %{buildroot}/usr/lib/tmpfiles.d")
            self._write_strip("install -m 0644 %{{SOURCE{0}}} %{{buildroot}}/usr/lib/tmpfiles.d/{1}.conf"
                              .format(self.source_index[self.config.sources["tmpfile"][0]], self.name))
        if len(self.config.sources["sysuser"]) != 0:
            self._write_strip("mkdir -p %{buildroot}/usr/lib/sysusers.d")
            self._write_strip("install -m 0644 %{{SOURCE{0}}} %{{buildroot}}/usr/lib/sysusers.d/{1}.conf"
                              .format(self.source_index[self.config.sources["sysuser"][0]], self.name))

        for source in self.config.extra_sources:
            if len(source) == 1:
                # Don't automatically install if we don't have install arguments
                continue
            actual_source = "%{_sourcedir}/" + source[0]
            dest = None
            install_args = []
            for arg in source[1].split():
                if dest is None and arg.startswith('/'):
                    dest = arg
                else:
                    install_args.append(arg)
            self._write_strip("mkdir -p %{{buildroot}}{0}".format(os.path.dirname(dest)))
            self._write_strip("install {0} {1} %{{buildroot}}{2}"
                              .format(" ".join(install_args), actual_source, dest))

    def write_cmake_install(self):
        """Write install section to spec file for cmake builds."""
        self.write_build_append()
        self._write_strip("%install")
        self.write_variables()
        self._write_strip("export SOURCE_DATE_EPOCH={}".format(int(time.time())))
        self._write_strip("rm -rf %{buildroot}")
        self.write_install_prepend()

        self.write_license_files()

        self._write_strip("export GOAMD64=v2")

        if self.config.config_opts['use_ninja'] and self.config.install_macro == '%make_install':
            self.config.install_macro = '%ninja_install'

        if self.config.config_opts['32bit']:
            self._write_strip("pushd ../build32/" + self.config.subdir)
            self._write_strip("pushd clr-build32")
            self._write_strip("{}32 {} {}".format(self.config.install_macro,
                                                  self.config.extra_make_install,
                                                  self.config.extra_make32_install))
            self._write_strip("if [ -d  %{buildroot}/usr/lib32/pkgconfig ]")
            self._write_strip("then")
            self._write_strip("    pushd %{buildroot}/usr/lib32/pkgconfig")
            self._write_strip("    for i in *.pc ; do ln -s $i 32$i ; done")
            self._write_strip("    popd")
            self._write_strip("fi")
            self._write_strip("if [ -d %{buildroot}/usr/share/pkgconfig ]")
            self._write_strip("then")
            self._write_strip("    pushd %{buildroot}/usr/share/pkgconfig")
            self._write_strip("    for i in *.pc ; do ln -s $i 32$i ; done")
            self._write_strip("    popd")
            self._write_strip("fi")
            self._write_strip("popd")
            self._write_strip("popd")

        if self.config.config_opts['use_avx2']:
            self._write_strip("pushd ../buildavx2/" + self.config.subdir)
            self._write_strip("GOAMD64=v3")
            self._write_strip("pushd clr-build-avx2")
            self._write_strip("%s_v3 %s || :\n" % (self.config.install_macro, self.config.extra_make_install))
            self._write_strip("popd")
            self._write_strip("popd")

        if self.config.config_opts['use_avx512']:
            self._write_strip("pushd ../buildavx512/" + self.config.subdir)
            self._write_strip("GOAMD64=v4")
            self._write_strip("pushd clr-build-avx512")
            self._write_strip("%s_v4 %s || :\n" % (self.config.install_macro, self.config.extra_make_install))
            self._write_strip("popd")
            self._write_strip("popd")

        if self.config.config_opts['use_apx']:
            self._write_strip("pushd ../buildapx/" + self.config.subdir)
            self._write_strip("GOAMD64=v3")
            self._write_strip("pushd clr-build-apx")
            self._write_strip("%s_va %s || :\n" % (self.config.install_macro, self.config.extra_make_install))
            self._write_strip("popd")
            self._write_strip("popd")

        if self.config.config_opts['openmpi']:
            self._write_strip("pushd ../build-openmpi/" + self.config.subdir)
            self._write_strip("GOAMD64=v3")
            self._write_strip("pushd clr-build-openmpi")
            self.write_install_openmpi()
            self._write_strip("popd")
            self._write_strip("popd")

        if self.config.subdir:
            self._write_strip("pushd " + self.config.subdir)

        self._write_strip("GOAMD64=v2")
        self._write_strip("pushd clr-build")
        self._write_strip("%s %s\n" % (self.config.install_macro, self.config.extra_make_install))
        self._write_strip("popd")

        if self.config.subdir:
            self._write_strip("popd")

        self.write_find_lang()

    def get_profile_generate_flags(self):
        """Return profile generate flags if proper configuration is set.

        If config.profile_payload is non-empty, returns
                'CFLAGS="${CFLAGS_GENERATE}" '
                'CXXFLAGS="${CXXFLAGS_GENERATE}" '
                'FFLAGS="${FFLAGS_GENERATE}" '
                'FCFLAGS="${FCFLAGS_GENERATE}" '
                'LDFLAGS="${LDFLAGS_GENERATE}" '

        otherwise an empty string is returned.
        """
        if self.config.profile_payload and self.config.profile_payload[0]:
            return 'CFLAGS="${CFLAGS_GENERATE}" '     \
                   'CXXFLAGS="${CXXFLAGS_GENERATE}" ' \
                   'FFLAGS="${FFLAGS_GENERATE}" '     \
                   'FCFLAGS="${FCFLAGS_GENERATE}" '   \
                   'LDFLAGS="${LDFLAGS_GENERATE}" '
        return ""

    def get_profile_use_flags(self):
        """Return profile generate flags if proper configuration is set.

        If config.profile_payload is non-empty, returns
                'CFLAGS="${CFLAGS_USE}" '
                'CXXFLAGS="${CXXFLAGS_USE}" '
                'FFLAGS="${FFLAGS_USE}" '
                'FCFLAGS="${FCFLAGS_USE}" '
                'LDFLAGS="${LDFLAGS_USE}" '

        otherwise an empty string is returned.
        """
        if self.config.profile_payload and self.config.profile_payload[0]:
            return 'CFLAGS="${CFLAGS_USE}" '     \
                   'CXXFLAGS="${CXXFLAGS_USE}" ' \
                   'FFLAGS="${FFLAGS_USE}" '     \
                   'FCFLAGS="${FCFLAGS_USE}" '   \
                   'LDFLAGS="${LDFLAGS_USE}" '
        return ""

    def get_systemd_units(self):
        """Get systemd unit files from the files module."""
        service_file_section = "config"
        systemd_service_pattern = r"^/usr/lib/systemd/system/[^/]*\.(mount|service|socket|target)$"
        systemd_units = []

        if service_file_section not in self.packages:
            return systemd_units

        for serv_f in self.packages[service_file_section]:
            if re.search(systemd_service_pattern, serv_f) and serv_f not in self.excludes:
                systemd_units.append(serv_f)

        return systemd_units

    def write_systemd_units(self):
        """Write out installs for systemd unit files."""
        units = self.get_systemd_units()
        for unit in units:
            self._write("systemctl --root=%{{buildroot}} enable {0}\n".format(os.path.basename(unit)))

    def write_configure_pattern(self):
        """Write configure build pattern to spec file."""
        if self.config.autoreconf:
            # Patches affecting configure.* or Makefile.*, reconf instead
            self.write_configure_ac_pattern()
            return
        self.write_prep()
        self.write_lang_c(export_epoch=True)
        self.write_variables()
        self.write_profile_payload("configure")
        if self.config.subdir:
            self._write_strip("pushd {}".format(self.config.subdir))
        self._write_strip("export GOAMD64=v2")
        self._write_strip("{0}%configure {1} {2} {3}"
                          .format(self.get_profile_use_flags(),
                                  self.config.disable_static,
                                  self.config.extra_configure,
                                  self.config.extra_configure64))
        self.write_make_line()
        if self.config.subdir:
            self._write_strip("popd")
        self._write_strip("\n")
        if self.config.config_opts['32bit']:
            self._write_strip("pushd ../build32/" + self.config.subdir)
            self.write_build_prepend()
            self.write_32bit_exports()
            self._write_strip("%configure {0} {1} {2} "
                              " --libdir=/usr/lib32 "
                              "--build=i686-generic-linux-gnu "
                              "--host=i686-generic-linux-gnu "
                              "--target=i686-clr-linux-gnu"
                              .format(self.config.disable_static,
                                      self.config.extra_configure,
                                      self.config.extra_configure32))
            self.write_make_line(True)
            self._write_strip("popd")

        if self.config.config_opts['use_avx2']:
            self._write_strip("unset PKG_CONFIG_PATH")
            self._write_strip("pushd ../buildavx2/" + self.config.subdir)
            self.write_build_prepend()
            self._write_strip("GOAMD64=v3")
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {AVX2_CFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {AVX2_LCFLAGS} "')
            self._write_strip("%configure {0} {1} {2} "
                              .format(self.config.disable_static,
                                      self.config.extra_configure,
                                      self.config.extra_configure_avx2))
            self.write_make_line()
            self._write_strip("popd")

        if self.config.config_opts['use_avx512']:
            self._write_strip("unset PKG_CONFIG_PATH")
            self._write_strip("pushd ../buildavx512/" + self.config.subdir)
            self.write_build_prepend()
            self._write_strip("GOAMD64=v4")
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {AVX512_CFLAGS} {AVX512_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX512_CFLAGS} {AVX512_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {AVX512_CFLAGS} {AVX512_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {AVX512_FCFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {AVX512_LCFLAGS} "')
            self._write_strip("%configure {0} {1} {2} "
                              .format(self.config.disable_static,
                                      self.config.extra_configure,
                                      self.config.extra_configure_avx512))
            self.write_make_line()
            self._write_strip("popd")

        if self.config.config_opts['use_apx']:
            self._write_strip("unset PKG_CONFIG_PATH")
            self._write_strip("pushd ../buildapx/" + self.config.subdir)
            self.write_build_prepend()
            self._write_strip("GOAMD64=v3")
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {APX_CFLAGS} {APX_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {APX_CFLAGS} {APX_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {APX_CFLAGS} {APX_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {APX_CFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {APX_LCFLAGS} "')
            self._write_strip("%configure --host=x86_64-clr-linux-gnu {0} {1} {2} "
                              .format(self.config.disable_static,
                                      self.config.extra_configure,
                                      self.config.extra_configure_avx2))
            self.write_make_line()
            self._write_strip("popd")

        if self.config.config_opts['openmpi']:
            self._write_strip("pushd ../build-openmpi/" + self.config.subdir)
            self._write_strip(". /usr/share/defaults/etc/profile.d/modules.sh")
            self._write_strip("module load openmpi")
            self.write_build_prepend()
            self._write_strip("GOAMD64=v3")
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {AVX2_CFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {AVX2_LCFLAGS} "')
            self._write_strip("./configure {0} \\\n{1} {2}"
                              .format(self.config.conf_args_openmpi,
                                      self.config.disable_static,
                                      self.config.extra_configure_openmpi))
            self.write_make_line()
            self._write_strip("module unload openmpi")
            self._write_strip("popd")

        self.write_check()
        self.write_make_install()

    def write_configure_ac_pattern(self):
        """Write build pattern for configure.ac style build."""
        self.write_prep()
        self.write_lang_c(export_epoch=True)
        self.write_variables()
        self.write_profile_payload("configure_ac")
        if self.config.subdir:
            self._write_strip("pushd " + self.config.subdir)
        self._write_strip("export GOAMD64=v2")
        self._write_strip("{0}%reconfigure {1} {2} {3}"
                          .format(self.get_profile_use_flags(),
                                  self.config.disable_static,
                                  self.config.extra_configure,
                                  self.config.extra_configure64))
        self.write_make_line()
        if self.config.subdir:
            self._write_strip("popd")
        if self.config.config_opts['32bit']:
            self._write_strip("pushd ../build32/" + self.config.subdir)
            self.write_build_prepend()
            self.write_32bit_exports()
            self._write_strip("%reconfigure {0} {1} {2} "
                              "--libdir=/usr/lib32 "
                              "--build=i686-generic-linux-gnu "
                              "--host=i686-generic-linux-gnu "
                              "--target=i686-clr-linux-gnu"
                              .format(self.config.disable_static,
                                      self.config.extra_configure,
                                      self.config.extra_configure32))
            self.write_make_line(True)
            self._write_strip("popd")

        if self.config.config_opts['use_avx2']:
            self._write_strip("unset PKG_CONFIG_PATH")
            self._write_strip("pushd ../buildavx2/" + self.config.subdir)
            self.write_build_prepend()
            self._write_strip("GOAMD64=v3")
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {AVX2_CFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {AVX2_LCFLAGS} "')
            self._write_strip("%reconfigure {0} {1} {2} "
                              .format(self.config.disable_static,
                                      self.config.extra_configure,
                                      self.config.extra_configure_avx2))
            self.write_make_line()
            self._write_strip("popd")

        if self.config.config_opts['use_avx512']:
            self._write_strip("unset PKG_CONFIG_PATH")
            self._write_strip("pushd ../buildavx512/" + self.config.subdir)
            self.write_build_prepend()
            self._write_strip("GOAMD64=v4")
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {AVX512_CFLAGS} {AVX512_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX512_CFLAGS} {AVX512_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {AVX512_CFLAGS} {AVX512_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {AVX512_FCFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {AVX512_LCFLAGS} "')
            self._write_strip("%reconfigure {0} {1} {2} "
                              .format(self.config.disable_static,
                                      self.config.extra_configure,
                                      self.config.extra_configure_avx512))
            self.write_make_line()
            self._write_strip("popd")

        if self.config.config_opts['use_apx']:
            self._write_strip("unset PKG_CONFIG_PATH")
            self._write_strip("pushd ../buildapx/" + self.config.subdir)
            self.write_build_prepend()
            self._write_strip("GOAMD64=v3")
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {APX_CFLAGS} {APX_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {APX_CFLAGS} {APX_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {APX_CFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {APX_LCFLAGS} "')
            self._write_strip("%reconfigure --host=x86_64-clr-linux-gnu {0} {1} {2} "
                              .format(self.config.disable_static,
                                      self.config.extra_configure,
                                      self.config.extra_configure_avx2))
            self.write_make_line()
            self._write_strip("popd")

        self._write_strip("\n")
        self.write_check()
        self.write_make_install()

    def write_make_pattern(self):
        """Write build pattern for make."""
        self.write_prep()
        self.write_lang_c(export_epoch=True)
        self.write_variables()
        self.write_profile_payload("make")
        if self.config.subdir:
            self._write_strip("pushd " + self.config.subdir)
        self._write_strip("export GOAMD64=v2")
        self.write_make_line()
        if self.config.subdir:
            self._write_strip("popd")
        self._write_strip("\n")
        if self.config.config_opts['32bit']:
            self._write_strip("pushd ../build32/" + self.config.subdir)
            self.write_32bit_exports()
            self.write_make_line(True)
            self._write_strip("popd")
        if self.config.config_opts['use_avx2']:
            self._write_strip("pushd ../buildavx2" + self.config.subdir)
            self.write_build_prepend()
            self._write_strip("GOAMD64=v3")
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {AVX2_CFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {AVX2_LCFLAGS} "')
            self.write_make_line()
            self._write_strip("popd")
        if self.config.config_opts['use_avx512']:
            self._write_strip("pushd ../buildavx512" + self.config.subdir)
            self.write_build_prepend()
            self._write_strip("GOAMD64=v4")
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {AVX512_CFLAGS} {AVX512_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX512_CFLAGS} {AVX512_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {AVX512_CFLAGS} {AVX512_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {AVX512_FCFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {AVX512_LCFLAGS} "')
            self.write_make_line()
            self._write_strip("popd")
        if self.config.config_opts['use_apx'] and not self.config.config_opts['use_clang']:
            self._write_strip("pushd ../buildapx" + self.config.subdir)
            self.write_build_prepend()
            self._write_strip("GOAMD64=v3")
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {APX_CFLAGS} {APX_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {APX_CFLAGS} {APX_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {APX_CFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {APX_LCFLAGS} "')
            self.write_make_line()
            self._write_strip("popd")

        self._write_strip("\n")
        self.write_check()
        self.write_make_install()

    def write_autogen_pattern(self):
        """Write build pattern for autogen packages."""
        self.write_prep()
        self.write_lang_c(export_epoch=True)
        self.write_variables()
        self.write_profile_payload("autogen")
        if self.config.subdir:
            self._write_strip("pushd " + self.config.subdir)
        self._write_strip("export GOAMD64=v2")
        self._write_strip("{0}%autogen {1} {2} {3}"
                          .format(self.get_profile_use_flags(),
                                  self.config.disable_static,
                                  self.config.extra_configure,
                                  self.config.extra_configure64))
        self.write_make_line()
        self._write_strip("\n")
        if self.config.subdir:
            self._write_strip("popd")
        if self.config.config_opts['32bit']:
            self._write_strip("pushd ../build32/" + self.config.subdir)
            self.write_build_prepend()
            self.write_32bit_exports()
            self._write_strip("%autogen {0} {1} {2} "
                              "--libdir=/usr/lib32 "
                              "--build=i686-generic-linux-gnu "
                              "--host=i686-generic-linux-gnu "
                              "--target=i686-clr-linux-gnu"
                              .format(self.config.disable_static,
                                      self.config.extra_configure,
                                      self.config.extra_configure32))
            self.write_make_line(True)
            self._write_strip("popd")

        if self.config.config_opts['use_avx2']:
            self._write_strip("pushd ../buildavx2/" + self.config.subdir)
            self.write_build_prepend()
            self._write_strip("GOAMD64=v3")
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {AVX2_CFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {AVX2_LCFLAGS} "')
            self._write_strip("%autogen {0} {1} {2} "
                              .format(self.config.disable_static,
                                      self.config.extra_configure,
                                      self.config.extra_configure_avx2))
            self.write_make_line()
            self._write_strip("popd")

        if self.config.config_opts['use_avx512']:
            self._write_strip("pushd ../buildavx512/" + self.config.subdir)
            self.write_build_prepend()
            self._write_strip("GOAMD64=v4")
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {AVX512_CFLAGS} {AVX512_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX512_CFLAGS} {AVX512_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {AVX512_CFLAGS} {AVX512_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {AVX512_FCFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {AVX512_LCFLAGS} "')
            self._write_strip("%autogen {0} {1} {2} "
                              .format(self.config.disable_static,
                                      self.config.extra_configure,
                                      self.config.extra_configure_avx512))
            self.write_make_line()
            self._write_strip("popd")

        if self.config.config_opts['use_apx'] and not self.config.config_opts['use_clang']:
            self._write_strip("pushd ../buildapx/" + self.config.subdir)
            self.write_build_prepend()
            self._write_strip("GOAMD64=v3")
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {APX_CFLAGS} {APX_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {APX_CFLAGS} {APX_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {APX_CFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {APX_LCFLAGS} "')
            self._write_strip("%autogen --host=x86_64-clr-linux-gnu {0} {1} {2} "
                              .format(self.config.disable_static,
                                      self.config.extra_configure,
                                      self.config.extra_configure_apx))
            self.write_make_line()
            self._write_strip("popd")

        self.write_check()
        self.write_make_install()

    def write_pyproject_pattern(self):
        """Write build pattern for python packages using pyproject."""
        self.write_prep()
        self.write_lang_c(export_epoch=True)
        self.write_variables()
        self._write_strip("export MAKEFLAGS=%{?_smp_mflags}")
        if self.config.subdir:
            self._write_strip("pushd " + self.config.subdir)
        for module in self.config.pypi_overrides:
            self._write_strip(f"pypi-dep-fix.py . {module}")
        self._write_strip("python3 -m build --wheel --skip-dependency-check --no-isolation " + self.config.extra_configure)
        self._write_strip("\n")
        if self.config.subdir:
            self._write_strip("popd")

        if self.config.config_opts['use_avx2']:
            self._write_strip("pushd ../buildavx2/" + self.config.subdir)
            self.write_build_prepend()
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {AVX2_CFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {AVX2_LCFLAGS} "')
            for module in self.config.pypi_overrides:
                self._write_strip(f"pypi-dep-fix.py . {module}")
            self._write_strip("python3 -m build --wheel --skip-dependency-check --no-isolation " + self.config.extra_configure)
            self._write_strip("\n")
            self._write_strip("popd")

        if self.config.config_opts['use_apx'] and not self.config.config_opts['use_clang']:
            self._write_strip("pushd ../buildapx/" + self.config.subdir)
            self.write_build_prepend()
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {APX_CFLAGS} {APX_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {APX_CFLAGS} {APX_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {APX_CFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {APX_LCFLAGS} "')
            for module in self.config.pypi_overrides:
                self._write_strip(f"pypi-dep-fix.py . {module}")
            self._write_strip("python3 -m build --wheel --skip-dependency-check --no-isolation " + self.config.extra_configure)
            self._write_strip("\n")
            self._write_strip("popd")

        self._write_strip("\n")
        self.write_build_append()
        self.write_check()
        self._write_strip("%install")
        self.write_variables()
        self._write_strip("export MAKEFLAGS=%{?_smp_mflags}")
        self._write_strip("rm -rf %{buildroot}")
        self.write_install_prepend()

        self.write_license_files()

        if self.config.subdir:
            self._write_strip("pushd " + self.config.subdir)
        self._write_strip("python3 -m installer --destdir=%{buildroot} dist/*.whl")
        if self.config.subdir:
            self._write_strip("popd")
        for module in self.config.pypi_overrides:
            self._write_strip(f"pypi-dep-fix.py %{{buildroot}} {module}")
        self._write_strip("echo ----[ mark ]----")
        self._write_strip("cat %{buildroot}/usr/lib/python3*/site-packages/*/requires.txt || :")
        self._write_strip("echo ----[ mark ]----")

        if self.config.config_opts['use_avx2']:
            self._write_strip("pushd ../buildavx2/" + self.config.subdir)
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {AVX2_CFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {AVX2_LCFLAGS} "')
            self._write_strip("python3 -m installer --destdir=%{buildroot}-v3 dist/*.whl")
            self._write_strip("popd")

        if self.config.config_opts['use_apx'] and not self.config.config_opts['use_clang']:
            self._write_strip("pushd ../buildapx/" + self.config.subdir)
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {APX_CFLAGS} {APX_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {APX_CFLAGS} {APX_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {APX_CFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {APX_LCFLAGS} "')
            self._write_strip("python3 -m installer --destdir=%{buildroot}-va dist/*.whl")
            self._write_strip("popd")

        self.write_find_lang()

    def write_distutils3_pattern(self):
        """Write build pattern for python packages using distutils3."""
        self.write_prep()
        self.write_lang_c(export_epoch=True)
        self.write_variables()
        self._write_strip("export MAKEFLAGS=%{?_smp_mflags}")
        if self.config.subdir:
            self._write_strip("pushd " + self.config.subdir)
        for module in self.config.pypi_overrides:
            self._write_strip(f"pypi-dep-fix.py . {module}")
        self._write_strip("python3 setup.py build  " + self.config.extra_configure)
        self._write_strip("\n")
        if self.config.subdir:
            self._write_strip("popd")

        if self.config.config_opts['use_avx2']:
            self._write_strip("pushd ../buildavx2/" + self.config.subdir)
            self.write_build_prepend()
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {AVX2_CFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {AVX2_LCFLAGS} "')
            for module in self.config.pypi_overrides:
                self._write_strip(f"pypi-dep-fix.py . {module}")
            self._write_strip("python3 setup.py build  " + self.config.extra_configure)
            self._write_strip("\n")
            self._write_strip("popd")

        if self.config.config_opts['use_apx'] and not self.config.config_opts['use_clang']:
            self._write_strip("pushd ../buildapx/" + self.config.subdir)
            self.write_build_prepend()
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {APX_CFLAGS} {APX_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {APX_CFLAGS} {APX_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {APX_CFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {APX_LCFLAGS} "')
            for module in self.config.pypi_overrides:
                self._write_strip(f"pypi-dep-fix.py . {module}")
            self._write_strip("python3 setup.py build  " + self.config.extra_configure)
            self._write_strip("\n")
            self._write_strip("popd")

        self.write_build_append()
        self.write_check()
        self._write_strip("%install")
        self.write_variables()
        self._write_strip("export MAKEFLAGS=%{?_smp_mflags}")
        self._write_strip("rm -rf %{buildroot}")
        self.write_install_prepend()

        self.write_license_files()

        if self.config.subdir:
            self._write_strip("pushd " + self.config.subdir)
        self._write_strip("python3 -tt setup.py build  install --root=%{buildroot}")
        if self.config.subdir:
            self._write_strip("popd")
        for module in self.config.pypi_overrides:
            self._write_strip(f"pypi-dep-fix.py %{{buildroot}} {module}")
        self._write_strip("echo ----[ mark ]----")
        self._write_strip("cat %{buildroot}/usr/lib/python3*/site-packages/*/requires.txt || :")
        self._write_strip("echo ----[ mark ]----")

        if self.config.config_opts['use_avx2']:
            self._write_strip("pushd ../buildavx2/" + self.config.subdir)
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {AVX2_CFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {AVX2_LCFLAGS} "')
            self._write_strip("python3 -tt setup.py build install --root=%{buildroot}-v3")
            self._write_strip("popd")

        if self.config.config_opts['use_apx'] and not self.config.config_opts['use_clang']:
            self._write_strip("pushd ../buildapx/" + self.config.subdir)
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {APX_CFLAGS} {APX_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {APX_CFLAGS} {APX_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {APX_CFLAGS} "')
            self._write_strip(f'LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS {APX_LCFLAGS} "')
            self._write_strip("python3 -tt setup.py build install --root=%{buildroot}-va")
            self._write_strip("popd")

        self.write_find_lang()

    def write_R_pattern(self):
        """Write build pattern for R packages."""
        self.write_prep()
        self.write_lang_c(export_epoch=True)
        self._write_strip("\n")

        self._write_strip("%install")
        self._write_strip("export SOURCE_DATE_EPOCH={}".format(int(time.time())))
        self._write_strip("rm -rf %{buildroot}")
        self.write_install_prepend()
        self.write_license_files()
        self._write_strip("LANG=C.UTF-8")
        self._write_strip('CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS -O3 -flto -fno-semantic-interposition "\n')
        self._write_strip('FCFLAGS="$CLEAR_INTERMEDIATE_FFLAGS -O3 -flto -fno-semantic-interposition "\n')
        self._write_strip('FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS -O3 -flto -fno-semantic-interposition "\n')
        self._write_strip('CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS -O3 -flto -fno-semantic-interposition "\n')
        self._write_strip("AR=gcc-ar\n")
        self._write_strip("RANLIB=gcc-ranlib\n")
        self._write_strip('LDFLAGS="$CLEAR_INTERMEDIATE_LDFLAGS  -Wl,-z -Wl,relro"\n')

        self._write_strip("mkdir -p %{buildroot}/usr/lib64/R/library")
        self._write_strip("mkdir -p %{buildroot}-v3/usr/lib64/R/library")
        self._write_strip("mkdir -p %{buildroot}-v4/usr/lib64/R/library")
        self._write_strip("mkdir -p %{buildroot}-va/usr/lib64/R/library")
        self._write_strip("\n")
        self._write_strip("mkdir -p ~/.R")

        if self.config.config_opts['use_avx2']:
            self._write_strip(f"echo \"CFLAGS = $CFLAGS {AVX2_CFLAGS} -ftree-vectorize -mno-vzeroupper\" > ~/.R/Makevars")
            self._write_strip(f"echo \"FFLAGS = $FFLAGS {AVX2_CFLAGS} -ftree-vectorize -mno-vzeroupper \" >> ~/.R/Makevars")
            self._write_strip(f"echo \"CXXFLAGS = $CXXFLAGS {AVX2_CFLAGS} -ftree-vectorize -mno-vzeroupper \" >> ~/.R/Makevars")

            self._write_strip("R CMD INSTALL "
                              f"{self.config.extra_configure} "
                              "--install-tests "
                              "--use-LTO "
                              "--built-timestamp=${SOURCE_DATE_EPOCH} "
                              "--data-compress=none "
                              "--compress=none "
                              "--build  -l "
                              "%{buildroot}-v3/usr/lib64/R/library .")

        if self.config.config_opts['use_avx512']:
            self._write_strip(f"echo \"CFLAGS = $CFLAGS {AVX512_CFLAGS} -ftree-vectorize  -mno-vzeroupper \" > ~/.R/Makevars")
            self._write_strip(f"echo \"FFLAGS = $FFLAGS {AVX512_CFLAGS} -ftree-vectorize  -mno-vzeroupper \" >> ~/.R/Makevars")
            self._write_strip(f"echo \"CXXFLAGS = $CXXFLAGS {AVX512_CFLAGS} -ftree-vectorize -mno-vzeroupper \" >> ~/.R/Makevars")

            self._write_strip("R CMD INSTALL "
                              "--preclean "
                              f"{self.config.extra_configure} "
                              "--install-tests "
                              "--use-LTO "
                              "--no-test-load "
                              "--data-compress=none "
                              "--compress=none "
                              "--built-timestamp=${SOURCE_DATE_EPOCH} "
                              "--build  -l "
                              "%{buildroot}-v4/usr/lib64/R/library .")

        if self.config.config_opts['use_apx']:
            self._write_strip(f"echo \"CFLAGS = $CFLAGS {APX_CFLAGS} -ftree-vectorize -mno-vzeroupper\" > ~/.R/Makevars")
            self._write_strip(f"echo \"FFLAGS = $FFLAGS {APX_CFLAGS} -ftree-vectorize -mno-vzeroupper \" >> ~/.R/Makevars")
            self._write_strip(f"echo \"CXXFLAGS = $CXXFLAGS {AVX2_CFLAGS} -ftree-vectorize -mno-vzeroupper \" >> ~/.R/Makevars")

            self._write_strip("R CMD INSTALL "
                              f"{self.config.extra_configure} "
                              "--install-tests "
                              "--use-LTO "
                              "--built-timestamp=${SOURCE_DATE_EPOCH} "
                              "--data-compress=none "
                              "--compress=none "
                              "--build  -l "
                              "%{buildroot}-va/usr/lib64/R/library .")

        self._write_strip("echo \"CFLAGS = $CFLAGS -ftree-vectorize \" > ~/.R/Makevars")
        self._write_strip("echo \"FFLAGS = $FFLAGS -ftree-vectorize \" >> ~/.R/Makevars")
        self._write_strip("echo \"CXXFLAGS = $CXXFLAGS -ftree-vectorize \" >> ~/.R/Makevars")

        self._write_strip("R CMD INSTALL "
                          "--preclean "
                          f"{self.config.extra_configure} "
                          "--use-LTO "
                          "--install-tests "
                          "--data-compress=none "
                          "--compress=none "
                          "--built-timestamp=${SOURCE_DATE_EPOCH} "
                          "--build  -l "
                          "%{buildroot}/usr/lib64/R/library .")

        self._write_strip("%{__rm} -rf %{buildroot}%{_datadir}/R/library/R.css")
        self.write_find_lang()
        self.write_check()

    def write_cmake_pattern(self):
        """Write cmake pattern to spec file."""
        self.write_prep()
        self.write_lang_c(export_epoch=True)

        if self.config.subdir:
            self._write_strip("pushd " + self.config.subdir)

        self._write_strip("mkdir -p clr-build")
        self._write_strip("pushd clr-build")
        self.write_variables()
        self._write_strip("export GOAMD64=v2")
        if self.config.config_opts['use_ninja']:
            cmake_type = "-G Ninja"
        else:
            cmake_type = "-G 'Unix Makefiles'"
        self._write_strip(f"%cmake {self.config.cmake_srcdir} {self.extra_cmake} {cmake_type}")

        self.write_profile_payload("cmake")

        self.write_make_line()
        self._write_strip("popd")

        if self.config.subdir:
            self._write_strip("popd")

        if self.config.config_opts['use_avx2']:
            self._write_strip("pushd ../buildavx2/" + self.config.subdir)
            self._write_strip("mkdir -p clr-build-avx2")
            self._write_strip("pushd clr-build-avx2")
            self.write_build_prepend()
            self.write_variables()
            self._write_strip("GOAMD64=v3")
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {AVX2_CFLAGS} "')
            self._write_strip(f"%cmake {self.config.cmake_srcdir} {self.extra_cmake} {cmake_type}")
            self.write_make_line()
            self._write_strip("popd")
            self._write_strip("popd")

        if self.config.config_opts['use_avx512']:
            self._write_strip("pushd ../buildavx512/" + self.config.subdir)
            self._write_strip("mkdir -p clr-build-avx512")
            self._write_strip("pushd clr-build-avx512")
            self.write_build_prepend()
            self.write_variables()
            self._write_strip("GOAMD64=v4")
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {AVX512_CFLAGS} {AVX512_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX512_CFLAGS} {AVX512_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {AVX512_CFLAGS} {AVX512_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {AVX512_CFLAGS} "')
            self._write_strip(f"%cmake {self.config.cmake_srcdir} {self.extra_cmake} {cmake_type}")
            self.write_make_line()
            self._write_strip("popd")
            self._write_strip("popd")

        if self.config.config_opts['use_apx'] and not self.config.config_opts['use_clang']:
            self._write_strip("pushd ../buildapx/" + self.config.subdir)
            self._write_strip("mkdir -p clr-build-apx")
            self._write_strip("pushd clr-build-apx")
            self.write_build_prepend()
            self.write_variables()
            self._write_strip("GOAMD64=v3")
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {APX_CFLAGS} {APX_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {APX_CFLAGS} {APX_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {APX_CFLAGS} "')
            self._write_strip(f"%cmake {self.config.cmake_srcdir} {self.extra_cmake} {cmake_type}")
            self.write_make_line()
            self._write_strip("popd")
            self._write_strip("popd")

        if self.config.config_opts['32bit']:
            self._write_strip("pushd ../build32/" + self.config.subdir)
            self._write_strip("mkdir -p clr-build32")
            self._write_strip("pushd clr-build32")
            self.write_build_prepend()
            self.write_variables()
            self.write_32bit_exports()
            self._write_strip("%cmake -DLIB_INSTALL_DIR:PATH=/usr/lib32 "
                              "-DCMAKE_INSTALL_LIBDIR=/usr/lib32 "
                              "-DLIB_SUFFIX=32 "
                              f"{self.config.cmake_srcdir} {self.extra_cmake} {cmake_type}")
            self.write_make_line()
            self._write_strip("unset PKG_CONFIG_PATH")
            self._write_strip("popd")
            self._write_strip("popd")

        if self.config.config_opts['openmpi']:
            self._write_strip("pushd ../build-openmpi/" + self.config.subdir)
            self._write_strip("mkdir -p clr-build-openmpi")
            self._write_strip("pushd clr-build-openmpi")
            self._write_strip(". /usr/share/defaults/etc/profile.d/modules.sh")
            self._write_strip("module load openmpi")
            self.write_build_prepend()
            self.write_variables()
            self._write_strip("GOAMD64=v3")
            self._write_strip(f'CFLAGS="$CLEAR_INTERMEDIATE_CFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'CXXFLAGS="$CLEAR_INTERMEDIATE_CXXFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FFLAGS="$CLEAR_INTERMEDIATE_FFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "')
            self._write_strip(f'FCFLAGS="$CLEAR_INTERMEDIATE_FCFLAGS {AVX2_CFLAGS} "')
            self.write_cmake_line_openmpi()
            self.write_make_line()
            self._write_strip("module unload openmpi")
            self._write_strip("popd")
            self._write_strip("popd")

        self._write_strip("\n")
        self.write_check()

        self.write_cmake_install()

    def write_qmake_pattern(self):
        """Write qmake build pattern to spec file."""
        extra_qmake_args = ""
        if self.config.config_opts['use_clang']:
            extra_qmake_args = "-spec linux-clang "
        if self.config.config_opts['use_lto']:
            extra_qmake_args += "-config ltcg -config fat-static-lto "
        else:
            extra_qmake_args += "QMAKE_CFLAGS+=-fno-lto QMAKE_CXXFLAGS+=-fno-lto "

        self.write_prep()
        self._write_strip("%build")
        self.write_build_prepend()
        self.write_proxy_exports()
        self._write_strip("export LANG=C.UTF-8")
        self.write_variables()

        if self.config.subdir:
            self._write_strip("pushd " + self.config.subdir)

        self._write_strip('export QMAKE_CFLAGS="$CFLAGS"')
        self._write_strip('export QMAKE_CXXFLAGS="$CXXFLAGS"')
        self._write_strip('export QMAKE_LFLAGS="$LDFLAGS"')
        self._write_strip('export QMAKE_LIBDIR=/usr/lib64')
        self._write_strip('export QMAKE_CFLAGS_RELEASE=')
        self._write_strip('export QMAKE_CXXFLAGS_RELEASE=')

        # Add the qt6base tools to the path
        self._write_strip('export PATH=/usr/lib64/qt6/bin:$PATH')

        if self.config.make_command:
            qmake = self.config.make_command
        else:
            qmake = "qmake6"
        self._write_strip(f"{qmake} {extra_qmake_args} {self.config.extra_configure}")
        self._write_strip("test -r config.log && cat config.log")
        self.write_make_line()

        if self.config.subdir:
            self._write_strip("popd")

        if self.config.config_opts['use_avx2']:
            self._write_strip("pushd ../buildavx2/" + self.config.subdir)
            self._write(f"{qmake} 'QT_CPU_FEATURES.x86_64 += avx avx2 bmi bmi2 f16c fma lzcnt popcnt'\\\n")
            self._write(f'    QMAKE_CFLAGS+="{AVX2_CFLAGS} {AVX2_LFLAGS}" QMAKE_CXXFLAGS+="{AVX2_CFLAGS} {AVX2_LFLAGS}" \\\n')
            self._write(f'    QMAKE_LFLAGS+="{AVX2_LCFLAGS}" {extra_qmake_args} {self.config.extra_configure}\n')
            self.write_make_line()
            self._write_strip("popd")

        self.write_build_append()
        self._write_strip("\n")
        self.write_make_install()

    def write_cpan_pattern(self):
        """Write cpan build pattern to spec file."""
        self.write_prep()
        self._write_strip("%build")
        self.write_build_prepend()
        self.write_proxy_exports()
        self._write_strip("export LANG=C.UTF-8")
        self._write_strip("if test -f Makefile.PL; then")
        self._write_strip("%{__perl} -I. Makefile.PL")
        self.write_make_line()
        self._write_strip("else")
        self._write_strip("%{__perl} Build.PL")
        self._write_strip("./Build")
        self._write_strip("fi")
        self.write_build_append()
        self._write_strip("\n")
        self.write_check()
        self._write_strip("%install")
        self._write_strip("rm -rf %{buildroot}")
        self.write_install_prepend()
        self.write_license_files()
        self._write_strip("if test -f Makefile.PL; then")
        self._write_strip("make pure_install PERL_INSTALL_ROOT=%{buildroot} INSTALLDIRS=vendor " + self.config.extra_make_install)
        self._write_strip("else")
        self._write_strip("./Build install --installdirs=vendor --destdir=%{buildroot} " + self.config.extra_make_install)
        self._write_strip("fi")
        self._write_strip("find %{buildroot} -type f -name .packlist -exec rm -f {} ';'")
        self._write_strip("find %{buildroot} -depth -type d -exec rmdir {} 2>/dev/null ';'")
        self._write_strip("find %{buildroot} -type f -name '*.bs' -empty -exec rm -f {} ';'")
        self._write_strip("%{_fixperms} %{buildroot}/*")
        self.write_find_lang()

    def write_scons_pattern(self):
        """Write scons build pattern to spec file."""
        self.write_prep()
        self._write_strip("%build")
        self.write_build_prepend()
        self.write_proxy_exports()
        self._write_strip("export LANG=C.UTF-8")
        self.write_variables()
        self._write_strip("scons{} {}".format(self.config.parallel_build, self.config.extra_configure))
        self.write_build_append()
        self._write_strip("\n")
        self._write_strip("%install")
        self.write_install_prepend()
        self._write_strip("scons install " + self.config.extra_make_install)
        self.write_license_files()

    def write_meson_pattern(self):
        """Write meson build pattern to spec file."""
        self.write_prep()
        self.write_lang_c(export_epoch=True)
        self.write_variables()
        if self.config.subdir:
            self._write_strip("pushd " + self.config.subdir)
        self._write_strip("export GOAMD64=v2")
        self._write_strip('meson --libdir=lib64 --prefix=/usr --buildtype=plain {0} {1} builddir'
                          .format(self.config.extra_configure,
                                  self.config.extra_configure64))
        self._write_strip("ninja -v -C builddir")
        if self.config.config_opts['use_avx2']:
            self._write_strip("GOAMD64=v3")
            if self.config.config_opts['pgo'] and self.config.profile_payload != "":
                self._write_strip(f'CFLAGS="$CFLAGS_GENERATE {AVX2_CFLAGS} {AVX2_LFLAGS} " CXXFLAGS="$CXXFLAGS_GENERATE '
                                  f'{AVX2_CFLAGS} {AVX2_LFLAGS} " LDFLAGS="$LDFLAGS_GENERATE {AVX2_LCFLAGS} " '
                                  'meson --libdir=lib64 --prefix=/usr --buildtype=plain {0} '
                                  '{1} builddiravx2'.format(self.config.extra_configure, self.config.extra_configure64))
                self._write_strip('ninja -v -C builddiravx2')
                self._write_strip('pushd builddiravx2')
                self._write_strip("\n".join(self.config.profile_payload))
                self._write_strip('popd')
                self._write_strip('rm -rf builddiravx2')
                self._write_strip(f'CFLAGS="$CFLAGS_USE {AVX2_CFLAGS} {AVX2_LFLAGS} " CXXFLAGS="$CXXFLAGS_USE '
                                  f'{AVX2_CFLAGS} {AVX2_LFLAGS} " LDFLAGS="$LDFLAGS_USE {AVX2_LCFLAGS} " '
                                  'meson --libdir=lib64 --prefix=/usr --buildtype=plain {0} '
                                  '{1} builddiravx2'.format(self.config.extra_configure, self.config.extra_configure64))
                self._write_strip('ninja -v -C builddiravx2')
            else:
                self._write_strip(f'CFLAGS="$CFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} " CXXFLAGS="$CXXFLAGS '
                                  f'{AVX2_CFLAGS} {AVX2_LFLAGS} " LDFLAGS="$LDFLAGS {AVX2_LCFLAGS} " '
                                  'meson --libdir=lib64 --prefix=/usr --buildtype=plain {0} '
                                  '{1} builddiravx2'.format(self.config.extra_configure, self.config.extra_configure64))
                self._write_strip('ninja -v -C builddiravx2')
        if self.config.config_opts['use_avx512']:
            self._write_strip("GOAMD64=v4")
            if self.config.config_opts['pgo'] and self.config.profile_payload != "":
                self._write_strip(f'CFLAGS="$CFLAGS_GENERATE {AVX512_CFLAGS} {AVX512_LFLAGS} " CXXFLAGS="$CXXFLAGS_GENERATE '
                                  f'{AVX512_CFLAGS} {AVX512_LFLAGS} " LDFLAGS="$LDFLAGS_GENERATE {AVX512_LCFLAGS} " '
                                  'meson --libdir=lib64 --prefix=/usr --buildtype=plain {0} '
                                  '{1} builddiravx512'.format(self.config.extra_configure, self.config.extra_configure64))
                self._write_strip('ninja -v -C builddiravx512')
                self._write_strip('pushd builddiravx512')
                self._write_strip("\n".join(self.config.profile_payload))
                self._write_strip('popd')
                self._write_strip('rm -rf builddiravx512')
                self._write_strip(f'CFLAGS="$CFLAGS_USE {AVX512_CFLAGS} {AVX512_LFLAGS} " CXXFLAGS="$CXXFLAGS_USE '
                                  f'{AVX512_CFLAGS} {AVX512_LFLAGS} " LDFLAGS="$LDFLAGS_USE {AVX512_LCFLAGS} " '
                                  'meson --libdir=lib64 --prefix=/usr --buildtype=plain {0} '
                                  '{1} builddiravx512'.format(self.config.extra_configure, self.config.extra_configure64))
                self._write_strip('ninja -v -C builddiravx512')
            else:
                self._write_strip(f'CFLAGS="$CFLAGS {AVX512_CFLAGS} {AVX512_LFLAGS} " CXXFLAGS="$CXXFLAGS '
                                  f'{AVX512_CFLAGS} {AVX512_LFLAGS} " LDFLAGS="$LDFLAGS {AVX512_LCFLAGS} " '
                                  'meson --libdir=lib64 --prefix=/usr --buildtype=plain {0} '
                                  '{1} builddiravx512'.format(self.config.extra_configure, self.config.extra_configure64))
                self._write_strip('ninja -v -C builddiravx512')
        if self.config.config_opts['use_apx'] and not self.config.config_opts['use_clang']:
            self._write_strip("GOAMD64=v3")
            if self.config.config_opts['pgo'] and self.config.profile_payload != "":
                self._write_strip(f'CFLAGS="$CFLAGS_GENERATE {APX_CFLAGS} {APX_LFLAGS} "'
                                  f' CXXFLAGS="$CXXFLAGS_GENERATE {AVX2_CFLAGS} {AVX2_LFLAGS} "'
                                  f' LDFLAGS="$LDFLAGS_GENERATE {APX_LCFLAGS} " '
                                  ' meson --libdir=lib64 --prefix=/usr --buildtype=plain {0} '
                                  ' {1} builddirapx'.format(self.config.extra_configure, self.config.extra_configure64))
                self._write_strip('ninja -v -C builddirapx')
                self._write_strip('pushd builddirapx')
                self._write_strip("\n".join(self.config.profile_payload))
                self._write_strip('popd')
                self._write_strip('rm -rf builddirapx')
                self._write_strip(f'CFLAGS="$CFLAGS_USE {APX_CFLAGS} {APX_LFLAGS} "'
                                  f' CXXFLAGS="$CXXFLAGS_USE {AVX2_CFLAGS} {AVX2_LFLAGS} "'
                                  f' LDFLAGS="$LDFLAGS_USE {APX_LCFLAGS} " '
                                  ' meson --libdir=lib64 --prefix=/usr --buildtype=plain {0} '
                                  ' {1} builddirapx'.format(self.config.extra_configure, self.config.extra_configure64))
                self._write_strip('ninja -v -C builddirapx')
            else:
                self._write_strip(f'CFLAGS="$CFLAGS {APX_CFLAGS} {APX_LFLAGS} "'
                                  f' CXXFLAGS="$CXXFLAGS {AVX2_CFLAGS} {AVX2_LFLAGS} "'
                                  f' LDFLAGS="$LDFLAGS {APX_LCFLAGS} " '
                                  ' meson --libdir=lib64 --prefix=/usr --buildtype=plain {0} '
                                  ' {1} builddirapx'.format(self.config.extra_configure, self.config.extra_configure64))
                self._write_strip('ninja -v -C builddirapx')
        if self.config.subdir:
            self._write_strip("popd")
        if self.config.config_opts['32bit']:
            self._write_strip("pushd ../build32/" + self.config.subdir)
            self.write_32bit_exports()
            self._write_strip('meson '
                              '--libdir=lib32 --prefix=/usr --buildtype=plain {0} {1} builddir'
                              .format(self.config.extra_configure,
                                      self.config.extra_configure32))
            self._write_strip('ninja -v -C builddir')
            self._write_strip('popd')

        self.write_build_append()
        self._write_strip("\n")
        self.write_check()
        self._write_strip("%install")
        self.write_variables()
        self.write_install_prepend()
        self._write_strip("export GOAMD64=v2")
        self.write_license_files()
        if self.config.config_opts['32bit']:
            self._write_strip('pushd ../build32/' + self.config.subdir)
            self._write_strip('DESTDIR=%{buildroot} ninja -C builddir install')
            self._write_strip("if [ -d  %{buildroot}/usr/lib32/pkgconfig ]")
            self._write_strip("then")
            self._write_strip("    pushd %{buildroot}/usr/lib32/pkgconfig")
            self._write_strip("    for i in *.pc ; do ln -s $i 32$i ; done")
            self._write_strip("    popd")
            self._write_strip("fi")
            self._write_strip("if [ -d %{buildroot}/usr/share/pkgconfig ]")
            self._write_strip("then")
            self._write_strip("    pushd %{buildroot}/usr/share/pkgconfig")
            self._write_strip("    for i in *.pc ; do ln -s $i 32$i ; done")
            self._write_strip("    popd")
            self._write_strip("fi")
            self._write_strip("popd")
        if self.config.subdir:
            self._write_strip("pushd " + self.config.subdir)
        if self.config.config_opts['use_avx2']:
            self._write_strip("GOAMD64=v3")
            self._write_strip('DESTDIR=%{buildroot}-v3 ninja -C builddiravx2 install')
        if self.config.config_opts['use_avx512']:
            self._write_strip("GOAMD64=v4")
            self._write_strip('DESTDIR=%{buildroot}-v4 ninja -C builddiravx512 install')
        if self.config.config_opts['use_apx'] and not self.config.config_opts['use_clang']:
            self._write_strip("GOAMD64=v3")
            self._write_strip('DESTDIR=%{buildroot}-va ninja -C builddirapx install')

        self._write_strip("GOAMD64=v2")
        self._write_strip("DESTDIR=%{buildroot} ninja -C builddir install")
        if self.config.subdir:
            self._write_strip("popd")
        self.write_find_lang()

    def write_cargo_pattern(self):
        """Write cargo build pattern to spec file."""
        if self.config.make_command:
            cargo_build = self.config.make_command
        else:
            cargo_build = "cargo build --release"

        self.write_prep()

        self._write_strip("%build")
        self.write_build_prepend()
        self.write_proxy_exports()
        if self.config.subdir:
            self._write_strip("pushd " + self.config.subdir)
        self._write_strip(cargo_build)
        if self.config.subdir:
            self._write_strip("popd")
        self.write_build_append()
        self._write_strip("\n")

        self._write_strip("%install")
        self.write_install_prepend()
        self.write_license_files()
        if self.config.subdir:
            self._write_strip("pushd " + self.config.subdir)
        self._write_strip("cargo install --path .")
        self._write_strip("mkdir -p %{buildroot}/usr/bin")
        self._write_strip('pushd "${HOME}/.cargo/bin/"')
        self._write_strip("mv * %{buildroot}/usr/bin/")
        self._write_strip("popd")
        if self.config.subdir:
            self._write_strip("popd")
        self.write_install_append()

    def write_phpize_pattern(self):
        """Write phpize build pattern to spec file."""
        self.write_prep()
        self._write_strip("%build")
        self.write_build_prepend()
        self.write_proxy_exports()
        self._write_strip("phpize")
        self._write_strip("%configure {0} {1}"
                          .format(self.config.disable_static,
                                  self.config.extra_configure))
        self.write_make_line()
        self.write_build_append()
        self._write_strip("\n")
        self._write_strip("%install")
        self.write_install_prepend()
        self.write_license_files()
        self._write_strip("%make_install")
        self._write_strip("\n")

    def write_nginx_pattern(self):
        """Write nginx build pattern to spec file."""
        self.write_prep()
        self._write_strip("%build")
        self.write_build_prepend()
        self.write_proxy_exports()
        self._write_strip("nginx-module configure")
        self._write_strip("nginx-module build")
        self.write_build_append()
        self._write_strip("\n")
        self._write_strip("%install")
        self.write_install_prepend()
        self.write_license_files()
        self._write_strip("nginx-module install %{buildroot}")
        self._write_strip("\n")

    def write_find_lang(self):
        """Write %find_lang macro to spec file."""
        for lang in self.locales:
            self._write("%find_lang {}\n".format(lang))

    def apply_patches(self):
        """Write patch list to spec file."""
        counter = 1
        for p in self.config.patches:
            name = p.split(None, 1)[0]
            if name == p:
                options = "-p1"
            else:
                options = p.split(None, 1)[1]
            if not p.split()[0].endswith(".nopatch"):
                self._write("%patch -P {} {}\n".format(counter, options))
            counter = counter + 1

        # Write version-specific patch commands
        for version in self.config.verpatches:
            if self.config.verpatches[version]:
                self._write("cd ../{}\n".format(self.build_dirs[self.config.versions[version]]))
            for p in self.config.verpatches[version]:
                name = p.split(None, 1)[0]
                if name == p:
                    options = "-p1"
                else:
                    options = p.split(None, 1)[1]
                if not p.split()[0].endswith(".nopatch"):
                    self._write("%patch -P {} {}\n".format(counter, options))
                counter = counter + 1

    def _write(self, string):
        self.specfile.write(string)

    def _write_strip(self, string):
        self.specfile.write_strip(string)

    def quote_filename(self, filename):
        """Quotes the filename, if necessary. Identifies and skips any RPM directive prefix."""
        # Characters that require quoting -- only those with special
        # meaning in specfiles
        special_chars = set(" \t")
        # Build up the output as a string
        quoted = ''
        # Capture any directive prefix separately from actual filename
        #                          (1                   )(3 )
        directive_re = re.compile(r"(%\w+(\([^\)]*\))?\s+)(.*)")
        parts = directive_re.match(filename)
        if parts:
            # Add prefix to the output
            quoted += parts.group(1)
            # Set the filename to the remaining portion
            filename = parts.group(3)

        # Now check for special characters
        if any(c in filename for c in special_chars):
            # Quote the filename
            quoted += '"{}"'.format(filename)
        else:
            # Add the filename as-is
            quoted += filename
        return quoted
