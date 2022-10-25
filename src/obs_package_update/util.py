import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, Optional, TypeVar, Union
from datetime import timedelta

from dataclasses import dataclass


@dataclass
class CommandResult:
    """The result of an executed command.

    This class also works like an iterator:

    >>> retcode, stdout, stderr = CommandResult(1, "foo", "err")

    """

    #: the exit code
    exit_code: int

    #: decoded standard output
    stdout: str

    #: decoded standard error
    stderr: str

    def __iter__(self):
        return (self.exit_code, self.stdout, self.stderr).__iter__()


class CommandError(RuntimeError):
    """Exception class that is raised by :py:func:`run_cmd`.

    It stores the result of the command in the attribute
    :py:attr:`command_result`.

    """

    def __init__(self, command_result: CommandResult, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        assert (
            command_result.exit_code != 0
        ), f"The command must have failed but it has exit code {command_result.exit_code}."

        #: The result of the failed command
        self.command_result: CommandResult = command_result


async def run_cmd(
    cmd: str,
    cwd: Optional[str] = None,
    raise_on_error: bool = True,
    timeout: Optional[Union[int, float, timedelta]] = None,
    logger: Optional[logging.Logger] = None,
    env: Optional[Dict[str, str]] = None,
) -> CommandResult:
    """Simple asynchronous shell command execution.

    Args:
        cmd: The shell command to run
        cwd: the working directory where the shell command is executed (defaults to
            the current working directory)
        raise_on_err: raises a :py:class:`CommandError` if the shell command
            returns with an exit code not equal to 0
        timeout: an optional timeout in seconds or a ``timedelta``. The shell
            command is terminated if it takes longer than the timeout. Defaults
            to no timeout.
        logger: an optional logging class for debug logging
        env: an optional environment dictionary that is set as the environment
            for the shell command. If not provided, then the environment of the
            current process is inherited

    Raises:
        :py:class:`CommandError`: on failure and if ``raise_on_err`` is ``True``

    Returns:
        A :py:class:`CommandResult` containing the information about the finished process.
    """
    if logger:
        logger.debug("running command %s", cmd)

    proc = await asyncio.subprocess.create_subprocess_shell(
        cmd,
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=env,
    )
    if isinstance(timeout, timedelta):
        timeout = timeout.total_seconds()

    retcode = await asyncio.wait_for(proc.wait(), timeout=timeout)
    stdout, stderr = await proc.communicate()
    out = stdout.decode()
    err = stderr.decode()
    command_res = CommandResult(exit_code=retcode, stdout=out, stderr=err)
    if raise_on_error and retcode != 0:
        raise CommandError(
            command_res,
            f"Command {cmd} failed (exit code {retcode}) with stdout: '{out}', stderr: '{err}'",
        )
    if logger:
        logger.debug(
            "command terminated with %d, stdout: %s, stderr: %s", retcode, out, err
        )

    return command_res


@dataclass(frozen=True)
class RunCommand:
    """Helper class to run commands asynchronously via :py:func:`run_cmd` with a
    common set of parameters.

    """

    cwd: Optional[str] = None
    raise_on_error: bool = True
    timeout: Optional[Union[int, float, timedelta]] = None
    logger: Optional[logging.Logger] = None
    env: Optional[Dict[str, str]] = None

    async def __call__(
        self,
        cmd: str,
        cwd: Optional[str] = None,
        raise_on_error: Optional[bool] = None,
        timeout: Optional[Union[int, float, timedelta]] = None,
        logger: Optional[logging.Logger] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> CommandResult:
        raise_on_err = raise_on_error
        if raise_on_error is None:
            raise_on_err = self.raise_on_error
        assert raise_on_err is not None
        return await run_cmd(
            cmd,
            cwd or self.cwd,
            raise_on_err,
            timeout or self.timeout,
            logger or self.logger,
            env or self.env,
        )


#: Return type of the coroutine passed to :py:func:`retry_async_run_cmd`
T = TypeVar("T")


async def retry_async_run_cmd(
    coroutine: Callable[[], Coroutine[Any, Any, T]],
    retries: int = 10,
    logger: Optional[logging.Logger] = None,
) -> T:
    """Retry the coroutine up to ``retries`` times.

    Args:
        coroutine: An asynchronous that can throw a :py:class:`RuntimeError` on failure
        retries: The number of times the call of ``coroutine`` should be repeated
        logger: An optional logger, that will log all failures at debug level

    Returns:
        The returned value of `coroutine()`
    """
    for i in range(retries):
        try:
            res = await coroutine()
            return res
        except RuntimeError as runtime_err:
            if logger:
                logger.debug(
                    "async call failed with %s, retry count: %d", runtime_err, i + 1
                )
            if i != retries - 1:
                pass
            else:
                raise
    assert False, "This code must be unreachable"
