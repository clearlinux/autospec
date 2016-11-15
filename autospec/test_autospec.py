"""
autospec test suite
"""
import tarfile
import os
import shutil
import subprocess
import importlib
import multiprocessing
import getpass
import errno
from difflib import unified_diff

IGNORES = set(['expectations.py',
               'spec-expectations',
               '__pychache__',
               'autospecdir'])
BASEDIR = os.getcwd()
TESTDIR = BASEDIR + '/testfiles'


def tar_source(srcfiles):
    """tar the files in the testfiles directory"""
    os.chdir(TESTDIR)
    tar = tarfile.open('{}.tar.gz'.format(srcfiles), 'w:gz')
    files = set(os.listdir(srcfiles)).difference(IGNORES)
    for file in files:
        tar.add('{}/{}'.format(srcfiles, file))

    tar.close()
    os.chdir(BASEDIR)


def build_and_run(srctar, expectations, entry, test_results):
    """run make autospec against the tarball, then run the tests"""
    dest = '{}/test-{}'.format(TESTDIR, entry)
    add_files(srctar, entry, dest)
    os.chdir(dest)
    output = "".encode('utf-8')
    # pylint: disable=broad-except
    # pass on any exception because the build failure will be reported later
    try:
        output = subprocess.check_output(
            ['python3', '{}/autospec.py'.format(BASEDIR),
             '-n', entry, '-t', '.',
             '--config', '{}/autospec.conf'.format(TESTDIR),
             'file://{}/{}'.format(TESTDIR, srctar)])
    except Exception:
        pass

    print('Testing output for {}'.format(entry))
    if check_output(output, expectations, entry, test_results):
        with open('{}.spec'.format(entry), 'r') as spec_file:
            spc = spec_file.read()
            check_spec(spc, expectations, entry, test_results)

    os.chdir(BASEDIR)


def add_files(srctar, entry, dest):
    """add necessary files to the autospec test directory"""
    try:
        os.mkdir(dest)
    except OSError as excep:
        # errno 17 is a FileExists error
        if excep.errno is not 17:
            raise

    for file in os.listdir('{}/{}/autospecdir'.format(TESTDIR, entry)):
        shutil.copy2('{}/{}/autospecdir/{}'.format(TESTDIR, entry, file), dest)


def check_output(output, expectations, entry, test_results):
    """
    test the output of the autospec run against the expectations defined in
    expectations.py
    """
    if 'build successful' in output.decode('utf-8'):
        test_results[entry].append('PASS: Build status - successful')
        print('{} build successful'.format(entry))
    else:
        test_results[entry].append('FAIL: Build status - failed, '
                                   'skipping remaining tests')
        print('{} build failed'.format(entry))
        return False

    for item in expectations.output_strings:
        if item not in output:
            test_results[entry].append('FAIL: "{}" expected in output, but not'
                                       ' present'.format(item))
        else:
            test_results[entry].append('PASS: "{}" found in output'
                                       .format(item))
    return True


def check_spec(spec_contents, expectations, entry, test_results):
    """test the specfile against the expected specfile in spec-expectations"""
    diff = list(unified_diff(expectations.specfile,
                             spec_contents.split('\n'),
                             fromfile='expected_specfile',
                             tofile='generated_specfile'))
    if len(diff):
        test_results[entry].append('FAIL: generated specfile different from '
                                   'expected\n')
        for line in diff:
            test_results[entry][-1] += '\n{}'.format(line)

        test_results[entry][-1] += '\n'
    else:
        test_results[entry].append('PASS: generated specfile matches expected')

    # the following checks are superflous, but can give more granular
    # indications of what has gone wrong
    if expectations.license not in spec_contents:
        test_results[entry].append('FAIL: license not detected as "{}"'
                                   .format(expectations.license))
    else:
        test_results[entry].append('PASS: license correctly detected as "{}"'
                                   .format(expectations.license))

    for item in expectations.buildreqs:
        if item not in spec_contents:
            test_results[entry].append('FAIL: expected "{}" to be a build '
                                       'requirement, but was not found'
                                       .format(item))
        else:
            test_results[entry].append('PASS: build requirement "{}" '
                                       'successfully detected'.format(item))


def clean_up(entry):
    """clean up generated files and directories"""
    # try to remove each directory/file in turn
    shutil.rmtree('/tmp/{}'.format(getpass.getuser()), ignore_errors=True)
    shutil.rmtree('{}/{}/__pycache__'.format(TESTDIR, entry), ignore_errors=True)
    shutil.rmtree('{}/test-{}'.format(TESTDIR, entry), ignore_errors=True)
    try:
        os.remove('{}/{}.tar.gz'.format(TESTDIR, entry))
    except OSError as excep:
        if excep.errno != errno.ENOENT:
            raise


def print_results(entry, test_results):
    """pretty-print the results of the tests"""
    title = 'Test results for {}'.format(entry)
    line = ''
    for _ in range(len(title)):
        line += '-'

    print(line)
    print(title)
    print(line)
    print('\n')

    failures = 0
    passes = 0

    for result in test_results[entry]:
        print(result)
        if 'PASS' in result:
            passes += 1
        else:
            failures += 1

    print('\nFailed tests: {}'.format(failures))
    print('Passed tests: {}'.format(passes))
    print(line)
    print('\n')


def process_source(entry, test_results):
    """run autospec against entry and store the test results in test_results"""
    shutil.rmtree('{}/test-{}'.format(TESTDIR, entry), ignore_errors=True)
    expectations = importlib.import_module('testfiles.{}.expectations'
                                           .format(entry))
    tar_source(entry)
    print('Building {}'.format(entry))
    build_and_run('{}.tar.gz'.format(entry), expectations, entry, test_results)
    clean_up(entry)
    print_results(entry, test_results)


def main():
    """split off threads to run autospec and test the specfile and output"""
    test_results = {}
    results_list = []

    pool = multiprocessing.Pool()
    packages = (ent for ent in os.listdir(TESTDIR)
                if 'tar' not in ent
                and 'test-' not in ent
                and 'autospec.conf' not in ent)
    for entry in packages:
        test_results[entry] = []
        res = pool.apply_async(process_source, (entry, test_results))
        results_list.append(res)

    pool.close()
    pool.join()
    for result in results_list:
        result.get()


if __name__ == '__main__':
    main()
