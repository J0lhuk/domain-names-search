import httpx
import pytest

from domain_checker.config import Settings
from domain_checker.models import AvailabilityStatus, HistoryStatus
from domain_checker.normalization import expand_names
from domain_checker.pipeline import Checker
from domain_checker.storage import ResultStore


@pytest.mark.asyncio
async def test_offline_end_to_end_and_resume(tmp_path) -> None:
    settings = Settings.model_validate({"history": {"wayback": False}})
    store = ResultStore(tmp_path / "out")
    fixtures = {"free.com": {"registry_status": "not_found", "availability_status": "available"}}
    try:
        async with httpx.AsyncClient() as client:
            checker = Checker(settings, store, client, fixtures)
            result = (await checker.check_all(expand_names(["free"], ["com"])))[0]
            resumed = (await checker.check_all(expand_names(["free"], ["com"])))[0]
        csv_path, json_path = store.export()
    finally:
        store.close()
    assert result.availability_status == AvailabilityStatus.AVAILABLE
    assert result.history_status == HistoryStatus.NONE
    assert resumed.checked_at == result.checked_at
    assert csv_path.exists() and json_path.exists()


@pytest.mark.asyncio
async def test_registered_domain_skips_history(tmp_path) -> None:
    settings = Settings.model_validate({"history": {"wayback": True}})
    store = ResultStore(tmp_path / "out")
    fixtures = {"taken.com": {"registry_status": "registered", "availability_status": "registered"}}
    try:
        async with httpx.AsyncClient() as client:
            result = (await Checker(settings, store, client, fixtures).check_all(expand_names(["taken"], ["com"])))[0]
    finally:
        store.close()
    assert result.history_status == HistoryStatus.NOT_CHECKED
