#!/usr/bin/env python3

import os
import re
import sys
import argparse
import shutil
import tempfile
import pycurl
import hashlib
import signal
import json
from urllib.parse import urlparse
from io import BytesIO
from contextlib import contextmanager
from subprocess import Popen, PIPE, TimeoutExpired

import config

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
EMAIL = ""
GNUPGCONF = """keyserver keys.gnupg.net"""
PUBKEY_PATH = '/'.join([os.path.dirname(os.path.abspath(__file__)), "keyring", "{}.pkey"])
CMD_TIMEOUT = 20
ENV = os.environ
INPUT_GETTER_TIMEOUT = 60
CHUNK_SIZE = 2056


def update_gpg_conf(proxy_value):
    global GNUPGCONF
    GNUPGCONF = "{}\nkeyserver-options http-proxy={}".format(GNUPGCONF, proxy_value)


if 'http_proxy' in ENV.keys():
    update_gpg_conf(ENV.get('http_proxy'))
elif 'HTTP_PROXY' in ENV.keys():
    update_gpg_conf(ENV.get('HTTP_PROXY'))


# CLI interface to gpg command
class GPGCliStatus(object):
    """Mock gpgmeerror"""
    def __init__(self, strerror):
        self.strerror = strerror


class GPGCli(object):
    """cli wrapper for gpg"""

    @staticmethod
    def exec_cmd(args):
        proc = Popen(args, stdout=PIPE, stderr=PIPE)
        try:
            out, err = proc.communicate(timeout=CMD_TIMEOUT)
        except TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
        return out, err, proc.returncode

    def __init__(self, pubkey=None, home=None):
        _gpghome = home
        if _gpghome is None:
            _gpghome = tempfile.mkdtemp(prefix='tmp.gpghome')
        os.environ['GNUPGHOME'] = _gpghome
        self.args = ['gpg', '--homedir', _gpghome]
        with open(os.path.join(_gpghome, 'gpg.conf'), 'w') as conf:
            conf.write(GNUPGCONF)
            conf.close()
        if pubkey is not None:
            args = self.args + ['--import', pubkey]
            output, err, code = self.exec_cmd(args)
            if code == -9:
                raise Exception('Command {} timeout after {} seconds'.format(' '.join(args), CMD_TIMEOUT))
            elif code != 0:
                raise Exception(err.decode('utf-8'))
        self._home = _gpghome

    def verify(self, _, tarfile, signature):
        args = self.args + ['--verify', signature, tarfile]
        output, err, code = self.exec_cmd(args)
        if code == 0:
            return None
        elif code == -9:
            return GPGCliStatus('Command {} timeout after {} seconds'.format(' '.join(args), CMD_TIMEOUT))
        return GPGCliStatus(err.decode('utf-8'))

    def import_key(self, keyid):
        args = self.args + ['--recv-keys', keyid]
        output, err, code = self.exec_cmd(args)
        if code == 0:
            return None, output
        elif code == -9:
            return GPGCliStatus('Import key timeout after {} seconds, make sure keystore is reachable'.format(CMD_TIMEOUT)), None
        return GPGCliStatus(err.decode('utf-8')), None

    def export_key(self, keyid):
        args = self.args + ['--armor', '--export', keyid]
        output, err, code = self.exec_cmd(args)
        if output.decode('utf-8') == '':
            return GPGCliStatus(err.decode('utf-8')), None
        if code == 0:
            return None, output.decode('utf-8')
        return GPGCliStatus(err.decode('utf-8')), None

    def display_keyinfo(self, keyfile):
        args = self.args + ['--list-packet', keyfile]
        output, err, code = self.exec_cmd(args)
        if code == 0:
            return None, output.decode('utf-8')
        return GPGCliStatus(err.decode('utf-8')), None


@contextmanager
def cli_gpg_ctx(pubkey=None, gpghome=None):
    if pubkey is None:
        yield GPGCli()
    else:
        try:
            _gpghome = gpghome
            if _gpghome is None:
                _gpghome = tempfile.mkdtemp(prefix='tmp.gpghome')
            yield GPGCli(pubkey, _gpghome)
        finally:
            if gpghome is None:
                del os.environ['GNUPGHOME']
                shutil.rmtree(_gpghome, ignore_errors=True)


# Use gpg command line
def verify_cli(pubkey, tarball, signature, gpghome=None):
    with cli_gpg_ctx(pubkey, gpghome) as ctx:
        return ctx.verify(pubkey, tarball, signature)
    raise Exception('Verification did not take place using cli')


class Verifier(object):

    def __init__(self, **kwargs):
        self.url = kwargs.get('url', None)
        self.package_sign_path = kwargs.get('package_sign_path', None)
        print(SEPT)

    @staticmethod
    def download_file(url, destination):
        return attempt_to_download(url, destination)

    @staticmethod
    def quit():
        print('Critical error quitting...')
        exit(1)

    @staticmethod
    def calc_sum(filepath, digest_algo):
        BLOCK_SIZE = 4096
        with open(filepath, 'rb') as fp:
            digest = digest_algo()
            for block in iter(lambda: fp.read(BLOCK_SIZE), b''):
                digest.update(block)
            return digest.hexdigest()

    def print_result(self, result, err_msg=''):
        global EMAIL
        package_name = ''
        if self.url is not None:
            package_name = os.path.basename(self.url)
        if result:
            msg = "{} verification was successful ({})".format(package_name, EMAIL)
            print_success(msg)
        else:
            msg = "{} verification failed {}".format(package_name, err_msg)
            print_error(msg)

    def __del__(self):
        print(SEPT)


def head_request(url):
    curl = pycurl.Curl()
    curl.setopt(curl.URL, url)
    curl.setopt(curl.CUSTOMREQUEST, "HEAD")
    curl.setopt(curl.NOBODY, True)
    curl.setopt(curl.FOLLOWLOCATION, True)
    curl.setopt(curl.TIMEOUT, 5)
    curl.perform()
    http_code = curl.getinfo(pycurl.HTTP_CODE)
    curl.close()
    return http_code


def get_signature_url(package_url):
    if '://pypi.' in package_url[:13]:
        return package_url + '.asc'
    elif 'mirrors.kernel.org' in package_url:
        return package_url + '.sig'
    else:
        try:
            st = head_request(package_url + '.sig')
            if st == 200 or st == 302:
                return package_url + '.sig'
            st = head_request(package_url + '.asc')
            if st == 200 or st == 302:
                return package_url + '.asc'
            st = head_request(package_url + '.asc')
            if st == 200 or st == 302:
                return package_url + '.sign'
        except:
            pass
    return None


def get_hash_url(package_url):
    if 'download.gnome.org' in package_url:
        return package_url.replace('.tar.xz', '.sha256sum')
    return None


def compare_keys(newkey, oldkey):
    if newkey != oldkey:
        print_error('Public key has changed:\n'
                    '            old key: {}\n'
                    '            new key: {}\n'
                    'this is a critical security error, quitting...'
                    .format(oldkey, newkey))
        exit(1)

# sha256sum Verifier
class ShaSumVerifier(Verifier):

    def __init__(self, **kwargs):
        Verifier.__init__(self, **kwargs)
        self.package_path = kwargs.get('package_path', None)
        self.shalen = kwargs.get('shalen', 256)


    def verify_sum(self, shasum):
        print("Verifying sha{}sum digest\n".format(self.shalen))
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

    def __init__(self, **kwargs):
        Verifier.__init__(self, **kwargs)
        self.package_path = kwargs.get('package_path', None)
        self.md5_digest = kwargs.get('md5_digest', None)

    def verify_md5(self):
        print("Verifying MD5 digest\n")
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

    def __init__(self, **kwargs):
        kwargs.update({'shalen': 256})
        self.package_url = kwargs.get('url', None)
        ShaSumVerifier.__init__(self, **kwargs)

    @staticmethod
    def get_shasum_url(package_url):
        url = "{}.sha256sum".format(package_url.replace(".tar.xz", ""))
        if head_request(url) == 200:
            return url
        url = "{}.sha256sum".format(package_url)
        if head_request(url) == 200:
            return url
        return None

    @staticmethod
    def get_shasum(package_url):
        data = BytesIO()
        curl = pycurl.Curl()
        curl.setopt(curl.URL, package_url)
        curl.setopt(curl.WRITEFUNCTION, data.write)
        curl.setopt(curl.FOLLOWLOCATION, True)
        curl.perform()
        return data.getvalue().decode('utf-8')

    @staticmethod
    def parse_shasum(shasum_text):
        for line in shasum_text.split('\n'):
            sha, file = [col for col in line.split(' ') if col != '']
            if ".tar.xz" in file:
                return sha
        return None

    def verify(self):
        if self.package_url is None:
            self.print_result(False, err_msg='Package URL can not be None for GnomeOrgVerifier')
            return None
        shasum_url = self.get_shasum_url(self.package_url)
        if shasum_url is None:
            self.print_result(False, err_msg='Unable to find shasum URL for {}'.format(self.package_url))
            return None
        shasum = self.get_shasum(shasum_url)
        shasum = self.parse_shasum(shasum)
        if shasum is None:
            self.print_result(False, err_msg='Unable to parse shasum {}'.format(shasum_url))
            return None
        return self.verify_sum(shasum)


# PyPi Verifier
class PyPiVerifier(MD5Verifier):

    def __init__(self, **kwargs):
        MD5Verifier.__init__(self, **kwargs)

    def parse_name(self):
        pkg_name = os.path.basename(self.package_path)
        name, _ = re.split('-\d+\.', pkg_name)
        release_no = pkg_name.replace(name + '-', '')
        extensions = "({})".format("|".join(['\.tar\.gz$', '\.zip$', '\.tgz$', '\.tar\.bz2$']))
        ext = re.search(extensions, release_no)
        if ext is not None:
            release_no = release_no.replace(ext.group(), '')
        return name, release_no

    @staticmethod
    def get_info(package_name):
        url = PYPIORG_API.format(package_name)
        data = BytesIO()
        curl = pycurl.Curl()
        curl.setopt(curl.URL, url)
        curl.setopt(curl.WRITEFUNCTION, data.write)
        curl.setopt(curl.FOLLOWLOCATION, True)
        curl.perform()
        json_data = json.loads(data.getvalue().decode('utf-8'))
        return json_data

    @staticmethod
    def get_source_release(package_fullname, releases):
        for release in releases:
            if release.get('filename', 'not_found') == package_fullname:
                return release
        return None

    def verify(self):
        global EMAIL
        print("Searching for package information in pypi")
        name, release = self.parse_name()
        info = self.get_info(name)
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

    def __init__(self, **kwargs):
        Verifier.__init__(self, **kwargs)
        self.key_url = kwargs.get('key_url', None)
        self.package_path = kwargs.get('package_path', None)
        self.package_check = kwargs.get('package_check', None)
        self.interactive = kwargs.get('interactive', False)
        if not self.key_url and self.package_check:
            # signature exists locally, don't try to download self.url
            self.key_url = self.url.rstrip('/') + get_file_ext(self.package_check)
        if not self.key_url and self.url:
            # signature does not exist locally, find signature url from self.url,
            # may require a HEAD request.
            self.key_url = get_signature_url(self.url)
        if not self.package_sign_path:
            # the key exists (or will exist) at
            # <package directory>/<key url basename>
            self.package_sign_path = os.path.join(os.path.dirname(self.package_path),
                                                  os.path.basename(self.key_url))

    def get_pubkey_path(self):
        keyid = get_keyid(self.package_sign_path)
        if keyid:
            return PUBKEY_PATH.format(keyid)

    def get_sign(self):
        code = self.download_file(self.key_url, self.package_sign_path)
        if code == 200:
            return True
        else:
            msg = "Unable to download file {} http code {}"
            self.print_result(False, msg.format(self.key_url, code))

    def verify(self, recursion=False):
        global KEYID
        global EMAIL
        print("Verifying GPG signature\n")
        if os.path.exists(self.package_path) is False:
            self.print_result(False, err_msg='{} not found'.format(self.package_path))
            return None
        if os.path.exists(self.package_sign_path) is False and self.get_sign() is not True:
            self.print_result(False, err_msg='{} not found'.format(self.package_sign_path))
            return None
        if sign_isvalid(self.package_sign_path) is False:
            self.print_result(False, err_msg='{} is not a GPG signature'.format(self.package_sign_path))
            os.unlink(self.package_sign_path)
            return None
        pub_key = self.get_pubkey_path()
        EMAIL = parse_key(pub_key, r':user ID packet: ".* <(.+?)>"\n')
        if not pub_key or os.path.exists(pub_key) is False:
            key_id = get_keyid(self.package_sign_path)
            self.print_result(False, 'Public key {} not found in keyring'.format(key_id))
            if self.interactive is True and recursion is False and attempt_key_import(key_id):
                print(SEPT)
                return self.verify(recursion=True)
            return None
        sign_status = verify_cli(pub_key, self.package_path, self.package_sign_path)
        if sign_status is None:
            if config.old_keyid:
                compare_keys(KEYID_TRY, config.old_keyid)
            self.print_result(self.package_path)
            KEYID = KEYID_TRY
            config.signature = self.key_url
            config.config_opts['verify_required'] = True
            config.rewrite_config_opts(os.path.dirname(self.package_path))
            return True
        else:
            self.print_result(False, err_msg=sign_status.strerror)
            self.quit()


def quit_verify():
    print_error("verification required for build (verify_required option set)")
    Verifier.quit()


# GEM Verifier
class GEMShaVerifier(Verifier):

    def __init__(self, **kwargs):
        self.package_path = kwargs.get('package_path', None)
        Verifier.__init__(self, **kwargs)

    @staticmethod
    def get_rubygems_info(package_name):
        url = RUBYORG_API.format(package_name)
        data = BytesIO()
        curl = pycurl.Curl()
        curl.setopt(curl.URL, url)
        curl.setopt(curl.WRITEFUNCTION, data.write)
        curl.perform()
        json_data = json.loads(data.getvalue().decode('utf-8'))
        return json_data

    @staticmethod
    def get_gemnumber_sha(gems, number):
        mygem = [gem for gem in gems if gem.get('number', -100) == number]
        if len(mygem) == 1:
            return mygem[0].get('sha', None)
        else:
            return None

    def verify(self):
        gemname = os.path.basename(self.package_path).replace('.gem', '')
        print("Verifying SHA256 checksum\n")
        if os.path.exists(self.package_path) is False:
            self.print_result(False, 'GEM was not found {}'.format(self.package_path))
            return
        name, _ = re.split('-\d+\.', gemname)
        number = gemname.replace(name + '-', '')
        geminfo = self.get_rubygems_info(name)
        gemsha = self.get_gemnumber_sha(geminfo, number)

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
    return os.path.splitext(filename)[1]


def get_verifier(filename):
    ext = get_file_ext(filename)
    return VERIFIER_TYPES.get(ext, None)


def get_input(message, default):
    try:
        import_key = input(message)
        if import_key == '':
            import_key = default
        return import_key.lower() == 'y'
    except:
        return None


def input_timeout(signum, frame):
    print('\ninput timed out')
    raise Exception('keyboard timed out')


class InputGetter(object):

    def __init__(self, message='?', default='N', timeout=INPUT_GETTER_TIMEOUT):
        self.message = message
        self.default = default
        self.timeout = timeout
        signal.signal(signal.SIGALRM, input_timeout)

    def get_answer(self):
        signal.alarm(self.timeout)
        inpt = get_input(self.message, self.default)
        signal.alarm(0)
        return inpt


def attempt_key_import(keyid):
    print(SEPT)
    ig = InputGetter('\nDo you want to attempt to import keyid {}: (y/N) '.format(keyid))
    import_key_answer = ig.get_answer()
    if import_key_answer in [None, False]:
        return False
    with cli_gpg_ctx() as ctx:
        err, _ = ctx.import_key(keyid)
        if err is not None:
            print_error(err.strerror)
            return False
        err, key_content = ctx.export_key(keyid)
        if err is not None:
            print_error(err.strerror)
        key_fullpath = PUBKEY_PATH.format(keyid)
        with open(key_fullpath, 'w') as out_pubkey:
            out_pubkey.write(key_content)
            out_pubkey.close()
        print('\n')
        print_success('Public key id: {} was imported'.format(keyid))
        err, content = ctx.display_keyinfo(key_fullpath)
        if err is not None:
            print_error('Unable to parse {}, will be removed'.format(key_fullpath))
            os.unlink(key_fullpath)
            return False
        print('\n', '\n'.join(content.split('\n')[:10]))
        ig = InputGetter(message='\nDo you want to keep this key: (Y/n) ', default='y')
        if ig.get_answer() is True:
            return True
        else:
            os.unlink(key_fullpath)
    return False


def parse_key(filename, pattern, verbose=True):
    """
    Parse gpg --list-packet signature for pattern, return first match
    """
    args = ["gpg", "--list-packet", filename]
    try:
        out, err = Popen(args, stdout=PIPE, stderr=PIPE).communicate()
        if err.decode('utf-8') != '' and verbose is True:
            print(err.decode('utf-8'))
            return None
        out = out.decode('utf-8')
        match = re.search(pattern, out)
        return match.group(1).strip() if match else None
    except:
        return None
    return None


def get_keyid(sig_filename):
    global KEYID_TRY
    keyid = parse_key(sig_filename, r'keyid (.+?)\n')
    KEYID_TRY = keyid
    return keyid.upper() if keyid else None


def sign_isvalid(sig_filename):
    keyid = parse_key(sig_filename, r'keyid (.+?)\n', verbose=False)
    return keyid is not None


def attempt_to_download(url, sign_filename=None):
    """Download file helper"""
    with open(sign_filename, 'wb') as f:
        curl = pycurl.Curl()
        curl.setopt(curl.URL, url)
        curl.setopt(curl.WRITEDATA, f)
        curl.setopt(curl.FOLLOWLOCATION, True)
        try:
            curl.perform()
        except pycurl.error as e:
            print(e.args)
            return None
        code = curl.getinfo(pycurl.HTTP_CODE)
        curl.close()
        if code != 200:
            os.unlink(sign_filename)
        return code
    return None


def filename_from_url(url):
    return os.path.basename(url)


def print_success(msg):
    print("\033[92mSUCCESS:\033[0m {}".format(msg))


def print_error(msg):
    print("\033[91mERROR  :\033[0m {}".format(msg))


def print_info(msg):
    print("\033[93mINFO   :\033[0m {}".format(msg))


def apply_verification(verifier, **kwargs):
    if verifier is None:
        print_error("Package is not verifiable (yet)")
    else:
        v = verifier(**kwargs)
        return v.verify()


def from_url(url, download_path, interactive=True):
    package_name = filename_from_url(url)
    package_path = os.path.join(download_path, package_name)
    verifier = get_verifier(package_name)
    return apply_verification(verifier, **{
                              'package_path': package_path,
                              'url': url,
                              'interactive': interactive})


def from_disk(url, package_path, package_check, interactive=True):
    verifier = get_verifier(package_path)
    return apply_verification(verifier, **{
                              'package_path': package_path,
                              'package_check': package_check,
                              'url': url,
                              'interactive': interactive})


def attempt_verification_per_domain(package_path, url):
    netloc = urlparse(url).netloc
    if 'pypi' in netloc:
        domain = 'pypi'
    elif 'download.gnome.org' in netloc:
        domain = 'gnome.org'
    else:
        domain = 'unknown'
    verifier = {
        'pypi': PyPiVerifier,
        'gnome.org': GnomeOrgVerifier,
    }.get(domain, None)

    if verifier is None:
        return None
    else:
        print_info('Verification based on domain {}'.format(domain))
        return apply_verification(verifier, **{
                                  'package_path': package_path,
                                  'url': url})


def get_integrity_file(package_path):
    if os.path.exists(package_path + '.asc'):
        return package_path + '.asc'
    if os.path.exists(package_path + '.sig'):
        return package_path + '.sig'
    if os.path.exists(package_path + '.sign'):
        return package_path + '.sign'
    if os.path.exists(package_path + '.sha256'):
        return package_path + '.sha256'


def check(url, download_path, interactive=True):
    package_name = filename_from_url(url)
    package_path = os.path.join(download_path, package_name)
    package_check = get_integrity_file(package_path)
    try:
        interactive = interactive and sys.stdin.isatty()
    except ValueError:
        interactive = False
    print(SEPT)
    print('Performing package integrity verification\n')
    verified = None
    if package_check is not None:
        verified = from_disk(url, package_path, package_check, interactive=interactive)
    elif package_path[-4:] == '.gem':
        verified = from_url(url, download_path, interactive=interactive)
    else:
        print_info('{}.asc or {}.sha256 not found'.format(package_name, package_name))
        signature_url = get_signature_url(url)
        if signature_url is not None:
            print_info('Attempting to download {}'.format(signature_url))
            verified = from_url(url, download_path)
            if verified is None:
                print_info('Unable to find a signature, attempting domain verification')
                verified = attempt_verification_per_domain(package_path, url)
        elif get_hash_url(url) is not None:
            hash_url = get_hash_url(url)
            print_info('Attempting to download {} for domain verification'.format(hash_url))
            verified = attempt_verification_per_domain(package_path, url)

    if verified is None and config.config_opts['verify_required']:
        quit_verify()
    return verified


def parse_args():
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
    specfile.keyid = KEYID
    specfile.email = EMAIL


def main(args):
    from_disk(args.url, args.tar, args.sig)


if __name__ == '__main__':
    main(parse_args())
