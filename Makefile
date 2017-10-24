check: libautospec/*.py scripts/*.py
	@flake8 --max-line-length=199 --ignore=E722 $^

test_pkg_integrity:
	PYTHONPATH=${CURDIR} python3 tests/test_pkg_integrity.py

test_tarball:
	PYTHONPATH=${CURDIR} python3 tests/test_tarball.py

test_specfile:
	PYTHONPATH=${CURDIR} python3 tests/test_specfile.py

test_abireport:
	PYTHONPATH=${CURDIR} python3 tests/test_abireport.py

test_commitmessage:
	PYTHONPATH=${CURDIR} python3 tests/test_commitmessage.py

test_files:
	PYTHONPATH=${CURDIR} python3 tests/test_files.py

test_license:
	PYTHONPATH=${CURDIR} python3 tests/test_license.py

test_buildpattern:
	PYTHONPATH=${CURDIR} python3 tests/test_buildpattern.py

test_build:
	PYTHONPATH=${CURDIR} python3 tests/test_build.py

test_buildreq:
	PYTHONPATH=${CURDIR} python3 tests/test_buildreq.py

test_specdescription:
	PYTHONPATH=${CURDIR} python3 tests/test_specdescription.py

test_count:
	PYTHONPATH=${CURDIR} python3 tests/test_count.py

test_test:
	PYTHONPATH=${CURDIR} python3 tests/test_test.py

test_util:
	PYTHONPATH=${CURDIR} python3 tests/test_util.py

test_libautospec:
	PYTHONPATH=${CURDIR} python3 tests/test_libautospec.py -c ${CASES}

unittests:
	PYTHONPATH=${CURDIR} python3 -m unittest discover -b -s tests -p 'test_*.py'
