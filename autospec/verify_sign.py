#!/usr/bin/env python3

import os
import re
import argparse
import shutil, tempfile
import pycurl
import base64
import hashlib
import json
from io import BytesIO
from contextlib import contextmanager
from socket import timeout
from urllib.error import HTTPError, URLError
from html.parser import HTMLParser


GPG_CLI = False 
DESCRIPTION = "Performs package signature verification for packages signed with gpg."

USAGE = """
Verify package signature when public key present in default keyring:
{fn} --sig package.tar.gz.asc --tar package.tar.gz

Verify package signature when public key is provided as cleartext 
{fn} --sig package.tar.gz.asc --tar package.tar.gz --pubkey package_author.pubkey

Verify package signature when public key is in a keyring different from default keyring
{fn} --sig package.tar.gs.asc --tar package.tar.gz --gnupghome /opt/pki/gpghome

Verify package signature when public key is provided as a file and keyring is different from default
{fn} --sig package.tar.gs.asc --tar package.tar.gs --pubkey package_author.pubkey --gnupghome /opt/pki/gpghome

""".format(fn=__file__)


# Use gpgme if available
try:
    import gpgme as _gpg
except Exception as e:
    from subprocess import Popen, PIPE
    GPG_CLI = True

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
            _gpghome = home if home is not None else tempfile.mkdtemp(prefix='tmp.gpghome')
            os.environ['GNUPGHOME'] = _gpghome
            args = ['gpg', '--import', pubkey]
            output, err, code = self.exec_cmd(args)
            if code != 0:
               raise Exception(err.decode('utf-8'))
            #self.args = ['gpg', '--keyring', os.path.join(_gpghome, 'pubring.gpg'), '--verify']
        #else:
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
            _gpghome = tempfile.mkdtemp(prefix='tmp.gpghome') if gpghome is None else gpghome
            yield GPGCli(pubkey, _gpghome)
        finally:
            if gpghome is None:
                del os.environ['GNUPGHOME']
                shutil.rmtree(_gpghome, ignore_errors=True)

@contextmanager
def gpg_ctx(pubkey=None, gpghome=None):

    if pubkey is None:
        yield _gpg.Context()
    else:
        _gpghome = tempfile.mkdtemp(prefix='tmp.gpghome')
        os.environ['GNUPGHOME'] = _gpghome
        try:
            ctx = _gpg.Context()
            with open(pubkey, 'rb') as f:
                _pubkey = BytesIO(f.read())
            result = ctx.import_(_pubkey)
            key = ctx.get_key(result.imports[0][0])
            ctx.signers = [key]
            yield ctx
        finally:
            if gpghome is None:
                del os.environ['GNUPGHOME']
                shutil.rmtree(_gpghome, ignore_errors=True)

# Use gpgme python wrapper
def verify_gpgme(pubkey, tarball, signature, gpghome=None):
    with open(signature, 'rb') as f:
        signature = BytesIO(f.read())
    with open(tarball, 'rb') as f:
        tarball = BytesIO(f.read())
    with gpg_ctx(pubkey, gpghome) as ctx:
        sigs = ctx.verify(signature, tarball, None)
        return sigs[0].status
    raise Exception('Verification did not take place')

# Use gpg command line
def verify_cli(pubkey, tarball, signature, gpghome=None):
    with cli_gpg_ctx(pubkey, gpghome) as ctx:
        return ctx.verify(pubkey, tarball, signature)
    raise Exception('Verification did not take place using cli')


class Verifier(object):

    def __init__(self, **kwargs):
        self.url = kwargs.get('url', None)
        self.package_path = kwargs.get('package_path', None)
        print("-----------------------------------------------------------------------")

    @staticmethod
    def download_key(url, destination):
        return attempt_to_download(url, destination)

    def print_result(self, result, err_msg=''):
        package_name = os.path.basename(self.url)
        if result:
           print_success("{} verification was successful".format(package_name))
        else:
           print_error("{} verification failed {}".format(package_name, err_msg))

    def __del__(self):
        print("-----------------------------------------------------------------------")

## GPG Verification
class GPGVerifier(Verifier):

    def __init__(self, **kwargs):
        Verifier.__init__(self, **kwargs)
        self.key_url = kwargs.get('key_url', None)
        if self.key_url is None:
            self.key_url = self.url + '.asc'
        self.package_sign_path = self.package_path + '.asc'


    def verify(self, tarfile_path):
        print("Performing GPG signature validation for package\n")
        code = self.download_key(self.key_url, self.package_sign_path)
        if code == 200:
            keyid = get_keyid(self.package_sign_path)
            pub_key = '/'.join([os.path.dirname(os.path.abspath(__file__)), "keyring", "{}.pkey".format(keyid)])
            if not os.path.exists(pub_key):
                return print_error("Public key id {} was not found in keyring".format(keyid))
        else:
            return print_error("Unable to download file {}, returned code {}".format(self.key_url, code))
        sign_status = {
            True: verify_cli,
            False: verify_gpgme,
        }[GPG_CLI](*[pub_key, self.package_path, self.package_sign_path])
        if sign_status is None:
            self.print_result(tarfile_path)
        else:
            print_error(tarfile_path, sign_status.strerror)


## GEM Verifier
class GEMHashVerifier(Verifier):

    def __init__(self, **kwargs):
        Verifier.__init__(self, **kwargs)

    @staticmethod
    def get_rubygems_info(package_name):
        url = "https://rubygems.org/api/v1/versions/{}.json".format(package_name)
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

    def calc_sha(self, gemfile_path):
        BLOCK_SIZE = 4096
        with open(gemfile_path, 'rb') as gem:
            sha256 = hashlib.sha256()
            for block in iter(lambda: gem.read(BLOCK_SIZE), b''):
                sha256.update(block)
            return sha256.hexdigest()

    def verify(self, gemfile_path):
        print("Performing sha validation for package\n")
        gemname = os.path.basename(gemfile_path).replace('.gem', '')
        name, _ = re.split('-\d+\.', gemname)
        number = gemname.replace(name+'-', '')
        geminfo = self.get_rubygems_info(name)
        gemsha = self.get_gemnumber_sha(geminfo, number)

        if geminfo is None:
            print_error("unable to parse info for gem {}".format(gemname))
        else:
            calcsha = self.calc_sha(gemfile_path)
            self.print_result(gemsha == calcsha)

VERIFIERS = {
    '.gz':  GPGVerifier,
    '.gem': GEMHashVerifier,
}


def get_file_ext(filename):
    return os.path.splitext(filename)[1]

def get_verifier(filename):
    ext = get_file_ext(filename)
    return VERIFIERS.get(ext, None) 


def save_file_conditionally(data, filename):
    if filename is not None:
        with open(filename, 'w') as f:
            f.write(data)
    return data


def is_b64(line):
    if line == '' or "----" in line or \
       "Version" in line or "Comment" in line:
        return False
    elif line[-5] == '=':
        return False
    return True


def parse_sign(filename):
    with open(filename, 'r') as f:
        lines = f.read().split('\n')
        sign = ''.join([l for l in lines if is_b64(l.strip())])
        return sign

def parse_keyid(sig_filename):
    args = ["gpg", "--list-packet", sig_filename]
    out, err = Popen(args, stdout=PIPE, stderr=PIPE).communicate()
    if err.decode('utf-8') != '':
        print(err.decode('utf-8'))
        return None
    out = out.decode('utf-8')
    ai = out.index('keyid') + 6
    bi = ai + 16
    return out[ai:bi]


def get_keyid(sig_filename):
    keyid = parse_keyid(sig_filename)
    return keyid.upper()



def attempt_to_download(url, sign_filename=None):
    """Download file helper"""
    with open(sign_filename, 'wb') as f:
        curl = pycurl.Curl()
        curl.setopt(curl.URL, url)
        curl.setopt(curl.WRITEDATA, f)
        curl.setopt(curl.FOLLOWLOCATION, True)
        curl.perform()
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

def from_url(url, download_path):
    package_name = filename_from_url(url)
    package_path = os.path.join(download_path, package_name)
    verifier = get_verifier(package_name)
    if verifier is None:
        print_error("File {} is not verifiable (yet)".format(package_name))
    else:
        v = verifier(package_path=package_path, url=url)
        v.verify(package_path)

def parse_args():
    parser = argparse.ArgumentParser(usage=USAGE, description=DESCRIPTION)
    parser.add_argument('--tar', help='tar file to check signature', required=True)
    parser.add_argument('--sig', help='Signature file', required=True)
    parser.add_argument('--pubkey', help='Public key to use for signature verification', required=False, default=None)
    parser.add_argument('--gnupghome', help='GNUPGHOME', required=False, default=None)
    return parser.parse_args()


def main(args):
    if is_verifiable(args.tar) == False:
        print("File {} type is not verifiable (yet)".format(args.tar))
    sign_status = verify(args.pubkey, args.tar, args.sig, args.gnupghome)
    if sign_status is None:
        print('OK')
        exit(0)
    else:
        print(sign_status.strerror)
        exit(1)


if __name__ == '__main__':
    main(parse_args())

