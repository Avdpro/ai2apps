from unittest.mock import AsyncMock
import pytest
from ai2apps.intelligence.collector import IntelligenceCollector

@pytest.mark.asyncio
async def test_missing_images_recovered_without_replacing_text():
    collector = object.__new__(IntelligenceCollector)
    collector.read = AsyncMock(return_value={'text':'other', 'images':[{'url':'https://example.com/photo.jpg'}]})
    stats = {}
    page = await collector.ensure_images({}, {'url':'https://example.com'}, {'text':'original'}, 'https://example.com/a', 'images', stats)
    assert page['text'] == 'original'
    assert page['cover_image']['url'] == 'https://example.com/photo.jpg'
    assert stats['image_recovered'] == 1

@pytest.mark.asyncio
async def test_existing_images_skip_recovery_and_supply_cover():
    collector = object.__new__(IntelligenceCollector)
    collector.read = AsyncMock()
    page = await collector.ensure_images({}, {}, {'images':[{'url':'https://example.com/a.jpg'}]}, '', '', {})
    collector.read.assert_not_called()
    assert page['cover_image']['url'].endswith('a.jpg')

@pytest.mark.asyncio
@pytest.mark.parametrize('failed', [False, True])
async def test_no_image_is_bounded_and_keeps_text(failed):
    collector = object.__new__(IntelligenceCollector)
    collector.read = AsyncMock(side_effect=RuntimeError('blocked')) if failed else AsyncMock(return_value={'images':[]})
    stats = {}
    result = await collector.ensure_images({}, {'url':'https://example.com'}, {'text':'original'}, 'https://example.com/a', 'images', stats)
    assert result['text'] == 'original'
    assert stats['image_failed' if failed else 'image_missing'] == 1
    collector.read.assert_awaited_once()
