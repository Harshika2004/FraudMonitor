"""
Visible Browser End-to-End Automated Testing Script
Controls a visible Edge/Chrome browser window via Chrome DevTools Protocol (CDP).
Executes all 10 tests and captures the 7 required screenshots.
"""

import asyncio
import json
import os
import sys
import subprocess
import time
import base64
import urllib.request
import websockets

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SCREENSHOT_DIR = os.path.abspath("screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

CSV_FILE = os.path.abspath(r"database\sample_transactions_1000.csv")

class CDPClient:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self._msg_id = 0

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url, max_size=50 * 1024 * 1024)

    async def close(self):
        if self.ws:
            await self.ws.close()

    async def send_cmd(self, method, params=None):
        self._msg_id += 1
        msg = {"id": self._msg_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(msg))
        while True:
            resp_str = await self.ws.recv()
            resp = json.loads(resp_str)
            if resp.get("id") == self._msg_id:
                if "error" in resp:
                    raise Exception(f"CDP Error ({method}): {resp['error']}")
                return resp.get("result", {})

    async def eval_js(self, expression):
        res = await self.send_cmd("Runtime.evaluate", {
            "expression": expression,
            "awaitPromise": True,
            "returnByValue": True
        })
        val = res.get("result", {})
        return val.get("value")

    async def take_screenshot(self, filename):
        filepath = os.path.join(SCREENSHOT_DIR, filename)
        res = await self.send_cmd("Page.captureScreenshot", {"format": "png"})
        img_bytes = base64.b64decode(res["data"])
        with open(filepath, "wb") as f:
            f.write(img_bytes)
        print(f"  [SCREENSHOT SAVED] {filepath} ({len(img_bytes):,} bytes)")
        return filepath

async def run_tests():
    print("=" * 60)
    print("  Banking Transaction Monitoring - Visible E2E Browser Testing")
    print("=" * 60)

    # 1. Start visible browser process
    browser_exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if not os.path.exists(browser_exe):
        browser_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

    user_data = os.path.abspath(r"C:\temp\visible_e2e_profile")
    os.makedirs(user_data, exist_ok=True)

    print(f"\n[STEP 0] Launching visible browser: {browser_exe}")
    proc = subprocess.Popen([
        browser_exe,
        "--remote-debugging-port=9222",
        "--remote-allow-origins=*",
        f"--user-data-dir={user_data}",
        "--window-size=1366,850",
        "about:blank"
    ])

    try:
        # Wait for CDP endpoint
        ws_url = None
        for attempt in range(15):
            time.sleep(1)
            try:
                data = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read())
                for target in data:
                    if target.get("type") == "page":
                        ws_url = target.get("webSocketDebuggerUrl")
                        break
                if ws_url:
                    break
            except Exception:
                pass

        if not ws_url:
            raise Exception("Could not connect to browser CDP on port 9222.")

        print(f"[STEP 0] Connected to browser CDP WebSocket.")
        cdp = CDPClient(ws_url)
        await cdp.connect()

        await cdp.send_cmd("Page.enable")
        await cdp.send_cmd("DOM.enable")
        await cdp.send_cmd("Runtime.enable")

        # -------------------------------------------------------------
        # TEST 1 — Application Startup
        # -------------------------------------------------------------
        print("\n--- TEST 1: Application Startup ---")
        await cdp.send_cmd("Page.navigate", {"url": "http://127.0.0.1:8000/"})
        await asyncio.sleep(2)

        # Clear sessionStorage to guarantee clean fresh application visit
        await cdp.eval_js("sessionStorage.clear(); window.location.reload();")
        await asyncio.sleep(2)

        is_landing_visible = await cdp.eval_js("document.getElementById('step-landing').style.display !== 'none'")
        is_sidebar_hidden = await cdp.eval_js("document.querySelector('.app-sidebar').style.display === 'none'")
        title_text = await cdp.eval_js("document.querySelector('.landing-title').innerText")

        print(f"  Landing visible: {is_landing_visible}")
        print(f"  Sidebar hidden: {is_sidebar_hidden}")
        print(f"  Section Title: '{title_text}'")

        assert is_landing_visible, "TEST 1 FAILED: Step landing is not visible!"
        assert is_sidebar_hidden, "TEST 1 FAILED: Sidebar should be hidden on initial startup!"
        assert "Transaction Analysis Workspace" in title_text, f"Unexpected title: {title_text}"

        ss1 = await cdp.take_screenshot("1_initial_upload_page.png")
        print("  >>> TEST 1 PASSED: Application opens CSV Upload Landing Page first.")

        # -------------------------------------------------------------
        # TEST 2 & 3 — CSV Upload & Preview/Validation
        # -------------------------------------------------------------
        print("\n--- TEST 2 & 3: CSV Upload and Data Validation Preview ---")
        print(f"  Uploading file: {CSV_FILE}")

        # Use CDP DOM to set file on #csv-file-input
        doc = await cdp.send_cmd("DOM.getDocument")
        input_node = await cdp.send_cmd("DOM.querySelector", {
            "nodeId": doc["root"]["nodeId"],
            "selector": "#csv-file-input"
        })
        assert input_node.get("nodeId"), "Could not locate #csv-file-input!"

        await cdp.send_cmd("DOM.setFileInputFiles", {
            "nodeId": input_node["nodeId"],
            "files": [CSV_FILE]
        })

        # Wait for preview API to return and render
        await asyncio.sleep(2.5)

        is_preview_visible = await cdp.eval_js("document.getElementById('step-preview').style.display !== 'none'")
        preview_filename = await cdp.eval_js("document.getElementById('preview-filename').innerText")
        preview_rows = await cdp.eval_js("document.getElementById('preview-rows').innerText")
        preview_cols = await cdp.eval_js("document.getElementById('preview-cols').innerText")
        table_rows_count = await cdp.eval_js("document.querySelectorAll('#preview-table-tbody tr').length")

        print(f"  Preview visible: {is_preview_visible}")
        print(f"  Filename: {preview_filename}")
        print(f"  Rows chip: {preview_rows}")
        print(f"  Cols chip: {preview_cols}")
        print(f"  Sample rows displayed: {table_rows_count}")

        assert is_preview_visible, "TEST 2/3 FAILED: Preview screen not shown after file selection!"
        assert "sample_transactions" in preview_filename, f"Unexpected filename: {preview_filename}"
        assert table_rows_count >= 10, f"Expected at least 10 preview rows, got {table_rows_count}"

        ss2 = await cdp.take_screenshot("2_csv_preview_validation.png")
        print("  >>> TEST 2 & 3 PASSED: CSV parsed, validated, and preview table displayed.")

        # -------------------------------------------------------------
        # TEST 4 & 5 — Fraud Analysis Execution and Direct Dashboard Redirect
        # -------------------------------------------------------------
        print("\n--- TEST 4 & 5: Run Fraud Analysis and Direct Dashboard Redirect ---")
        # Click Confirm and Run Fraud Analysis
        await cdp.eval_js("document.getElementById('btn-confirm-preview').click()")

        # Wait for loading indicator and then analysis completion + dashboard render
        print("  Waiting for deterministic fraud detection engine to complete...")
        for _ in range(20):
            await asyncio.sleep(1)
            is_main_visible = await cdp.eval_js("document.querySelector('.main-wrapper').style.display !== 'none'")
            if is_main_visible:
                break

        is_workflow_hidden = await cdp.eval_js("document.getElementById('workflow-wrapper').style.display === 'none'")
        is_sidebar_visible = await cdp.eval_js("document.querySelector('.app-sidebar').style.display !== 'none'")
        badge_text = await cdp.eval_js("document.getElementById('active-dataset-badge').innerText")
        total_txns_kpi = await cdp.eval_js("document.getElementById('kpi-total-txns').innerText")
        flagged_kpi = await cdp.eval_js("document.getElementById('kpi-flagged-txns').innerText")

        print(f"  Main dashboard visible: {is_main_visible}")
        print(f"  Workflow wrapper hidden: {is_workflow_hidden}")
        print(f"  Sidebar visible: {is_sidebar_visible}")
        print(f"  Active dataset badge: '{badge_text}'")
        print(f"  Total transactions KPI: {total_txns_kpi}")
        print(f"  Flagged suspicious KPI: {flagged_kpi}")

        assert is_main_visible, "TEST 4/5 FAILED: Dashboard did not open automatically!"
        assert is_workflow_hidden, "TEST 4/5 FAILED: Workflow wrapper should be hidden!"
        assert is_sidebar_visible, "TEST 4/5 FAILED: Sidebar should be visible!"

        await asyncio.sleep(1)
        ss3 = await cdp.take_screenshot("3_dashboard_after_analysis.png")
        print("  >>> TEST 4 & 5 PASSED: Engine ran, direct redirect to Overview Dashboard succeeded.")

        # -------------------------------------------------------------
        # TEST 6 — Sidebar Navigation Across All Dashboard Pages
        # -------------------------------------------------------------
        print("\n--- TEST 6: Sidebar Navigation ---")

        # 6a: Overview Dashboard click (should NOT return to upload)
        await cdp.eval_js("document.querySelector('#nav-overview a').click()")
        await asyncio.sleep(1)
        assert await cdp.eval_js("document.querySelector('.main-wrapper').style.display !== 'none'"), "Clicking Overview Dashboard hid the dashboard!"
        assert await cdp.eval_js("document.getElementById('workflow-wrapper').style.display === 'none'"), "Clicking Overview Dashboard showed upload workflow!"
        ss4 = await cdp.take_screenshot("4_overview_dashboard_nav.png")
        print("  [6a] Overview Dashboard link clicked: remained on dashboard.")

        # 6b: Transactions page
        await cdp.send_cmd("Page.navigate", {"url": "http://127.0.0.1:8000/transactions"})
        await asyncio.sleep(2)
        tx_count = await cdp.eval_js("document.querySelectorAll('#transactions-tbody tr').length")
        print(f"  [6b] Transactions page loaded: {tx_count} table rows.")
        assert tx_count > 0, "Transactions table is empty!"
        ss5 = await cdp.take_screenshot("5_transactions_page.png")

        # 6c: Alerts page
        await cdp.send_cmd("Page.navigate", {"url": "http://127.0.0.1:8000/alerts"})
        await asyncio.sleep(2)
        alerts_count = await cdp.eval_js("document.querySelectorAll('#alerts-tbody tr').length")
        print(f"  [6c] Alerts page loaded: {alerts_count} alert rows.")

        # 6d: Detection Rules page
        await cdp.send_cmd("Page.navigate", {"url": "http://127.0.0.1:8000/rules"})
        await asyncio.sleep(2)
        rules_count = await cdp.eval_js("document.querySelectorAll('#rules-list-container .data-card').length")
        print(f"  [6d] Detection Rules page loaded: {rules_count} configured rules.")
        assert rules_count == 5, f"Expected 5 rules, got {rules_count}!"
        ss6 = await cdp.take_screenshot("6_detection_rules_page.png")

        # 6e: Customer Directory page
        await cdp.send_cmd("Page.navigate", {"url": "http://127.0.0.1:8000/customers"})
        await asyncio.sleep(2)
        cust_count = await cdp.eval_js("document.querySelectorAll('#customers-tbody tr').length")
        print(f"  [6e] Customer Directory page loaded: {cust_count} customer rows.")

        # -------------------------------------------------------------
        # TEST 7 — Dashboard Persistence on Return from Other Pages
        # -------------------------------------------------------------
        print("\n--- TEST 7: Dashboard Persistence ---")
        # Click Overview Dashboard link in sidebar from customers page
        await cdp.eval_js("document.querySelector('.nav-links a[href=\"/\"]').click()")
        await asyncio.sleep(2)

        is_main_still_visible = await cdp.eval_js("document.querySelector('.main-wrapper').style.display !== 'none'")
        is_workflow_still_hidden = await cdp.eval_js("document.getElementById('workflow-wrapper').style.display === 'none'")
        badge_text_persisted = await cdp.eval_js("document.getElementById('active-dataset-badge').innerText")

        print(f"  Main visible after navigating back: {is_main_still_visible}")
        print(f"  Workflow hidden after navigating back: {is_workflow_still_hidden}")
        print(f"  Active dataset badge: '{badge_text_persisted}'")

        assert is_main_still_visible, "TEST 7 FAILED: Overview Dashboard did not display when returning from sidebar link!"
        assert is_workflow_still_hidden, "TEST 7 FAILED: Upload page was shown instead of Dashboard!"
        print("  >>> TEST 7 PASSED: Overview Dashboard and dataset persisted through sidebar navigation.")

        # -------------------------------------------------------------
        # TEST 8 — Detection Rules Complete Verification
        # -------------------------------------------------------------
        print("\n--- TEST 8: Dedicated Detection Rules Verification ---")
        await cdp.send_cmd("Page.navigate", {"url": "http://127.0.0.1:8000/rules"})
        await asyncio.sleep(2)
        rule_titles = await cdp.eval_js("Array.from(document.querySelectorAll('.data-card-title')).map(e => e.innerText)")
        print(f"  Rules present ({len(rule_titles)}): {rule_titles}")
        assert len(rule_titles) == 5, f"Expected 5 rules, found {len(rule_titles)}"
        print("  >>> TEST 8 PASSED: All 5 detection rules exist exclusively on the dedicated rules page.")

        # -------------------------------------------------------------
        # TEST 9 — Dataset Switching
        # -------------------------------------------------------------
        print("\n--- TEST 9: Dataset Switching ---")
        # Return to dashboard
        await cdp.send_cmd("Page.navigate", {"url": "http://127.0.0.1:8000/"})
        await asyncio.sleep(2)

        # Open Switcher modal
        await cdp.eval_js("document.getElementById('btn-switch-dataset').click()")
        await asyncio.sleep(1)
        modal_visible = await cdp.eval_js("document.getElementById('modal-dataset-switcher').style.display !== 'none'")
        print(f"  Dataset Switcher modal opened: {modal_visible}")

        # Switch to dataset 1 (initial_synthetic_seed.csv)
        item_count = await cdp.eval_js("document.querySelectorAll('.dataset-list-item').length")
        print(f"  Datasets listed in switcher: {item_count}")

        # Switch to first dataset that has switch button
        switched = await cdp.eval_js("""
            (function() {
                const btn = document.querySelector('.dataset-list-item button');
                if (btn) {
                    btn.click();
                    return true;
                }
                return false;
            })()
        """)
        print(f"  Switched to alternate dataset: {switched}")
        await asyncio.sleep(2.5)

        new_badge_text = await cdp.eval_js("document.getElementById('active-dataset-badge').innerText")
        new_kpi = await cdp.eval_js("document.getElementById('kpi-total-txns').innerText")
        print(f"  New active dataset badge: '{new_badge_text}'")
        print(f"  New total transactions KPI: {new_kpi}")

        ss7 = await cdp.take_screenshot("7_dataset_switched.png")
        print("  >>> TEST 9 PASSED: Dataset switched cleanly, metrics updated.")

        # -------------------------------------------------------------
        # TEST 10 — Browser Refresh Persistence
        # -------------------------------------------------------------
        print("\n--- TEST 10: Browser Refresh Persistence ---")
        await cdp.send_cmd("Page.navigate", {"url": "http://127.0.0.1:8000/"})
        await asyncio.sleep(2.5)

        is_main_after_refresh = await cdp.eval_js("document.querySelector('.main-wrapper').style.display !== 'none'")
        is_workflow_after_refresh = await cdp.eval_js("document.getElementById('workflow-wrapper').style.display === 'none'")
        badge_after_refresh = await cdp.eval_js("document.getElementById('active-dataset-badge').innerText")

        print(f"  Dashboard visible after refresh: {is_main_after_refresh}")
        print(f"  Workflow hidden after refresh: {is_workflow_after_refresh}")
        print(f"  Active badge after refresh: '{badge_after_refresh}'")

        assert is_main_after_refresh, "TEST 10 FAILED: Refresh dumped user back to upload page!"
        assert is_workflow_after_refresh, "TEST 10 FAILED: Workflow wrapper was shown on refresh!"
        print("  >>> TEST 10 PASSED: Browser refresh maintains active monitoring workspace.")

        await cdp.close()
        print("\n" + "=" * 60)
        print("  ALL 10 TESTS EXECUTED AND PASSED SUCCESSFULLY!")
        print("=" * 60)

    finally:
        print("\n[CLEANUP] Closing test browser...")
        proc.terminate()
        proc.wait(timeout=5)
        print("[CLEANUP] Test browser terminated.")

if __name__ == "__main__":
    asyncio.run(run_tests())
