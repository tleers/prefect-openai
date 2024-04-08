"""Module for authenticating with OpenAI."""

from types import ModuleType
from typing import Optional

import openai
from openai import AzureOpenAI
from prefect.blocks.abstract import CredentialsBlock
from pydantic import VERSION as PYDANTIC_VERSION

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import Field, SecretStr
else:
    from pydantic import Field, SecretStr


class OpenAICredentials(CredentialsBlock):
    """
    Credentials used to authenticate with OpenAI.

    Attributes:
        api_key: The API key used to authenticate with OpenAI.

    Example:
        Load a configured block:
        ```python
        from prefect_openai import OpenAICredentials

        credentials = OpenAICredentials.load("BLOCK_NAME")
        ```

        Get the OpenAPI client:
        ```python
        from prefect_openai import OpenAICredentials

        credentials = OpenAICredentials.load("BLOCK_NAME")
        client = credentials.get_client()
        ```
    """

    _block_type_name = "OpenAI Credentials"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/760539393a7dbf93a143fb01c2a8b0fe7157a8d8-247x250.png"  # noqa
    _documentation_url = "https://prefecthq.github.io/prefect-openai/credentials/#prefect_openai.credentials.OpenAICredentials"  # noqa

    api_key: SecretStr = Field(
        default=...,
        title="API Key",
        description="The API key used to authenticate with OpenAI.",
    )

    organization: Optional[str] = Field(
        default=None,
        title="Organization",
        description="Specify which organization is used for an API request.",
    )

    def get_client(self) -> ModuleType:
        """
        Gets the OpenAPI client.

        Returns:
            The OpenAPI client.
        """
        openai.api_key = self.api_key.get_secret_value()
        openai.organization = self.organization
        return openai


class AzureOpenAICredentials(CredentialsBlock):
    """
    Credentials used to authenticate with OpenAI.

    Attributes:
        api_key: The API key used to authenticate with OpenAI.

    Example:
        Load a configured block:
        ```python
        from prefect_openai import AzureOpenAICredentials

        credentials = AzureOpenAICredentials.load("BLOCK_NAME")
        ```

        Get the OpenAPI client:
        ```python
        from prefect_openai import AzureOpenAICredentials

        credentials = AzureOpenAICredentials.load("BLOCK_NAME")
        client = credentials.get_client()
        ```
    """

    _block_type_name = "Azure OpenAI Credentials"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/760539393a7dbf93a143fb01c2a8b0fe7157a8d8-247x250.png"  # noqa
    _documentation_url = "https://prefecthq.github.io/prefect-openai/credentials/#prefect_openai.credentials.OpenAICredentials"  # noqa

    api_key: SecretStr = Field(
        default=...,
        title="API Key",
        description="The API key used to authenticate with OpenAI.",
    )

    api_version: str = Field(
        title="API Version",
        description="The API version of the Azure OpenAI model.",
    )

    azure_endpoint: str = Field(
        default="2023-12-01-preview",
        title="Azure Endpoint URL",
        description="The Azure Endpoint URL.",
    )

    azure_ad_token_provider: Optional[str] = Field(
        default=None,
        title="Azure AD Token Provider",
        description="The Azure AD Token Provider.",
    )

    def get_client(self) -> ModuleType:
        """
        Gets the OpenAPI client.

        Returns:
            The OpenAPI client.
        """
        if self.azure_ad_token_provider is None:
            client = AzureOpenAI(
                api_key=self.api_key.get_secret_value(),
                api_version=self.api_version,
                azure_endpoint=self.azure_endpoint,
            )
        else:
            client = AzureOpenAI(
                api_key=self.api_key.get_secret_value(),
                api_version=self.api_version,
                azure_endpoint=self.azure_endpoint,
                azure_ad_token_provider=self.azure_ad_token_provider,
            )
        return client
