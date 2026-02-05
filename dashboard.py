import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import os
from selenium.webdriver.chrome.service import Service
import re

# --- Improved Parse Function ---
def parse_orderbook(text: str):
    def parse_number(value):
        if not value or "--" in value:
            return None # Return None for empty/placeholder layers
        try:
            if value.endswith('K'): return float(value[:-1]) * 1_000
            elif value.endswith('M'): return float(value[:-1]) * 1_000_000
            return float(value.replace(',', ''))
        except:
            return None

    lines = text.split("\n")
    asks, bids = [], []
    spread_price, spread_pct = None, None
    side = "asks"

    for line in lines:
        if "Spread" in line:
            side = "bids"
            continue
            
        parts = line.split()
        
        # Handle the Spread Price Row
        if len(parts) == 1:
            try: spread_price = float(parts[0].replace(',', ''))
            except: pass
        # Handle the Spread Percentage Row
        elif len(parts) == 2:
            try:
                pct = parts[1].replace('(', '').replace('%)', '').replace('+', '')
                spread_pct = float(pct)
            except: pass
        # Handle Order Rows (Price, Amount, Total)
        elif len(parts) == 3:
            try:
                p_val = float(parts[0].replace(',', ''))
                amt = parse_number(parts[1])
                tot = parse_number(parts[2])
                
                # Only add if we have actual numeric data (skips '--' rows)
                if amt is not None and tot is not None:
                    row = {"price": p_val, "amount": amt, "total": tot}
                    if side == "asks": asks.append(row)
                    else: bids.append(row)
            except ValueError:
                continue

    asks_df = pd.DataFrame(asks, columns=["price", "amount", "total"])
    bids_df = pd.DataFrame(bids, columns=["price", "amount", "total"])

    if not asks_df.empty:
        asks_df = asks_df.sort_values("price", ascending=False).reset_index(drop=True)
    if not bids_df.empty:
        bids_df = bids_df.sort_values("price", ascending=False).reset_index(drop=True)

    spread_df = pd.DataFrame([{"spread_price": spread_price, "spread_percent": spread_pct}])
    return asks_df, bids_df, spread_df

# --- Streamlit UI Setup ---
st.set_page_config(page_title="Crypto Spread Monitor", layout="wide")
st.title("Quidax Orderbook Monitor")

if st.button('Start Scraping'):
    # ... inside your button click logic ...

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    chrome_options.add_argument(f"user-agent={user_agent}")

    # --- PATH FIX FOR STREAMLIT CLOUD ---
    # If running on Streamlit Cloud, use the chromium paths from packages.txt
    if os.path.exists("/usr/bin/chromium-browser"):
        chrome_options.binary_location = "/usr/bin/chromium-browser"
    elif os.path.exists("/usr/bin/chromium"):
        chrome_options.binary_location = "/usr/bin/chromium"

    # Try to initialize the driver with a service path
    try:
        # Most common path on Streamlit Cloud
        service = Service("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception:
        # Fallback for local testing
        driver = webdriver.Chrome(options=chrome_options)

# --- NEW: Cloud-Specific Rendering Wait ---
# Headless browsers on Linux servers are sometimes slower than local ones

    wait = WebDriverWait(driver, 5) # Shorter wait for better responsiveness

    url = "https://pro.quidax.io/en_US/trade/"
    pairs = [
        ['QDX_NGN', 10.00],['AAVE_USDT', 0.30], ['ADA_USDT', 0.26], ['ALGO_USDT', 2.00], ['BCH_USDT', 0.26],
        ['BNB_USDT', 0.30], ['BONK_USDT', 2.00], ['BTC_USDT', 0.20], ['CAKE_USDT', 0.30],
        ['CFX_USDT', 2.00], ['DOT_USDT', 0.26], ['DOGE_USDT', 0.26], ['ETH_USDT', 0.25],
        ['FARTCOIN_USDT', 2.00], ['FLOKI_USDT', 0.50], ['HYPE_USDT', 2.00], ['LINK_USDT', 0.26],
        ['NEAR_USDT', 2.00], ['NOS_USDT', 2.00], ['PEPE_USDT', 0.50], ['POL_USDT', 0.50],
        ['QDX_USDT', 10.00], ['RENDER_USDT', 2.00], ['SONIC_USDT', 2.00], ['SHIB_USDT', 0.40],
        ['SLP_USDT', 2.00], ['SOL_USDT', 0.30], ['STRK_USDT', 2.00], ['SUI_USDT', 2.00],
        ['TON_USDT', 0.30], ['TRX_USDT', 0.30], ['USDC_USDT', 0.02], ['WIF_USDT', 2.00],
        ['XLM_USDT', 0.30], ['XRP_USDT', 0.30], ['XYO_USDT', 1.00], ['ZKSync_USDT', 2.00],
        ['BTC_NGN', 0.50], ['USDT_NGN', 0.50], ['ETH_NGN', 0.50],
        ['TRX_NGN', 0.50], ['XRP_NGN', 0.50], ['DASH_NGN', 0.50], ['LTC_NGN', 0.50],
        ['SOL_NGN', 0.50], ['USDC_NGN', 0.50]
    ]

    status_text = st.empty()
    table_placeholder = st.empty()
    
    MAX_WARNING_RETRIES = 3
    MAX_FAIL_RETRIES = 3
    
    tracking_queue = [{"symbol": p[0], "target": p[1], "warn_count": 0, "fail_count": 0} for p in pairs]
    results_map = {p[0]: {"Pair": p[0], "Current Spread %": None, "Target %": p[1], "Difference": None, "Percent Diff %": None, "Status": "Pending...", "Last Updated": "-"} for p in pairs}

    def render_table():
        df_display = pd.DataFrame(list(results_map.values()))
        def highlight_rows(row):
            status_val = str(row['Status'])
            if status_val == 'Warning':
                return ['background-color: rgba(255, 50, 50, 0.3)'] * len(row)
            elif status_val == 'Okay':
                return ['background-color: rgba(50, 255, 50, 0.3)'] * len(row)
            elif 'Retry' in status_val:
                return ['background-color: rgba(255, 165, 0, 0.2)'] * len(row)
            return [''] * len(row)
        table_placeholder.dataframe(df_display.style.apply(highlight_rows, axis=1), use_container_width=True)

    render_table()

    try:
        pass_idx = 1
        while tracking_queue:
            next_pass_queue = []
            for item in tracking_queue:
                symbol = item["symbol"]
                target = item["target"]
                
                status_text.text(f"Scanning {symbol} (Pass {pass_idx})...")
                
                try:
                    driver.get(url + symbol)
                    selector = ".newTrade-depth-block.depath-index-container"
                    element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    
                    # NEW WAIT LOGIC: Wait until the text contains "Spread" and at least one digit 
                    # This allows "--" to remain in the rest of the element.
                    wait.until(lambda d: "Spread" in element.text and any(c.isdigit() for c in element.text))
                    
                    # Optional: small sleep to let the specific numbers settle
                    time.sleep(0.5)
                    
                    asks_df, bids_df, spread_df = parse_orderbook(element.text)

                    if not spread_df.empty and spread_df['spread_percent'][0] is not None:
                        current_val = spread_df['spread_percent'][0]
                        diff = current_val - target
                        percent_diff = (diff / target) * 100
                        
                        # Logic: Warning if > 100% higher or > 40% lower
                        if percent_diff > 100 or percent_diff < -40:
                            if item["warn_count"] < MAX_WARNING_RETRIES:
                                item["warn_count"] += 1
                                next_pass_queue.append(item)
                                status = f'Warning (Retry {item["warn_count"]}/{MAX_WARNING_RETRIES})'
                            else:
                                status = 'Warning'
                        else:
                            status = 'Okay'
                        
                        results_map[symbol].update({
                            "Current Spread %": current_val,
                            "Difference": round(diff, 4),
                            "Percent Diff %": round(percent_diff, 2),
                            "Status": status,
                            "Last Updated": time.strftime("%H:%M:%S")
                        })
                    else:
                        raise ValueError("Spread data not found in element text")
                    
                except Exception:
                    item["fail_count"] += 1
                    if item["fail_count"] <= MAX_FAIL_RETRIES:
                        next_pass_queue.append(item)
                        status = f'Failed (Retry {item["fail_count"]}/{MAX_FAIL_RETRIES})'
                    else:
                        status = 'Failed Permanently'
                    results_map[symbol]["Status"] = status
                
                render_table()

            tracking_queue = next_pass_queue
            pass_idx += 1

        status_text.success("Scraping complete.")
    finally:
        driver.quit()