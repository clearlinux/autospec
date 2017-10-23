import unittest
import unittest.mock
import os

import infile_parser


class TestParseBitBakeFile(unittest.TestCase):
    def test_scrape_version_htop(self):
        """"
        Test that the version is correctly scraped from the file name
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'htop_1.0.3.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "1.0.3"
        self.assertEqual(expect, bb_dict.get('VERSION'))

    def test_scrape_version_vim(self):
        """"
        Test that the version is correctly scraped from the file name
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'vim_8.0.0983.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "8.0.0983"
        self.assertEqual(expect, bb_dict.get('VERSION'))

    def test_scrape_inherits_htop(self):
        """
        Test that the package inherits are correctly scraped as a list with
        only one line/inherit
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'htop_1.0.3.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = ["autotools"]
        self.assertEqual(expect, bb_dict.get('inherits'))

    def test_scrape_inherits_vim(self):
        """
        Test that the package inherits are correctly scraped as a list with
        multiple lines/inherits
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'vim_8.0.0983.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = ["autotools update-alternatives", "autotools-brokensep"]
        self.assertEqual(expect, bb_dict.get('inherits'))

    def test_scrape_summary_htop(self):
        """
        Test that the package summary is correctly scraped
        from the bitbake file.
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'htop_1.0.3.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "htop process monitor"
        self.assertEqual(expect, bb_dict.get('SUMMARY'))

    def test_scrape_section_htop(self):
        """
        Test that the package section is correctly scraped
        from the bitbake file.
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'htop_1.0.3.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "console/utils"
        self.assertEqual(expect, bb_dict.get('SECTION'))

    def test_scrape_license_htop(self):
        """
        Test that the package license is correctly scraped
        from the bitbake file.
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'htop_1.0.3.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "GPLv2"
        self.assertEqual(expect, bb_dict.get('LICENSE'))

    def test_scrape_depends_htop(self):
        """
        Test that the package depends is correctly scraped
        from the bitbake file.
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'htop_1.0.3.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "ncurses"
        self.assertEqual(expect, bb_dict.get('DEPENDS'))

    def test_scrape_rdepends_htop(self):
        """
        Test that the package rsuggests_${PN} is correctly scraped
        from the bitbake file.
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'htop_1.0.3.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "ncurses-terminfo"
        self.assertEqual(expect, bb_dict.get('RDEPENDS_${PN}'))

    def test_scrape_lic_files_chksum_htop_double_eq(self):
        """
        Test that the package license file checksum is correctly scraped
        from the bitbake file. This line contains two equal signs - which
        will test pattern matching identifies the correct one.
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'htop_1.0.3.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "file://COPYING;md5=c312653532e8e669f30e5ec8bdc23be3"
        self.assertEqual(expect, bb_dict.get('LIC_FILES_CHKSUM'))

    def test_scrape_s_variable_vim(self):
        """
        Test that the s variable is correctly scraped from the bitbake file.
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'vim_8.0.0983.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "${WORKDIR}/git/src"
        self.assertEqual(expect, bb_dict.get('S'))

    def test_scrape_vimdir_vim(self):
        """
        Test that the vimdir variable is correctly scraped from the bitbake
        file. This value contains multile 'PV' variables.
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'vim_8.0.0983.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "vim${@d.getVar('PV').split('.')[0]}${@d.getVar('PV').split('.')[1]}"
        self.assertEqual(expect, bb_dict.get('VIMDIR'))

    def test_scrape_packageconfig_gtkgui_vim(self):
        """
        Test that packageconfig[gtkgui] returns the correct value scraped with
        the parser.
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'vim_8.0.0983.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "--enable-gtk2-test --enable-gui=gtk2,--enable-gui=no,gtk+,"
        self.assertEqual(expect, bb_dict.get('PACKAGECONFIG[gtkgui]'))

    def test_scrape_packageconfig_tiny_vim(self):
        """
        Test that packageconfig[tiny] returns the correct value scraped with
        the parser.
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'vim_8.0.0983.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "--with-features=tiny,--with-features=big,,"
        self.assertEqual(expect, bb_dict.get('PACKAGECONFIG[tiny]'))

    def test_scrape_alternative_link_name_vim(self):
        """
        Test that ALTERNATIVE_LINK_NAME[vim] is correctly scraped from the
        bitbake file.
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'vim_8.0.0983.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "${bindir}/vim"
        self.assertEqual(expect, bb_dict.get('ALTERNATIVE_LINK_NAME[vim]'))

    def test_scrape_files_tutor_has_hyphen_vim(self):
        """
        Test that FILES_${PN}-tutor is correctly scraped. It contains a hyphen
        in the variable name.
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'vim_8.0.0983.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "${datadir}/${BPN}/${VIMDIR}/tutor ${bindir}/${BPN}tutor"
        self.assertEqual(expect, bb_dict.get('FILES_${PN}-tutor'))

    def test_scrape_packageconfig_x11_has_digits_vim(self):
        """
        Test that PACKAGECONFIG[x11] is correctly scraped. It contains digits
        in the variable name.
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'vim_8.0.0983.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "--with-x,--without-x,xt,"
        self.assertEqual(expect, bb_dict.get('PACKAGECONFIG[x11]'))

    def test_scrape_src_uri_replace_version_htop(self):
        """
        Test that the occurance of ${PV} is replaced by the scraped version.
        """

        bb_file = os.path.join('tests', 'testfiles', 'bb', 'htop_1.0.3.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "http://hisham.hm/htop/releases/1.0.3/htop-1.0.3.tar.gz"
        self.assertEqual(expect, bb_dict.get('SRC_URI'))

    def test_concatenation_op_packageconfig_vim(self):
        """
        Test that the resulting value for the PACKAGECONFIG variable, is
        the += of the initialization with ??= "".
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'vim_8.0.0983.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "${@bb.utils.filter('DISTRO_FEATURES', 'acl selinux', d)}"
        self.assertEqual(expect, bb_dict.get('PACKAGECONFIG'))

    def test_operations_one(self):
        """
        Test that the operations result in the correct assignments in the
        bb_dict
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'op_tests.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "second value"
        self.assertEqual(expect, bb_dict.get('ONE'))

    def test_operations_two(self):
        """
        Test that the operations result in the correct assignments in the
        bb_dict
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'op_tests.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "first value"
        self.assertEqual(expect, bb_dict.get('TWO'))

    def test_operations_three(self):
        """
        Test that the operations result in the correct assignments in the
        bb_dict
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'op_tests.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "third value"
        self.assertEqual(expect, bb_dict.get('THREE'))

    def test_operations_four(self):
        """
        Test that the operations result in the correct assignments in the
        bb_dict
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'op_tests.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "third value first value second value"
        self.assertEqual(expect, bb_dict.get('FOUR'))

    def test_operations_five(self):
        """
        Test that the operations result in the correct assignments in the
        bb_dict
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'op_tests.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "third valuefirst valuesecond value"
        self.assertEqual(expect, bb_dict.get('FIVE'))

    def test_line_continuation_src_uri_vim(self):
        """
        Test that when there is a line continuation, the entire line is
        appended to a single string value.
        """

        bb_file = os.path.join('tests', 'testfiles', 'bb', 'vim_8.0.0983.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = 'git://github.com/vim/vim.git \\\
           file://disable_acl_header_check.patch;patchdir=.. \\\
           file://vim-add-knob-whether-elf.h-are-checked.patch;patchdir=.. \\'
        self.assertEqual(expect, bb_dict.get('SRC_URI'))

    def test_line_continuation_extra_oeconf_vim(self):
        """
        Test that when there is a line continuation, the entire line is
        appended to a single string value.
        """

        bb_file = os.path.join('tests', 'testfiles', 'bb', 'vim_8.0.0983.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = ' \\\
    --disable-gpm \\\
    --disable-gtktest \\\
    --disable-xim \\\
    --disable-netbeans \\\
    --with-tlib=ncurses \\\
    ac_cv_small_wchar_t=no \\\
    vim_cv_getcwd_broken=no \\\
    vim_cv_memmove_handles_overlap=yes \\\
    vim_cv_stat_ignores_slash=no \\\
    vim_cv_terminfo=yes \\\
    vim_cv_tgent=non-zero \\\
    vim_cv_toupper_broken=no \\\
    vim_cv_tty_group=world \\\
    STRIP=/bin/true \\'
        self.assertEqual(expect, bb_dict.get('EXTRA_OECONF'))

    def test_command_scraping_do_configure_vim(self):
        """
        Test that when a line starts with do_ it is scraped as a command and
        stored as a string.
        """
        bb_file = os.path.join('tests', 'testfiles', 'bb', 'vim_8.0.0983.bb')
        bb_dict = infile_parser.bb_scraper(bb_file)
        expect = "do_configure () {\
    rm -f auto/*\
    touch auto/config.mk\
    aclocal\
    autoconf\
    oe_runconf\
    touch auto/configure\
    touch auto/config.mk auto/config.h}"
        self.assertEqual(expect, bb_dict.get('do_configure'))


if __name__ == '__main__':
    unittest.main(buffer=True)
