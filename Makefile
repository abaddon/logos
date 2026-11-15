PYTHON ?= python3
LOGOSC ?= ./tools/logosc.sh

# What survives the cutover are the tests that never touched the Python
# implementation: the gate-list agreement, the C runtime compiled directly, and
# the self-hosting summary lines. They are named rather than discovered, because
# the deleted suites imported `logos` (or ran it as an oracle) and discovery
# would fail on them. Everything else that judged the compiler is a Logos suite
# below, or the corpus.
CONTRACT_TESTS = tests.test_contributing tests.test_runtime tests.test_selfhost

LOGOS_SUITES = src/logosc/body_test.logos src/logosc/check_test.logos \
	src/logosc/resolve_test.logos

.PHONY: test contract suites suites-all fmt clean

# The compiler's own suites restate what the deleted white-box tests covered:
# 361 body cases, 80 checker cases and 38 resolver cases. They run at `-O0` in
# the gate because every case lowers and links its whole module, which makes two
# levels a ninety-minute gate; the corpus already runs all 308 language cases at
# both levels, and `make suites-all` is the two-level form. Measure a level
# difference here when you change lowering or the emitter.
test: contract suites

contract:
	$(PYTHON) -m unittest -v $(CONTRACT_TESTS)

suites:
	$(LOGOSC) test src/logosc/body_test.logos --opt -O0
	$(LOGOSC) test src/logosc/check_test.logos --opt -O0
	$(LOGOSC) test src/logosc/resolve_test.logos --opt -O0

suites-all:
	$(LOGOSC) test src/logosc/body_test.logos --opt -O0 --opt -O2
	$(LOGOSC) test src/logosc/check_test.logos --opt -O0 --opt -O2
	$(LOGOSC) test src/logosc/resolve_test.logos --opt -O0 --opt -O2

fmt:
	$(LOGOSC) fmt .

clean:
	rm -rf build dist *.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -f *.o *.ll *.out
