import pytest
from prefect.testing.utilities import MagicMock, prefect_test_harness

from prefect_openai.credentials import OpenAICredentials


@pytest.fixture(scope="session", autouse=True)
def prefect_db():
    """
    Sets up test harness for temporary DB during test runs.
    """
    with prefect_test_harness():
        yield


@pytest.fixture(autouse=True)
def reset_object_registry():
    """
    Ensures each test has a clean object registry.
    """
    from prefect.context import PrefectObjectRegistry

    with PrefectObjectRegistry():
        yield


async def mock_acreate(prompt, **kwargs):
    result = MagicMock(prompt=prompt)
    for k, v in kwargs.items():
        setattr(result, k, v)
    return result


@pytest.fixture
def mock_openai_credentials(monkeypatch) -> OpenAICredentials:
    mock_model = MagicMock()
    mock_model.acreate.side_effect = mock_acreate
    monkeypatch.setattr("openai.Completion", mock_model)
    monkeypatch.setattr("openai.Image", mock_model)
    return OpenAICredentials(api_key="my_api_key", _mock_model=mock_model)
