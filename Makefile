check: autospec/*.py
	@python3 /usr/bin/flake8 --max-line-length=199 --ignore=E402 $^

test_pkg_integrity:
	PYTHONPATH=`pwd` python3 tests/pkg_integrity.py

test_tarball:
	PYTHONPATH=`pwd`/autospec python3 tests/test_tarball.py

test_autospec:
	python3 tests/test_autospec.py
