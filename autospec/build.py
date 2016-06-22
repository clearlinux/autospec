#!/bin/true
#
# build.py - part of autospec
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
# Actually build the package
#

import buildreq
import files
import getpass
import re
import tarball

import util
import filecmp

success = 0
round = 0
must_restart = 0
failed_commands = dict()
base_path = "/tmp/" + getpass.getuser() + "/"
output_path = base_path + "output"
download_path = output_path
mock_cmd = '/usr/bin/mock'


def setup_patterns():
    global failed_commands
    failed_commands["doxygen"] = "doxygen"
    failed_commands["scrollkeeper-config"] = "rarian"
    failed_commands["dot"] = "graphviz"
    failed_commands["nroff"] = "groff"
    failed_commands["flex"] = "flex"
    failed_commands["Berkeley DB"] = "db"
    failed_commands["libdb"] = "db"
    failed_commands["lex"] = "flex"
    failed_commands["rake"] = "rubygem-rake"
    failed_commands["py.test"] = "pytest"
    failed_commands["freetype-config"] = "freetype-dev"
    failed_commands["Freetype"] = "freetype-dev"
    failed_commands["makeinfo"] = "texinfo"
    failed_commands["install-info"] = "texinfo"
    failed_commands["desktop-file-install"] = "desktop-file-utils"
    failed_commands["deflateBound in -lz"] = "zlib-dev"
    failed_commands["zlib"] = "zlib-dev"
    failed_commands["-lgnutls-openssl"] = "gnutls-dev"
    failed_commands["gnutls/openssl.h"] = "gnutls-dev"
    failed_commands["zlib.h"] = "pkgconfig(zlib)"
    failed_commands["inflate in -lz"] = "zlib-dev"
    failed_commands["udev_new in -ludev"] = "systemd-dev"
    failed_commands["libudev.h"] = "systemd-dev"
    failed_commands["jpeglib.h"] = "libjpeg-turbo-dev"
    failed_commands["JPEG"] = "libjpeg-turbo-dev"
    failed_commands["expat.h"] = "expat-dev"
    failed_commands["Expat"] = "expat-dev"
    failed_commands["bison"] = "bison"
    failed_commands["numa.h"] = "numactl-dev"
    failed_commands["cmdtest"] = "cmdtest"
    failed_commands["runtest"] = "dejagnu"
    failed_commands["msgfmt"] = "gettext"
    failed_commands["gmsgfmt"] = "gettext"
    failed_commands["msgmerge"] = "gettext"
    failed_commands["xgettext"] = "gettext"
    failed_commands["xkbcomp"] = "xkbcomp-bin"
    failed_commands["CHECK"] = "check"
    failed_commands["curl-config"] = "curl-dev"
    failed_commands["curl"] = "curl-dev"
    failed_commands["gnome-session"] = "gnome-session"
    failed_commands["mkfontdir"] = "mkfontdir-bin"
    failed_commands["mkfontscale"] = "mkfontscale-bin"
    failed_commands["doxygen"] = "doxygen"
    failed_commands["krb5/krb.h"] = "krb5-dev"
    failed_commands["krb/krb5.h"] = "krb5-dev"
    failed_commands["krb5-config"] = "krb5-dev"
    failed_commands["X"] = "pkgconfig(x11)"
    failed_commands["valgrind"] = "valgrind"
    failed_commands["nasm"] = "nasm-bin"
    failed_commands["clang"] = "llvm-dev"
    failed_commands["XML::Parser"] = "perl(XML::Parser)"
    failed_commands["XML::Simple"] = "perl(XML::Simple)"
    failed_commands["ExtUtils::Depends"] = "perl(ExtUtils::Depends)"
    failed_commands["ExtUtils::PkgConfig"] = "perl(ExtUtils::PkgConfig)"
    failed_commands["LIBRSVG"] = "librsvg-dev"
    failed_commands["openssl/opensslconf.h"] = "openssl-dev"
    failed_commands["openssl/evp.h"] = "openssl-dev"
    failed_commands["openssl"] = "openssl-dev"
    failed_commands["openssl/hmac.h"] = "openssl-dev"
    failed_commands["libgnutls"] = "gnutls-dev"
    failed_commands["attr/libattr.h"] = "attr-dev"
    failed_commands["acl/libacl.h"] = "acl-dev"
    failed_commands["openssl/ssl.h"] = "openssl-dev"
    failed_commands["Ogg"] = "libogg-dev"
    failed_commands["X"] = "pkgconfig(x11)"
    failed_commands["X11/Intrinsic.h"] = "pkgconfig(xt)"
    failed_commands["X11/Xmu/Atoms.h"] = "pkgconfig(xmu)"
#    failed_commands["tiffio.h"] = "tiff-dev"
#    failed_commands["TIFF"] = "tiff-dev"
#    failed_commands["tiff.h"] = "tiff-dev"
    failed_commands["readline/history.h"] = "readline-dev"
    failed_commands["readline.h"] = "readline-dev"
    failed_commands["readline in -lreadline"] = "readline-dev"
    failed_commands["readline"] = "readline-dev"
    failed_commands["libgcrypt-config"] = "libgcrypt-dev"
    failed_commands["gpg-error.h"] = "libgpg-error-dev"
    failed_commands["Xapian"] = "xapian-core-dev"
    failed_commands["raptor"] = "raptor2-dev"
    failed_commands["rasqal"] = "rasqal-dev"
    failed_commands["DBUS"] = "dbus-dev"
    failed_commands["less"] = "less"
    failed_commands["pam_authenticate"] = "Linux-PAM-dev"
    failed_commands["vim"] = "vim"
    failed_commands["valac"] = "vala-dev"
    failed_commands["vapigen"] = "vala-dev"
    failed_commands["CLUTTER"] = "clutter-dev"
    failed_commands["asciidoc"] = "asciidoc"
    failed_commands["webp/decode.h"] = "libwebp-dev"
    failed_commands["inkscape"] = "inkscape"
    failed_commands["desktop-file-validate"] = "desktop-file-utils"
    failed_commands["openssl/opensslv.h"] = "openssl-dev"
    failed_commands["/usr/lib64/libsoprano.so"] = "soprano-dev"
    failed_commands["PulseAudio"] = "pulseaudio-dev"
    failed_commands["FindKDEGames"] = "libkdegames-dev"
    failed_commands["FindStrigi"] = "strigi-dev"
    failed_commands["akonadi/private/imapparser_p.h"] = "akonadi-dev"
    failed_commands["LIBLZMA"] = "xz-dev"
    failed_commands["LibAttica"] = "attica-dev"
    failed_commands["FindAnalitza"] = "analitza-dev"
    failed_commands["R"] = "R"
    failed_commands["gfortran"] = "gfortran"
    failed_commands["EXIV2"] = "exiv2-dev"
    failed_commands["Exiv2"] = "exiv2-dev"
    failed_commands["KDE4Workspace"] = "kde-workspace-dev"
    failed_commands["LIBKONQ"] = "kde-baseapps-dev"
    failed_commands["Jasper"] = "jasper-dev"
    failed_commands["JASPER"] = "jasper-dev"
    failed_commands["dot"] = "graphviz"
    failed_commands["qjson/parser.h"] = "qjson-dev"
    failed_commands["Sasl2"] = "cyrus-sasl-dev"
    failed_commands["FindAkonadi"] = "akonadi-dev"
    failed_commands["LIBICAL"] = "libical-dev"
    failed_commands["Nepomuk"] = "nepomuk-core-dev"
    failed_commands["FindNepomukCore"] = "nepomuk-core-dev"
    failed_commands["FindNepomukWidgets"] = "nepomuk-widgets-dev"
    failed_commands["Analitza"] = "analitza-dev"
    failed_commands["DBusMenuQt"] = "libdbusmenu-qt-dev"
    failed_commands["FindKActivities"] = "kactivities-dev"
    failed_commands["Soprano"] = "soprano-dev"
    failed_commands["PopplerQt4"] = "poppler-dev"
    failed_commands[
        "SharedDesktopOntologies"] = "shared-desktop-ontologies-dev"
    failed_commands["KDE4"] = "kdelibs-dev"
    failed_commands["kde4-config"] = "kdelibs-dev"
    failed_commands["KdepimLibs"] = "kdepimlibs-dev"
    failed_commands["efi.h"] = "gnu-efi"
    failed_commands["CAIRO"] = "cairo-dev"
    failed_commands["Qt4"] = "qt-everywhere-opensource-src-dev"
    failed_commands["FindQt4"] = "qt-everywhere-opensource-src-dev"
    failed_commands["Phonon"] = "phonon-dev"
    failed_commands["xdg-user-dirs-update"] = "xdg-user-dirs"
    failed_commands["gtk-builder-convert"] = "compat-gtk2-dev"
    failed_commands["DGA"] = "libXxf86dga-dev"
    failed_commands["DMXMODULES"] = "libdmx-dev"
    failed_commands["ImathInt64.h"] = "pkgconfig(IlmBase)"
    failed_commands["jade"] = "openjade-dev"
    failed_commands["JSON"] = "json-dev"
    failed_commands["ltdl.h"] = "libtool-dev"
    failed_commands["DRI2PROTO"] = "pkgconfig(dri2proto)"
    failed_commands["killall"] = "psmisc"
    failed_commands["pkill"] = "psmisc"
    failed_commands["cairo/cairo-xcb.h"] = "cairo-dev"
    failed_commands["XCB"] = "libxcb-dev"
    failed_commands["XCB_IMAGE"] = "xcb-util-image-dev"
    failed_commands["XCB_RENDERUTIL"] = "xcb-util-renderutil-dev"
    failed_commands["pango/pangocairo.h"] = "pkgconfig(pangocairo)"
    failed_commands["LIBUSB1"] = "libusb-dev"
    failed_commands["libusb-1.0/libusb.h"] = "libusb-dev"
    failed_commands["X11/extensions/saver.h"] = "pkgconfig(scrnsaverproto)"
    failed_commands["apr_general.h"] = "apr-dev"
    failed_commands["apr_md5.h"] = "apr-util-dev"
    failed_commands["pkg.m4"] = "pkg-config-dev"
    failed_commands["mate-common.m4"] = "mate-common-dev"
    failed_commands["intltool.m4"] = "intltool-dev"
    failed_commands["glib-gettext.m4"] = "glib-dev"
    failed_commands["GLIB2"] = "glib-dev"
    failed_commands["-lname-matecorba-server-2"] = "mate-corba-dev"
    failed_commands["-lelf"] = "elfutils-dev"
    failed_commands["mate-compiler-flags.m4"] = "mate-common-dev"
    failed_commands["xmlcatalog"] = "libxml2-dev"
    failed_commands["getopt"] = "util-linux"
    failed_commands["ps"] = "procps-ng"
    failed_commands["Xinerama"] = "libXinerama-dev"
    failed_commands["XineramaQueryExtension"] = "libXinerama-dev"
    failed_commands["matedialog"] = "mate-dialogs"
    failed_commands["-lXinerama"] = "libXinerama-dev"
    failed_commands["-lXv"] = "libXv-dev"
    failed_commands["XvQueryExtension in -lXv"] = "libXv-dev"
    failed_commands["IceConnectionNumber"] = "pkgconfig(ice)"
    failed_commands["/etc/xml/catalog"] = "docbook-xml"
    failed_commands["/usr/share/sgml/docbook/xsl-stylesheets"] = "docbook-xml"
    failed_commands["mate-autogen"] = "mate-common-dev"
    failed_commands["itstool"] = "itstool"
    failed_commands["X11/extensions/XKBrules.h"] = "libxkbfile-dev"
    failed_commands["X11/extensions/XResproto.h"] = "pkgconfig(resourceproto)"
    failed_commands["X11/extensions/scrnsaver.h"] = "libXScrnSaver-dev"
    failed_commands[
        "XF86MiscSetGrabKeysState in -lXxf86misc"] = "libXxf86misc-dev"
    failed_commands["gtk-update-icon-cache"] = "pkgconfig(gtk+-3.0)"
    failed_commands["gtk-config"] = "pkgconfig(gtk+-2.0)"
    failed_commands["gphoto2-config"] = "libgphoto2-dev"
    failed_commands["update-mime-database"] = "shared-mime-info"
    failed_commands["SharedMimeInfo"] = "shared-mime-info"
    failed_commands["crack.h"] = "cracklib-dev"
    failed_commands["XML"] = "libxml2-dev"
    failed_commands["LibXml2"] = "libxml2-dev"
    failed_commands["EDS"] = "evolution-data-server-dev"
    failed_commands["icu-config"] = "icu4c-dev"
    failed_commands["ICU"] = "icu4c-dev"
    failed_commands["ruby"] = "ruby"
    failed_commands["XGetEventData"] = "inputproto"
    failed_commands["X11/extensions/XInput.h"] = "libXi-dev"
    failed_commands["libgtop"] = "libgtop-dev"
    failed_commands["libcanberra-gtk"] = "libcanberra-dev"
    failed_commands["update-desktop-database"] = "desktop-file-utils"
    failed_commands["Startup notification library"] = "libnotify-dev"
    failed_commands["Xcursor"] = "pkgconfig(xcursor)"
    failed_commands["-lXrandr"] = "pkgconfig(xrandr)"
    failed_commands["xrandr"] = "pkgconfig(xrandr)"
    failed_commands["mateconf-sanity-check-2"] = "mate-conf-dev"
    failed_commands["DEPENDENT_WITH_GTK"] = "compat-gtk2-dev"
    failed_commands["zenity"] = "zenity"
    failed_commands["gobject-introspection"] = "gobject-introspection-dev"
    failed_commands["XCOMPOSITE extension"] = "libXcomposite-dev"
    failed_commands["xauth"] = "xauth"
    failed_commands["gconftool-2"] = "GConf-dev"
    failed_commands["-lXss"] = "libXScrnSaver-dev"
    failed_commands["-lSM"] = "pkgconfig(sm)"
    failed_commands["X11/Xmu/Error.h"] = "libXmu-dev"
    failed_commands["X11/extensions/Xinerama.h"] = "libXinerama-dev"
    failed_commands["PAM"] = "Linux-PAM-dev"
    failed_commands["gtk+-2.0"] = "gtk+-dev"
    failed_commands["bc"] = "bc"
    failed_commands["GL/glx.h"] = "pkgconfig(gl)"
    failed_commands["lzma.h"] = "xz-dev"
    failed_commands["lzma"] = "xz-dev"
    failed_commands["liblzma"] = "xz-dev"
    failed_commands["boost/unordered_map.hpp"] = "boost-dev"
    failed_commands["Boost"] = "boost-dev"
    failed_commands["Eigen/Core"] = "eigen-dev"
    failed_commands["GL/glu.h"] = "glu-dev"
    failed_commands["opencsg.h"] = "OpenCSG-dev"
    failed_commands["GL/glut.h"] = "freeglut-dev"
    failed_commands["enlightenment_start"] = "pkgconfig(enlightenment)"
    failed_commands["-lcap-ng"] = "libcap-ng-dev"
    failed_commands["ALSA"] = "alsa-lib-dev"
    failed_commands["alsa/asoundlib.h"] = "alsa-lib-dev"
    failed_commands["autoconf"] = "autoconf"
    failed_commands["automake-1.12"] = "automake"
    failed_commands["automake-1.14"] = "automake"
    failed_commands["autoreconf"] = "autoconf"
    failed_commands["GSTREAMER"] = "gstreamer-dev"
    failed_commands["USB"] = "libusb-dev"
    failed_commands["SNDFILE"] = "libsndfile-dev"
    failed_commands["sys/capability.h"] = "libcap-dev"
    failed_commands["cap_rights_init"] = "libcap-ng-dev"
    failed_commands["readline/readline.h"] = "readline-dev"
    failed_commands["xorg-launch-helper"] = "xorg-launch-helper"
    failed_commands["blkid/blkid.h"] = "util-linux-dev"
    failed_commands["-lblkid"] = "util-linux-dev"
    failed_commands["-ltirpc"] = "libtirpc-dev"
    failed_commands["-lreadline"] = "readline-dev"
    failed_commands["-lnfsidmap"] = "libnfsidmap-dev"
    failed_commands["pycurl"] = "pycurl"
    failed_commands["gpgme.h"] = "gpgme-dev"
    failed_commands["gcrypt.h"] = "libgcrypt-dev"
    failed_commands["ffi_call"] = "libffi-dev"
    failed_commands["boost/concept_check.hpp"] = "boost-dev"
    failed_commands["gc/gc.h"] = "gc-dev"
    failed_commands["D-Bus .pc file"] = "dbus-dev"
    failed_commands["magic.h"] = "file-dev"
    failed_commands["libproxy-1.0 pkg-config data"] = "libproxy-dev"
    failed_commands["-lproxy"] = "libproxy-dev"
    failed_commands["neon-config"] = "neon-dev"
    failed_commands["-lbz2"] = "bzip2-dev"
    failed_commands["-lbz2"] = "bzip2-dev"
    failed_commands["asn1Parser"] = "libtasn1-dev"
    failed_commands["gcj"] = "gcj"
    failed_commands["pam/pam_modules.h"] = "Linux-PAM-dev"
    failed_commands["-lXmu"] = "pkgconfig(xmu)"
    failed_commands["convert"] = "ImageMagick"
    failed_commands["-lIlmThread"] = "ilmbase-dev"
    failed_commands["emacs"] = "emacs"
    failed_commands["-lSM"] = "pkgconfig(sm)"
    failed_commands["GTK"] = "gtk+-dev"
    failed_commands["IDN"] = "libidn-dev"
    failed_commands["GIF"] = "giflib-dev"
    failed_commands["sqlite3.h"] = "sqlite-autoconf-dev"
    failed_commands["Sqlite"] = "sqlite-autoconf-dev"
    failed_commands["sqlite3"] = "sqlite-autoconf-dev"
    failed_commands["sqlite.h"] = "sqlite-autoconf-dev"
    failed_commands["zip"] = "zip"
    failed_commands["unzip"] = "unzip"
    failed_commands["cups/cups.h"] = "cups-dev"
    failed_commands["cups-config"] = "cups-dev"
    failed_commands["-lcrack"] = "cracklib-dev"
    failed_commands["-lc"] = "glibc-staticdev"
    failed_commands["uuid/uuid.h"] = "util-linux-dev"
    failed_commands["uuid_generate"] = "util-linux-dev"
    failed_commands["-luuid"] = "util-linux-dev"
    failed_commands["dbus"] = "dbus-dev"
    failed_commands["ltdl.h"] = "libtool-dev"
    failed_commands["fontconfig"] = "pkgconfig(fontconfig)"
    failed_commands["Fontconfig"] = "pkgconfig(fontconfig)"
    failed_commands["FcInit in -lfontconfig"] = "pkgconfig(fontconfig)"
    failed_commands["more"] = "util-linux"
    failed_commands["OpenGL library"] = "mesa-dev"
    failed_commands["OpenGL"] = "mesa-dev"
    failed_commands["QImageBlitz"] = "qimageblitz-dev"
    failed_commands["GLUT library"] = "freeglut-dev"
    failed_commands["gs"] = "ghostscript"
    failed_commands["-lgs"] = "ghostscript"
    failed_commands["xcursorgen"] = "xcursorgen"
    failed_commands["bzlib.h"] = "bzip2-dev"
    failed_commands["diff"] = "diffutils"
    failed_commands["cmp"] = "diffutils"
    failed_commands["X11/Xtrans/Xtrans.h"] = "xtrans-dev"
    failed_commands["patch"] = "patch"
    failed_commands["GMP"] = "gmp-dev"
    failed_commands["FindGMP"] = "gmp-dev"
    failed_commands["MPFR"] = "mpfr-dev"
    failed_commands["cmake"] = "cmake"
    failed_commands["exo-1"] = "pkgconfig(exo-1)"
    failed_commands["python2.5"] = "python"
    failed_commands["-lpython2.7"] = "python-dev"
    failed_commands["python-config"] = "python-dev"
    failed_commands["python"] = "python-dev"
    failed_commands["ZLIB"] = "zlib-dev"
    failed_commands["BZip2"] = "bzip2-dev"
    failed_commands["BZ2_bzCompress"] = "bzip2-dev"
    failed_commands["gsapi_new_instance"] = "ghostscript"
    failed_commands["FreeType 2"] = "freetype-dev"
    failed_commands["GNU MP"] = "gmp-dev"
    failed_commands["OpenSSL"] = "openssl-dev"
    failed_commands["cURL"] = "curl-dev"
    failed_commands["DGA"] = "pkgconfig(xf86dgaproto)"
    failed_commands["APR"] = "apr-dev"
    failed_commands["APR-util"] = "apr-util-dev"
    failed_commands["pcre-config"] = "pcre-dev"
    failed_commands["nspr.h"] = "nspr-dev"
    failed_commands["wpa_supplicant"] = "wpa_supplicant"
    failed_commands["pcap-config"] = "libpcap-dev"
    failed_commands["Tcl configuration"] = "tcl"
    failed_commands["tclsh"] = "tcl"
    failed_commands["tgetent"] = "ncurses-dev"
    failed_commands["tinfo"] = "ncurses-dev"
    failed_commands["term.h"] = "ncurses-dev"
    failed_commands["python2.7/Python.h"] = "python-dev"
    failed_commands["PythonLibsUnix"] = "python-dev"
    failed_commands["llvm-config"] = "llvm-dev"
    failed_commands["Python.h"] = "python-dev"
    failed_commands["SDL"] = "pkgconfig(sdl)"
    failed_commands["CURL"] = "curl-dev"
    failed_commands["GLIB"] = "glib-dev"
    failed_commands["makedepend"] = "makedepend"
    failed_commands["OpenGL X11"] = "mesa-dev"
    failed_commands["intltool-update"] = "intltool"
    failed_commands["intltool-merge"] = "intltool"
    failed_commands["scrollkeeper-preinstall"] = "rarian"
    failed_commands["librsvg-2.0"] = "librsvg-dev"
    failed_commands["SVG"] = "librsvg-dev"
    failed_commands["EET"] = "eet-dev"
    failed_commands["gawk"] = "gawk"
    failed_commands["xbkcomp"] = "xkbcomp"
    failed_commands["Vorbis"] = "libvorbis-dev"
    failed_commands["Expat 1.95.x"] = "expat-dev"
    failed_commands["libexpat"] = "expat-dev"
    failed_commands["pcap.h"] = "libpcap-dev"
    failed_commands["nl_handle_alloc"] = "libnl-dev"
    failed_commands["svn_client.h"] = "subversion-dev"
    failed_commands["bluetooth/bluetooth.h"] = "bluez-dev"
    failed_commands["xml2-config path"] = "libxml2-dev"
    failed_commands["xmllint"] = "libxml2-dev"
    failed_commands["xml2-config"] = "libxml2-dev"
    failed_commands["gmp.h"] = "gmp-dev"
    failed_commands["gc/gc.h"] = "gc-dev"
    failed_commands["Eet.h"] = "eet-dev"
    failed_commands["MPFR"] = "mpfr-dev"
    failed_commands["-lncurses"] = "ncurses-dev"
    failed_commands["ncurses.h"] = "ncurses-dev"
    failed_commands["gperf"] = "gperf"
    failed_commands["groff"] = "groff"
    failed_commands["yacc"] = "bison"
    failed_commands["db.h"] = "db-dev"
    failed_commands["Berkeley DB4"] = "db"
    failed_commands["gdbm.h"] = "gdbm-dev"
    failed_commands["GDBM"] = "gdbm-dev"
    failed_commands["GD"] = "gd-dev"
    failed_commands["ENCHANT"] = "enchant-dev"
    failed_commands["libelf.h"] = "elfutils-dev"
    failed_commands["libgpg-error"] = "libgpg-error-dev"
    failed_commands["gpg-error-config"] = "libgpg-error-dev"
    failed_commands["libgcrypt"] = "libgcrypt-dev"
    failed_commands["pth-config"] = "pth-dev"
    failed_commands["libassuan-config"] = "libassuan-dev"
    failed_commands["libassuan"] = "libassuan-dev"
    failed_commands["ksba-config"] = "libksba-dev"
    failed_commands["libksba"] = "libksba-dev"
    failed_commands["which"] = "which"
    failed_commands["libnettle"] = "nettle-dev nettle-lib"
    failed_commands["nettle/md5.h"] = "nettle-dev nettle-lib"
    failed_commands["cap_init"] = "libcap-dev"
    failed_commands["lzo/lzoconf.h"] = "lzo-dev"
    failed_commands["security/pam_appl.h"] = "Linux-PAM-dev"
    failed_commands["popt.h"] = "popt-dev"
    failed_commands["-lpopt"] = "popt-dev"
    failed_commands["poptStrippedArgv"] = "popt-dev"
    failed_commands["sysfs/libsysfs.h"] = "sysfsutils-dev"
    failed_commands["curl.h"] = "curl-dev"
    failed_commands["libxml2 library"] = "libxml2-dev"
    failed_commands["sys/acl.h"] = "acl-dev"
    failed_commands["attr/xattr.h"] = "attr-dev"
    failed_commands["-lattr"] = "attr-dev"
    failed_commands["DBUS_GLIB"] = "glib-dev"
    failed_commands["xsltproc"] = "libxslt-bin"
    failed_commands["xslt-config"] = "libxslt-dev"
    failed_commands["X11/Xaw/SimpleMenu.h"] = "libXaw-dev"
    failed_commands["X11/Xcursor/Xcursor.h"] = "libXcursor-dev"
    failed_commands["X11/extensions/Xcomposite.h"] = "libXcomposite-dev"
    failed_commands["X11/extensions/Xdamage.h"] = "libXdamage-dev"
    failed_commands["X11/extensions/Xfixes.h"] = "libXfixes-dev"
    failed_commands["X11/extensions/Xrandr.h"] = "libXrandr-dev"
    failed_commands["X11/extensions/Xrender.h"] = "libXrender-dev"
    failed_commands["GL/gl.h"] = "mesa-dev"
    failed_commands["PNG"] = "pkgconfig(libpng)"
    failed_commands["png_read_info in -lpng"] = "pkgconfig(libpng)"
    failed_commands["libpng-config"] = "pkgconfig(libpng)"
    failed_commands["lua"] = "lua"
    failed_commands["pcre.h"] = "pcre-dev"
    failed_commands["-lSM"] = "pkgconfig(sm)"
    failed_commands["X11/xpm.h"] = "pkgconfig(xpm)"
    failed_commands["XpmReadFileToXpmImage in -lXpm"] = "pkgconfig(xpm)"
    failed_commands["gif_lib.h"] = "giflib-dev"
    failed_commands["pixman"] = "pkgconfig(pixman-1)"
    failed_commands["libpng"] = "pkgconfig(libpng)"
    failed_commands["XOpenDisplay"] = "pkgconfig(xext)"
    failed_commands["iceauth"] = "iceauth-bin"
    failed_commands["perl module URI::URL"] = "URI"
    failed_commands["X11/SM/SMlib.h"] = "pkgconfig(sm)"
    failed_commands["-lXfixes"] = "pkgconfig(xfixes)"
    failed_commands["-lz"] = "zlib-dev"
    failed_commands["-lncursesw"] = "ncurses-dev"
    failed_commands["-lncurses"] = "ncurses-dev"
#    failed_commands["-ltiff"] = "tiff-dev"
    failed_commands["-lasound"] = "alsa-lib-dev"
    failed_commands["-lgmp"] = "gmp-dev"
    failed_commands["Curses"] = "ncurses-dev"
    failed_commands["-lexpat"] = "expat-dev"
    failed_commands["-lpam"] = "Linux-PAM-dev"
    failed_commands["DBI"] = "perl(Bundle::DBI)"
    failed_commands["-lcurl"] = "curl-dev"
    failed_commands["-lXau"] = "libXau-dev"
    failed_commands["-lX11"] = "pkgconfig(x11)"
    failed_commands["X11"] = "pkgconfig(x11)"
    failed_commands["automoc4"] = "automoc4"
    failed_commands["-lXt"] = "pkgconfig(xt)"
    failed_commands["-lICE"] = "pkgconfig(ice)"
    failed_commands["-lXext"] = "pkgconfig(xext)"
    failed_commands["libXext"] = "pkgconfig(xext)"
    failed_commands["libz"] = "zlib-dev"
    failed_commands["-lXtst"] = "pkgconfig(xtst)"
    failed_commands["-lGL"] = "pkgconfig(gl)"
    failed_commands["-lGLU"] = "pkgconfig(glu)"
    failed_commands["-lXi"] = "pkgconfig(xi)"
    failed_commands["-lXmu"] = "pkgconfig(xmu)"
    failed_commands["-lXaw"] = "pkgconfig(xaw)"
    failed_commands["X11/extensions/randr.h"] = "pkgconfig(xrandr)"
    failed_commands["X11/Xlib.h"] = "pkgconfig(x11)"
    failed_commands["X11/extensions/XShm.h"] = "pkgconfig(xext)"
    failed_commands["X11/extensions/shape.h"] = "pkgconfig(xext)"
    failed_commands["ncurses.h"] = "pkgconfig(ncursesw)"
    failed_commands["curses.h"] = "pkgconfig(ncurses)"
    failed_commands["pci/pci.h"] = "pkgconfig(libpci)"
    failed_commands["xf86.h"] = "pkgconfig(xorg-server)"
    failed_commands["uuid/uuid.h"] = "pkgconfig(uuid)"
    failed_commands[
        "X11/extensions/composite.h"] = "pkgconfig(compositeproto)"
    failed_commands["X11/extensions/XIproto.h"] = "pkgconfig(xi)"
    failed_commands["xmlto"] = "xmlto"
    failed_commands["ffi.h"] = "libffi-dev"
    failed_commands["setuptools"] = "setuptools"
    failed_commands["testtools"] = "testtools"
    failed_commands["unittest2"] = "unittest2"
    failed_commands["find_packages"] = "setuptools"
    failed_commands["pkg_resources"] = "setuptools"
    failed_commands["setup"] = "setuptools"
    failed_commands["ez_setup"] = "setuptools"
    failed_commands["cffi"] = "cffi"
    failed_commands["pbr"] = "pbr"
    failed_commands["pip"] = "pip"
    failed_commands["six"] = "six"
    failed_commands["extras"] = "extras"
    failed_commands["testscenarios"] = "testscenarios"
    failed_commands["mimeparse"] = "python-mimeparse"
    failed_commands["libudev.h"] = "systemd-dev"
    failed_commands["pycparser"] = "pycparser"
    failed_commands["swig"] = "swig"
    failed_commands["SLANG"] = "slang-dev"
    failed_commands["libiberty.h"] = "binutils-dev"
    failed_commands["Judy"] = "Judy-dev"
    failed_commands["systemctl"] = "systemd"
    failed_commands["mysql_config"] = "mariadb-dev"
    failed_commands["-lssl"] = "openssl-dev"
    failed_commands["apxs"] = "httpd-dev"
    failed_commands["apr-1-config"] = "apr-dev"
    failed_commands["apu-1-config"] = "apr-util-dev"
    failed_commands["erl"] = "otp"
    failed_commands["nc"] = "netcat"
    failed_commands["wx-config"] = "wxGTK-dev"
    failed_commands["gem"] = "ruby"
    failed_commands["go"] = "go"


def simple_pattern_pkgconfig(line, pattern, pkgconfig):
    global must_restart
    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        must_restart = must_restart + \
            buildreq.add_pkgconfig_buildreq(pkgconfig)


def simple_pattern(line, pattern, req):
    global must_restart
    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        must_restart = must_restart + buildreq.add_buildreq(req)


def failed_pattern(line, pattern, verbose=0):
    global must_restart
    global failed_commands

    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        s = match.group(1)
        try:
            req = failed_commands[s]
            if req:
                must_restart = must_restart + buildreq.add_buildreq(req)
        except:
            if verbose > 0:
                print("Unknown pattern match: ", pattern, s)


def failed_pattern_pkgconfig(line, pattern, verbose=0):
    global must_restart
    global failed_commands

    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        s = match.group(1)
        must_restart = must_restart + buildreq.add_pkgconfig_buildreq(s)


def failed_pattern_R(line, pattern, verbose=0):
    global must_restart
    global failed_commands

    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        s = match.group(1)
        try:
            if buildreq.add_buildreq("R-" + s) > 0:
                must_restart = must_restart + 1
                files.push_main_requires("R-" + s)
        except:
            if verbose > 0:
                print("Unknown pattern match: ", pattern, s)


def failed_pattern_perl(line, pattern, verbose=0):
    global must_restart
    global failed_commands

    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        s = match.group(1)
        try:
            must_restart = must_restart + buildreq.add_buildreq('perl(%s)' % s)
        except:
            if verbose > 0:
                print("Unknown pattern match: ", pattern, s)


def failed_pattern_pypi(line, pattern, verbose=0):
    global must_restart
    global failed_commands

    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        s = util.translate(match.group(1))
        if s == "":
            return
        try:
            must_restart = must_restart + buildreq.add_buildreq(util.translate('%s-python' % s))
        except:
            if verbose > 0:
                print("Unknown python pattern match: ", pattern, s, line)


def failed_pattern_go(line, pattern, verbose=0):
    global must_restart
    global failed_commands

    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        s = util.translate(match.group(1))
        if s == "":
            return
        elif s == match.group(1):
            # the requirement it's also golang libpath format
            # (e.g: github.com/<project>/<repo> so transform into pkg name
            s = util.golang_name(s)
        try:
            must_restart = must_restart + buildreq.add_buildreq(s)
        except:
            if verbose > 0:
                print("Unknown golang pattern match: ", pattern, s, line)


def failed_pattern_ruby(line, pattern, verbose=0):
    global must_restart
    global failed_commands

    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        s = match.group(1)
        try:
            if s in buildreq.gems:
                must_restart = must_restart + buildreq.add_buildreq(buildreq.gems[s])
            else:
                must_restart = must_restart + buildreq.add_buildreq('rubygem-%s' % s)
        except:
            if verbose > 0:
                print("Unknown pattern match: ", pattern, s)


def failed_pattern_ruby_table(line, pattern, verbose=0):
    global must_restart
    global failed_commands

    pat = re.compile(pattern)
    match = pat.search(line)
    if match:
        s = match.group(1)
        try:
            if s in buildreq.gems:
                must_restart = must_restart + buildreq.add_buildreq(buildreq.gems[s])
            else:
                print("Unknown ruby gem match", s)
        except:
            if verbose > 0:
                print("Unknown pattern match: ", pattern, s)


def parse_build_results(filename, returncode):
    global must_restart
    global success
    buildreq.verbose = 1
    must_restart = 0
    infiles = 0

    # Flush the build-log to disk, before reading it
    util.call("sync")
    file = open(filename, "r", encoding="latin-1")
    for line in file.readlines():
        simple_pattern_pkgconfig(line, r"which: no qmake", "Qt")
        simple_pattern_pkgconfig(line, r"XInput2 extension not found", "xi")
        simple_pattern_pkgconfig(line, r"checking for UDEV\.\.\. no", "udev")
        simple_pattern_pkgconfig(
            line, r"checking for UDEV\.\.\. no", "libudev")
        simple_pattern_pkgconfig(
            line, r"XMLLINT not set and xmllint not found in path", "libxml-2.0")
        simple_pattern_pkgconfig(
            line, r"error\: xml2-config not found", "libxml-2.0")
        simple_pattern_pkgconfig(
            line, r"error: must install xorg-macros", "xorg-macros")
        simple_pattern(
            line, r"Cannot find development files for any supported version of libnl", "libnl-dev")
        simple_pattern(line, r"/<http:\/\/www.cmake.org>", "cmake")
        simple_pattern(line, r"\-\- Boost libraries:", "boost-dev")
        simple_pattern(line, r"XInput2 extension not found", "inputproto")
        simple_pattern(line, r"^WARNING: could not find 'runtest'$", "dejagnu")
        simple_pattern(line, r"^WARNING: could not find 'runtest'$", "expect")
        simple_pattern(line, r"^WARNING: could not find 'runtest'$", "tcl")
        simple_pattern(line, r"VignetteBuilder package required for checking but installed:", "R-knitr")
        simple_pattern(
            line, r"You must have XML::Parser installed", "perl(XML::Parser)")
        simple_pattern(
            line, r"checking for Apache .* module support", "httpd-dev")
        simple_pattern(
            line, r"checking for.*in -ljpeg... no", "libjpeg-turbo-dev")
        simple_pattern(
            line, r"fatal error\: zlib\.h\: No such file or directory", "zlib-dev")
        simple_pattern(line, r"\* tclsh failed", "tcl")
        simple_pattern(
            line, r"\/usr\/include\/python2\.7\/pyconfig.h", "python-dev")
        simple_pattern(
            line, r"checking \"location of ncurses\.h file\"", "ncurses-dev")
        simple_pattern(line, r"Can't exec \"aclocal\"", "automake")
        simple_pattern(line, r"Can't exec \"aclocal\"", "libtool")
        simple_pattern(
            line, r"configure: error: no suitable Python interpreter found", "python-dev")
        simple_pattern(line, r"Checking for header Python.h", "python-dev")
        simple_pattern(
            line, r"configure: error: No curses header-files found", "ncurses-dev")
        simple_pattern(line, r" \/usr\/include\/python2\.6$", "python-dev")
        simple_pattern(line, r"to compile python extensions", "python-dev")
        simple_pattern(line, r"testing autoconf... not found", "autoconf")
        simple_pattern(line, r"configure\: error\: could not find Python headers", "python-dev")
        simple_pattern(line, r"checking for libxml libraries", "libxml2-dev")
        simple_pattern(line, r"configure: error: no suitable Python interpreter found", "python3")
        simple_pattern(line, r"configure: error: pcre-config for libpcre not found", "pcre")
        simple_pattern(line, r"checking for OpenSSL", "openssl-dev")
        simple_pattern(line, r"Package systemd was not found in the pkg-config search path.", "systemd-dev")
        simple_pattern(line, r"Unable to find the requested Boost libraries.", "boost-dev")
        # simple_pattern(line, r"Can't locate Test/More.pm", "perl-Test-Simple")

        failed_pattern(line, r"checking for library containing (.*)... no")
        failed_pattern(line, r"checking for (.*?)\.\.\. not_found")
        failed_pattern(line, r"checking for (.*?)\.\.\. not found")
        failed_pattern(line, r"configure: error: pkg-config missing (.*)")
        failed_pattern(line, r"configure: error: Cannot find (.*)\. Make sure")
        failed_pattern(line, r"checking for (.*?)\.\.\. no")
        failed_pattern(line, r"checking for (.*) support\.\.\. no")
        failed_pattern(line, r"checking (.*?)\.\.\. no")
        failed_pattern(line, r"checking for (.*)... configure: error")
        failed_pattern(line, r"checking for (.*) with pkg-config... no")
        failed_pattern(line, r"Checking for (.*) development files... No")
        failed_pattern(line, r"which\: no ([a-zA-Z\-]*) in \(")
        failed_pattern(line, r"checking for (.*) support\.\.\. no")
        failed_pattern(
            line, r"checking for (.*) in default path\.\.\. not found")
        failed_pattern(line, r" ([a-zA-Z0-9\-]*\.m4) not found")
        failed_pattern(line, r"configure\: error\: Unable to locate (.*)")
        failed_pattern(line, r"No rule to make target `(.*)',")
        failed_pattern(line, r"ImportError\: No module named (.*)")
        failed_pattern(line, r"/usr/bin/python.*\: No module named (.*)")
        failed_pattern(line, r"ImportError\: cannot import name (.*)")
        failed_pattern(line, r"ImportError\: ([a-zA-Z]+) module missing")
        failed_pattern(
            line, r"checking for [a-zA-Z0-9\_\-]+ in (.*?)\.\.\. no")
        failed_pattern(line, r"No library found for -l([a-zA-Z\-])")
        failed_pattern(line, r"\-\- Could NOT find ([a-zA-Z0-9]+)")
        failed_pattern(
            line, r"By not providing \"([a-zA-Z0-9]+).cmake\" in CMAKE_MODULE_PATH this project")
        failed_pattern(
            line, r"CMake Error at cmake\/modules\/([a-zA-Z0-9]+).cmake")
        failed_pattern(line, r"Could NOT find ([a-zA-Z0-9]+)")
        failed_pattern(line, r"  Could not find ([a-zA-Z0-9]+)")
        failed_pattern(line, r"  Did not find ([a-zA-Z0-9]+)")
        failed_pattern(
            line, r"([a-zA-Z\-]+) [0-9\.]+ is required to configure this module; please install it or upgrade your CPAN\/CPANPLUS shell.")
        failed_pattern(line, r"\/bin\/ld: cannot find (-l[a-zA-Z0-9\_]+)")
        failed_pattern(line, r"fatal error\: (.*)\: No such file or directory")
        failed_pattern(line, r"([a-zA-Z0-9\-\_\.]*)\: command not found", 1)
#    failed_pattern(line, r"\: (.*)\: command not found", 1)
        failed_pattern(line, r"-- (.*) not found.", 1)
        failed_pattern(
            line, r"You need ([a-zA-Z0-9\-\_]*) to build this program.", 1)
        failed_pattern(line, r"Cannot find ([a-zA-Z0-9\-_\.]*)", 1)
        failed_pattern(line, r"    ([a-zA-Z]+\:\:[a-zA-Z]+) not installed", 1)
        failed_pattern(line, r"([a-zA-Z\-]*) tool not found or not executable")
        failed_pattern(line, r"([a-zA-Z\-]*) validation tool not found or not executable")
        failed_pattern(line, r"Could not find suitable distribution for Requirement.parse\('([a-zA-Z\-]*)")
        failed_pattern(line, r"unable to execute '([a-zA-Z\-]*)': No such file or directory")
        failed_pattern(line, r"Unable to find '(.*)'")
        failed_pattern(line, r"Downloading https?://.*\.python\.org/packages/.*/.?/([A-Za-z]*)/.*")
        failed_pattern(line, r"configure\: error\: ([a-zA-Z0-9]+) is required to build")
        failed_pattern(line, r".* /usr/bin/([a-zA-Z0-9-_]*).*not found")
        failed_pattern(line, r"warning: failed to load external entity \"(/usr/share/sgml/docbook/xsl-stylesheets)/.*\"")
        failed_pattern(line, r"Warning\: no usable ([a-zA-Z0-9]+) found")
        failed_pattern(line, r"/usr/bin/env\: (.*)\: No such file or directory")
        failed_pattern(line, r"make: ([a-zA-Z0-9].+): Command not found")
        failed_pattern_R(line, r"ERROR: dependencies.*'([a-zA-Z0-9\-]*)' are not available for package '.*'")
        failed_pattern_R(line, r"Package which this enhances but not available for checking: '([a-zA-Z0-9\-]*)'")
        failed_pattern_R(line, r"Unknown packages '([a-zA-Z0-9\-]*)'.* in Rd xrefs")
        failed_pattern_R(line, r"Unknown package '([a-zA-Z0-9\-]*)'.* in Rd xrefs")
        failed_pattern_R(line, r"ERROR: dependencies '([a-zA-Z0-9\-]*)'.* are not available for package '.*'")
        failed_pattern_R(line, r"ERROR: dependencies '.*', '([a-zA-Z0-9\-]*)',.* are not available for package '.*'")
        failed_pattern_R(line, r"ERROR: dependency '([a-zA-Z0-9\-]*)' is not available for package '.*'")
        failed_pattern_R(line, r"there is no package called '([a-zA-Z0-9\-]*)'")
        failed_pattern_perl(line, r"you may need to install the ([a-zA-Z0-9\-:]*) module")
        failed_pattern_perl(line, r"    !  ([a-zA-Z:]+) is not installed")
        failed_pattern_perl(line, r"Warning: prerequisite ([a-zA-Z:]+) [0-9\.]+ not found.")
        failed_pattern_perl(line, r"Can't locate [a-zA-Z\/\.]+ in @INC \(you may need to install the ([a-zA-Z:]+) module\)")
        failed_pattern_pypi(line, r"Download error on https://pypi.python.org/simple/([a-zA-Z0-9\-\._:]+)/")
        failed_pattern_pypi(line, r"No matching distribution found for ([a-zA-Z0-9\-\._]+)")
        failed_pattern_pypi(line, r"ImportError:..*: No module named ([a-zA-Z0-9\-\._]+)")
        failed_pattern_pypi(line, r"ImportError: No module named ([a-zA-Z0-9\-\._]+)")
        failed_pattern_pypi(line, r"ImportError: No module named '([a-zA-Z0-9\-\._]+)'")
        failed_pattern_pkgconfig(line, r"Perhaps you should add the directory containing `([a-zA-Z0-9\-:]*)\.pc'")
        failed_pattern_pkgconfig(line, r"No package '([a-zA-Z0-9\-:]*)' found")
        failed_pattern_pkgconfig(line, r"Package '([a-zA-Z0-9\-:]*)', required by '.*', not found")
        failed_pattern_ruby(line, r"WARNING:  [a-zA-Z\-\_]+ dependency on ([a-zA-Z0-9\-\_:]*) \([<>=~]+ ([0-9.]+).*\) .*")
        failed_pattern_ruby(line, r"ERROR:  Could not find a valid gem '([a-zA-Z0-9\-:]*)' \([>=]+ ([0-9.]+).*\), here is why:")
        failed_pattern_ruby(line, r"ERROR:  Could not find a valid gem '([a-zA-Z0-9\-\_]*)' \([>=]+ ([0-9.]+).*\) in any repository")
        failed_pattern_ruby(line, r"Could not find '([a-zA-Z0-9\-\_]*)' \([~<>=]+ ([0-9.]+).*\) among [0-9]+ total gem")
        failed_pattern_ruby(line, r"Could not find gem '([a-zA-Z0-9\-\_]+) \([~<>=0-9\.\, ]+\) ruby'")
        failed_pattern_ruby(line, r"Gem::LoadError: Could not find '([a-zA-Z0-9\-\_]*)'")
        failed_pattern_ruby(line, r"[a-zA-Z0-9\-:]* is not installed: cannot load such file -- rdoc/([a-zA-Z0-9\-:]*)")
        failed_pattern_ruby(line, r"LoadError: cannot load such file -- ([a-zA-Z0-9\-:]+)/.*")
        failed_pattern_ruby(line, r":in `require': cannot load such file -- ([a-zA-Z0-9\-\_:]+) ")
        failed_pattern_ruby_table(line, r":in `require': cannot load such file -- ([a-zA-Z0-9\-\_:\/]+)")
        failed_pattern_ruby_table(line, r"LoadError: cannot load such file -- ([a-zA-Z0-9\-:\/\_]+)")
        failed_pattern_go(line, r".*\.go:.*cannot find package \"(.*)\" in any of:")

        if infiles == 1 and line.find("RPM build errors") >= 0:
            infiles = 2
        if infiles == 1 and line.find("Childreturncodewas") >= 0:
            infiles = 2
        if infiles == 1 and line.find("Child returncode") >= 0:
            infiles = 2
        if infiles == 1 and line.startswith("Building"):
            infiles = 2
        if infiles == 1 and line.startswith("Child return code was"):
            infiles = 2
        if infiles == 1 and line.find("Empty %files file") >= 0:
            infiles = 2

        if line.find("Installed (but unpackaged) file(s) found:") >= 0:
            infiles = 1
        else:
            if infiles == 1:
                files.push_file(line.strip())

        if line.startswith("Sorry: TabError: inconsistent use of tabs and spaces in indentation"):
            print(line)
            returncode = 99

        if "File not found: /builddir/build/BUILDROOT/" in line:
            left = "File not found: /builddir/build/BUILDROOT/%s-%s-%s.x86_64/" % (tarball.name, tarball.version, tarball.release)
            missing_file = "/" + line.split(left)[1].strip()
            files.remove_file(missing_file)

        if line.startswith("Executing(%clean") and returncode == 0:
            print("RPM build successful")
            success = 1

    file.close()


def set_mock():
    global mock_cmd
    if filecmp.cmp('/usr/bin/mock', '/usr/sbin/mock'):
        mock_cmd = 'sudo /usr/bin/mock'


def package():
    global round
    round = round + 1
    set_mock()
    print("Building package " + tarball.name + " round", round)
    # call(mock_cmd + " -q -r clear --scrub=cache")
    # call(mock_cmd + " -q -r clear --scrub=all")
    util.call("mkdir -p %s/results" % download_path)
    util.call(mock_cmd + " -r clear --buildsrpm --sources=./ --spec={0}.spec --uniqueext={0} --result=results/ --no-cleanup-after".format(tarball.name),
              logfile="%s/mock_srpm.log" % download_path, cwd=download_path)
    util.call("rm -f results/build.log", cwd=download_path)
    srcrpm = "results/%s-%s-%s.src.rpm" % (tarball.name, tarball.version, tarball.release)
    returncode = util.call(mock_cmd + " -r clear  --result=results/ %s --enable-plugin=ccache  --uniqueext=%s --no-cleanup-after" % (srcrpm, tarball.name),
                           logfile="%s/mock_build.log" % download_path, check=False, cwd=download_path)
    parse_build_results(download_path + "/results/build.log", returncode)
