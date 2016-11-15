check: autospec/*.py
	@python3 /usr/bin/flake8 --max-line-length=199 --ignore=E402 $^

test_verify:
	PYTHONPATH=`pwd`/autospec:${PYTHONPATH} python3 tests/verify_utils.py 
