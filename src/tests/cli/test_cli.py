
import sys
import dfbar
import pytest

class TestCli:
    def test_1(self):
        sys.argv = ["dfbar", "--help"]

        with pytest.raises(SystemExit):
            res = dfbar.dfbar.process_args()

