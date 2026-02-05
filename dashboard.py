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

# --- Improved Parse Function ---
def parse_orderbook(text: str):
    def parse_number(value):
        if not value or "--" in value:
            return None 
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
        
        if len(parts) == 1:
            try: spread_price = float(parts[0].replace(',', ''))
            except: pass
        elif len(parts) == 2:
            try:
                pct = parts[1].replace('(', '').replace('%)', '').replace('+', '')
                spread_pct = float(pct)
            except: pass
        elif len(parts) == 3:
            try:
                p_val = float(parts[0].replace(',', ''))
                amt = parse_number(parts[1])
                tot = parse_number(parts[2])
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
st.title("Quidax Orderbook Monitor (Continuous)")

pairs = [
    ['AAVE_USDT', 0.30], ['ADA_USDT', 0.26], ['ALGO_USDT', 2.00], ['BCH_USDT', 0.26],
    ['BNB_USDT', 0.30], ['BONK_USDT', 2.00], ['BTC_USDT', 0.20], ['CAKE_USDT', 0.30],
    ['CFX_USDT', 2.00], ['DOT_USDT', 0.26], ['DOGE_USDT', 0.26], ['ETH_USDT', 0.25],
    ['FARTCOIN_USDT', 2.00], ['FLOKI_USDT', 0.50], ['HYPE_USDT', 2.00], ['LINK_USDT', 0.26],
    ['NEAR_USDT', 2.00], ['NOS_USDT', 2.00], ['PEPE_USDT', 0.50], ['POL_USDT', 0.50],
    ['QDX_USDT', 10.00], ['RENDER_USDT', 2.00], ['Sonic_USDT', 2.00], ['SHIB_USDT', 0.40],
    ['SLP_USDT', 2.00], ['SOL_USDT', 0.30], ['STRK_USDT', 2.00], ['SUI_USDT', 2.00],
    ['TON_USDT', 0.30], ['TRX_USDT', 0.30], ['USDC_USDT', 0.02], ['WIF_USDT', 2.00],
    ['XLM_USDT', 0.30], ['XRP_USDT', 0.30], ['XYO_USDT', 1.00], ['ZKSync_USDT', 2.00],
    ['BTC_NGN', 0.50], ['USDT_NGN', 0.50], ['QDX_NGN', 10.00], ['ETH_NGN', 0.50],
    ['TRX_NGN', 0.50], ['XRP_NGN', 0.50], ['DASH_NGN', 0.50], ['LTC_NGN', 0.50],
    ['SOL_NGN', 0.50], ['USDC_NGN', 0.50]
]

# Initialize results_map with an extra field for 'prev_final_status'
if 'results_map' not in st.session_state:
    st.session_state.results_map = {p[0]: {
        "Pair": p[0], 
        "Current Spread %": None, 
        "Target %": p[1], 
        "Difference": None, 
        "Percent Diff %": None, 
        "Status": "Pending...", 
        "Last Updated": "-",
        "prev_final_status": "Pending" 
    } for p in pairs}

if st.button('Start Scraping'):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    if os.path.exists("/usr/bin/chromium-browser"):
        chrome_options.binary_location = "/usr/bin/chromium-browser"
    elif os.path.exists("/usr/bin/chromium"):
        chrome_options.binary_location = "/usr/bin/chromium"

    try:
        service = Service("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception:
        driver = webdriver.Chrome(options=chrome_options)

    wait = WebDriverWait(driver, 10)
    url = "https://pro.quidax.io/en_US/trade/"
    
    status_text = st.empty()
    table_placeholder = st.empty()
    
    MAX_WARNING_RETRIES = 3
    MAX_FAIL_RETRIES = 3

    def render_table():
        df_display = pd.DataFrame(list(st.session_state.results_map.values()))
        # Remove internal helper column from display
        display_cols = [c for c in df_display.columns if c != 'prev_final_status']
        
        def highlight_rows(row):
            status_val = str(row['Status'])
            prev_status = str(row['prev_final_status'])
            
            # 1. Red logic: If current status is Warning OR if it's a Warning-Retry but was Red before
            if status_val == 'Warning' or (status_val.startswith('Warning (Retry') and prev_status == 'Warning'):
                return ['background-color: rgba(255, 50, 50, 0.4)'] * len(row)
            
            # 2. Green logic
            elif status_val == 'Okay':
                return ['background-color: rgba(50, 255, 50, 0.3)'] * len(row)
            
            # 3. Yellow logic: For Retries (Undecided) or Failures
            elif 'Retry' in status_val or 'Failed' in status_val:
                return ['background-color: rgba(255, 255, 0, 0.3)'] * len(row)
            
            return [''] * len(row)

        table_placeholder.dataframe(
            df_display[display_cols].style.apply(highlight_rows, axis=1), 
            use_container_width=True,
            height=1000
        )

    try:
        # Loop 1: The Indefinite Run
        while True:
            # Prepare tracking queue for a full run
            tracking_queue = [{"symbol": p[0], "target": p[1], "warn_count": 0, "fail_count": 0} for p in pairs]
            
            # Loop 2: Processing the Queue (including retries)
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
                        wait.until(lambda d: "Spread" in element.text and any(c.isdigit() for c in element.text))
                        time.sleep(0.5)
                        
                        asks_df, bids_df, spread_df = parse_orderbook(element.text)

                        if not spread_df.empty and spread_df['spread_percent'][0] is not None:
                            current_val = spread_df['spread_percent'][0]
                            diff = current_val - target
                            percent_diff = (diff / target) * 100
                            
                            if percent_diff > 100 or percent_diff < -40:
                                if item["warn_count"] < MAX_WARNING_RETRIES:
                                    item["warn_count"] += 1
                                    next_pass_queue.append(item)
                                    status = f'Warning (Retry {item["warn_count"]}/{MAX_WARNING_RETRIES})'
                                else:
                                    status = 'Warning'
                            else:
                                status = 'Okay'
                            
                            st.session_state.results_map[symbol].update({
                                "Current Spread %": current_val,
                                "Difference": round(diff, 4),
                                "Percent Diff %": round(percent_diff, 2),
                                "Status": status,
                                "Last Updated": time.strftime("%H:%M:%S")
                            })
                        else:
                            raise ValueError("Spread data not found")
                        
                    except Exception:
                        item["fail_count"] += 1
                        if item["fail_count"] <= MAX_FAIL_RETRIES:
                            next_pass_queue.append(item)
                            status = f'Failed (Retry {item["fail_count"]}/{MAX_FAIL_RETRIES})'
                        else:
                            status = 'Failed Permanently'
                        st.session_state.results_map[symbol]["Status"] = status
                    
                    render_table()

                tracking_queue = next_pass_queue
                pass_idx += 1
            
            # After a full run finishes, update 'prev_final_status' for the next run's color logic
            for symbol in st.session_state.results_map:
                st.session_state.results_map[symbol]["prev_final_status"] = st.session_state.results_map[symbol]["Status"]

    finally:
        driver.quit()
