import asyncio
import pathlib
from dataclasses import dataclass
from datetime import timedelta
from logging import Logger
from typing import Generic, Optional, TypeVar
from pytest_mock import MockerFixture
import pytest
from obs_package_update import run_cmd
from obs_package_update.util import (
    CommandError,
    CommandResult,
    RunCommand,
    retry_async_run_cmd,
)


@pytest.mark.asyncio
async def test_basic_run():
    res = await run_cmd("echo 'foobar'")
    assert "foobar" in res.stdout


@pytest.mark.asyncio
async def test_timeout():
    with pytest.raises(asyncio.exceptions.TimeoutError):
        await run_cmd("sleep 2", timeout=timedelta(seconds=1))


@pytest.mark.asyncio
async def test_timeout_seconds():
    with pytest.raises(asyncio.exceptions.TimeoutError):
        await run_cmd("sleep 2", timeout=1)


@pytest.mark.asyncio
async def test_env():
    res = await run_cmd("echo $FOOBAR")
    assert "" == res.stdout.strip()

    res = await run_cmd("echo $FOOBAR", env={"FOOBAR": "value"})
    assert "value" == res.stdout.strip()


@pytest.mark.asyncio
async def test_raise_on_err_exc():
    with pytest.raises(RuntimeError) as runtime_err_ctx:
        await run_cmd("sed '|afs|d'", raise_on_error=True)

    assert (
        "Command sed '|afs|d' failed (exit code 1) with stdout: '', stderr: 'sed: -e expression #1, char 1: unknown command: `|'"
        in str(runtime_err_ctx.value)
    )

    assert isinstance(runtime_err_ctx.value, CommandError)
    command_res = runtime_err_ctx.value.command_result
    assert command_res.exit_code == 1
    assert command_res.stdout == ""
    assert (
        command_res.stderr.strip()
        == "sed: -e expression #1, char 1: unknown command: `|'"
    )


@pytest.mark.asyncio
async def test_raise_on_err():
    res = await run_cmd("false", raise_on_error=False)

    assert res.exit_code == 1


@pytest.mark.asyncio
async def test_iterator_CommandResult():
    exit_code = 42
    stderr = "errorrrrr!"
    stdout = "foobar"
    retval, out, err = CommandResult(exit_code=exit_code, stderr=stderr, stdout=stdout)

    assert retval == exit_code
    assert out == stdout
    assert err == stderr


@pytest.mark.asyncio
async def test_RunCommand_success():
    caller = RunCommand()
    res = await caller("true")
    assert res.exit_code == 0
    assert res.stdout == ""
    assert res.stderr == ""


@pytest.mark.asyncio
async def test_RunCommand_fail():
    with pytest.raises(RuntimeError) as runtime_err_ctx:
        await RunCommand()("false")

    assert "Command false failed (exit code 1) with stdout: '', stderr: ''" in str(
        runtime_err_ctx
    )


@pytest.mark.asyncio
async def test_RunCommand_cwd(tmp_path: pathlib.Path):
    fname = "test-random-string-IwJLivCaJp"
    with open(tmp_path / fname, "w") as tmp:
        tmp.write("1")

    cmd = f"cat {fname}"
    with pytest.raises(RuntimeError):
        await RunCommand()(cmd)

    assert (await RunCommand(cwd=str(tmp_path))(cmd)).stdout.strip() == "1"
    assert (await RunCommand()(cmd, cwd=str(tmp_path))).stdout.strip() == "1"
    assert (await RunCommand(cwd="/")(cmd, cwd=str(tmp_path))).stdout.strip() == "1"


@pytest.mark.asyncio
async def test_RunCommand_raise_on_error():
    for fut in (
        RunCommand()("false"),
        RunCommand(raise_on_error=True)("false"),
        RunCommand(raise_on_error=True)("false", raise_on_error=True),
        RunCommand(raise_on_error=False)("false", raise_on_error=True),
        RunCommand()("false", raise_on_error=True),
    ):
        with pytest.raises(RuntimeError):
            await fut

    assert (await RunCommand(raise_on_error=False)("false")).exit_code == 1
    assert (
        await RunCommand(raise_on_error=False)("false", raise_on_error=False)
    ).exit_code == 1
    assert (
        await RunCommand(raise_on_error=True)("false", raise_on_error=False)
    ).exit_code == 1
    assert (await RunCommand()("false", raise_on_error=False)).exit_code == 1


@pytest.mark.asyncio
async def test_RunCommand_env():
    _cmd = "echo $FOOBAR"
    _env = {"FOOBAR": "test"}

    assert (await RunCommand(env=_env)(_cmd)).stdout.strip() == "test"
    assert (await RunCommand()(_cmd, env=_env)).stdout.strip() == "test"
    assert (
        await RunCommand(env={"FOOBAR": "not TEST!"})(_cmd, env=_env)
    ).stdout.strip() == "test"
    assert (await RunCommand()(_cmd)).stdout.strip() == ""


T = TypeVar("T")


@dataclass
class FailNCalls(Generic[T]):
    calls_to_fail: int

    return_value: Optional[T] = None
    _call_count: int = 0

    async def __call__(self) -> Optional[T]:
        self._call_count += 1
        if self._call_count <= self.calls_to_fail:
            raise RuntimeError("🤮")

        return self.return_value

    @property
    def call_count(self) -> int:
        return self._call_count


@pytest.mark.asyncio
@pytest.mark.parametrize("failures", range(5))
async def test_retry_async_cmd(failures: int):
    bump_call_count: FailNCalls = FailNCalls(failures)

    await retry_async_run_cmd(bump_call_count)

    assert bump_call_count.call_count == failures + 1


@pytest.mark.asyncio
async def test_retry_async_cmd_return():
    test_coro = FailNCalls(2, return_value=42)

    assert await retry_async_run_cmd(test_coro) == 42


@pytest.mark.asyncio
async def test_retry_async_cmd_logger(mocker: MockerFixture):
    fail_once: FailNCalls = FailNCalls(1)

    class StubLogger(Logger):
        def debug(self, *args, **kwargs) -> None:
            pass

    spy = mocker.spy(StubLogger, "debug")
    logger = StubLogger(name=__name__)

    await retry_async_run_cmd(fail_once, logger=logger)
    spy.assert_called_once()


@pytest.mark.asyncio
async def test_retry_async_cmd_fail():
    fail_twice = FailNCalls(2)

    with pytest.raises(RuntimeError) as runtime_err_ctx:
        await retry_async_run_cmd(fail_twice, retries=1)

    assert "🤮" in str(runtime_err_ctx)
