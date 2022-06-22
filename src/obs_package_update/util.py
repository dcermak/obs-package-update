import asyncio
import logging
from typing import Optional, Union
from datetime import timedelta

from dataclasses import dataclass


@dataclass
class CommandResult:
    """The result of an executed command."""

    #: the exit code
    exit_code: int

    #: decoded standard output
    stdout: str

    #: decoded standard error
    stderr: str


async def run_cmd(
    cmd: str,
    cwd: Optional[str] = None,
    raise_on_error: bool = True,
    timeout: Optional[Union[int, float, timedelta]] = None,
    logger: Optional[logging.Logger] = None,
) -> CommandResult:
    """Simple asynchronous command shell command execution.

    Parameters:
    cmd: The shell command to run
    cwd: the working directory where the shell command is executed (defaults to
         the current working directory)
    raise_on_err: raises a ``RuntimeError`` if the shell command returns with an
                  exit code not equal to 0
    timeout: an optional timeout in seconds or a ``timedelta``. The shell
             command is terminated if it takes longer than the timeout. Defaults
             to no timeout.
    logger: an optional logging class for debug logging

    Returns:
    A ``CommandResult`` containing the information about the finished process.
    """
    if logger:
        logger.debug("running command %s", cmd)

    proc = await asyncio.subprocess.create_subprocess_shell(
        cmd,
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    if isinstance(timeout, timedelta):
        timeout = timeout.total_seconds()

    retcode = await asyncio.wait_for(proc.wait(), timeout=timeout)
    stdout, stderr = await proc.communicate()
    if raise_on_error and retcode != 0:
        raise RuntimeError(
            f"Command {cmd} failed (exit code {retcode}) with: {stdout.decode()}"
        )
    out = stdout.decode()
    err = stderr.decode()
    if logger:
        logger.debug(
            "command terminated with %d, stdout: %s, stderr: %s", retcode, out, err
        )

    return CommandResult(exit_code=retcode, stdout=out, stderr=err)
