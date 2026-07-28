import os

import pytest


def pytest_sessionfinish(session, exitstatus):
    if os.environ.get("PYTEST_FAIL_ON_SKIP") != "1":
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter and reporter.stats.get("skipped"):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
