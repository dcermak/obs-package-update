import asyncio
from datetime import timedelta
import pytest
from obs_package_update import run_cmd


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
