"""Test runner that prints PASSED/FAILED per test and a summary at the end."""
import unittest

from django.test.runner import DiscoverRunner


class PassFailResult(unittest.TextTestResult):
    def _name(self, test):
        return f"{test.__class__.__module__.split('.')[-1]}.{test.__class__.__name__}.{test._testMethodName}"

    def startTest(self, test):
        unittest.TestResult.startTest(self, test)  # skip the default dot output
        self.stream.write(f"{self._name(test)} ... ")
        self.stream.flush()

    def _mark(self, label):
        self.stream.writeln(label)
        self.stream.flush()

    def addSuccess(self, test):
        unittest.TestResult.addSuccess(self, test)
        self._mark("PASSED")

    def addFailure(self, test, err):
        unittest.TestResult.addFailure(self, test, err)
        self._mark("FAILED")

    def addError(self, test, err):
        unittest.TestResult.addError(self, test, err)
        self._mark("ERROR")

    def addSkip(self, test, reason):
        unittest.TestResult.addSkip(self, test, reason)
        self._mark(f"SKIPPED ({reason})")

    def addExpectedFailure(self, test, err):
        unittest.TestResult.addExpectedFailure(self, test, err)
        self._mark("PASSED (expected failure)")

    def addUnexpectedSuccess(self, test):
        unittest.TestResult.addUnexpectedSuccess(self, test)
        self._mark("FAILED (unexpected success)")


class PassFailRunner(DiscoverRunner):
    def get_resultclass(self):
        return PassFailResult

    def run_suite(self, suite, **kwargs):
        result = super().run_suite(suite, **kwargs)
        failed = len(result.failures) + len(result.unexpectedSuccesses)
        errors = len(result.errors)
        skipped = len(result.skipped)
        passed = result.testsRun - failed - errors - skipped
        print("\n" + "=" * 40)
        print(f"  {passed} passed, {failed} failed, {errors} errors, {skipped} skipped  ({result.testsRun} total)")
        print("=" * 40)
        return result
