#!/usr/bin/env python3

import os
import argparse
import shutil, tempfile
import pycurl
import base64
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


## GPG Verification
class Verifier(object):
    def __init__(self, _type):
        self.type = _type

    def verify(self, *args):
        return


class GPGVerifier(Verifier):

    def __init__(self):
        Verifier.__init__(self, 'GPG')

    def verify(self, *args):
       sign_status = {
            True: verify_cli,
            False: verify_gpgme,
       }[GPG_CLI](*args)
       if sign_status is None:
           print("{} signature verification was \033[92mSUCCESSFUL\033[0m".format(args[1]))
       else:
           print("Verification {} \033[91mFAILED\033[0m with {}".format(args[1], sign_status.strerror))


       
def get_verifier(filename):    
    """Is this file type supported? this initial implementation 
        supports only gpg verification"""
    _, ext = os.path.splitext(filename)
    if ext == '.gz':
        return GPGVerifier
    else:
        return None


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



def attempt_download_sign(url, sign_filename=None):
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


def from_url(url, download_path):
    tarfile = os.path.basename(url)
    tarfile_path = os.path.join(download_path, tarfile)
    print("""Verifying signature for {}
--------------------------------------------------------------------------------""".format(tarfile))
    verifier = get_verifier(tarfile)
    if verifier is None:
        print("File {} is not verifiable (yet)".format(tarfile))
    else:
        tarfile_sign = tarfile + '.asc'
        tarfile_sign_url = url + '.asc' # Right now assuming gpg only
        tarfile_sign_file = os.path.join(download_path, tarfile_sign)
        code = attempt_download_sign(tarfile_sign_url, tarfile_sign_file)
        if code is None:
            return
        elif code == 200:
            keyid = get_keyid(tarfile_sign_file)
            pub_key = '/'.join([os.path.dirname(os.path.abspath(__file__)), "keyring", "{}.pkey".format(keyid)])
            if os.path.exists(pub_key) == False:
                print("Verification \033[91mFAILED\033[0m\nPublic key id {} was not found in keyring".format(pub_key))
            else:
                v = verifier()
                v.verify(pub_key, tarfile_path, tarfile_sign_file)
        #        if sign_status is None:
        #            print("{} signature verification was \033[92mSUCCESSFUL\033[0m".format(tarfile))
        #        else:
        #            print("Verification {} \033[91mFAILED\033[0m with {}".format(tarfile, sign_status.strerror))
        else:
            print("Verification \033[91mFAILED\033[0m attempt to download signature returned {}".format(code))
    print("--------------------------------------------------------------------------------")

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

