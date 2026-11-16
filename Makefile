PYTHON ?= python3
LOGOSC ?= ./tools/logosc.sh

# What survives the cutover are the tests that never touched the Python
# implementation: the gate-list agreement, the C runtime compiled directly, and
# the self-hosting summary lines. They are named rather than discovered, because
# the deleted suites imported `logos` (or ran it as an oracle) and discovery
# would fail on them. Everything else that judged the compiler is a Logos suite
# below, or the corpus.
CONTRACT_TESTS = tests.test_contributing tests.test_runtime tests.test_cli \
	tests.test_qa tests.test_selfhost tests.test_docs

# The seconds-scale loop: everything that judges a change without building the
# compiler twice or running a corpus. `make test` is the gate; this is what an
# agent runs between edits. tests.test_selfhost is the sixth gate end to end
# (about seven minutes) and stays out of it.
FAST_TESTS = tests.test_contributing tests.test_runtime tests.test_cli \
	tests.test_qa tests.test_docs

LOGOS_SUITES = src/logosc/body_test.logos src/logosc/check_test.logos \
	src/logosc/resolve_test.logos src/logosc/lex_test.logos \
	src/logosc/tree_test.logos src/logosc/types_test.logos \
	src/logosc/emit_test.logos src/logosc/fmt_test.logos \
	src/logosc/harness_test.logos

.PHONY: test contract fast suites suites-all fmt dist verify-install release publish clean

# Every tracked `src/logosc/*_test.logos` file is listed above, and
# tests/test_qa.py fails when one is not: six of these nine suites (206 cases:
# lexer, tree, types, emitter, formatter, harness) were in the repository and
# run by nothing until this list grew, which is a suite that cannot fail.
# They run at `-O0` in the gate because every case lowers and links its whole
# module, which makes two levels a ninety-minute gate: the nine suites are about
# four minutes at one level. The corpus already runs every language case at both
# levels, and `make suites-all` is the two-level form. Measure a level
# difference here when you change lowering or the emitter.
test: contract suites

contract:
	$(PYTHON) -m unittest -v $(CONTRACT_TESTS)

fast:
	$(PYTHON) -m unittest $(FAST_TESTS)
	$(LOGOSC) test tests --only regress
	$(LOGOSC) guide --check

suites:
	@for suite in $(LOGOS_SUITES); do \
		echo "== $$suite"; \
		$(LOGOSC) test $$suite --opt -O0 || exit 1; \
	done

suites-all:
	@for suite in $(LOGOS_SUITES); do \
		echo "== $$suite"; \
		$(LOGOSC) test $$suite --opt -O0 --opt -O2 || exit 1; \
	done

fmt:
	$(LOGOSC) fmt .

# Shipping. `dist` assembles the tarball from a compiler built out of src/,
# `verify-install` proves that tarball installs and compiles with nothing but
# itself, and `release` rehearses the whole publish without publishing. The
# version comes from the compiler (`logosc version`), never from this file:
# one string in src/logosc/main.logos is what a release is named after.
dist:
	bash tools/dist.sh

verify-install:
	bash tools/verify_install.sh $$(ls -t dist/logos-*-x86_64-linux.tar.gz | head -n 1)

release:
	bash tools/release.sh

publish:
	bash tools/release.sh --publish

clean:
	rm -rf build dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -f *.o *.ll *.out
