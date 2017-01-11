#!/usr/bin/env python3

import os
import re
import argparse
import shutil
import tempfile
import pycurl
import hashlib
import json
from io import BytesIO
from contextlib import contextmanager
from subprocess import Popen, PIPE

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
KEYID_TRY = ""
KEYID = ""
EMAIL = ""


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
        out, err = proc.communicate()
        return out, err, proc.returncode

    def __init__(self, pubkey=None, home=None):
        if pubkey is not None:
            _gpghome = home
            if _gpghome is None:
                _gpghome = tempfile.mkdtemp(prefix='tmp.gpghome')
            os.environ['GNUPGHOME'] = _gpghome
            args = ['gpg', '--import', pubkey]
            output, err, code = self.exec_cmd(args)
            if code != 0:
                raise Exception(err.decode('utf-8'))
        self.args = ['gpg', '--verify']

    def verify(self, _, tarfile, signature):
        args = self.args + [signature, tarfile]
        output, err, code = self.exec_cmd(args)
        if code == 0:
            return None
        return GPGCliStatus(err.decode('utf-8'))


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
        package_name = ''
        if self.url is not None:
            package_name = os.path.basename(self.url)
        if result:
            msg = "{} verification was successful".format(package_name)
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
    curl.perform()
    http_code = curl.getinfo(pycurl.HTTP_CODE)
    curl.close()
    return http_code


def get_signature_url(package_url):
    if '://pypi.' in package_url[:13]:
        return package_url + '.asc'
    elif '.gnu.' in package_url:
        return package_url + '.sig'
    elif 'mirrors.kernel.org' in package_url:
        return package_url + '.sig'
    else:
        if head_request(package_url + '.sig') == 200:
            return package_url + '.sig'
        if head_request(package_url + '.asc') == 200:
            return package_url + '.asc'
        if head_request(package_url + '.sign') == 200:
            return package_url + '.sign'
    return None


# GPG Verification
class GPGVerifier(Verifier):

    def __init__(self, **kwargs):
        Verifier.__init__(self, **kwargs)
        self.key_url = kwargs.get('key_url', None)
        self.package_path = kwargs.get('package_path', None)
        if self.key_url is None and self.url is not None:
            self.key_url = get_signature_url(self.url)
        if self.package_sign_path is None:
            self.package_sign_path = self.package_path + '.asc'

    def get_pubkey_path(self):
        keyid = get_keyid(self.package_sign_path)
        if keyid:
            return '/'.join([os.path.dirname(os.path.abspath(__file__)),
                            "keyring", "{}.pkey".format(keyid)])

    def get_sign(self):
        code = self.download_file(self.key_url, self.package_sign_path)
        if code == 200:
            return True
        else:
            msg = "Unable to download file {} http code {}"
            self.print_result(False, msg.format(self.key_url, code))

    def verify(self):
        global KEYID
        global EMAIL
        print("Verifying GPG signature\n")
        if os.path.exists(self.package_path) is False:
            self.print_result(False, err_msg='{} not found'.format(self.package_path))
            if config.config_opts['verify_required']:
                self.quit_verify()
            return None
        if os.path.exists(self.package_sign_path) is False and self.get_sign() is not True:
            self.print_result(False, err_msg='{} not found'.format(self.package_sign_path))
            if config.config_opts['verify_required']:
                self.quit_verify()
            return None
        if sign_isvalid(self.package_sign_path) is False:
            self.print_result(False, err_msg='{} is not a GPG signature'.format(self.package_sign_path))
            if config.config_opts['verify_required']:
                self.quit_verify()
            return None
        pub_key = self.get_pubkey_path()
        EMAIL = parse_key(pub_key, r':user ID packet: ".* <(.+?)>"\n')
        if not pub_key or os.path.exists(pub_key) is False:
            key_id = get_keyid(self.package_sign_path)
            self.print_result(False, 'Public key {} not found in keyring'.format(key_id))
            if config.config_opts['verify_required']:
                self.quit_verify()
            return None
        sign_status = verify_cli(pub_key, self.package_path, self.package_sign_path)
        if sign_status is None:
            self.print_result(self.package_path)
            KEYID = KEYID_TRY
            config.config_opts['verify_required'] = True
            config.rewrite_config_opts()
            return True
        else:
            self.print_result(False, err_msg=sign_status.strerror)
            self.quit()

    def quit_verify(self):
        print_error("verification required for build (verify_required option set)")
        self.quit()


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
    '.gem': GEMShaVerifier,
}


def get_file_ext(filename):
    return os.path.splitext(filename)[1]


def get_verifier(filename):
    ext = get_file_ext(filename)
    return VERIFIER_TYPES.get(ext, None)


def parse_key(filename, pattern, verbose=True):
    """
    Parse gpg --list-packet signature for pattern, return first match
    """
    args = ["gpg", "--list-packet", filename]
    try:
        out, err = Popen(args, stdout=PIPE, stderr=PIPE).communicate()
        if err.decode('utf-8') != '' and verbose == True:
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


def from_url(url, download_path):
    package_name = filename_from_url(url)
    package_path = os.path.join(download_path, package_name)
    verifier = get_verifier(package_name)
    return apply_verification(verifier, **{
                              'package_path': package_path,
                              'url': url, })


def from_disk(package_path, package_check):
    verifier = get_verifier(package_path)
    return apply_verification(verifier, **{
                              'package_path': package_path,
                              'package_check': package_check, })


def get_integrity_file(package_path):
    if os.path.exists(package_path + '.asc'):
        return package_path + '.asc'
    if os.path.exists(package_path + '.sig'):
        return package_path + '.sig'
    if os.path.exists(package_path + '.sign'):
        return package_path + '.sign'
    if os.path.exists(package_path + '.sha256'):
        return package_path + '.sha256'


def check(url, download_path):
    package_name = filename_from_url(url)
    package_path = os.path.join(download_path, package_name)
    package_check = get_integrity_file(package_path)
    print(SEPT)
    print('Performing package integrity verification\n')
    if package_check is not None:
        return from_disk(package_path, package_check)
    elif package_path[-4:] == '.gem':
        return from_url(url, download_path)
    else:
        print_info('{}.asc or {}.sha256 not found'.format(package_name, package_name))
        signature_url = get_signature_url(url)
        if signature_url is not None:
            print_info('Attempting to download {}'.format(signature_url))
            return from_url(url, download_path)
        print_info('Unable to find a url for package signature')
        return None


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
    from_disk(args.tar, args.sig)


if __name__ == '__main__':
    main(parse_args())
