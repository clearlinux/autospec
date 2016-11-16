check: autospec/*.py
	@python3 /usr/bin/flake8 --max-line-length=199 --ignore=E402 $^

test_pkg_integrity:
	PYTHONPATH=`pwd` python3 tests/pkg_integrity.py 
