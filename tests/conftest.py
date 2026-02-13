import uuid

import pytest
from approvaltests.reporters import PythonNativeReporter, set_default_reporter

set_default_reporter(PythonNativeReporter())


@pytest.fixture
def test_function_id() -> str:
    """Generate a unique identifier for the current test function.

    Useful for creating distinct names for shared resources (e.g., databases, files) that need to be unique across concurrent test runs.
    """
    return str(uuid.uuid4())[:8]
