#!/bin/true
#
# buildpattern.py - part of autospec
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
# Deduce and emit the patterns for %build
#

import config
import files
import lang
import os
import patches
import re
import tarball
import test

default_pattern = "make"
pattern_strengh = 0

disable_static = "--disable-static"

extra_make = ""
extra_cmake = ""
extra_make_install = ""
install_macro = "%make_install"
make_install_append = []
prep_append = []
subdir = ""
sources = {"unit": [], "gcov": [], "tmpfile": [], "archive": []}
source_index = {}
archive_details = {}


def write_prep(file, ruby_pattern=False):
    file.write_strip("%prep")
    for archive in sources["archive"]:
        file.write_strip("tar -xf %{{SOURCE{}}}".format(source_index[archive]))
    if sources["archive"]:
        file.write_strip("cd ..")
    if ruby_pattern:
        file.write_strip("gem unpack %{SOURCE0}")
        file.write_strip("%setup -q -D -T -n " + tarball.tarball_prefix)
        file.write_strip("gem spec %{SOURCE0} -l --ruby > " + tarball.name + ".gemspec")
    else:
        if default_pattern == 'R':
            file.write_strip("%setup -q -c -n " + tarball.tarball_prefix)
        else:
            file.write_strip("%setup -q -n " + tarball.tarball_prefix)
    for archive in sources["archive"]:
        file.write_strip('mkdir -p %{{_topdir}}/BUILD/{0}/{1}'
                         .format(tarball.tarball_prefix,
                                 archive_details[archive + "destination"]))
        file.write_strip('mv %{{_topdir}}/BUILD/{0}/* %{{_topdir}}/BUILD/{1}/{2}'
                         .format(archive_details[archive + "prefix"],
                                 tarball.tarball_prefix,
                                 archive_details[archive + "destination"]))
    patches.apply_patches(file)
    file.write_strip("\n")
    write_prep_append(file)


def write_variables(file):
    flags = []
    if config.want_clang:
        file.write_strip("export CC=clang\n")
        file.write_strip("export CXX=clang++\n")
        file.write_strip("export LD=ld.gold\n")
    if config.optimize_size:
        flags.extend(["-Os", "-ffunction-sections"])
    if config.broken_cpp:
        flags.extend(["-std=gnu++98"])
    if config.insecure_build:
        file.write_strip("export CFLAGS=\"-O3 -g -fopt-info-vec \"\n")
        file.write_strip("unset LDFLAGS\n")
    if config.conservative_flags:
        file.write_strip("export CFLAGS=\"-O2 -g -Wp,-D_FORTIFY_SOURCE=2 "
                         "-fexceptions -fstack-protector "
                         "--param=ssp-buffer-size=32 -Wformat "
                         "-Wformat-security -Wno-error -Wl,-z -Wl,now "
                         "-Wl,-z -Wl,relro -Wl,-z,max-page-size=0x1000 -m64 "
                         "-march=westmere -mtune=haswell\"\n")
        file.write_strip("export CXXFLAGS=$CFLAGS\n")
        file.write_strip("unset LDFLAGS\n")
    if config.clang_flags:
        file.write_strip("export CFLAGS=\"-g -O3 "
                         "-feliminate-unused-debug-types  -pipe -Wall "
                         "-D_FORTIFY_SOURCE=2 -fexceptions -fstack-protector "
                         "--param=ssp-buffer-size=32 -Wformat "
                         "-Wformat-security -Wl,--copy-dt-needed-entries -m64 "
                         "-march=westmere  -mtune=native "
                         "-fasynchronous-unwind-tables -D_REENTRANT  "
                         "-Wl,-z -Wl,now -Wl,-z -Wl,relro \"\n")
        file.write_strip("export CXXFLAGS=$CFLAGS\n")
        file.write_strip("unset LDFLAGS\n")
    if config.optimize_speed:
        flags.extend(["-O3", "-fno-semantic-interposition", "-falign-functions=32"])
        file.write_strip("export AR=gcc-ar\n")
        file.write_strip("export RANLIB=gcc-ranlib\n")
        file.write_strip("export NM=gcc-nm\n")
    if config.fast_math:
        flags.extend(["-ffast-math", "-ftree-loop-vectorize"])
    if config.pgo:
        flags.extend(["-O3", "-fprofile-use", "-fprofile-dir=pgo", "-fprofile-correction"])
    if tarball.gcov_file:
        flags = list(filter(("-flto").__ne__, flags))
        flags.extend(["-O3", "-fauto-profile=%{{SOURCE{0}}}".format(source_index[sources["gcov"][0]])])
    if flags:
        flags = list(set(flags))
        file.write_strip("export CFLAGS=\"$CFLAGS {0} \"\n".format(" ".join(flags)))
        file.write_strip("export FCFLAGS=\"$CFLAGS {0} \"\n".format(" ".join(flags)))
        file.write_strip("export FFLAGS=\"$CFLAGS {0} \"\n".format(" ".join(flags)))
        file.write_strip("export CXXFLAGS=\"$CXXFLAGS {0} \"\n".format(" ".join(flags)))

    if config.profile_payload and config.profile_payload[0]:
        genflags = list()
        genflags.extend(["-fprofile-generate", "-fprofile-dir=pgo"])
        useflags = list()
        useflags.extend(["-fprofile-use", "-fprofile-dir=pgo", "-fprofile-correction"])

        file.write_strip("export CFLAGS_GENERATE=\"$CFLAGS {0} \"\n".format(" ".join(genflags)))
        file.write_strip("export FCFLAGS_GENERATE=\"$FCFLAGS {0} \"\n".format(" ".join(genflags)))
        file.write_strip("export FFLAGS_GENERATE=\"$FFLAGS {0} \"\n".format(" ".join(genflags)))
        file.write_strip("export CXXFLAGS_GENERATE=\"$CXXFLAGS {0} \"\n".format(" ".join(genflags)))

        file.write_strip("export CFLAGS_USE=\"$CFLAGS {0} \"\n".format(" ".join(useflags)))
        file.write_strip("export FCFLAGS_USE=\"$FCFLAGS {0} \"\n".format(" ".join(useflags)))
        file.write_strip("export FFLAGS_USE=\"$FFLAGS {0} \"\n".format(" ".join(useflags)))
        file.write_strip("export CXXFLAGS_USE=\"$CXXFLAGS {0} \"\n".format(" ".join(useflags)))


def write_check(file):
    if test.tests_config and not test.skip_tests:
        file.write_strip("%check")
        file.write_strip("export LANG=C")
        file.write_strip("export http_proxy=http://127.0.0.1:9/")
        file.write_strip("export https_proxy=http://127.0.0.1:9/")
        file.write_strip("export no_proxy=localhost")
        file.write_strip(test.tests_config)
        file.write_strip("\n")


def write_make_install(file):
    file.write_strip("%install")
    file.write_strip("rm -rf %{buildroot}")
    if subdir:
        file.write_strip("pushd %s" % subdir)
    file.write_strip("%s %s\n" % (install_macro, extra_make_install))
    if subdir:
        file.write_strip("popd")
    lang.write_find_lang(file)


def get_profile_generate_flags():
    if config.profile_payload and config.profile_payload[0]:
        return "CFLAGS=\"${CFLAGS_GENERATE}\" CXXFLAGS=\"${CXXFLAGS_GENERATE}\" FFLAGS=\"${FFLAGS_GENERATE}\" FCFLAGS=\"${FCFLAGS_GENERATE}\" "
    return ""


def get_profile_use_flags():
    if config.profile_payload and config.profile_payload[0]:
        return "CFLAGS=\"${CFLAGS_USE}\" CXXFLAGS=\"${CXXFLAGS_USE}\" FFLAGS=\"${FFLAGS_USE}\" FCFLAGS=\"${FCFLAGS_USE}\" "
    return ""


def write_configure_pattern(file):
    if patches.autoreconf:
        # Patches affecting configure.* or Makefile.*, reconf instead
        write_configure_ac_pattern(file)
        return
    write_prep(file)
    file.write_strip("%build")
    file.write_strip("export LANG=C")
    if config.asneeded == 0:
        file.write_strip("unset LD_AS_NEEDED\n")
    write_variables(file)

    # Prep it for PGO
    if config.profile_payload and config.profile_payload[0]:
        if subdir:
            file.write_strip("pushd %s" % subdir)
        file.write_strip(get_profile_generate_flags() + "%configure " + disable_static + " " + config.extra_configure)
        file.write_strip("make V=1 " + config.parallel_build + extra_make)
        if subdir:
            file.write_strip("popd")
        file.write_strip("\n")

        file.write_strip("\n".join(config.profile_payload))
        file.write_strip("\nmake clean\n")

    if subdir:
        file.write_strip("pushd %s" % subdir)
    file.write_strip(get_profile_use_flags() + "%configure " + disable_static + " " + config.extra_configure)
    file.write_strip("make V=1 " + config.parallel_build + extra_make)
    if subdir:
        file.write_strip("popd")
    file.write_strip("\n")
    write_check(file)
    write_make_install(file)


def write_configure_ac_pattern(file):
    write_prep(file)
    file.write_strip("%build")
    file.write_strip("export LANG=C")
    if config.asneeded == 0:
        file.write_strip("unset LD_AS_NEEDED\n")
    write_variables(file)
    # Prep it for PGO
    if config.profile_payload and config.profile_payload[0]:
        if subdir:
            file.write_strip("pushd %s" % subdir)
        file.write_strip(get_profile_generate_flags() + "%reconfigure " + disable_static + " " + config.extra_configure)
        file.write_strip("make V=1 " + config.parallel_build + extra_make)
        if subdir:
            file.write_strip("popd")
        file.write_strip("\n")

        file.write_strip("\n".join(config.profile_payload))
        file.write_strip("\nmake clean\n")

    if subdir:
        file.write_strip("pushd %s" % subdir)
    file.write_strip(get_profile_use_flags() + "%reconfigure " + disable_static + " " + config.extra_configure)
    file.write_strip("make V=1 " + config.parallel_build + extra_make)
    if subdir:
        file.write_strip("popd")
    file.write_strip("\n")
    write_check(file)
    write_make_install(file)


def write_make_pattern(file):
    write_prep(file)
    file.write_strip("%build")
    file.write_strip("export LANG=C")
    if config.asneeded == 0:
        file.write_strip("unset LD_AS_NEEDED\n")
    write_variables(file)
    if subdir:
        file.write_strip("pushd %s" % subdir)
    file.write_strip("make V=1 " + config.parallel_build + extra_make)
    if subdir:
        file.write_strip("popd")
    file.write_strip("\n")
    write_check(file)
    write_make_install(file)


def write_autogen_pattern(file):
    write_prep(file)
    file.write_strip("%build")
    file.write_strip("export LANG=C")
    if config.asneeded == 0:
        file.write_strip("unset LD_AS_NEEDED\n")
    write_variables(file)
    if config.profile_payload and config.profile_payload[0]:
        file.write_strip(get_profile_generate_flags() + "%autogen " + disable_static + " " + config.extra_configure)
        file.write_strip("make V=1 " + config.parallel_build + extra_make)
        file.write_strip("\n")

        file.write_strip("\n".join(config.profile_payload))
        file.write_strip("\nmake clean\n")

    file.write_strip(get_profile_use_flags() + "%autogen " + disable_static + " " + config.extra_configure)
    file.write_strip("make V=1 " + config.parallel_build + extra_make)
    file.write_strip("\n")
    write_check(file)
    write_make_install(file)


def write_distutils_pattern(file):
    write_prep(file)
    file.write_strip("%build")
    file.write_strip("export LANG=C")
    if config.asneeded == 0:
        file.write_strip("unset LD_AS_NEEDED\n")
    write_variables(file)
    file.write_strip("python2 setup.py build -b py2 " + config.extra_configure)
    file.write_strip("\n")
    if test.tests_config and not test.skip_tests:
        file.write_strip("%check")
        # Prevent setuptools from hitting the internet
        file.write_strip("export http_proxy=http://127.0.0.1:9/")
        file.write_strip("export https_proxy=http://127.0.0.1:9/")
        file.write_strip("export no_proxy=localhost,127.0.0.1,0.0.0.0")
        file.write_strip(test.tests_config)
    file.write_strip("%install")
    file.write_strip("rm -rf %{buildroot}")
    file.write_strip("python2 -tt setup.py build -b py2 install --root=%{buildroot}")
    lang.write_find_lang(file)


def write_distutils3_pattern(file):
    write_prep(file)
    file.write_strip("%build")
    file.write_strip("export LANG=C")
    if config.asneeded == 0:
        file.write_strip("unset LD_AS_NEEDED\n")
    write_variables(file)
    file.write_strip("python3 setup.py build -b py3 " + config.extra_configure)
    file.write_strip("\n")
    if test.tests_config and not test.skip_tests:
        file.write_strip("%check")
        # Prevent setuptools from hitting the internet
        file.write_strip("export http_proxy=http://127.0.0.1:9/")
        file.write_strip("export https_proxy=http://127.0.0.1:9/")
        file.write_strip("export no_proxy=localhost,127.0.0.1,0.0.0.0")
        file.write_strip(test.tests_config)
    file.write_strip("%install")
    file.write_strip("rm -rf %{buildroot}")
    file.write_strip("python3 -tt setup.py build -b py3 install --root=%{buildroot}")
    lang.write_find_lang(file)


def write_distutils23_pattern(file):
    write_prep(file)
    file.write_strip("%build")
    file.write_strip("export LANG=C")
    if config.asneeded == 0:
        file.write_strip("unset LD_AS_NEEDED\n")
    write_variables(file)
    file.write_strip("python2 setup.py build -b py2 " + config.extra_configure)
    file.write_strip("python3 setup.py build -b py3 " + config.extra_configure)
    file.write_strip("\n")
    if test.tests_config and not test.skip_tests:
        file.write_strip("%check")
        # Prevent setuptools from hitting the internet
        file.write_strip("export http_proxy=http://127.0.0.1:9/")
        file.write_strip("export https_proxy=http://127.0.0.1:9/")
        file.write_strip("export no_proxy=localhost,127.0.0.1,0.0.0.0")
        file.write_strip(test.tests_config)

    file.write_strip("%install")
    file.write_strip("rm -rf %{buildroot}")
    file.write_strip("python2 -tt setup.py build -b py2 install --root=%{buildroot}")
    file.write_strip("python3 -tt setup.py build -b py3 install --root=%{buildroot}")
    lang.write_find_lang(file)


def write_R_pattern(file):
    write_prep(file)
    file.write_strip("%build")
    file.write_strip("export LANG=C")
    if config.asneeded == 0:
        file.write_strip("unset LD_AS_NEEDED\n")
    file.write_strip("\n")

    file.write_strip("%install")
    file.write_strip("rm -rf %{buildroot}")
    file.write_strip("export LANG=C")
    file.write_strip("export CFLAGS=\"$CFLAGS -O3 -flto -fno-semantic-interposition \"\n")
    file.write_strip("export FCFLAGS=\"$CFLAGS -O3 -flto -fno-semantic-interposition \"\n")
    file.write_strip("export FFLAGS=\"$CFLAGS -O3 -flto -fno-semantic-interposition \"\n")
    file.write_strip("export CXXFLAGS=\"$CXXFLAGS -O3 -flto -fno-semantic-interposition \"\n")
    file.write_strip("export AR=gcc-ar\n")
    file.write_strip("export RANLIB=gcc-ranlib\n")
    file.write_strip("export LDFLAGS=\"$LDFLAGS  -Wl,-z -Wl,relro\"\n")

    file.write_strip("mkdir -p %{buildroot}/usr/lib64/R/library")
    file.write_strip("R CMD INSTALL --install-tests --build  -l %{buildroot}/usr/lib64/R/library " + tarball.rawname)
    file.write_strip("%{__rm} -rf %{buildroot}%{_datadir}/R/library/R.css")
    lang.write_find_lang(file)
    write_check(file)


def write_ruby_pattern(file):
    write_prep(file, ruby_pattern=True)
    file.write_strip("%build")
    file.write_strip("export LANG=C")
    file.write_strip("gem build " + tarball.name + ".gemspec")
    file.write_strip("\n")

    file.write_strip("%install")
    file.write_strip("%global gem_dir $(ruby -e'puts Gem.default_dir')")
    file.write_strip("gem install -V \\")
    file.write_strip("  --local \\")
    file.write_strip("  --force \\")
    file.write_strip("  --install-dir .%{gem_dir} \\")
    file.write_strip("  --bindir .%{_bindir} \\")
    file.write_strip(" " + tarball.tarball_prefix + ".gem")
    file.write_strip("\n")

    file.write_strip("mkdir -p %{buildroot}%{gem_dir}")
    file.write_strip("cp -pa .%{gem_dir}/* \\")
    file.write_strip("        %{buildroot}%{gem_dir}")
    file.write_strip("\n")

    file.write_strip("if [ -d .%{_bindir} ]; then")
    file.write_strip("    mkdir -p %{buildroot}%{_bindir}")
    file.write_strip("    cp -pa .%{_bindir}/* \\")
    file.write_strip("        %{buildroot}%{_bindir}/")
    file.write_strip("fi")
    file.write_strip("\n")
    lang.write_find_lang(file)
    write_check(file)


def write_cmake_pattern(file):
    global subdir
    subdir = "clr-build"
    write_prep(file)
    file.write_strip("%build")
    file.write_strip("export LANG=C")
    if config.asneeded == 0:
        file.write_strip("unset LD_AS_NEEDED\n")
    file.write_strip("mkdir clr-build")
    file.write_strip("pushd clr-build")
    write_variables(file)
    file.write_strip("cmake .. -G \"Unix Makefiles\" "
                     "-DCMAKE_INSTALL_PREFIX=/usr -DBUILD_SHARED_LIBS:BOOL=ON "
                     "-DLIB_INSTALL_DIR:PATH=%{_libdir} "
                     "-DCMAKE_AR=/usr/bin/gcc-ar "
                     "-DCMAKE_RANLIB=/usr/bin/gcc-ranlib " + extra_cmake)
    file.write_strip("make VERBOSE=1 " + config.parallel_build + extra_make)
    file.write_strip("popd")
    file.write_strip("\n")
    write_check(file)
    write_make_install(file)


def write_cpan_pattern(file):
    global subdir
    write_prep(file)
    file.write_strip("%build")
    file.write_strip("export LANG=C")
    file.write_strip("if test -f Makefile.PL; then")
    file.write_strip("%{__perl} Makefile.PL")
    file.write_strip("make V=1 " + config.parallel_build + extra_make)
    file.write_strip("else")
    file.write_strip("%{__perl} Build.PL")
    file.write_strip("./Build")
    file.write_strip("fi")
    file.write_strip("\n")
    write_check(file)
    file.write_strip("%install")
    file.write_strip("rm -rf %{buildroot}")
    file.write_strip("if test -f Makefile.PL; then")
    file.write_strip("make pure_install PERL_INSTALL_ROOT=%{buildroot}")
    file.write_strip("else")
    file.write_strip("./Build install --installdirs=site --destdir=%{buildroot}")
    file.write_strip("fi")
    file.write_strip("find %{buildroot} -type f -name .packlist -exec rm -f {} ';'")
    file.write_strip("find %{buildroot} -depth -type d -exec rmdir {} 2>/dev/null ';'")
    file.write_strip("find %{buildroot} -type f -name '*.bs' -empty -exec rm -f {} ';'")
    file.write_strip("%{_fixperms} %{buildroot}/*")
    lang.write_find_lang(file)


def write_scons_pattern(file):
    write_prep(file)
    file.write_strip("%build")
    file.write_strip("export LANG=C")
    write_variables(file)
    file.write_strip("scons" + config.parallel_build + " " + config.extra_configure)
    file.write_strip("\n")
    file.write_strip("%install")
    file.write_strip("scons install " + extra_make_install)


def write_golang_pattern(file):
    library_path = tarball.golibpath
    tolerance = ""
    write_prep(file)
    file.write_strip("%build")
    file.write_strip("export LANG=C")
    file.write_strip("\n")
    file.write_strip("%install")
    file.write_strip("gopath=\"/usr/lib/golang\"")
    file.write_strip("library_path=\"" + library_path + "\"")
    file.write_strip("rm -rf %{buildroot}")
    file.write_strip("install -d -p %{buildroot}${gopath}/src/${library_path}/")
    file.write_strip("for file in $(find . -iname \"*.go\" -o -iname \"*.h\" -o -iname \"*.c\") ; do")
    file.write("     echo ${file}\n")
    file.write("     install -d -p %{buildroot}${gopath}/src/${library_path}/$(dirname $file)\n")
    file.write("     cp -pav $file %{buildroot}${gopath}/src/${library_path}/$file\n")
    file.write_strip("done")
    write_make_install_append(file)
    file.write_strip("\n")
    if not test.skip_tests:
        if test.allow_test_failures:
            tolerance = " || :"
        file.write_strip("%check")
        file.write_strip("export http_proxy=http://127.0.0.1:9/")
        file.write_strip("export https_proxy=http://127.0.0.1:9/")
        file.write_strip("export no_proxy=localhost")
        file.write_strip("gopath=\"/usr/lib/golang\"")
        file.write_strip("export GOPATH=\"%{buildroot}${gopath}\"")
        if test.tests_config:
            file.write_strip(test.tests_config)
        else:
            file.write_strip("go test -v -x " + library_path + tolerance)


def write_maven_pattern(file):
    write_prep(file)
    file.write_strip("%build")
    file.write_strip("python3 /usr/share/java-utils/mvn_build.py " + extra_make)
    file.write_strip("\n")
    file.write_strip("%install")
    file.write_strip("xmvn-install  -R .xmvn-reactor -n maven-parent -d %{buildroot}")


def set_build_pattern(pattern, strength):
    global default_pattern
    global pattern_strengh
    if strength <= pattern_strengh:
        return 0
    default_pattern = pattern
    pattern_strengh = strength


def get_systemd_units():
    """get systemd unit files from the files module"""
    service_file_section = "config"
    systemd_service_pattern = r"^/usr/lib/systemd/system/[^/]*\.(mount|service|socket|target)$"
    systemd_units = []

    if service_file_section not in files.packages:
        return systemd_units

    for f in files.packages[service_file_section]:
        if re.search(systemd_service_pattern, f) and f not in files.excludes:
            systemd_units.append(f)

    return systemd_units


def write_sources(file):
    """write out installs from SourceX lines"""
    if len(sources["unit"]) != 0:
        file.write_strip("mkdir -p %{buildroot}/usr/lib/systemd/system")
        for unit in sources["unit"]:
            file.write_strip("install -m 0644 %{{SOURCE{0}}} %{{buildroot}}/usr/lib/systemd/system/{1}"
                             .format(source_index[unit], unit))
    if len(sources["tmpfile"]) != 0:
        file.write_strip("mkdir -p %{buildroot}/usr/lib/tmpfiles.d")
        file.write_strip("install -m 0644 %{{SOURCE{0}}} %{{buildroot}}/usr/lib/tmpfiles.d/{1}.conf"
                         .format(source_index[sources["tmpfile"][0]], tarball.name))


def write_make_install_append(file):
    """write out any custom supplied commands at the very end of the %install section"""
    if make_install_append and make_install_append[0]:
        file.write_strip("## make_install_append content")
        for line in make_install_append:
            file.write_strip("%s\n" % line)
        file.write_strip("## make_install_append end")


def write_prep_append(file):
    """write out any custom supplied commands at the very end of the %prep section"""
    if prep_append and prep_append[0]:
        for line in prep_append:
            file.write_strip("%s\n" % line)
        file.write_strip("\n")


def write_systemd_units(file):
    """write out installs for systemd unit files"""
    units = get_systemd_units()
    for unit in units:
        file.write("systemctl --root=%{{buildroot}} enable {0}\n".format(os.path.basename(unit)))


def write_buildpattern(file):
    file.write_strip("\n")

    pattern_method = globals().get('write_%s_pattern' % default_pattern, None)
    if pattern_method:
        pattern_method(file)

    write_sources(file)
    write_make_install_append(file)
    # write_systemd_units(file)
