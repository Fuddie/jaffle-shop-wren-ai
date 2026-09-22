"""Browser acceptance checks. Uses temporary Playwright tooling and installed Chrome."""
import json
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(tempfile.gettempdir()) / 'jaffle-browser-tools'))
from playwright.sync_api import sync_playwright

APP = Path(__file__).resolve().parent
errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    page = browser.new_page(viewport={'width':1440,'height':1000}, device_scale_factor=1)
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
    page.goto('http://127.0.0.1:4173/', wait_until='domcontentloaded')
    try:
        page.wait_for_function("window.dashboardState?.ready || !document.getElementById('error').hidden", timeout=180000)
        if page.locator('#error').is_visible():
            raise AssertionError(page.locator('#error-message').inner_text())
        baseline = page.evaluate('window.dashboardState.results')
        assert baseline['kpis'][0]['order_count'] == 99
        assert baseline['kpis'][0]['total_order_amount'] == 1672
        assert baseline['inventory'][0]['customer_count'] == 100
        assert baseline['payments'][0]['payment_count'] == 113
        assert baseline['kpis'][0]['purchasing_customers'] == 62
        assert round(baseline['kpis'][0]['average_order_value'], 2) == 16.89
        assert baseline['kpis'][0]['completed_order_amount'] == 1103
        assert len(baseline['customers']) == 10
        assert baseline['customers'][0]['customer_id'] == 51
        for key in ['orphanOrders','orphanPayments','mismatches']:
            assert baseline[key][0]['issues'] == 0
        screenshot_dir = Path(tempfile.gettempdir()) / 'jaffle-browser-checks'
        screenshot_dir.mkdir(exist_ok=True)
        page.screenshot(path=str(screenshot_dir/'desktop.png'), full_page=True)
        for month in ['', '2018-01','2018-02','2018-03','2018-04']:
            for status in ['', 'completed','placed','returned','return_pending','shipped']:
                page.locator('#month').select_option(month)
                page.wait_for_function("document.getElementById('dashboard').getAttribute('aria-busy') === 'false'")
                page.locator('#status').select_option(status)
                page.wait_for_function("document.getElementById('dashboard').getAttribute('aria-busy') === 'false'")
                assert not page.locator('#error').is_visible(), page.locator('#error-message').inner_text()
                state=page.evaluate('window.dashboardState')
                assert state['month']==month and state['status']==status
                results=state['results']
                assert sum(r['order_count'] for r in results['monthly'])==results['kpis'][0]['order_count']
                assert abs(sum(r['total_order_amount'] for r in results['monthly'])-(results['kpis'][0]['total_order_amount'] or 0)) < 0.000001
                if status and status != 'completed':
                    assert (results['kpis'][0]['completed_order_amount'] or 0)==0
                if status == 'completed':
                    assert results['kpis'][0]['completed_order_amount']==results['kpis'][0]['total_order_amount']
        page.locator('#reset').click()
        page.wait_for_function("window.dashboardState?.month === '' && window.dashboardState?.status === ''")
        assert page.evaluate('window.dashboardState.results.kpis[0].order_count')==99
        # Keyboard controls, accessible disclosures, and tooltips.
        page.locator('#month').focus()
        page.keyboard.press('Tab')
        assert page.locator('#status').evaluate('(el) => el === document.activeElement')
        summary=page.locator('summary',has_text='Metric definitions')
        summary.focus(); page.keyboard.press('Enter')
        assert summary.locator('..').get_attribute('open') is not None
        page.locator('#chart g[tabindex]').first.focus()
        assert page.locator('#tooltip').is_visible()
        page.keyboard.press('Escape')
        assert not page.locator('#tooltip').is_visible()
        summary.focus(); page.keyboard.press('Enter')
        assert '\u2014' not in page.locator('body').inner_text()
        for width in [320,375,768,1024,1440]:
            page.set_viewport_size({'width':width,'height':900})
            page.wait_for_timeout(180)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Page overflow at {width}'
            assert page.locator('#month').is_visible()
            if width==320:
                page.screenshot(path=str(screenshot_dir/'mobile.png'),full_page=True)
        assert not errors, errors
        print(json.dumps({'passed':True,'filter_combinations':30,'widths':[320,375,768,1024,1440],'console_errors':errors,'screenshots':str(screenshot_dir)}))
    except Exception:
        print(json.dumps({'console_errors':errors,'body':page.locator('body').inner_text()[:3000]}))
        raise
    finally:
        browser.close()
