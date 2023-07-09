import pytest

from protosaurus import Context


@pytest.fixture
def ctx():
    return Context()
