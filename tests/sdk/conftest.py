import os

import pytest


_PENDING_TEMP_FILES = []


@pytest.fixture(scope="session", autouse=True)
def _cleanup_gltest_windows_temp_files():
    yield
    for path in _PENDING_TEMP_FILES:
        try:
            os.unlink(path)
        except (FileNotFoundError, PermissionError):
            pass


@pytest.fixture
def direct_deploy_compat(direct_deploy):
    def deploy(path):
        if os.name != "nt":
            return direct_deploy(path)
        original_unlink = os.unlink

        def delayed_unlink(temp_path):
            try:
                original_unlink(temp_path)
            except PermissionError:
                _PENDING_TEMP_FILES.append(temp_path)

        os.unlink = delayed_unlink
        try:
            return direct_deploy(path)
        finally:
            os.unlink = original_unlink

    return deploy
