import unittest
from ai2apps.browser.article_access import classify,preview
from ai2apps.intelligence.models import Page

class AccessTests(unittest.TestCase):
    def test_reasons(self):
        self.assertEqual(classify('Subscribe to continue reading'),'paywall')
        self.assertEqual(classify('Sign in to read this article'),'login_required')
        self.assertEqual(classify('We are checking your access. Subscribe to continue reading'),'access_verification_pending')
        self.assertEqual(classify('An ordinary news article'), '')
        self.assertEqual(classify('Create a free account or log in'), 'login_required')
    def test_preview(self):
        p=preview({'url':'https://example.com/story','paragraphs':['We are checking your access.', 'Observed article paragraph with actual facts. '*8]},'paywall')
        self.assertEqual(p['coverage'],'preview')
        self.assertNotIn('checking your access',p['text'])
        self.assertEqual(Page.model_validate({**p,'source_id':'s'}).access_reason,'paywall')
    def test_prompt_not_article(self):
        self.assertIsNone(preview({'url':'https://example.com','paragraphs':['Subscribe to continue reading']},'paywall'))

from ai2apps.browser.background_page import BackgroundPage
from unittest.mock import AsyncMock
class PipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_returns_preview_before_empty_readability(self):
        page=BackgroundPage(None,'ctx')
        page.snapshot=AsyncMock(return_value={'url':'https://example.com/story'})
        page.navigate=AsyncMock()
        page.call_json=AsyncMock(return_value={'url':'https://example.com/story','notice':'Subscribe to continue reading','paragraphs':['Already visible article facts. '*12]})
        page.handle_access=AsyncMock(return_value={'classification':'restricted','reason':'paywall'})
        result=await page.read_page({'url':'https://example.com/story','new_tab':False,'allow_preview':True})
        self.assertEqual(result['outcome'],'success')
        self.assertEqual(result['coverage'],'preview')
        self.assertEqual(result['access_reason'],'paywall')
        self.assertEqual(page.context_id,'ctx')
    async def test_empty_preview_has_specific_failure(self):
        page=BackgroundPage(None,'ctx')
        page.snapshot=AsyncMock(return_value={'url':'https://example.com/story'})
        page.navigate=AsyncMock()
        page.call_json=AsyncMock(return_value={'notice':'Sign in to read this article','paragraphs':[]})
        page.handle_access=AsyncMock(return_value={'classification':'none'})
        result=await page.read_page({'url':'https://example.com/story','new_tab':False,'allow_preview':True})
        self.assertEqual(result['outcome'],'failed')
        self.assertIn('需要登录',result['reason'])
