import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import os
import re
from selenium.webdriver.chrome.service import Service
import gc  # Garbage collector


# --- Improved Parse Function ---
def parse_orderbook(text: str):
    """
    Parse orderbook text into structured dataframes for asks, bids, and spread.
    
    Args:
        text: Raw text from orderbook element
        
    Returns:
        Tuple of (asks_df, bids_df, spread_df)
    """
    def parse_number(value):
        """Convert K/M suffixes to numeric values, handle placeholders"""
        if not value or "--" in value:
            return None
        try:
            if '{' in value and '}' in value:
                match = re.search(r"0\.0\{(\d+)\}(\d+)", value)
                if match:
                    zeros = int(match.group(1))
                    digits = match.group(2)
                    value = "0." + ("0" * zeros) + digits
            if value.endswith('K'):
                return float(value[:-1]) * 1_000
            elif value.endswith('M'):
                return float(value[:-1]) * 1_000_000
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
            try:
                spread_price = float(parts[0].replace(',', ''))
            except:
                pass
                
        # Handle the Spread Percentage Row
        elif len(parts) == 2:
            try:
                pct = parts[1].replace('(', '').replace('%)', '').replace('+', '')
                spread_pct = float(pct)
            except:
                pass
                
        # Handle Order Rows (Price, Amount, Total)
        elif len(parts) == 3:
            try:
                p_val = float(parts[0].replace(',', ''))
                amt = parse_number(parts[1])
                tot = parse_number(parts[2])
                
                # Only add if we have actual numeric data (skips '--' rows)
                if amt is not None and tot is not None:
                    row = {"price": p_val, "amount": amt, "total": tot}
                    if side == "asks":
                        asks.append(row)
                    else:
                        bids.append(row)
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


# --- Depth Calculation Function (Quote Currency) ---
def calculate_liquidity_depth(asks_df, bids_df, spread_pct):
    """
    Calculate total liquidity depth within spread_pct of mid-price IN QUOTE CURRENCY.
    
    Args:
        asks_df: DataFrame with ask orders (price, amount, total)
        bids_df: DataFrame with bid orders (price, amount, total)
        spread_pct: Percentage range from mid-price (e.g., 1.0 for 1%, 2.0 for 2%)
        
    Returns:
        Total liquidity in quote currency (USDT/NGN) within the spread range, or None if data unavailable
    """
    # Check if we have data
    if asks_df.empty or bids_df.empty:
        return None
    
    # Get best bid and ask prices
    best_ask = asks_df['price'].min()  # Lowest ask
    best_bid = bids_df['price'].max()  # Highest bid
    
    # Calculate mid-price
    mid_price = (best_ask + best_bid) / 2
    
    # Calculate price bounds
    upper_bound = mid_price * (1 + spread_pct / 100)
    lower_bound = mid_price * (1 - spread_pct / 100)
    
    # Filter orders within bounds
    valid_bids = bids_df[bids_df['price'] >= lower_bound].copy()
    valid_asks = asks_df[asks_df['price'] <= upper_bound].copy()
    
    # Calculate bid-side liquidity in QUOTE CURRENCY (price × amount)
    if not valid_bids.empty:
        valid_bids['quote_value'] = valid_bids['price'] * valid_bids['amount']
        bid_depth = valid_bids['quote_value'].sum()
    else:
        bid_depth = 0
    
    # Calculate ask-side liquidity in QUOTE CURRENCY (price × amount)
    if not valid_asks.empty:
        valid_asks['quote_value'] = valid_asks['price'] * valid_asks['amount']
        ask_depth = valid_asks['quote_value'].sum()
    else:
        ask_depth = 0
    
    # Total depth (both sides) in quote currency
    total_depth = bid_depth + ask_depth
    
    return total_depth


def format_depth_value(depth_value):
    """
    Format depth value for display with K/M suffix.
    
    Args:
        depth_value: Numeric depth value in USD
        
    Returns:
        Formatted string (e.g., "$10.5K", "$1.2M")
    """
    if depth_value is None:
        return "--"
    
    if depth_value >= 1_000_000:
        return f"${depth_value / 1_000_000:.2f}M"
    elif depth_value >= 1_000:
        return f"${depth_value / 1_000:.1f}K"
    else:
        return f"${depth_value:.0f}"


def init_chrome_driver():
    """
    Initialize Chrome WebDriver with appropriate options for headless operation.
    
    Returns:
        WebDriver instance
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # MEMORY OPTIMIZATION: Limit cache and disable features
    chrome_options.add_argument("--disk-cache-size=1")
    chrome_options.add_argument("--media-cache-size=1")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    chrome_options.add_argument(f"user-agent={user_agent}")
    
    # Path fix for Streamlit Cloud
    if os.path.exists("/usr/bin/chromium-browser"):
        chrome_options.binary_location = "/usr/bin/chromium-browser"
    elif os.path.exists("/usr/bin/chromium"):
        chrome_options.binary_location = "/usr/bin/chromium"
    
    try:
        service = Service("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception:
        driver = webdriver.Chrome(options=chrome_options)
    
    return driver


def cleanup_driver(driver):
    """
    Properly cleanup driver resources.
    """
    try:
        driver.quit()
    except:
        pass
    
    # Force garbage collection
    gc.collect()


# --- Streamlit UI Setup ---
st.set_page_config(page_title="Crypto Spread Monitor", layout="wide")
st.title("Quidax Orderbook Monitor")

# Initialize session state for button control
if 'scraping_active' not in st.session_state:
    st.session_state.scraping_active = False

# Trading pairs configuration
PAIRS = [
    ['AAVE_USDT', 0.30], ['ADA_USDT', 0.26], ['ALGO_USDT', 2.00],
    ['BCH_USDT', 0.26], ['BNB_USDT', 0.30], ['BONK_USDT', 2.00],
    ['BTC_USDT', 0.20], ['CAKE_USDT', 0.30], ['CFX_USDT', 2.00],
    ['DOT_USDT', 0.26], ['DOGE_USDT', 0.26], ['ETH_USDT', 0.25],
    ['FARTCOIN_USDT', 2.00], ['FLOKI_USDT', 0.50], ['HYPE_USDT', 2.00],
    ['LINK_USDT', 0.26], ['NEAR_USDT', 2.00], ['NOS_USDT', 2.00],
    ['PEPE_USDT', 0.50], ['POL_USDT', 0.50], ['QDX_USDT', 10.00],
    ['RENDER_USDT', 2.00], ['Sonic_USDT', 2.00], ['SHIB_USDT', 0.40],
    ['SLP_USDT', 2.00], ['SOL_USDT', 0.30], ['STRK_USDT', 2.00],
    ['SUI_USDT', 2.00], ['TON_USDT', 0.30], ['TRX_USDT', 0.30],
    ['USDC_USDT', 0.02], ['WIF_USDT', 2.00], ['XLM_USDT', 0.30],
    ['XRP_USDT', 0.30], ['XYO_USDT', 1.00], ['ZKSync_USDT', 2.00],
    ['BTC_NGN', 0.50], ['USDT_NGN', 0.50], ['QDX_NGN', 10.00],
    ['ETH_NGN', 0.50], ['TRX_NGN', 0.50], ['XRP_NGN', 0.50],
    ['DASH_NGN', 0.50], ['LTC_NGN', 0.50], ['SOL_NGN', 0.50],
    ['USDC_NGN', 0.50]
]

# Constants
MAX_WARNING_RETRIES = 3
MAX_FAIL_RETRIES = 3
BASE_URL = "https://pro.quidax.io/en_US/trade/"
DRIVER_RESTART_CYCLES = 5  # Restart driver every N cycles to prevent memory leaks

# Initialize results map with persistent tracking (NOW WITH DEPTH FIELDS)
if 'results_map' not in st.session_state:
    st.session_state.results_map = {
        p[0]: {
            "Pair": p[0],
            "Current Spread %": None,
            "Target %": p[1],
            "Difference": None,
            "Percent Diff %": None,
            "Depth @ 1.25x": None,
            "Depth @ 1.5x": None,
            "Status": "Pending...",
            "Last Updated": "-",
            "warn_count": 0,
            "fail_count": 0
        } for p in PAIRS
    }

results_map = st.session_state.results_map

# UI placeholders
status_text = st.empty()
health_metric = st.empty()  # NEW: Health indicator
table_placeholder = st.empty()


def render_table():
    """Render the results table with color-coded status highlighting"""
    df_display = pd.DataFrame([
        {k: v for k, v in item.items() if k not in ['warn_count', 'fail_count']}
        for item in results_map.values()
    ])
    
    def highlight_rows(row):
        """Apply background color based on status"""
        status_val = str(row['Status'])
        
        if status_val == 'Warning':
            # Red for poor spread
            return ['background-color: rgba(255, 50, 50, 0.3)'] * len(row)
        elif status_val == 'Okay':
            # Green for good spread
            return ['background-color: rgba(50, 255, 50, 0.3)'] * len(row)
        else:
            # Yellow for everything else (Pending, Retry, Re-checking, Failed)
            return ['background-color: rgba(255, 255, 0, 0.2)'] * len(row)
    
    table_placeholder.dataframe(
        df_display.style.apply(highlight_rows, axis=1),
        use_container_width=True
    )


# Main scraping button
if st.button('Start Scraping', disabled=st.session_state.scraping_active):
    st.session_state.scraping_active = True
    
    driver = None
    cycle_number = 1
    
    try:
        while True:  # Infinite loop for continuous monitoring
            # DRIVER RESTART LOGIC - Restart driver periodically to prevent memory leaks
            if driver is None or cycle_number % DRIVER_RESTART_CYCLES == 1:
                if driver is not None:
                    status_text.text("♻️ Restarting browser to free memory...")
                    cleanup_driver(driver)
                    time.sleep(2)
                
                status_text.text("🔧 Initializing browser...")
                driver = init_chrome_driver()
                wait = WebDriverWait(driver, 10)
                health_metric.success(f"✅ Browser healthy (Cycle {cycle_number})")
            
            # Initialize tracking queue for this cycle
            tracking_queue = []
            
            for p in PAIRS:
                symbol = p[0]
                target = p[1]
                previous_status = results_map[symbol]["Status"]
                
                # Preserve counters from previous cycles
                item = {
                    "symbol": symbol,
                    "target": target,
                    "warn_count": results_map[symbol]["warn_count"],
                    "fail_count": results_map[symbol]["fail_count"],
                    "previous_status": previous_status
                }
                tracking_queue.append(item)
            
            # Render initial table state for this cycle
            render_table()
            
            # Process markets in passes (with retry logic)
            pass_idx = 1
            
            while tracking_queue:
                next_pass_queue = []
                
                for item in tracking_queue:
                    symbol = item["symbol"]
                    target = item["target"]
                    previous_status = item["previous_status"]
                    
                    status_text.text(f"Cycle {cycle_number} | Pass {pass_idx} | Scanning {symbol}...")
                    
                    try:
                        # Navigate to market page
                        driver.get(BASE_URL + symbol)
                        
                        # Wait for orderbook element
                        selector = ".newTrade-depth-block.depath-index-container"
                        element = wait.until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        
                        # Wait for spread data to load
                        wait.until(lambda d: "Spread" in element.text and 
                                  any(c.isdigit() for c in element.text))
                        
                        # Small buffer for number stabilization
                        time.sleep(0.5)
                        
                        # Parse orderbook data
                        asks_df, bids_df, spread_df = parse_orderbook(element.text)
                        
                        # Calculate Depth Metrics at 1.25x and 1.5x current spread
                        if not spread_df.empty and spread_df['spread_percent'][0] is not None:
                            current_spread = spread_df['spread_percent'][0]
                            depth_1_25x = calculate_liquidity_depth(asks_df, bids_df, current_spread * 1.25)
                            depth_1_5x = calculate_liquidity_depth(asks_df, bids_df, current_spread * 1.5)
                        else:
                            depth_1_25x = None
                            depth_1_5x = None
                        
                        # Format depth for display
                        depth_1_25x_display = format_depth_value(depth_1_25x)
                        depth_1_5x_display = format_depth_value(depth_1_5x)
                        
                        if not spread_df.empty and spread_df['spread_percent'][0] is not None:
                            current_val = spread_df['spread_percent'][0]
                            diff = current_val - target
                            percent_diff = (diff / target) * 100
                            
                            # Check if spread is poor
                            is_poor_spread = (percent_diff > 100 or percent_diff < -40)
                            
                            # Special handling for markets that were Warning in previous cycle
                            if previous_status == "Warning":
                                if is_poor_spread:
                                    # Still poor - keep RED, don't retry
                                    results_map[symbol].update({
                                        "Current Spread %": current_val,
                                        "Difference": round(diff, 4),
                                        "Percent Diff %": round(percent_diff, 2),
                                        "Depth @ 1.25x": depth_1_25x_display,
                                        "Depth @ 1.5x": depth_1_5x_display,
                                        "Status": "Warning",
                                        "Last Updated": time.strftime("%H:%M:%S")
                                    })
                                    # Don't add to retry queue
                                    render_table()
                                    continue
                                # else: spread improved, fall through to normal evaluation
                            
                            # Normal spread evaluation logic
                            if is_poor_spread:
                                if item["warn_count"] < MAX_WARNING_RETRIES:
                                    item["warn_count"] += 1
                                    next_pass_queue.append(item)
                                    status = f'Warning (Retry {item["warn_count"]}/{MAX_WARNING_RETRIES})'
                                else:
                                    status = 'Warning'
                            else:
                                status = 'Okay'
                            
                            # Update results with DEPTH DATA
                            results_map[symbol].update({
                                "Current Spread %": current_val,
                                "Difference": round(diff, 4),
                                "Percent Diff %": round(percent_diff, 2),
                                "Depth @ 1.25x": depth_1_25x_display,
                                "Depth @ 1.5x": depth_1_5x_display,
                                "Status": status,
                                "Last Updated": time.strftime("%H:%M:%S"),
                                "warn_count": item["warn_count"],
                                "fail_count": item["fail_count"]
                            })
                        else:
                            raise ValueError("Spread data not found in element text")
                    
                    except Exception as e:
                        # Handle scraping failures
                        item["fail_count"] += 1
                        
                        if item["fail_count"] <= MAX_FAIL_RETRIES:
                            next_pass_queue.append(item)
                            status = f'Failed (Retry {item["fail_count"]}/{MAX_FAIL_RETRIES})'
                        else:
                            status = 'Failed Permanently'
                        
                        results_map[symbol].update({
                            "Status": status,
                            "warn_count": item["warn_count"],
                            "fail_count": item["fail_count"]
                        })
                    
                    # Update table after each market
                    render_table()
                    
                    # MEMORY CLEANUP: Clear variables
                    if 'asks_df' in locals():
                        del asks_df, bids_df, spread_df
                
                # Move to next pass
                tracking_queue = next_pass_queue
                pass_idx += 1
            
            # Cycle complete
            cycle_number += 1
            status_text.text(f"✅ Cycle {cycle_number - 1} complete. Starting Cycle {cycle_number}...")
            
            # Memory health check
            if cycle_number % DRIVER_RESTART_CYCLES == 0:
                health_metric.warning(f"⚠️ Browser will restart next cycle (Memory management)")
            
            time.sleep(2)  # Brief pause between cycles
    
    except Exception as e:
        status_text.error(f"Critical error occurred: {str(e)}")
    
    finally:
        if driver is not None:
            cleanup_driver(driver)
        st.session_state.scraping_active = False
        status_text.success("Scraping stopped.")
        health_metric.info("Browser closed")
