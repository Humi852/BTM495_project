import subprocess
import sys
import unittest
from pathlib import Path


if __name__ == "__main__":
    test_directory = Path(__file__).resolve().parent
    project_directory = test_directory.parents[1]
    sys.path.insert(0, str(project_directory))

    test_suite = unittest.defaultTestLoader.discover(
        start_dir=str(test_directory),
        pattern="test*.py",
        top_level_dir=str(test_directory.parent),
    )
    test_result = unittest.TextTestRunner(verbosity=2).run(test_suite)
    admin_demo = subprocess.run(
        [sys.executable, str(test_directory / "test_admin_payment.py")],
        check=False,
    )
    passed_tests = (
        test_result.testsRun
        - len(test_result.failures)
        - len(test_result.errors)
        - len(test_result.skipped)
        - len(test_result.expectedFailures)
        - len(test_result.unexpectedSuccesses)
    )
    print(f"Ran {test_result.testsRun} tests ({passed_tests}/{test_result.testsRun} passed)")
    sys.exit(not test_result.wasSuccessful() or admin_demo.returncode != 0)
