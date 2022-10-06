import asyncio
from dataclasses import dataclass
from datetime import timedelta
from logging import Logger
from typing import Generic, Optional, TypeVar
from pytest_mock import MockerFixture
import pytest
from obs_package_update import run_cmd
from obs_package_update.util import CommandResult, retry_async_run_cmd


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
async def test_raise_on_err_exc():
    with pytest.raises(RuntimeError) as runtime_err_ctx:
        await run_cmd("false", raise_on_error=True)

    assert "Command false failed (exit code 1)" in str(runtime_err_ctx.value)


@pytest.mark.asyncio
async def test_raise_on_err():
    res = await run_cmd("false", raise_on_error=False)

    assert res.exit_code == 1


@pytest.mark.asyncio
async def test_iterator_CommandResult():
    exit_code = 42
    stderr = "errorrrrr!"
    stdout = "foobar"
    cmd_res = CommandResult(exit_code=exit_code, stderr=stderr, stdout=stdout)

    e, out, err = cmd_res
    assert e == exit_code
    assert out == stdout
    assert err == stderr


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
    bump_call_count = FailNCalls(failures)

    await retry_async_run_cmd(bump_call_count)

    assert bump_call_count.call_count == failures + 1


@pytest.mark.asyncio
async def test_retry_async_cmd_return():
    test_coro = FailNCalls(2, return_value=42)

    assert await retry_async_run_cmd(test_coro) == 42


@pytest.mark.asyncio
async def test_retry_async_cmd_logger(mocker: MockerFixture):
    fail_once = FailNCalls(1)

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
