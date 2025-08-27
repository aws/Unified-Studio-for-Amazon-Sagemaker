By default, this package is configured to run PyTest tests
(http://pytest.org/).

## Writing tests

Place test files in this directory, using file names that start with `test_`.

## Running tests

```
$ brazil-build test
```

To configure pytest's behaviour in a single run, you can add options using the --addopts flag:

```
$ brazil-build test --addopts="[pytest options]"
```

For example, to run a single test, or a subset of tests, you can use pytest's
options to select tests:

```
$ brazil-build test --addopts="-k TEST_PATTERN"
```

Code coverage is automatically reported for smus_cicd_pipeline_cli;
to add other packages, modify setup.cfg in the package root directory.

To debug the failing tests:

```
$ brazil-build test --addopts=--pdb
```

This will drop you into the Python debugger on the failed test.

### Importing tests/fixtures

The `test` module is generally not direcrtly importable and it's generally acceptable to use relative imports inside test cases.

### Fixtures

Pytest provides `conftest.py` as a mechanism to store test fixtures.  However, there may be times when it makes sense to include a `test/fixtures` module to locate complex or large fixtures.

### Common Errors

#### ModuleNotFoundError: No module named "test.fixtures"

The `test` and sometimes `test/fixtures` modules need to be importable.  To allow these to be importable, create a `__init__.py` file in each directory.
- `test/__init__.py`
- `test/fixtures/__init__.py` (optional)
