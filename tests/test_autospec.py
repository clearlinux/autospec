"""
autospec test suite
"""
import tarfile
import os
import re
import shutil
import subprocess
import importlib
import multiprocessing
import getpass
import errno
import argparse
from difflib import unified_diff

IGNORES = set(['expectations.py',
               'spec-expectations',
               '__pychache__',
               'autospecdir'])
NOT_PACKAGE = ['.tar', 'test', 'autospec.conf', 'results']
BASEDIR = os.getcwd()
TESTDIR = BASEDIR + '/tests/testfiles'
PCOLOR = '\033[92m'
FCOLOR = '\033[91m'
ENDCOLOR = '\033[0m'


def fmt_fail(msg):
    """returns colored and formatted failure message"""
    return '{}FAIL:{} {}'.format(FCOLOR, ENDCOLOR, msg)


def fmt_pass(msg):
    """returns colored and formatted pass message"""
    return '{}PASS:{} {}'.format(PCOLOR, ENDCOLOR, msg)


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
            ['python3', '{}/autospec/autospec.py'.format(BASEDIR),
             '-n', entry, '-t', '.',
             'file://{}/{}'.format(TESTDIR, srctar)])
    except Exception:
        pass

    print('Testing output for {}'.format(entry))
    if check_output(output.decode('utf-8'), expectations, entry, test_results):
        with open('{}.spec'.format(entry), 'r') as spec_file:
            spc = spec_file.read()
            check_spec(spc, expectations, entry, test_results)
        with open('options.conf', 'r') as conf_file:
            check_conf(conf_file.read(), expectations, entry, test_results)

    os.chdir(BASEDIR)


def add_files(srctar, entry, dest):
    """add necessary files to the autospec test directory"""
    os.makedirs(dest, exist_ok=True)
    for file in os.listdir('{}/{}/autospecdir'.format(TESTDIR, entry)):
        shutil.copy2('{}/{}/autospecdir/{}'.format(TESTDIR, entry, file), dest)


def check_output(output, expectations, entry, test_results):
    """
    test the output of the autospec run against the expectations defined in
    expectations.py
    """
    if 'build successful' in output:
        test_results[entry].append(fmt_pass('Build status - successful'))
        print('{} build successful'.format(entry))
    else:
        test_results[entry].append(fmt_fail('Build status - failed, '
                                            'skipping remaining tests'))
        print('{} build failed'.format(entry))
        os.makedirs('{}/results'.format(TESTDIR), exist_ok=True)
        try:
            shutil.copy2('{}/test-{}/results/build.log'.format(TESTDIR, entry),
                         '{}/results/{}-build.log'.format(TESTDIR, entry))
            shutil.copy2('{}/test-{}/mock_srpm.log'.format(TESTDIR, entry),
                         '{}/results/{}-mock_srpm.log'.format(TESTDIR, entry))
            shutil.copy2('{}/test-{}/mock_build.log'.format(TESTDIR, entry),
                         '{}/results/{}-mock_build.log'.format(TESTDIR, entry))
            print('check {}/results/ for more logfiles and output'
                  .format(TESTDIR, entry))
        except Exception:
            print('no build log found')
        with open('{}/results/{}.out'.format(TESTDIR, entry), 'w') as outf:
            outf.write(output)

        return False

    for item in expectations.output_strings:
        if item not in output:
            test_results[entry].append(fmt_fail('"{}" expected in output, but '
                                                'not present'.format(item)))
        else:
            test_results[entry].append(fmt_pass('"{}" found in output'
                                                .format(item)))
    return True


def check_spec(spec_contents, expectations, entry, test_results):
    """test the specfile against the expected specfile in spec-expectations"""
    # replace the epoch time with a 1 so it can be tested for
    spec_contents = re.sub(r'SOURCE_DATE_EPOCH=[0-9]+\n',
                           'SOURCE_DATE_EPOCH=1\n',
                           spec_contents)
    diff = list(unified_diff(expectations.specfile,
                             spec_contents.split('\n'),
                             fromfile='expected_specfile',
                             tofile='generated_specfile'))
    if len(diff):
        test_results[entry].append(fmt_fail('generated specfile different from '
                                            'expected\n'))
        for line in diff:
            test_results[entry][-1] += '\n{}'.format(line)

        test_results[entry][-1] += '\n'
    else:
        test_results[entry].append(fmt_pass('generated specfile matches expected'))

    # the following checks are superflous, but can give more granular
    # indications of what has gone wrong
    if expectations.license not in spec_contents:
        test_results[entry].append(fmt_fail('license not detected as "{}"'
                                            .format(expectations.license)))
    else:
        test_results[entry].append(fmt_pass('license correctly detected as "{}"'
                                            .format(expectations.license)))

    for item in expectations.buildreqs:
        if item not in spec_contents:
            test_results[entry].append(fmt_fail('expected "{}" to be a build '
                                                'requirement, but was not found'
                                                .format(item)))
        else:
            test_results[entry].append(fmt_pass('build requirement "{}" '
                                                'successfully detected'
                                                .format(item)))


def check_conf(conf_contents, expectations, entry, test_results):
    """test the specfile against the expected specfile in spec-expectations"""
    diff = list(unified_diff(expectations.conffile,
                             conf_contents.split('\n'),
                             fromfile='expected_conffile',
                             tofile='generated_conffile'))
    if len(diff):
        test_results[entry].append(fmt_fail('generated conf file different '
                                            'from expected\n'))
        for line in diff:
            test_results[entry][-1] += '\n{}'.format(line)

        test_results[entry][-1] += '\n'
    else:
        test_results[entry].append(fmt_pass('generated configuration file '
                                            'matches expected'))


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
    fcolor = ''
    pcolor = ''

    for result in test_results[entry]:
        print(result)
        if 'PASS' in result:
            passes += 1
            pcolor = PCOLOR
        else:
            failures += 1
            fcolor = FCOLOR

    print('\nFailed tests: {}{}{}'.format(fcolor, failures, ENDCOLOR))
    print('Passed tests: {}{}{}'.format(pcolor, passes, ENDCOLOR))
    print(line)
    print('\n')


def process_source(entry, test_results):
    """run autospec against entry and store the test results in test_results"""
    # Remove previous run failure logs
    shutil.rmtree('{}/results'.format(TESTDIR), ignore_errors=True)
    expectations = importlib.import_module('testfiles.{}.expectations'
                                           .format(entry))
    tar_source(entry)
    print('Building {}'.format(entry))
    build_and_run('{}.tar.gz'.format(entry), expectations, entry, test_results)
    print_results(entry, test_results)
    clean_up(entry)


def main():
    """split off threads to run autospec and test the specfile and output"""
    test_results = {}
    results_list = []

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--test-cases", dest="cases", nargs='*',
                        help="List of test cases to run (by package name) "
                        "separated by whitespace")
    args = parser.parse_args()

    pool = multiprocessing.Pool()
    for entry in os.listdir(TESTDIR):
        if any(x in entry for x in NOT_PACKAGE):
            continue
        clean_up(entry)
        if args.cases and entry not in args.cases:
            continue

        test_results[entry] = []
        res = pool.apply_async(process_source, (entry, test_results))
        results_list.append(res)

    pool.close()
    pool.join()
    for result in results_list:
        result.get()


if __name__ == '__main__':
    main()
