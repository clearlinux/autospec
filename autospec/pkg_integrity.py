#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from urllib.parse import urlparse

import download
import util

GPG_CLI = False
DESCRIPTION = "Performs package signature verification for packages signed with\
gpg."
USAGE = """
Verify package signature when public key present in default keyring:
{fn} --sig package.tar.gz.asc --tar package.tar.gz

Verify package signature when public key is provided as cleartext
{fn} --sig package.tar.gz.asc --tar package.tar.gz --pubkey package_author\
.pubkey

Verify package signature when public key is in a keyring different from \
default keyring
{fn} --sig package.tar.gs.asc --tar package.tar.gz --gnupghome /opt/pki/gpghome

Verify package signature when public key is provided as a file and keyring is \
different from default
{fn} --sig package.tar.gs.asc --tar package.tar.gs --pubkey package_author.\
pubkey --gnupghome /opt/pki/gpghome

""".format(fn=__file__)

SEPT = "-------------------------------------------------------------------------------"
RUBYORG_API = "https://rubygems.org/api/v1/versions/{}.json"
PYPIORG_API = "https://pypi.python.org/pypi/{}/json"
KEYID_TRY = ""
KEYID = ""
IMPORTED = ""
EMAIL = ""
GNUPGCONF = """keyserver keys.gnupg.net"""
CMD_TIMEOUT = 20
ENV = os.environ
INPUT_GETTER_TIMEOUT = 60
CHUNK_SIZE = 2056

PYPI_DOMAINS = [
    'files.pythonhosted.org',
    'pypi.debian.net',
    'pypi.python.org',
    'pypi.io',
]


def update_gpg_conf(proxy_value):
    """Set GNUPGCONF with http_proxy value."""
    global GNUPGCONF
    GNUPGCONF = "{}\nkeyserver-options http-proxy={}".format(GNUPGCONF, proxy_value)


if 'http_proxy' in ENV.keys():
    update_gpg_conf(ENV.get('http_proxy'))
elif 'HTTP_PROXY' in ENV.keys():
    update_gpg_conf(ENV.get('HTTP_PROXY'))


# CLI interface to gpg command
class GPGCliStatus(object):
    """Mock gpgmeerror."""

    def __init__(self, strerror):
        """Initialize mock GPGCliStatus."""
        self.strerror = strerror


class GPGCli(object):
    """CLI wrapper for gpg."""

    @staticmethod
    def exec_cmd(args):
        """Popen wrapper."""
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            out, err = proc.communicate(timeout=CMD_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
        return out, err, proc.returncode

    def __init__(self, pubkey=None, home=None):
        """Set GPGCli defaults."""
        _gpghome = home
        if _gpghome is None:
            _gpghome = tempfile.mkdtemp(prefix='tmp.gpghome')
        os.environ['GNUPGHOME'] = _gpghome
        self.args = ['gpg', '--homedir', _gpghome]
        util.write_out(os.path.join(_gpghome, 'gpg.conf'), GNUPGCONF)
        if pubkey is not None:
            args = self.args + ['--import', pubkey]
            output, err, code = self.exec_cmd(args)
            if code == -9:
                raise Exception('Command {} timeout after {} seconds'.format(' '.join(args), CMD_TIMEOUT))
            elif code != 0:
                raise Exception(err.decode('utf-8'))
        self._home = _gpghome

    def verify(self, _, tarfile, signature):
        """Validate tarfile with signature."""
        # Since autospec can only verify one signature for now, extract the
        # first signature from the detached signature file.
        sig_name = signature
        packets = parse_gpg_packets(signature)
        if len(packets) > 1:
            # sig file may be ascii-armored, so dearmor it first...
            args = self.args + ['--dearmor', '--output', '-', signature]
            output, err, code = self.exec_cmd(args)
            if code != 0:
                return GPGCliStatus(f'Failed to convert {signature} to binary format')
            num_bytes = packets[0].get("length")
            if not num_bytes:
                return GPGCliStatus(f'Cannot verify first signature from {signature}')
            first_sig = output[:num_bytes]
            with tempfile.NamedTemporaryFile(prefix="newsig-", dir=self._home, delete=False) as new_sig_file:
                new_sig_file.write(first_sig)
                sig_name = new_sig_file.name
        args = self.args + ['--verify', sig_name, tarfile]
        output, err, code = self.exec_cmd(args)
        if code == 0:
            return None
        elif code == -9:
            return GPGCliStatus('Command {} timeout after {} seconds'.format(' '.join(args), CMD_TIMEOUT))
        return GPGCliStatus(err.decode('utf-8'))

    def import_key(self, keyid):
        """Import signer key."""
        args = self.args + ['--recv-keys', keyid]
        output, err, code = self.exec_cmd(args)
        if code == 0:
            return None, output
        elif code == -9:
            return GPGCliStatus('Import key timeout after {} seconds, make sure keystore is reachable'.format(CMD_TIMEOUT)), None
        return GPGCliStatus(err.decode('utf-8')), None

    def export_key(self, keyid):
        """Export signer key with armor."""
        args = self.args + ['--armor', '--export', keyid]
        output, err, code = self.exec_cmd(args)
        if output.decode('utf-8') == '':
            return GPGCliStatus(err.decode('utf-8')), None
        if code == 0:
            return None, output.decode('utf-8')
        return GPGCliStatus(err.decode('utf-8')), None

    def display_keyinfo(self, keyfile):
        """Show signer key information."""
        args = self.args + ['--list-packet', keyfile]
        lp, err, code = self.exec_cmd(args)
        if code != 0:
            return GPGCliStatus(err.decode('utf-8')), None

        # trim list-packet output to 10 lines
        lp = "--list-packet:\n" + "\n".join(lp.decode("utf-8").split("\n")[:10])

        args = self.args + ['--fingerprint', os.path.basename(keyfile.replace(".pkey", ""))]
        fp, err, code = self.exec_cmd(args)
        if code != 0:
            return GPGCliStatus(err.decode('utf-8')), None

        fp = "--fingerprint:\n" + fp.decode("utf-8")
        return None, "{}\n\n{}".format(lp, fp)


@contextmanager
def cli_gpg_ctx(pubkey=None):
    """Return correctly initialized GPGCli."""
    _gpghome = None
    try:
        _gpghome = tempfile.mkdtemp(prefix='tmp.gpghome')
        yield GPGCli(pubkey, _gpghome)
    finally:
        if _gpghome is not None:
            _ = subprocess.run(["gpgconf", "--homedir", _gpghome, "--kill", "all"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            del os.environ['GNUPGHOME']
            shutil.rmtree(_gpghome, ignore_errors=True)


# Use gpg command line
def verify_cli(pubkey, tarball, signature):
    """Validate tarfile with signature."""
    with cli_gpg_ctx(pubkey) as ctx:
        return ctx.verify(pubkey, tarball, signature)
    raise Exception('Verification did not take place using cli')


class Verifier(object):
    """Base validation class."""

    def __init__(self, **kwargs):
        """Set default values."""
        self.url = kwargs.get('url', None)
        self.package_sign_path = kwargs.get('package_sign_path', None)
        self.config = kwargs.get('config', None)
        print(SEPT)

    @staticmethod
    def quit():
        """Stop verification."""
        print('Critical error quitting...')
        print(SEPT)
        exit(1)

    @staticmethod
    def calc_sum(filepath, digest_algo):
        """Use digest_algo to calculate block sum of a file."""
        BLOCK_SIZE = 4096
        with open(filepath, 'rb') as fp:
            digest = digest_algo()
            for block in iter(lambda: fp.read(BLOCK_SIZE), b''):
                digest.update(block)
            return digest.hexdigest()

    def print_result(self, result, err_msg=''):
        """Display verification results."""
        global EMAIL
        package_name = ''
        if self.url is not None:
            package_name = os.path.basename(self.url)
        if result:
            msg = "{} verification was successful ({})".format(package_name, EMAIL)
            util.print_success(msg)
        else:
            msg = "{} verification failed {}".format(package_name, err_msg)
            util.print_error(msg)

    def __del__(self):
        """Display partition."""
        print(SEPT)


def get_signature_file(package_url, package_path):
    """Attempt to build signature file URL and download it."""
    sign_urls = []
    netloc = urlparse(package_url).netloc
    if 'samba.org' in netloc:
        sign_urls.append(package_url + '.asc')
    elif any(loc in netloc for loc in PYPI_DOMAINS):
        sign_urls.append(package_url + '.asc')
    elif 'mirrors.kernel.org' in netloc:
        sign_urls.append(package_url + '.sig')
    else:
        iter = (package_url + "." + ext for ext in ("asc", "sig", "sign"))
        for sign_url in iter:
            sign_urls.append(sign_url)

    sign_file = None
    dest = None
    for url in sign_urls:
        dest = os.path.join(package_path, os.path.basename(url))
        sign_file = download.do_curl(url, dest)
        if sign_file is not None:
            return sign_file

    return None


def compare_keys(newkey, oldkey):
    """Key comparison to check against key tampering."""
    if newkey != oldkey:
        util.print_error('Public key has changed:\n'
                         '            old key: {}\n'
                         '            new key: {}\n'
                         'this is a critical security error, quitting...'
                         .format(oldkey, newkey))
        exit(1)


# sha256sum Verifier
class ShaSumVerifier(Verifier):
    """Extend verification for sha sums."""

    def __init__(self, **kwargs):
        """Add shalen initialization."""
        Verifier.__init__(self, **kwargs)
        self.package_path = kwargs.get('package_path', None)
        self.shalen = kwargs.get('shalen', 256)

    def verify_sum(self, shasum):
        """Verify sha sum."""
        util.print_info("Verifying sha{}sum digest".format(self.shalen))
        if shasum is None:
            self.print_result(False, err_msg='Verification requires shasum')
            return None
        if os.path.exists(self.package_path) is False:
            self.print_result(False, err_msg='{} not found'.format(self.package_path))
            return None

        sha_algo = {
            256: hashlib.sha256
        }.get(self.shalen, None)

        if sha_algo is None:
            self.print_result(False, err_msg='sha{} algorithm not found'.format(self.shalen))
            return None

        digest = self.calc_sum(self.package_path, sha_algo)
        self.print_result(digest == shasum)
        return digest == shasum


# MD5 Verifier
class MD5Verifier(Verifier):
    """Extend verification for MD5."""

    def __init__(self, **kwargs):
        """Add MD5 initialization."""
        Verifier.__init__(self, **kwargs)
        self.package_path = kwargs.get('package_path', None)
        self.md5_digest = kwargs.get('md5_digest', None)

    def verify_md5(self):
        """Verify MD5."""
        util.print_info("Verifying MD5 digest")
        if self.md5_digest is None:
            self.print_result(False, err_msg='Verification requires a md5_digest')
            return None
        if os.path.exists(self.package_path) is False:
            self.print_result(False, err_msg='{} not found'.format(self.package_path))
            return None
        md5_digest = self.calc_sum(self.package_path, hashlib.md5)
        self.print_result(md5_digest == self.md5_digest)
        return md5_digest == self.md5_digest


# gnome.org Verifier
class GnomeOrgVerifier(ShaSumVerifier):
    """Verify sha sums for gnome.org."""

    def __init__(self, **kwargs):
        """Initialize with gnome.org url."""
        kwargs.update({'shalen': 256})
        self.package_url = kwargs.get('url', None)
        ShaSumVerifier.__init__(self, **kwargs)

    @staticmethod
    def fetch_shasum(shasum_url):
        """Get shasum file from gnome.org."""
        data = download.do_curl(shasum_url)
        if data:
            return data.getvalue().decode('utf-8')
        else:
            return None

    @staticmethod
    def get_shasum(package_url):
        """Try and get sha url based on package url."""
        ext_pos = package_url.find(".tar.")
        if ext_pos < 0:
            shasum_url = "{}.sha256sum".format(package_url)
        else:
            shasum_url = package_url[:ext_pos] + ".sha256sum"
        shasum = GnomeOrgVerifier.fetch_shasum(shasum_url)
        if shasum:
            return shasum
        return None

    @staticmethod
    def parse_shasum(package_url, shasum_text):
        """Parse shasum from sha url file content."""
        for line in shasum_text.split('\n'):
            if not line.strip():
                continue
            sha, file = [col for col in line.split() if col != '']
            if os.path.basename(package_url) == file:
                return sha
        return None

    def verify(self):
        """Verify tar file with sha from gnome.org."""
        if self.package_url is None:
            self.print_result(False, err_msg='Package URL can not be None for GnomeOrgVerifier')
            return None
        shasum = self.get_shasum(self.package_url)
        if shasum is None:
            self.print_result(False, err_msg='Unable to find shasum URL for {}'.format(self.package_url))
            return None
        shasum = self.parse_shasum(self.package_url, shasum)
        if shasum is None:
            self.print_result(False, err_msg='Unable to parse shasum {}'.format(shasum))
            return None
        return self.verify_sum(shasum)


# download.qt.io Verifier
class QtIoVerifier(ShaSumVerifier):
    """Verify sha256 hashes for download.qt.io."""

    def __init__(self, **kwargs):
        """Initialize with package URL."""
        kwargs.update({'shalen': 256})
        self.package_url = kwargs.get('url', None)
        ShaSumVerifier.__init__(self, **kwargs)

    def fetch_shasum(self):
        """Fetch sha256 file associated with the package URL."""
        shasum_url = "{}.sha256".format(self.package_url)
        data = download.do_curl(shasum_url)
        if data:
            return data.getvalue().decode('utf-8')
        else:
            return None

    def parse_shasum(self, content):
        """Parse sha256 file."""
        basename = os.path.basename(self.package_url)
        line = content.split('\n')[0]
        match = re.match(r'([0-9a-f]{64})\s+' + basename, line)
        if not match:
            return None
        return match.group(1)

    def verify(self):
        """Verify the source file's sha256 hash."""
        if self.package_url is None:
            self.print_result(False, err_msg='Package URL is empty')
            return None
        content = self.fetch_shasum()
        if content is None:
            self.print_result(False, err_msg='Unable to download sha256 for {}'.format(self.package_url))
            return None
        shasum = self.parse_shasum(content)
        if shasum is None:
            self.print_result(False, err_msg='Unable to parse sha256 for {}'.format(self.package_url))
            return None
        return self.verify_sum(shasum)


# PyPi Verifier
class PyPiVerifier(MD5Verifier):
    """Verify MD5 signature for pypi."""

    def __init__(self, **kwargs):
        """Passthrough initialization to MD5."""
        MD5Verifier.__init__(self, **kwargs)

    def parse_name(self):
        """Get pypi package name and release number."""
        pkg_name = os.path.basename(self.package_path)
        name, _ = re.split(r'-\d+\.', pkg_name, maxsplit=1)
        release_no = pkg_name.replace(name + '-', '')
        extensions = "({})".format("|".join([r'\.tar\.gz$', r'\.zip$', r'\.tgz$', r'\.tar\.bz2$']))
        ext = re.search(extensions, release_no)
        if ext is not None:
            release_no = release_no.replace(ext.group(), '')
        return name, release_no

    @staticmethod
    def get_info(package_name):
        """Get json dump of pypi package."""
        url = PYPIORG_API.format(package_name)
        data = download.do_curl(url)
        if data:
            return json.loads(data.getvalue().decode('utf-8'))
        else:
            return None

    @staticmethod
    def get_source_release(package_fullname, releases):
        """Lookup release for package name."""
        for release in releases:
            if release.get('filename', 'not_found') == package_fullname:
                return release
        return None

    def verify(self):
        """Verify pypi file with MD5."""
        global EMAIL
        util.print_info("Searching for package information in pypi")
        name, release = self.parse_name()
        info = PyPiVerifier.get_info(name)
        releases_info = info.get('releases', None)
        if releases_info is None:
            self.print_result(False, err_msg='Error in package info from {}'.format(PYPIORG_API))
            return None
        release_info = releases_info.get(release, None)
        if release_info is None:
            self.print_result(False,
                              err_msg='Information for package {} with release {} not found'.format(name, release))
            return None
        release_info = self.get_source_release(os.path.basename(self.package_path), release_info)
        package_info = info.get('info', None)
        if package_info is not None:
            EMAIL = package_info.get('author_email', '')
        self.md5_digest = release_info.get('md5_digest', '')
        return self.verify_md5()


# GPG Verification
class GPGVerifier(Verifier):
    """Verify GPG signature."""

    def __init__(self, **kwargs):
        """Initialize gpg signature validation."""
        Verifier.__init__(self, **kwargs)
        self.key_url = kwargs.get('key_url', None)
        self.package_path = kwargs.get('package_path', None)
        self.package_check = kwargs.get('package_check', None)
        self.interactive = kwargs.get('interactive', False)
        if not self.key_url and self.package_check:
            # signature exists locally, don't try to download self.url
            self.key_url = self.url.rstrip('/') + get_file_ext(self.package_check)
        if not self.package_sign_path:
            # the key exists (or will exist) at
            # <package directory>/<key url basename>
            self.package_sign_path = os.path.join(os.path.dirname(self.package_path),
                                                  os.path.basename(self.key_url))
        # pubkey path is the package directory - this is where imports will go
        self.pubkey_path = os.path.join(os.path.dirname(self.package_path), "{}.pkey")

    def get_sign(self):
        """Attempt to download gpg signature file."""
        sign_file = download.do_curl(self.key_url, self.package_sign_path)
        if sign_file is not None:
            return True
        else:
            msg = "Unable to download file {}"
            self.print_result(False, msg.format(self.key_url))

    def verify(self, recursion=False):
        """Verify file using gpg signature."""
        global KEYID
        global EMAIL
        util.print_info("Verifying GPG signature")
        if os.path.exists(self.package_path) is False:
            self.print_result(False, err_msg='{} not found'.format(self.package_path))
            return None
        if os.path.exists(self.package_sign_path) is False and self.get_sign() is not True:
            self.print_result(False, err_msg='{} not found'.format(self.package_sign_path))
            return None
        if sign_isvalid(self.package_sign_path) is False:
            self.print_result(False, err_msg='{} is not a GPG signature'.format(self.package_sign_path))
            try:
                os.unlink(self.package_sign_path)
            except Exception:
                pass
            return None
        # valid signature exists at package_sign_path, operate on it now
        keyid = get_keyid(self.package_sign_path)
        # default location first
        pubkey_loc = self.pubkey_path.format(keyid)
        if not os.path.exists(pubkey_loc):
            # attempt import the key interactively if set to do so
            self.print_result(False, 'Public key {} not found'.format(keyid))
            if not self.interactive or recursion:
                return None
            if attempt_key_import(keyid, self.pubkey_path.format(keyid)):
                return self.verify(recursion=True)
            return None
        # public key exists or is imported, verify
        EMAIL = get_email(pubkey_loc)
        sign_status = verify_cli(pubkey_loc, self.package_path, self.package_sign_path)
        if not sign_status:
            if self.config.old_keyid:
                compare_keys(KEYID_TRY, self.config.old_keyid)
            self.print_result(self.package_path)
            KEYID = KEYID_TRY
            self.config.signature = self.key_url
            self.config.config_opts['verify_required'] = True
            self.config.rewrite_config_opts()
            return True
        else:
            self.print_result(False, err_msg=sign_status.strerror)
            self.quit()


def quit_verify():
    """Halt build due to verification being required."""
    util.print_error("Verification required for build (verify_required option set)")
    Verifier.quit()


# GEM Verifier
class GEMShaVerifier(Verifier):
    """Verify signatures for ruby gems."""

    def __init__(self, **kwargs):
        """Initialize gem verification."""
        self.package_path = kwargs.get('package_path', None)
        Verifier.__init__(self, **kwargs)

    @staticmethod
    def get_rubygems_info(package_name):
        """Get json dump of ruby gem."""
        url = RUBYORG_API.format(package_name)
        data = download.do_curl(url)
        if data:
            return json.loads(data.getvalue().decode('utf-8'))
        else:
            return None

    @staticmethod
    def get_gemnumber_sha(gems, number):
        """Get sha for a gem based on the gem's number."""
        mygem = [gem for gem in gems if gem.get('number', -100) == number]
        if len(mygem) == 1:
            return mygem[0].get('sha', None)
        else:
            return None

    def verify(self):
        """Verify ruby gem based on sha sum."""
        gemname = os.path.basename(self.package_path).replace('.gem', '')
        util.print_info("Verifying SHA256 checksum")
        if os.path.exists(self.package_path) is False:
            self.print_result(False, 'GEM was not found {}'.format(self.package_path))
            return
        name, _ = re.split(r'-\d+\.', gemname)
        number = gemname.replace(name + '-', '')
        geminfo = GEMShaVerifier.get_rubygems_info(name)
        gemsha = GEMShaVerifier.get_gemnumber_sha(geminfo, number)

        if geminfo is None:
            self.print_result(False, "unable to parse info for gem {}".format(gemname))
        else:
            calcsha = self.calc_sum(self.package_path, hashlib.sha256)
            self.print_result(gemsha == calcsha)
            result = gemsha == calcsha
            if result is False:
                self.quit()
            return result


VERIFIER_TYPES = {
    '.gz': GPGVerifier,
    '.tgz': GPGVerifier,
    '.tar': GPGVerifier,
    '.bz2': GPGVerifier,
    '.xz': GPGVerifier,
    '.zip': GPGVerifier,
    '.gem': GEMShaVerifier,
}


def get_file_ext(filename):
    """Return filename extension."""
    return os.path.splitext(filename)[1]


def get_verifier(filename):
    """Return verification based on filename."""
    ext = get_file_ext(filename)
    return VERIFIER_TYPES.get(ext, None)


def get_input(message, default):
    """Parse user input."""
    try:
        import_key = input(message)
        if import_key == '':
            import_key = default
        return import_key.lower() == 'y'
    except Exception:
        return None


def input_timeout(signum, frame):
    """Handle input timeouts."""
    print('\ninput timed out')
    raise Exception('keyboard timed out')


class InputGetter(object):
    """Simple class for user input."""

    def __init__(self, message='?', default='N', timeout=INPUT_GETTER_TIMEOUT):
        """Initialize input class."""
        self.message = message
        self.default = default
        self.timeout = timeout
        signal.signal(signal.SIGALRM, input_timeout)

    def get_answer(self):
        """Read user input."""
        signal.alarm(self.timeout)
        inpt = get_input(self.message, self.default)
        signal.alarm(0)
        return inpt


def attempt_key_import(keyid, key_fullpath):
    """Ask user to import key."""
    global IMPORTED
    print(SEPT)
    ig = InputGetter('\nDo you want to attempt to import keyid {}: (y/N) '.format(keyid))
    import_key_answer = ig.get_answer()
    if import_key_answer in [None, False]:
        return False
    with cli_gpg_ctx() as ctx:
        err, _ = ctx.import_key(keyid)
        if err is not None:
            util.print_error(err.strerror)
            return False
        err, key_content = ctx.export_key(keyid)
        if err is not None:
            util.print_error(err.strerror)
            return False
        util.write_out(key_fullpath, key_content)
        print('\n')
        util.print_success('Public key id: {} was imported'.format(keyid))
        err, content = ctx.display_keyinfo(key_fullpath)
        if err is not None:
            util.print_error('Unable to parse {}, will be removed'.format(key_fullpath))
            os.unlink(key_fullpath)
            return False
        print("\n", content)
        ig = InputGetter(message='\nDo you want to keep this key: (Y/n) ', default='y')
        if ig.get_answer() is True:
            IMPORTED = content
            return True
        else:
            os.unlink(key_fullpath)
    return False


def parse_gpg_packets(filename, verbose=True):
    """Return a list with metadata about each packet from a GPG key or signature."""
    args = ["gpg", "--list-packets", filename]
    try:
        out, err = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        if err.decode('utf-8') != '' and verbose is True:
            print(err.decode('utf-8'))
            return None
        out = out.decode('utf-8')
        packets = []
        packet = {}
        for line in out.splitlines():
            complete = False
            m = re.search(r'^# off=(\d+) ctb=.* tag=.* hlen=(\d+) plen=(\d+).*$', line)
            if m:
                packet["offset"] = int(m.group(1))
                packet["length"] = int(m.group(2)) + int(m.group(3))
            m = re.search(r'^:(signature) packet:.* keyid ([0-9A-F]+)$', line)
            if m and "type" not in packet:
                packet["type"] = m.group(1)
                packet["keyid"] = m.group(2)
                complete = True
            m = re.search(r'^:(user ID) packet: "(.*) <(.+?)>"', line)
            if m and "type" not in packet:
                packet["type"] = m.group(1)
                packet["user"] = m.group(2)
                packet["email"] = m.group(3)
                complete = True
            # add the packet only if we've extracted all data we need from it
            if complete:
                packets.append(packet)
                packet = {}
        return packets
    except Exception:
        return None
    return None


def get_keyid(sig_filename):
    """Get keyid from GPG pubkey or signature file and set global KEYID_TRY."""
    global KEYID_TRY
    keyid = None
    packets = parse_gpg_packets(sig_filename)
    if packets:
        for p in packets:
            if "keyid" in p:
                keyid = p["keyid"]
                break
    KEYID_TRY = keyid
    return keyid.upper() if keyid else None


def get_email(pubkey):
    """Get user email address from GPG pubkey file and set global EMAIL."""
    email = None
    packets = parse_gpg_packets(pubkey)
    if packets:
        for p in packets:
            if "email" in p:
                email = p["email"]
                break
    return email


def sign_isvalid(sig_filename):
    """Get keyid from signature file."""
    keyid = None
    packets = parse_gpg_packets(sig_filename, verbose=False)
    if packets:
        keyid = packets[0].get("keyid")
    return keyid is not None


def filename_from_url(url):
    """Run os.path.basename for a url."""
    return os.path.basename(url)


def apply_verification(verifier, **kwargs):
    """Attempt to run verification routine."""
    if verifier is None:
        util.print_error("Package is not verifiable (yet)")
    else:
        v = verifier(**kwargs)
        return v.verify()


def from_disk(url, package_path, package_check, config, interactive=True):
    """Run verification."""
    verifier = get_verifier(package_path)
    return apply_verification(verifier,
                              **{
                                  'package_path': package_path,
                                  'package_check': package_check,
                                  'url': url,
                                  'interactive': interactive,
                                  'config': config,
                              })


def attempt_verification_per_domain(package_path, url):
    """Use url domain name to set verification type."""
    netloc = urlparse(url).netloc
    if any(loc in netloc for loc in PYPI_DOMAINS):
        domain = 'pypi'
    elif 'download.gnome.org' in netloc:
        domain = 'gnome.org'
    elif 'download.qt.io' in netloc:
        domain = 'qt.io'
    else:
        domain = 'unknown'
    verifier = {
        'pypi': PyPiVerifier,
        'gnome.org': GnomeOrgVerifier,
        'qt.io': QtIoVerifier,
    }.get(domain, None)

    if verifier is None:
        util.print_info('Skipping domain verification')
        return None
    else:
        util.print_info('Verification based on domain {}'.format(domain))
        return apply_verification(verifier, **{
                                  'package_path': package_path,
                                  'url': url})


def get_integrity_file(package_path):
    """Get verification filename."""
    iter = (package_path + "." + ext for ext in ("asc", "sig", "sign", "sha256"))
    for sign_file in iter:
        if os.path.isfile(sign_file):
            return sign_file
    return None


def check(url, config, interactive=True):
    """Run verification based on tar file url."""
    package_name = filename_from_url(url)
    package_path = os.path.join(config.download_path, package_name)
    package_check = get_integrity_file(package_path)
    try:
        interactive = interactive and sys.stdin.isatty()
    except ValueError:
        interactive = False
    print(SEPT)
    util.print_info('Performing package integrity verification')
    verified = None
    if package_check is not None:
        verified = from_disk(url, package_path, package_check, config, interactive=interactive)
    elif package_path[-4:] == '.gem':
        signature_file = get_signature_file(url, config.download_path)
        verified = from_disk(url, package_path, signature_file, config, interactive=interactive)
    else:
        util.print_info('None of {}.(asc|sig|sign|sha256) is found in {}'.format(package_name, config.download_path))
        signature_file = get_signature_file(url, config.download_path)
        if signature_file is not None:
            verified = from_disk(url, package_path, signature_file, config, interactive=interactive)
            if verified is None:
                util.print_info('Unable to find a signature')
                verified = attempt_verification_per_domain(package_path, url)
        else:
            verified = attempt_verification_per_domain(package_path, url)

    if verified is None and config.config_opts['verify_required']:
        quit_verify()
    elif verified is None:
        print(SEPT)
    return verified


def parse_args():
    """Set args for tarfile verification."""
    parser = argparse.ArgumentParser(usage=USAGE, description=DESCRIPTION)
    parser.add_argument('--tar', required=True,
                        help='tar file to check signature')
    parser.add_argument('--sig', required=True,
                        help='Signature file')
    parser.add_argument('--pubkey', required=False, default=None,
                        help='Public key to use for signature verification')
    parser.add_argument('--gnupghome', required=False, default=None,
                        help='GNUPGHOME')
    return parser.parse_args()


def load_specfile(specfile):
    """Set key and email in specfile."""
    specfile.keyid = KEYID
    specfile.email = EMAIL
