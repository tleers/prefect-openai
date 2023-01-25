"""Module for generating and configuring OpenAI completions."""
import functools
import inspect
import sys
from logging import Logger
from typing import Any, Callable, Dict, Optional, Tuple, Union

from openai.openai_object import OpenAIObject
from prefect.blocks.core import Block
from prefect.exceptions import MissingContextError
from prefect.flows import Flow
from prefect.logging.loggers import get_logger, get_run_logger
from prefect.tasks import Task
from prefect.utilities.asyncutils import is_async_fn, sync_compatible
from pydantic import Field
from typing_extensions import Literal

from prefect_openai import OpenAICredentials


class CompletionModel(Block):
    """
    A block that contains config for an OpenAI Completion Model.
    Learn more in the [OpenAPI Text Completion docs](
        https://beta.openai.com/docs/guides/completion)

    Attributes:
        openai_credentials: The credentials used to authenticate with OpenAI.
        model: ID of the model to use.
        temperature: What sampling temperature to use.
            Higher values means the model will take more risks.
            Try 0.9 for more creative applications, and 0 (argmax sampling)
            for ones with a well-defined answer.
        max_tokens: The maximum number of tokens to generate in the completion.
            The token count of your prompt plus max_tokens cannot exceed the
            model's context length. Most models have a context length of 2048 tokens
            (except for the newest models, which support 4096).
        suffix: The suffix to append to the prompt.
        echo: Echo back the prompt in addition to the completion.
        timeout: The maximum time to wait for the model to warm up.

    Example:
        Load a configured block:
        ```python
        from prefect_openai import CompletionModel

        completion_model = CompletionModel.load("BLOCK_NAME")
        ```
    """

    openai_credentials: OpenAICredentials = Field(
        default=..., description="The credentials used to authenticate with OpenAI."
    )
    model: Union[
        Literal[
            "text-davinci-003", "text-curie-001", "text-babbage-001", "text-ada-001"
        ],
        str,
    ] = Field(default="text-curie-001", description="ID of the model to use.")
    temperature: float = Field(
        default=0.5,
        description=(
            "What sampling temperature to use. Higher values means the model will take "
            "more risks. Try 0.9 for more creative applications, and 0 "
            "(argmax sampling) for ones with a well-defined answer."
        ),
    )
    max_tokens: int = Field(
        default=16,
        description=(
            "The maximum number of tokens to generate in the completion. "
            "The token count of your prompt plus max_tokens cannot exceed the "
            "model's context length. Most models have a context length of 2048 tokens "
            "(except for the newest models, which support 4096)."
        ),
    )
    suffix: Optional[str] = Field(
        default=None, description="The suffix to append to the prompt."
    )
    echo: bool = Field(default=False, description="Whether to echo the prompt.")
    timeout: Optional[float] = Field(
        default=None, description="The maximum time to wait for the model to warm up."
    )

    _block_type_name = "OpenAI Completion Model"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/QE8JwcbZBmIfiognXDLcY/2bcd4c759f877d37159f576101218b49/open-ai-logo-8B9BFEDC26-seeklogo.com.png?h=250"  # noqa
    _documentation_url = "https://prefecthq.github.io/prefect-openai/completion/#prefect_openai.completion.CompletionModel"  # noqa

    @property
    def logger(self) -> Logger:
        """
        Returns a logger based on whether the CompletionModel
        is called from within a flow or task run context.
        If a run context is present, the logger property returns a run logger.
        Else, it returns a default logger labeled with the class's name.

        Returns:
            The run logger or a default logger with the class's name.
        """
        try:
            return get_run_logger()
        except MissingContextError:
            return get_logger(self.__class__.__name__)

    @sync_compatible
    async def submit_prompt(
        self, prompt: str, **acreate_kwargs: Dict[str, Any]
    ) -> OpenAIObject:
        """
        Submits a prompt for the model to generate a text completion.
        OpenAI will return an object potentially containing multiple `choices`,
        where the zeroth index is what they consider the "best" completion.
        Learn more in the [OpenAPI Text Completion docs](
            https://beta.openai.com/docs/guides/completion)

        Args:
            prompt: The prompt to use for the completion.
            **acreate_kwargs: Additional keyword arguments to pass
                to [`openai.Completion.acreate`](
                https://beta.openai.com/docs/api-reference/completions/create).

        Returns:
            The OpenAIObject containing the completion and associated metadata.

        Example:
            Create an OpenAI Completion given a prompt:
            ```python
            from prefect import flow
            from prefect_openai import CompletionModel, OpenAICredentials

            @flow(log_prints=True)
            def my_ai_bot(model_name: str = "text-davinci-003")
                credentials = OpenAICredentials.load("my-openai-creds")

                completion_model = CompletionModel(
                    openai_credentials=credentials,
                )

                for prompt in ["hi!", "what is the meaning of life?"]:
                    completion = completion_model.submit_prompt(prompt)
                    print(completion.choices[0].text)
            ```
        """
        client = self.openai_credentials.get_client()

        input_kwargs = dict(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            suffix=self.suffix,
            echo=self.echo,
            timeout=self.timeout,
        )
        input_kwargs.update(acreate_kwargs)

        creation = await client.Completion.acreate(prompt=prompt, **input_kwargs)
        total_tokens = creation.usage["total_tokens"]
        num_choices = len(creation.choices)
        self.logger.info(
            f"Finished text completion using the {self.model!r} "
            f"model with {total_tokens} tokens, creating {num_choices} choice(s)."
        )
        return creation


@sync_compatible
async def _raise_interpreted_exc(block_name: str, exc: Exception):
    """
    Helper function for reuse so that this doesn't get repeated for sync/async flavors.
    """
    # gather args and kwargs from the original exception to rebuild
    exc_type = type(exc)
    exc_traceback = sys.exc_info()[-1]
    args = exc.args[1:]  # first arg is message, which we're overwriting
    try:
        signature = inspect.signature(exc_type)
        kwargs = {
            param.name: getattr(exc, param.name, None)
            for param in signature.parameters.values()
            if param.kind == param.KEYWORD_ONLY
        }
    except ValueError:
        # no signature available like ZeroDivisionError
        kwargs = {}

    # create a new message
    completion_model = await CompletionModel.load(block_name)
    prompt = f"Summarize: ```{str(exc)}```."
    response = await completion_model.submit_prompt(prompt)
    interpretation = f"{response.choices[0].text.strip()}"
    new_exc_msg = f"{exc}\nOpenAI: {interpretation}"

    # push the original traceback to the tail so it's not obscured by
    # the additional logic in this except clause
    raise exc_type(new_exc_msg, *args, **kwargs).with_traceback(exc_traceback) from exc


def interpret_exception(block_name: str) -> Callable:
    """
    Use OpenAI to interpret the exception raised from the decorated function.
    If used with a flow and return_state=True, will override the original state's
    data and message with the OpenAI interpretation.

    Args:
        block_name: The name of the CompletionModel block to use for the summary.

    Returns:
        A decorator that will use an OpenAI CompletionModel to interpret the exception
        raised from the decorated function.

    Examples:
        Interpret the exception raised from a flow.
        ```python
        from prefect import flow
        from prefect_openai.completion import interpret_exception

        @flow
        @interpret_exception("BLOCK_NAME")
        def example_flow():
            return 1 / 0

        example_flow()
        ```
    """

    def decorator(fn: Callable) -> Callable:
        """
        The actual decorator.
        """
        if isinstance(fn, (Flow, Task)):
            raise ValueError(
                "interpret_exception should be nested under the flow / task decorator, "
                "e.g. `@flow` -> `@interpret_exception('curie')` -> `def function()`"
            )

        @functools.wraps(fn)
        def sync_wrapper(*args: Tuple[Any], **kwargs: Dict[str, Any]) -> Any:
            """
            The sync version of the wrapper function that will execute the function.
            """
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                _raise_interpreted_exc(block_name, exc)

        # couldn't get sync_compatible working so had to define an async flavor
        @functools.wraps(fn)
        async def async_wrapper(*args: Tuple[Any], **kwargs: Dict[str, Any]) -> Any:
            """
            The async version of the wrapper function that will execute the function.
            """
            try:
                return await fn(*args, **kwargs)
            except Exception as exc:
                await _raise_interpreted_exc(block_name, exc)

        wrapper = async_wrapper if is_async_fn(fn) else sync_wrapper
        return wrapper

    return decorator
