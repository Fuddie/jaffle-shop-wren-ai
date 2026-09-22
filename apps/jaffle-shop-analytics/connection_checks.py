"""Verify both the legacy static preview and canonical local service origin."""
import json
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(tempfile.gettempdir()) / 'jaffle-browser-tools'))
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    errors=[]; responses=[]
    page=browser.new_page(viewport={'width':1280,'height':900})
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
    page.on('response',lambda r:responses.append((r.url,r.status)))
    page.goto('http://127.0.0.1:4173/',wait_until='domcontentloaded')
    page.wait_for_function("window.dashboardState?.ready",timeout=180000)
    page.wait_for_function("document.getElementById('ask-service-status').textContent.startsWith('Local service connected')",timeout=15000)
    assert '4174' in page.locator('#ask-service-status').inner_text()
    page.locator('input[value=local]').check()
    page.locator('#ask-question').fill('Which five customers have the highest total order amount?')
    assert page.locator('#ask-submit').is_enabled()
    page.locator('#ask-submit').click()
    page.wait_for_function("document.getElementById('ask-progress').textContent === 'Answer ready.'",timeout=210000)
    text=page.locator('#ask-answer').inner_text()
    for expected in ['Howard R.','Inspect generated SQL','Models and views used','not revenue']:
        assert expected in text, expected
    page.reload(wait_until='domcontentloaded')
    page.wait_for_function("window.dashboardState?.ready",timeout=180000)
    page.wait_for_function("document.getElementById('ask-service-status').textContent.startsWith('Local service connected')",timeout=15000)
    page.locator('input[value=verified]').check()
    page.locator('#ask-samples button').first.click()
    assert 'VERIFIED EXAMPLE' in page.locator('#ask-answer').inner_text()
    page2=browser.new_page(viewport={'width':1280,'height':900})
    page2.goto('http://127.0.0.1:4174/',wait_until='domcontentloaded')
    page2.wait_for_function("window.dashboardState?.ready",timeout=180000)
    page2.wait_for_function("document.getElementById('ask-service-status').textContent.startsWith('Local service connected')",timeout=15000)
    assert page2.locator('#ask-submit').is_disabled()
    assert not errors, errors
    assert any('/local-status.json' in url and status==200 for url,status in responses)
    assert any('/api/ask' in url and status==202 for url,status in responses)
    print(json.dumps({'passed':True,'legacy_preview_online':True,'canonical_service_online':True,'browser_question_answered':True,'refresh_reconnected':True,'console_errors':errors}))
    browser.close()
