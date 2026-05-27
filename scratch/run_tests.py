import pytest
import sys

if __name__ == "__main__":
    retcode = pytest.main(["tests/test_polish.py"])
    sys.exit(retcode)
