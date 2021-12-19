import pytest

from tests.utils import SampleClass


@pytest.fixture
def client():
    yield SampleClass()
