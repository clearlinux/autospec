import unittest
import unittest.mock
import buildreq
import config
import specfiles
import tarball


class TestSpecfileWrite(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        self.specfile = None
        self.WRITES = []

    def setUp(self):
        conf = config.Config('/download/path')
        conf.config_opts['dev_requires_extras'] = False
        url = "http://www.testpkg.com/testpkg/pkg-1.0.tar.gz"
        content = tarball.Content(url, 'pkg', '1.0', [], conf, '/tmp')
        conf.content = content
        reqs = buildreq.Requirements(url)
        self.specfile = specfiles.Specfile(url, '1.0', 'pkg', '2', conf, reqs, content)

        def mock_write(string):
            self.WRITES.append(string)

        self.specfile._write = mock_write
        self.specfile._write_strip = mock_write
        self.WRITES = []

    def test_write_nvr_no_urlban(self):
        """
        test Specfile.write_nvr with no urlban set
        """
        self.specfile.write_nvr()
        expect = ["Name     : pkg\n",
                  "Version  : 1.0\n",
                  "Release  : 2\n",
                  "URL      : http://www.testpkg.com/testpkg/pkg-1.0.tar.gz\n",
                  "Source0  : http://www.testpkg.com/testpkg/pkg-1.0.tar.gz\n"]
        self.assertEqual(expect, self.WRITES)

    def test_write_nvr_urlban(self):
        """
        test Specfile.write_nvr with urlban set
        """
        self.specfile.config.urlban = "www.testpkg.com"
        self.specfile.write_nvr()
        expect = ["Name     : pkg\n",
                  "Version  : 1.0\n",
                  "Release  : 2\n",
                  "URL      : http://localhost/testpkg/pkg-1.0.tar.gz\n",
                  "Source0  : http://localhost/testpkg/pkg-1.0.tar.gz\n"]
        self.assertEqual(expect, self.WRITES)

    def test_write_sources(self):
        """
        test write_sources with all Specfile.sources set.
        """
        self.specfile.config.sources["unit"] = ["pkg2.service", "pkg1.service"]
        self.specfile.config.sources["archive"] = ["archA", "archD", "archB", "archC"]
        self.specfile.config.sources["tmpfile"] = ["tmp1", "tmp2"]
        self.specfile.config.sources["gcov"] = ["pkg.gcov"]
        self.specfile.config.sources["godep"] = ["pkg.godep"]
        self.specfile.config.sources["version"] = ["pkg.oldver"]
        self.specfile.write_sources()
        expect = ["Source1  : archA\n",
                  "Source2  : archB\n",
                  "Source3  : archC\n",
                  "Source4  : archD\n",
                  "Source5  : pkg.gcov\n",
                  "Source6  : pkg.godep\n",
                  "Source7  : pkg.oldver\n",
                  "Source8  : pkg1.service\n",
                  "Source9  : pkg2.service\n",
                  "Source10  : tmp1\n",
                  "Source11  : tmp2\n"]
        self.assertEqual(expect, self.WRITES)

    def test_write_summary(self):
        """
        test write_summary with unstripped summary and group strings
        """
        self.specfile.default_sum = "   This is unstripped summary  "
        self.specfile.write_summary()
        expect = ["Summary  : This is unstripped summary\n",
                  "Group    : Development/Tools\n"]
        self.assertEqual(expect, self.WRITES)

    def test_write_license(self):
        """
        test write_license with unsorted list of licenses
        """
        self.specfile.licenses = ["MIT", "IJG", "GPL-3.0", "GPL-2.0", "ICU"]
        self.specfile.write_license()
        expect = ["License  : GPL-2.0 GPL-3.0 ICU IJG MIT\n"]
        self.assertEqual(expect, self.WRITES)

    def test_write_main_subpackage_requires_no_autostart(self):
        """
        test write_main_subpackage_requires with autostart package and
        Specfile.no_autostart set.
        """
        self.specfile.packages["autostart"] = ["autostart"]
        self.specfile.packages["bin"] = []
        self.specfile.packages["lib"] = ["package.so"]
        self.specfile.requirements.requires[None] = set(["pkg1", "pkg2"])
        self.specfile.config.config_opts['no_autostart'] = True
        self.specfile.write_main_subpackage_requires()
        expect = ["Requires: pkg-bin = %{version}-%{release}\n",
                  "Requires: pkg-lib = %{version}-%{release}\n",
                  "Requires: pkg1\n",
                  "Requires: pkg2\n"]
        self.assertEqual(expect, self.WRITES)

    def test_write_main_subpackage_requires_autostart(self):
        """
        test write_main_subpackage_requires with autostart package and
        Specfile.no_autostart not set. Also has other ignored packages.
        """
        self.specfile.packages["autostart"] = ["autostart"]
        self.specfile.packages["bin"] = []
        self.specfile.packages["lib"] = ["package.so"]
        self.specfile.packages["main"] = ["main/file.py"]
        self.specfile.packages["ignore"] = []
        self.specfile.packages["dev"] = []
        self.specfile.packages["active-units"] = []
        self.specfile.requirements.requires[None] = set(["pkg1", "pkg2"])
        self.specfile.write_main_subpackage_requires()
        expect = ["Requires: pkg-autostart = %{version}-%{release}\n",
                  "Requires: pkg-bin = %{version}-%{release}\n",
                  "Requires: pkg-lib = %{version}-%{release}\n",
                  "Requires: pkg1\n",
                  "Requires: pkg2\n"]
        self.assertEqual(expect, self.WRITES)

    def test_write_main_subpackage_requires_empty(self):
        """
        test write_main_subpackage_requires with no required subpackages.
        """
        self.specfile.write_main_subpackage_requires()
        self.assertEqual([], self.WRITES)

    def test_write_buildreq(self):
        """
        test write_buildreq with unsorted list of build requirements.
        """
        self.specfile.requirements.buildreqs = ["python", "ruby", "go"]
        self.specfile.write_buildreq()
        expect = ["BuildRequires : go\n",
                  "BuildRequires : python\n",
                  "BuildRequires : ruby\n"]
        self.assertEqual(expect, self.WRITES)

    def test_write_buildreq_empty(self):
        """
        test write_buildreq with no build requirements.
        """
        self.specfile.write_buildreq()
        self.assertEqual([], self.WRITES)

    def test_write_patch_header(self):
        """
        test write_patch_header with list of patches.
        """
        self.specfile.config.patches = ["speedup.patch",
                                        "slowdown.patch",
                                        "revert.patch reverts slowdown.patch"]
        self.specfile.write_patch_header()
        expect = ["Patch1: speedup.patch\n",
                  "Patch2: slowdown.patch\n",
                  "Patch3: revert.patch\n"]
        self.assertEqual(expect, self.WRITES)

    def test_write_patch_header_empty(self):
        """
        test write_patch_header with empty patch list.
        """
        self.specfile.write_patch_header()
        self.assertEqual([], self.WRITES)

    def test_write_description(self):
        """
        test write_description with unstripped description
        """
        self.specfile.default_desc = " This package is for testing only       "
        self.specfile.write_description()
        expect = ["\n%description\nThis package is for testing only\n"]
        self.assertEqual(expect, self.WRITES)

    def test_write_files_header_base(self):
        """
        base test for write_files_header
        """
        self.specfile.packages["data"] = ["df1", "df2", "df3"]
        self.specfile.packages["ignore"] = ["doesn't matter"]
        self.specfile.packages["python"] = ["pyfile1", "pyfile2"]
        self.specfile.packages["dev"] = ["dev1", "dev2"]
        self.specfile.packages["pack"] = ["packf1"]
        self.specfile.requirements.buildreqs = ["pep8", "pycurl"]
        self.specfile.write_files_header()
        expect = ["\n%package data\n",
                  "Summary: data components for the pkg package.\n",
                  "Group: Data\n",
                  "\n%description data\n",
                  "data components for the pkg package.\n",
                  "\n",
                  "\n%package dev\n",
                  "Summary: dev components for the pkg package.\n",
                  "Group: Development\n",
                  "Requires: pkg-data = %{version}-%{release}\n",
                  "Provides: pkg-devel = %{version}-%{release}\n",
                  "Requires: pkg = %{version}-%{release}\n",
                  "\n%description dev\n",
                  "dev components for the pkg package.\n",
                  "\n",
                  "\n%package pack\n",
                  "Summary: pack components for the pkg package.\n",
                  "Group: Default\n",
                  "\n%description pack\n",
                  "pack components for the pkg package.\n",
                  "\n",
                  "\n%package python\n",
                  "Summary: python components for the pkg package.\n",
                  "Group: Default\n",
                  "\n%description python\n",
                  "python components for the pkg package.\n",
                  "\n"]
        self.assertEqual(expect, self.WRITES)

    def test_write_files_header_custom_extra_requires(self):
        """
        test write_files_header with custom extras requires.
        """
        self.specfile.packages["data"] = ["file1"]
        self.specfile.packages["foobar-extras"] = ["file2"]
        self.specfile.file_maps = { 'foobar-extras': { 'requires': ["data"] }}
        self.specfile.write_files_header()
        expect = ["\n%package data\n",
                  "Summary: data components for the pkg package.\n",
                  "Group: Data\n",
                  "\n%description data\n",
                  "data components for the pkg package.\n",
                  "\n",
                  "\n%package foobar-extras\n",
                  "Summary: foobar-extras components for the pkg package.\n",
                  "Group: Default\n",
                  "Requires: pkg-data = %{version}-%{release}\n",
                  "\n%description foobar-extras\n",
                  "foobar-extras components for the pkg package.\n",
                  "\n"]
        self.assertEqual(expect, self.WRITES)

    def test_write_files_header_python_name(self):
        """
        test write_files_header with uppercase letter in Specfile.name, causing
        a Provides line to be written.
        """
        self.specfile.name = 'Pkg'
        self.specfile.packages["python"] = ["pyfile1", "pyfile2"]
        self.specfile.write_files_header()
        expect = ["\n%package python\n",
                  "Summary: python components for the Pkg package.\n",
                  "Group: Default\n",
                  "Provides: pkg-python\n",
                  "\n%description python\n",
                  "python components for the Pkg package.\n",
                  "\n"]
        self.assertEqual(expect, self.WRITES)


    def test_write_files_header_bare(self):
        """
        test write_files_header with no packages
        """
        self.specfile.write_files_header()
        self.assertEqual([], self.WRITES)

    def test_write_buildpattern(self):
        """
        test write_buildpattern
        """
        # Should be doable but probably worth waiting for specfile template rework
        pass

    def test_write_scriplets_base(self):
        """
        test write_scriplets base test
        """
        def mock_read_conf_file(name):
            prefix = "pre" if "pre" in name else "post"
            return ["{}-script line 1\n".format(prefix),
                    "{}-script line 2\n".format(prefix),
                    "{}-script line 3\n".format(prefix)]

        class MockSpecfile(object):
            @staticmethod
            def writelines(stringlist):
                self.WRITES.extend(stringlist)

        self.specfile.config.read_conf_file = mock_read_conf_file
        self.specfile.specfile = MockSpecfile()
        self.specfile.packages["ruby"] = ["rubyfile1"]
        self.specfile.packages["ignore"] = ["ignorefile1", "ignorefile2"]
        self.specfile.write_scriplets()
        expect = ["\n%post ruby\n",
                  "post-script line 1\n\n",
                  "post-script line 2\n\n",
                  "post-script line 3\n\n",
                  "\n%pre ruby\n",
                  "pre-script line 1\n\n",
                  "pre-script line 2\n\n",
                  "pre-script line 3\n\n"]

        self.assertEqual(expect, self.WRITES)

    def test_write_scriplets_pre_only(self):
        """
        test write_scriplets with only pre-scripts present.
        """
        def mock_read_conf_file(name):
            if "pre" in name:
                return ["pre-script line 1\n",
                        "pre-script line 2\n",
                        "pre-script line 3\n"]
            else:
                return []

        class MockSpecfile(object):
            @staticmethod
            def writelines(stringlist):
                self.WRITES.extend(stringlist)

        self.specfile.config.read_conf_file = mock_read_conf_file
        self.specfile.specfile = MockSpecfile()
        self.specfile.packages["ruby"] = ["rubyfile1"]
        self.specfile.packages["ignore"] = ["ignorefile1", "ignorefile2"]
        self.specfile.write_scriplets()
        expect = ["\n%pre ruby\n",
                  "pre-script line 1\n\n",
                  "pre-script line 2\n\n",
                  "pre-script line 3\n\n"]

        self.assertEqual(expect, self.WRITES)

    def test_write_scriplets_bare(self):
        """
        test write_scriplets with no scripts present.
        """
        def mock_read_conf_file(name):
            return []

        class MockSpecfile(object):
            @staticmethod
            def writelines(stringlist):
                self.WRITES.extend(stringlist)

        self.specfile.config.read_conf_file = mock_read_conf_file
        self.specfile.specfile = MockSpecfile()
        self.specfile.packages["ruby"] = ["rubyfile1"]
        self.specfile.packages["ignore"] = ["ignorefile1", "ignorefile2"]
        self.specfile.write_scriplets()
        self.assertEqual([], self.WRITES)

    def test_write_files_base(self):
        """
        test write_files base test.
        """
        self.specfile.packages["main"] = ["mainfile1", "/mainfile2", "/mainfile3",
                "/mainfile 4", "mainfile\t5", "%foo /mainfile6", "%bar /mainfile 7"]
        self.specfile.packages["ignore"] = ["ignorepkg"]
        self.specfile.packages["other"] = ["other2", "other1"]
        self.specfile.write_files()
        # Note the special sorting
        expect = ["\n%files\n",
                  "%defattr(-,root,root,-)\n",
                  '%bar "/mainfile 7"\n',
                  "%foo /mainfile6\n",
                  '"/mainfile 4"\n',
                  "/mainfile2\n",
                  "/mainfile3\n",
                  '"mainfile\t5"\n',
                  "mainfile1\n",
                  "\n%files other\n",
                  "%defattr(-,root,root,-)\n",
                  "other1\n",
                  "other2\n"]
        self.assertEqual(expect, self.WRITES)

    def test_write_files_empty(self):
        """
        test write_files with empty package list.
        """
        self.specfile.write_files()
        expect = ["\n%files\n",
                  "%defattr(-,root,root,-)\n"]
        self.assertEqual(expect, self.WRITES)

    def test_write_lang_files_base(self):
        """
        write_lang_files base test
        """
        self.specfile.locales = ["pkg1", "pkg2"]
        self.specfile.write_lang_files()
        expect = ["\n%files locales",
                  " -f pkg1.lang",
                  " -f pkg2.lang",
                  "\n%defattr(-,root,root,-)\n\n"]
        self.assertEqual(expect, self.WRITES)

    def test_write_lang_files_empty(self):
        """
        test write_lang_files with empty lang list
        """
        self.specfile.write_lang_files()
        self.assertEqual([], self.WRITES)

    def test_write_service_restart(self):
        """
        Validate that service_restart configuration is written to the spec file
        correctly.
        """
        self.specfile.config.service_restart = [
                "/usr/lib/systemd/system/foo.service",
                "/usr/lib/systemd/system/bar.service",
        ]
        self.specfile.write_service_restart()
        expect = [
            "## service_restart content",
            "mkdir -p %{buildroot}/usr/share/clr-service-restart",
            "ln -s /usr/lib/systemd/system/foo.service %{buildroot}/usr/share/clr-service-restart/foo.service",
            "ln -s /usr/lib/systemd/system/bar.service %{buildroot}/usr/share/clr-service-restart/bar.service",
            "## service_restart end",
        ]
        self.assertEqual(expect, self.WRITES)

    def test_write_exclude_deletes(self):
        """
        Validate that excludes configuration is written to the spec file correctly.
        """
        self.specfile.excludes = [
                "/usr/bin/bar",
                "/usr/bin/foo",
        ]
        self.specfile.write_exclude_deletes()
        expect = [
            "## Remove excluded files",
            "rm -f %{buildroot}*/usr/bin/bar",
            "rm -f %{buildroot}*/usr/bin/foo",
        ]
        self.assertEqual(expect, self.WRITES)


if __name__ == '__main__':
    unittest.main()
