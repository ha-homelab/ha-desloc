"""All returned models/pages are discovered without inventing pagination fields."""
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.desloc.api import DeslocProtocolError, LIST_REQUEST


def page(row, start, count):
    return [dict(row, id=i + 1, mac=f"{i + 1:012x}", sortFlag=1000 - i,
                 model="C100 Plus" if i == 0 else "Synthetic other model")
            for i in range(start, start + count)]


async def test_all_pages_and_model_names(transport, row):
    api, *_ = transport
    first, last = page(row, 0, 20), page(row, 20, 3)
    api._post = AsyncMock(side_effect=[first, last])
    result = await api.async_devices()
    assert len(result) == 23
    assert result[-1].model == "Synthetic other model"
    assert api._post.await_args_list[0].args[1] == {"groupId": 0, "size": 20}
    assert api._post.await_args_list[1].args[1] == {"groupId": 0, "size": 20, "sortFlag": 981}
    assert LIST_REQUEST == {"groupId": 0, "size": 20}


async def test_duplicate_page_rows_do_not_duplicate_locks(transport, row):
    api, *_ = transport
    first = page(row, 0, 20)
    api._post = AsyncMock(side_effect=[first, [first[-1], *page(row, 20, 1)]])
    result = await api.async_devices()
    assert len(result) == 21


async def test_conflicting_identity_on_later_page_is_rejected(transport, row):
    api, *_ = transport
    first = page(row, 0, 20)
    api._post = AsyncMock(side_effect=[first, [dict(first[-1], id=999)]])
    with pytest.raises(DeslocProtocolError, match="conflicting identities"):
        await api.async_devices()


@pytest.mark.parametrize("cursor", [None, True, "981"])
async def test_full_page_requires_real_cursor(transport, row, cursor):
    api, *_ = transport
    first = page(row, 0, 20)
    first[-1]["sortFlag"] = cursor
    api._post = AsyncMock(return_value=first)
    with pytest.raises(DeslocProtocolError, match="pagination did not advance"):
        await api.async_devices()
    assert api._post.await_count == 1


async def test_repeated_cursor_is_bounded(transport, row):
    api, *_ = transport
    api._post = AsyncMock(return_value=page(row, 0, 20))
    with pytest.raises(DeslocProtocolError, match="pagination did not advance"):
        await api.async_devices()
    assert api._post.await_count == 2


async def test_later_page_failure_does_not_return_partial_discovery(transport, row):
    api, *_ = transport
    api._post = AsyncMock(side_effect=[page(row, 0, 20), DeslocProtocolError("Failure")])
    with pytest.raises(DeslocProtocolError):
        await api.async_devices()


async def test_page_limit_is_reported_not_silently_truncated(transport, row):
    api, *_ = transport
    api._post = AsyncMock(return_value=page(row, 0, 20))
    with patch("custom_components.desloc.api.MAX_DEVICE_PAGES", 1), pytest.raises(
        DeslocProtocolError, match="pagination limit"
    ):
        await api.async_devices()
