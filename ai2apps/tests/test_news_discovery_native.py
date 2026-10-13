"""Opt-in public F1 experiment in a disposable native browser container.

Set AI2APPS_F1_ACCEPTANCE=1 and the app-dev AI2APPS_SHELL_AUTOMATION_PATH.
No user profile, channel data, model calls or authentication state is used.
"""
import os
import pytest
from ai2apps.browser.background_bidi import BackgroundBiDi
from ai2apps.browser.background_page import BackgroundPage

pytestmark=pytest.mark.skipif(not os.environ.get('AI2APPS_F1_ACCEPTANCE'),reason='requires app-dev native browser and public network')


@pytest.mark.asyncio
async def test_f1_homepage_and_news_discovery():
    connection=await BackgroundBiDi().connect()
    user=None
    try:
        user=(await connection.command('browser.createUserContext',{}))['userContext']
        tab=(await connection.command('browsingContext.create',{'type':'window','userContext':user,'background':True}))['context']
        page=BackgroundPage(connection,tab,interaction_mode=lambda url:'fast')
        await page.navigate('https://www.formula1.com/',delay_ms=300)
        access=await page.handle_access()
        assert access['classification'] not in ('needs_user','restricted')
        generic=await page.extract_list({'arguments':{'news_scan':True,'limit':40}})
        expected={i['url'] for i in generic['items'] if '/article/' in i['url']}
        assert len(expected)>=10
        assert 'https://www.formula1.com/en/latest' in generic['discovery']['pages']
        await page.navigate('https://www.formula1.com/',delay_ms=300)
        compiled=await page.extract_list({'arguments':{'news_scan':True,'limit':40,'site_extraction':{
            'schema':'ai2apps.site-extraction/v1','kind':'list','origin':'https://www.formula1.com','path':'/','selector':'main'}}})
        actual={i['url'] for i in compiled['items']}
        assert len(actual&expected)/len(expected)>=.8
        await connection.command('browsingContext.close',{'context':tab})
        tree=await connection.command('browsingContext.getTree',{'maxDepth':0})
        assert tab not in {i['context'] for i in tree['contexts']}
    finally:
        if user:await connection.command('browser.removeUserContext',{'userContext':user})
        await connection.close()
