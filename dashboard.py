# import streamlit as st
# import pandas as pd
# from selenium import webdriver
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver.chrome.options import Options
# import time
# import os
# from selenium.webdriver.chrome.service import Service
# from collections import deque


# # --- Improved Parse Function ---
# def parse_orderbook(text: str):
#     """
#     Parse orderbook text into structured dataframes for asks, bids, and spread.
    
#     Args:
#         text: Raw text from orderbook element
        
#     Returns:
#         Tuple of (asks_df, bids_df, spread_df)
#     """
#     def parse_number(value):
#         """Convert K/M suffixes to numeric values, handle placeholders"""
#         if not value or "--" in value:
#             return None
#         try:
#             if value.endswith('K'):
#                 return float(value[:-1]) * 1_000
#             elif value.endswith('M'):
#                 return float(value[:-1]) * 1_000_000
#             return float(value.replace(',', ''))
#         except:
#             return None
    
#     lines = text.split("\n")
#     asks, bids = [], []
#     spread_price, spread_pct = None, None
#     side = "asks"
    
#     for line in lines:
#         if "Spread" in line:
#             side = "bids"
#             continue
            
#         parts = line.split()
        
#         # Handle the Spread Price Row
#         if len(parts) == 1:
#             try:
#                 spread_price = float(parts[0].replace(',', ''))
#             except:
#                 pass
                
#         # Handle the Spread Percentage Row
#         elif len(parts) == 2:
#             try:
#                 pct = parts[1].replace('(', '').replace('%)', '').replace('+', '')
#                 spread_pct = float(pct)
#             except:
#                 pass
                
#         # Handle Order Rows (Price, Amount, Total)
#         elif len(parts) == 3:
#             try:
#                 p_val = float(parts[0].replace(',', ''))
#                 amt = parse_number(parts[1])
#                 tot = parse_number(parts[2])
                
#                 # Only add if we have actual numeric data (skips '--' rows)
#                 if amt is not None and tot is not None:
#                     row = {"price": p_val, "amount": amt, "total": tot}
#                     if side == "asks":
#                         asks.append(row)
#                     else:
#                         bids.append(row)
#             except ValueError:
#                 continue
    
#     asks_df = pd.DataFrame(asks, columns=["price", "amount", "total"])
#     bids_df = pd.DataFrame(bids, columns=["price", "amount", "total"])
    
#     if not asks_df.empty:
#         asks_df = asks_df.sort_values("price", ascending=False).reset_index(drop=True)
#     if not bids_df.empty:
#         bids_df = bids_df.sort_values("price", ascending=False).reset_index(drop=True)
        
#     spread_df = pd.DataFrame([{"spread_price": spread_price, "spread_percent": spread_pct}])
    
#     return asks_df, bids_df, spread_df


# def calculate_detailed_metrics(asks_df, bids_df, spread_pct):
#     """
#     Calculate detailed orderbook health metrics.
    
#     Args:
#         asks_df: DataFrame of ask orders
#         bids_df: DataFrame of bid orders
#         spread_pct: Current spread percentage
        
#     Returns:
#         Dictionary containing all calculated metrics
#     """
#     metrics = {
#         "bid_volume": 0.0,
#         "ask_volume": 0.0,
#         "total_volume": 0.0,
#         "imbalance": 0.0,
#         "bid_orders": 0,
#         "ask_orders": 0
#     }
    
#     # Handle empty orderbooks
#     if asks_df.empty or bids_df.empty:
#         return metrics
    
#     # Calculate mid-price
#     best_bid = bids_df['price'].iloc[0] if not bids_df.empty else 0
#     best_ask = asks_df['price'].iloc[-1] if not asks_df.empty else 0
    
#     if best_bid == 0 or best_ask == 0:
#         return metrics
    
#     mid_price = (best_bid + best_ask) / 2
#     threshold = 0.01  # 1% threshold
    
#     # Calculate volume within 1% of mid-price
#     lower_bound = mid_price * (1 - threshold)
#     upper_bound = mid_price * (1 + threshold)
    
#     # Bid volume within 1%
#     bids_in_range = bids_df[
#         (bids_df['price'] >= lower_bound) & 
#         (bids_df['price'] <= mid_price)
#     ]
#     metrics["bid_volume"] = bids_in_range['total'].sum() if not bids_in_range.empty else 0.0
#     metrics["bid_orders"] = len(bids_in_range)
    
#     # Ask volume within 1%
#     asks_in_range = asks_df[
#         (asks_df['price'] >= mid_price) & 
#         (asks_df['price'] <= upper_bound)
#     ]
#     metrics["ask_volume"] = asks_in_range['total'].sum() if not asks_in_range.empty else 0.0
#     metrics["ask_orders"] = len(asks_in_range)
    
#     # Total volume
#     metrics["total_volume"] = metrics["bid_volume"] + metrics["ask_volume"]
    
#     # Imbalance ratio (avoid division by zero)
#     if metrics["ask_volume"] > 0:
#         metrics["imbalance"] = metrics["bid_volume"] / metrics["ask_volume"]
#     else:
#         metrics["imbalance"] = 0.0
    
#     return metrics


# def update_history(market_data, new_metrics, spread_pct, timestamp):
#     """
#     Update historical data for a market (maintains last 3 cycles).
    
#     Args:
#         market_data: Dictionary containing market data from results_map
#         new_metrics: Dictionary of newly calculated metrics
#         spread_pct: Current spread percentage
#         timestamp: Current timestamp string
#     """
#     if "history" not in market_data:
#         market_data["history"] = {
#             "spread_pct": deque(maxlen=3),
#             "bid_volume": deque(maxlen=3),
#             "ask_volume": deque(maxlen=3),
#             "total_volume": deque(maxlen=3),
#             "imbalance": deque(maxlen=3),
#             "bid_orders": deque(maxlen=3),
#             "ask_orders": deque(maxlen=3),
#             "timestamp": deque(maxlen=3)
#         }
    
#     # Append new data (deque automatically maintains max length of 3)
#     market_data["history"]["spread_pct"].append(spread_pct)
#     market_data["history"]["bid_volume"].append(new_metrics["bid_volume"])
#     market_data["history"]["ask_volume"].append(new_metrics["ask_volume"])
#     market_data["history"]["total_volume"].append(new_metrics["total_volume"])
#     market_data["history"]["imbalance"].append(new_metrics["imbalance"])
#     market_data["history"]["bid_orders"].append(new_metrics["bid_orders"])
#     market_data["history"]["ask_orders"].append(new_metrics["ask_orders"])
#     market_data["history"]["timestamp"].append(timestamp)


# def calculate_changes_and_trends(history):
#     """
#     Calculate percentage changes and trend indicators from historical data.
    
#     Args:
#         history: Dictionary containing historical metrics
        
#     Returns:
#         Dictionary with change percentages and trend indicators
#     """
#     changes = {
#         "spread_change": 0.0,
#         "volume_change": 0.0,
#         "imbalance_change": 0.0,
#         "trend": "Insufficient data"
#     }
    
#     if len(history["spread_pct"]) < 2:
#         return changes
    
#     # Calculate changes from previous cycle
#     prev_spread = history["spread_pct"][-2]
#     curr_spread = history["spread_pct"][-1]
#     if prev_spread > 0:
#         changes["spread_change"] = ((curr_spread - prev_spread) / prev_spread) * 100
    
#     prev_volume = history["total_volume"][-2]
#     curr_volume = history["total_volume"][-1]
#     if prev_volume > 0:
#         changes["volume_change"] = ((curr_volume - prev_volume) / prev_volume) * 100
    
#     prev_imbalance = history["imbalance"][-2]
#     curr_imbalance = history["imbalance"][-1]
#     if prev_imbalance > 0:
#         changes["imbalance_change"] = ((curr_imbalance - prev_imbalance) / prev_imbalance) * 100
    
#     # Determine 3-cycle trend (if we have 3 cycles)
#     if len(history["spread_pct"]) == 3:
#         spreads = list(history["spread_pct"])
#         volumes = list(history["total_volume"])
        
#         # Check if spread is consistently widening and volume dropping
#         spread_trend = spreads[2] > spreads[1] > spreads[0]
#         volume_trend = volumes[2] < volumes[1] < volumes[0]
        
#         if spread_trend and volume_trend:
#             changes["trend"] = "⬇️ Deteriorating"
#         elif not spread_trend and not volume_trend:
#             changes["trend"] = "⬆️ Improving"
#         else:
#             changes["trend"] = "→ Mixed signals"
    
#     return changes


# def get_flag_emoji(metric_name, value, change_value=None):
#     """
#     Return appropriate emoji flag based on metric thresholds.
    
#     Args:
#         metric_name: Name of the metric being evaluated
#         value: Current value of the metric
#         change_value: Change percentage (for delta metrics)
        
#     Returns:
#         String containing emoji flag or empty string
#     """
#     if metric_name == "total_volume":
#         if value < 1000:
#             return " 🔴"
#         return ""
    
#     elif metric_name == "imbalance":
#         if value > 2.0 or value < 0.5:
#             return " 🔴"
#         elif value > 1.5 or value < 0.67:
#             return " 🟡"
#         return ""
    
#     elif metric_name == "order_count":
#         if value < 5:
#             return " 🔴"
#         return ""
    
#     elif metric_name == "spread_change":
#         if change_value is not None:
#             if change_value > 50:
#                 return " 🔴"
#         return ""
    
#     elif metric_name == "volume_change":
#         if change_value is not None:
#             if change_value < -50:
#                 return " 🔴"
#         return ""
    
#     elif metric_name == "imbalance_change":
#         if change_value is not None:
#             if abs(change_value) > 100:
#                 return " 🟡"
#         return ""
    
#     return ""


# def render_detail_expander(symbol, market_data):
#     """
#     Render detailed metrics expander for a single market.
    
#     Args:
#         symbol: Market pair symbol
#         market_data: Dictionary containing all market data
#     """
#     if "history" not in market_data or len(market_data["history"]["spread_pct"]) == 0:
#         st.warning(f"No detailed metrics available for {symbol} yet.")
#         return
    
#     # Get current metrics (last entry in history)
#     history = market_data["history"]
#     bid_vol = history["bid_volume"][-1]
#     ask_vol = history["ask_volume"][-1]
#     total_vol = history["total_volume"][-1]
#     imbalance = history["imbalance"][-1]
#     bid_orders = history["bid_orders"][-1]
#     ask_orders = history["ask_orders"][-1]
    
#     # Calculate changes and trends
#     changes = calculate_changes_and_trends(history)
    
#     # Liquidity Depth Section
#     st.markdown("**📊 Liquidity Depth (within 1%)**")
#     st.text(f"Bid Volume:   ${bid_vol:,.0f}")
#     st.text(f"Ask Volume:   ${ask_vol:,.0f}{get_flag_emoji('imbalance', imbalance)}")
#     st.text(f"Total Volume: ${total_vol:,.0f}{get_flag_emoji('total_volume', total_vol)}")
    
#     st.markdown("---")
    
#     # Market Pressure Section
#     st.markdown("**⚖️ Market Pressure**")
#     imbalance_pct = ((imbalance - 1.0) * 100) if imbalance != 0 else 0
#     imbalance_desc = f"{abs(imbalance_pct):.0f}% more {'bids' if imbalance > 1 else 'asks'}"
#     st.text(f"Imbalance Ratio: {imbalance:.2f} ({imbalance_desc}){get_flag_emoji('imbalance', imbalance)}")
#     st.text(f"Order Count:     {bid_orders} bids | {ask_orders} asks{get_flag_emoji('order_count', min(bid_orders, ask_orders))}")
    
#     # Only show changes if we have at least 2 cycles
#     if len(history["spread_pct"]) >= 2:
#         st.markdown("---")
        
#         # Changes & Trends Section
#         st.markdown("**📈 Changes & Trends**")
        
#         spread_change = changes["spread_change"]
#         spread_direction = "Widening" if spread_change > 0 else "Tightening"
#         if abs(spread_change) > 50:
#             spread_severity = "rapidly" if abs(spread_change) > 100 else ""
#         else:
#             spread_severity = ""
#         st.text(f"Spread Change:    {spread_change:+.0f}%{get_flag_emoji('spread_change', spread_change, spread_change)} ({spread_direction} {spread_severity})".strip())
        
#         volume_change = changes["volume_change"]
#         volume_direction = "growing" if volume_change > 0 else "dropping"
#         st.text(f"Volume Change:    {volume_change:+.0f}%{get_flag_emoji('volume_change', volume_change, volume_change)} (Liquidity {volume_direction})")
        
#         imbalance_change = changes["imbalance_change"]
#         st.text(f"Imbalance Change: {imbalance_change:+.0f}%{get_flag_emoji('imbalance_change', imbalance_change, imbalance_change)}")
        
#         # Show trend if we have 3 cycles
#         if len(history["spread_pct"]) == 3:
#             st.text(f"3-Cycle Trend:    {changes['trend']}")


# def render_detail_expanders(results_map):
#     """
#     Render expanders only for markets with Warning status (red).
    
#     Args:
#         results_map: Dictionary containing all market data
#     """
#     # Filter only Warning (red) markets
#     warning_markets = {
#         symbol: data for symbol, data in results_map.items()
#         if data["Status"] == "Warning"
#     }
    
#     if not warning_markets:
#         return
    
#     st.markdown("---")
#     st.subheader("🔍 Detailed Metrics for Markets with Poor Spread")
    
#     for symbol, data in warning_markets.items():
#         status = data["Status"]
        
#         with st.expander(f"🔴 {symbol} - {status}"):
#             render_detail_expander(symbol, data)


# def init_chrome_driver():
#     """
#     Initialize Chrome WebDriver with appropriate options for headless operation.
    
#     Returns:
#         WebDriver instance
#     """
#     chrome_options = Options()
#     chrome_options.add_argument("--headless=new")
#     chrome_options.add_argument("--no-sandbox")
#     chrome_options.add_argument("--disable-dev-shm-usage")
#     chrome_options.add_argument("--disable-gpu")
#     chrome_options.add_argument("--window-size=1920,1080")
#     chrome_options.add_argument("--disable-blink-features=AutomationControlled")
#     chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
#     chrome_options.add_experimental_option("useAutomationExtension", False)
    
#     user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
#     chrome_options.add_argument(f"user-agent={user_agent}")
    
#     # Path fix for Streamlit Cloud
#     if os.path.exists("/usr/bin/chromium-browser"):
#         chrome_options.binary_location = "/usr/bin/chromium-browser"
#     elif os.path.exists("/usr/bin/chromium"):
#         chrome_options.binary_location = "/usr/bin/chromium"
    
#     try:
#         service = Service("/usr/bin/chromedriver")
#         driver = webdriver.Chrome(service=service, options=chrome_options)
#     except Exception:
#         driver = webdriver.Chrome(options=chrome_options)
    
#     return driver


# # --- Streamlit UI Setup ---
# st.set_page_config(page_title="Crypto Spread Monitor", layout="wide")
# st.title("Quidax Orderbook Monitor")

# # Initialize session state for button control
# if 'scraping_active' not in st.session_state:
#     st.session_state.scraping_active = False

# # Trading pairs configuration
# PAIRS = [
#     ['AAVE_USDT', 0.30], ['ADA_USDT', 0.26], ['ALGO_USDT', 2.00],
#     ['BCH_USDT', 0.26], ['BNB_USDT', 0.30], ['BONK_USDT', 2.00],
#     ['BTC_USDT', 0.20], ['CAKE_USDT', 0.30], ['CFX_USDT', 2.00],
#     ['DOT_USDT', 0.26], ['DOGE_USDT', 0.26], ['ETH_USDT', 0.25],
#     ['FARTCOIN_USDT', 2.00], ['FLOKI_USDT', 0.50], ['HYPE_USDT', 2.00],
#     ['LINK_USDT', 0.26], ['NEAR_USDT', 2.00], ['NOS_USDT', 2.00],
#     ['PEPE_USDT', 0.50], ['POL_USDT', 0.50], ['QDX_USDT', 10.00],
#     ['RENDER_USDT', 2.00], ['Sonic_USDT', 2.00], ['SHIB_USDT', 0.40],
#     ['SLP_USDT', 2.00], ['SOL_USDT', 0.30], ['STRK_USDT', 2.00],
#     ['SUI_USDT', 2.00], ['TON_USDT', 0.30], ['TRX_USDT', 0.30],
#     ['USDC_USDT', 0.02], ['WIF_USDT', 2.00], ['XLM_USDT', 0.30],
#     ['XRP_USDT', 0.30], ['XYO_USDT', 1.00], ['ZKSync_USDT', 2.00],
#     ['BTC_NGN', 0.50], ['USDT_NGN', 0.50], ['QDX_NGN', 10.00],
#     ['ETH_NGN', 0.50], ['TRX_NGN', 0.50], ['XRP_NGN', 0.50],
#     ['DASH_NGN', 0.50], ['LTC_NGN', 0.50], ['SOL_NGN', 0.50],
#     ['USDC_NGN', 0.50]
# ]

# # Constants
# MAX_WARNING_RETRIES = 3
# MAX_FAIL_RETRIES = 3
# BASE_URL = "https://pro.quidax.io/en_US/trade/"

# # Initialize results map with persistent tracking
# if 'results_map' not in st.session_state:
#     st.session_state.results_map = {
#         p[0]: {
#             "Pair": p[0],
#             "Current Spread %": None,
#             "Target %": p[1],
#             "Difference": None,
#             "Percent Diff %": None,
#             "Status": "Pending...",
#             "Last Updated": "-",
#             "warn_count": 0,
#             "fail_count": 0
#         } for p in PAIRS
#     }

# results_map = st.session_state.results_map

# # UI placeholders
# status_text = st.empty()
# table_placeholder = st.empty()
# detail_placeholder = st.empty()


# def render_table():
#     """Render the results table with color-coded status highlighting"""
#     df_display = pd.DataFrame([
#         {k: v for k, v in item.items() if k not in ['warn_count', 'fail_count', 'history']}
#         for item in results_map.values()
#     ])
    
#     def highlight_rows(row):
#         """Apply background color based on status"""
#         status_val = str(row['Status'])
        
#         if status_val == 'Warning':
#             # Red for poor spread
#             return ['background-color: rgba(255, 50, 50, 0.3)'] * len(row)
#         elif status_val == 'Okay':
#             # Green for good spread
#             return ['background-color: rgba(50, 255, 50, 0.3)'] * len(row)
#         else:
#             # Yellow for everything else (Pending, Retry, Re-checking, Failed)
#             return ['background-color: rgba(255, 255, 0, 0.2)'] * len(row)
    
#     table_placeholder.dataframe(
#         df_display.style.apply(highlight_rows, axis=1),
#         use_container_width=True
#     )


# # Main scraping button
# if st.button('Start Scraping', disabled=st.session_state.scraping_active):
#     st.session_state.scraping_active = True
    
#     # Initialize driver once for all cycles
#     driver = init_chrome_driver()
#     wait = WebDriverWait(driver, 10)
    
#     try:
#         cycle_number = 1
        
#         while True:  # Infinite loop for continuous monitoring
#             # Initialize tracking queue for this cycle
#             tracking_queue = []
            
#             for p in PAIRS:
#                 symbol = p[0]
#                 target = p[1]
#                 previous_status = results_map[symbol]["Status"]
                
#                 # Preserve counters from previous cycles
#                 item = {
#                     "symbol": symbol,
#                     "target": target,
#                     "warn_count": results_map[symbol]["warn_count"],
#                     "fail_count": results_map[symbol]["fail_count"],
#                     "previous_status": previous_status
#                 }
#                 tracking_queue.append(item)
            
#             # Render initial table state for this cycle
#             render_table()
            
#             # Process markets in passes (with retry logic)
#             pass_idx = 1
            
#             while tracking_queue:
#                 next_pass_queue = []
                
#                 for item in tracking_queue:
#                     symbol = item["symbol"]
#                     target = item["target"]
#                     previous_status = item["previous_status"]
                    
#                     status_text.text(f"Cycle {cycle_number} | Pass {pass_idx} | Scanning {symbol}...")
                    
#                     try:
#                         # Navigate to market page
#                         driver.get(BASE_URL + symbol)
                        
#                         # Wait for orderbook element
#                         selector = ".newTrade-depth-block.depath-index-container"
#                         element = wait.until(
#                             EC.presence_of_element_located((By.CSS_SELECTOR, selector))
#                         )
                        
#                         # Wait for spread data to load
#                         wait.until(lambda d: "Spread" in element.text and 
#                                   any(c.isdigit() for c in element.text))
                        
#                         # Small buffer for number stabilization
#                         time.sleep(0.5)
                        
#                         # Parse orderbook data
#                         asks_df, bids_df, spread_df = parse_orderbook(element.text)
                        
#                         if not spread_df.empty and spread_df['spread_percent'][0] is not None:
#                             current_val = spread_df['spread_percent'][0]
#                             diff = current_val - target
#                             percent_diff = (diff / target) * 100
                            
#                             # Calculate detailed metrics
#                             detailed_metrics = calculate_detailed_metrics(asks_df, bids_df, current_val)
                            
#                             # Update historical data
#                             current_timestamp = time.strftime("%H:%M:%S")
#                             update_history(results_map[symbol], detailed_metrics, current_val, current_timestamp)
                            
#                             # Check if spread is poor
#                             is_poor_spread = (percent_diff > 100 or percent_diff < -40)
                            
#                             # Special handling for markets that were Warning in previous cycle
#                             if previous_status == "Warning":
#                                 if is_poor_spread:
#                                     # Still poor - keep RED, don't retry
#                                     results_map[symbol].update({
#                                         "Current Spread %": current_val,
#                                         "Difference": round(diff, 4),
#                                         "Percent Diff %": round(percent_diff, 2),
#                                         "Status": "Warning",
#                                         "Last Updated": current_timestamp
#                                     })
#                                     # Don't add to retry queue
#                                     render_table()
#                                     with detail_placeholder.container():
#                                         render_detail_expanders(results_map)
#                                     continue
#                                 # else: spread improved, fall through to normal evaluation
                            
#                             # Normal spread evaluation logic
#                             if is_poor_spread:
#                                 if item["warn_count"] < MAX_WARNING_RETRIES:
#                                     item["warn_count"] += 1
#                                     next_pass_queue.append(item)
#                                     status = f'Warning (Retry {item["warn_count"]}/{MAX_WARNING_RETRIES})'
#                                 else:
#                                     status = 'Warning'
#                             else:
#                                 status = 'Okay'
                            
#                             # Update results
#                             results_map[symbol].update({
#                                 "Current Spread %": current_val,
#                                 "Difference": round(diff, 4),
#                                 "Percent Diff %": round(percent_diff, 2),
#                                 "Status": status,
#                                 "Last Updated": current_timestamp,
#                                 "warn_count": item["warn_count"],
#                                 "fail_count": item["fail_count"]
#                             })
#                         else:
#                             raise ValueError("Spread data not found in element text")
                    
#                     except Exception as e:
#                         # Handle scraping failures
#                         item["fail_count"] += 1
                        
#                         if item["fail_count"] <= MAX_FAIL_RETRIES:
#                             next_pass_queue.append(item)
#                             status = f'Failed (Retry {item["fail_count"]}/{MAX_FAIL_RETRIES})'
#                         else:
#                             status = 'Failed Permanently'
                        
#                         results_map[symbol].update({
#                             "Status": status,
#                             "warn_count": item["warn_count"],
#                             "fail_count": item["fail_count"]
#                         })
                    
#                     # Update table and detail view after each market
#                     render_table()
#                     with detail_placeholder.container():
#                         render_detail_expanders(results_map)
                
#                 # Move to next pass
#                 tracking_queue = next_pass_queue
#                 pass_idx += 1
            
#             # Cycle complete, increment counter and loop continues
#             cycle_number += 1
#             status_text.text(f"Cycle {cycle_number - 1} complete. Starting Cycle {cycle_number}...")
#             time.sleep(2)  # Brief pause between cycles
    
#     except Exception as e:
#         status_text.error(f"Critical error occurred: {str(e)}")
    
#     finally:
#         driver.quit()
#         st.session_state.scraping_active = False
#         status_text.success("Scraping stopped.")
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


# --- NEW: Depth Calculation Function ---
def calculate_liquidity_depth(asks_df, bids_df, spread_pct):
    """
    Calculate total liquidity depth within spread_pct of mid-price.
    
    Args:
        asks_df: DataFrame with ask orders (price, amount, total)
        bids_df: DataFrame with bid orders (price, amount, total)
        spread_pct: Percentage range from mid-price (e.g., 1.0 for 1%, 2.0 for 2%)
        
    Returns:
        Total liquidity in USD within the spread range, or None if data unavailable
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
    
    # Calculate bid-side liquidity (orders >= lower_bound)
    bid_depth = bids_df[bids_df['price'] >= lower_bound]['total'].sum()
    
    # Calculate ask-side liquidity (orders <= upper_bound)
    ask_depth = asks_df[asks_df['price'] <= upper_bound]['total'].sum()
    
    # Total depth (both sides)
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

# Initialize results map with persistent tracking (NOW WITH DEPTH FIELDS)
if 'results_map' not in st.session_state:
    st.session_state.results_map = {
        p[0]: {
            "Pair": p[0],
            "Current Spread %": None,
            "Target %": p[1],
            "Difference": None,
            "Percent Diff %": None,
            "Depth @ 1%": None,      # NEW
            "Depth @ 2%": None,      # NEW
            "Status": "Pending...",
            "Last Updated": "-",
            "warn_count": 0,
            "fail_count": 0
        } for p in PAIRS
    }

results_map = st.session_state.results_map

# UI placeholders
status_text = st.empty()
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
    
    # Initialize driver once for all cycles
    driver = init_chrome_driver()
    wait = WebDriverWait(driver, 10)
    
    try:
        cycle_number = 1
        
        while True:  # Infinite loop for continuous monitoring
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
                        
                        # --- NEW: Calculate Depth Metrics ---
                        depth_1pct = calculate_liquidity_depth(asks_df, bids_df, 1.0)
                        depth_2pct = calculate_liquidity_depth(asks_df, bids_df, 2.0)
                        
                        # Format depth for display
                        depth_1pct_display = format_depth_value(depth_1pct)
                        depth_2pct_display = format_depth_value(depth_2pct)
                        
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
                                        "Depth @ 1%": depth_1pct_display,  # NEW
                                        "Depth @ 2%": depth_2pct_display,  # NEW
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
                                "Depth @ 1%": depth_1pct_display,  # NEW
                                "Depth @ 2%": depth_2pct_display,  # NEW
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
                
                # Move to next pass
                tracking_queue = next_pass_queue
                pass_idx += 1
            
            # Cycle complete, increment counter and loop continues
            cycle_number += 1
            status_text.text(f"Cycle {cycle_number - 1} complete. Starting Cycle {cycle_number}...")
            time.sleep(2)  # Brief pause between cycles
    
    except Exception as e:
        status_text.error(f"Critical error occurred: {str(e)}")
    
    finally:
        driver.quit()
        st.session_state.scraping_active = False
        status_text.success("Scraping stopped.")