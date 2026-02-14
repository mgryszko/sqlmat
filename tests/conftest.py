import uuid

import pytest
from approvaltests.reporters import PythonNativeReporter, set_default_reporter

set_default_reporter(PythonNativeReporter())


@pytest.fixture
def test_function_id() -> str:
    return str(uuid.uuid4())[:8]
