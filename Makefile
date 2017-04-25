check: autospec/*.py
	@python3 /usr/bin/flake8 --max-line-length=199 --ignore=E402 $^

test_pkg_integrity:
	PYTHONPATH=${CURDIR}/autospec python3 tests/test_pkg_integrity.py

test_tarball:
	PYTHONPATH=${CURDIR}/autospec python3 tests/test_tarball.py

test_specfile:
	PYTHONPATH=${CURDIR}/autospec python3 tests/test_specfile.py

test_abireport:
	PYTHONPATH=${CURDIR}/autospec python3 tests/test_abireport.py

test_commitmessage:
	PYTHONPATH=${CURDIR}/autospec python3 tests/test_commitmessage.py

test_files:
	PYTHONPATH=${CURDIR}/autospec python3 tests/test_files.py

test_license:
	PYTHONPATH=${CURDIR}/autospec python3 tests/test_license.py

test_buildpattern:
	PYTHONPATH=${CURDIR}/autospec python3 tests/test_buildpattern.py

test_autospec:
	python3 tests/test_autospec.py -c ${CASES}

unittests:
	PYTHONPATH=${CURDIR}/autospec python3 -m unittest discover -b -s tests/ -p 'test_*.py'
