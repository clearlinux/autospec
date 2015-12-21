check: autospec/*.py
	@python3 /usr/bin/flake8 --max-line-length=199 --ignore=E402 $^
