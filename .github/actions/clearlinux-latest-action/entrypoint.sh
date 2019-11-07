#!/bin/bash -lx

run_flake8() {
	make check
}

run_unittests() {
	make unittests
}

if t=$(type -t "$INPUT_TESTFUNC"); then
	if [ "$t" = "function" ]; then
		$INPUT_TESTFUNC
	fi
fi
