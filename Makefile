check: autospec/*.py
	@flake8 --ignore=B902,D100,I201 $^

test_download:
	PYTHONPATH=${CURDIR}/autospec python3 tests/test_download.py

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

test_config:
	PYTHONPATH=${CURDIR}/autospec python3 tests/test_config.py

test_build:
	PYTHONPATH=${CURDIR}/autospec python3 tests/test_build.py

test_buildreq:
	PYTHONPATH=${CURDIR}/autospec python3 tests/test_buildreq.py

test_specdescription:
	PYTHONPATH=${CURDIR}/autospec python3 tests/test_specdescription.py

test_count:
	PYTHONPATH=${CURDIR}/autospec python3 tests/test_count.py

test_check:
	PYTHONPATH=${CURDIR}/autospec python3 tests/test_check.py

test_util:
	PYTHONPATH=${CURDIR}/autospec python3 tests/test_util.py

test_general:
	PYTHONPATH=${CURDIR}/autospec python3 tests/test_general.py

unittests:
	PYTHONPATH=${CURDIR}/autospec coverage run -m unittest discover -b -s tests -p 'test_*.py' && coverage report

unittests-no-coverage:
	PYTHONPATH=${CURDIR}/autospec python3 -m unittest discover -b -s tests -p 'test_*.py'

coverage:
	coverage report -m
