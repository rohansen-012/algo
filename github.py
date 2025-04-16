import requests
import pandas as pd
import json
import time
import pandas_ta as ta
from datetime import datetime, timezone, timedelta
import hashlib
import hmac

# initialise
base_url = 'https://api.india.delta.exchange'
api_key = "API_KEY"
api_secret = "API_SECRET"
symbol = "BTCUSD"
timeframe = "15m"
side = ""
sl, tp, entry = 0.0, 0.0, 0.0
size = 1
signature, timestamp, active_orders = None, None, None

# Create the signature
def generate_signature(api_secret, signature_data):
    message = bytes(signature_data, 'utf-8')
    secret = bytes(api_secret, 'utf-8')
    hash = hmac.new(secret, message, hashlib.sha256)
    return hash.hexdigest()

def generate_timestamp():
    timestamp = str(int(time.time()))
    return timestamp

def price_fetch(symbol):
    response = requests.get("https://cdn.india.deltaex.org/v2/tickers" + f"/{symbol}")
    if response.status_code == 200:
        ticker_info = response.json()
        if "result" in ticker_info:
            # Convert the data into a pandas DataFrame
            df = pd.DataFrame([ticker_info["result"]])
            return float(df["close"].iloc[0]), int(df["timestamp"].iloc[0])

# Convert timestamp from tickerinfo to unix time
def time_range(timestamp):
    # Convert to seconds by dividing by 1,000,000
    api_timestamp_seconds = timestamp / 1_000_000

    # Create a datetime object
    end = datetime.fromtimestamp(api_timestamp_seconds, timezone.utc)
    start = end - timedelta(minutes=2000000) # how many minutes to go back

    # Convert to standard UNIX timestamp (seconds since the epoch)
    start_time = int(start.timestamp())
    end_time = int(end.timestamp())
    return int(start_time), int(end_time)

# Historical data
def historical_data(start, end, symbol, timeframe):
    params = {
    'resolution': timeframe,
    'symbol': symbol,
    'start': start,
    'end': end
    }
    response = requests.get("https://cdn.india.deltaex.org/v2/history/candles", params=params)
    if response.status_code == 200:
        historical_data = response.json()

        # Extract data from the response
        if "result" in historical_data:
            # Convert the data into a pandas DataFrame
            df = pd.DataFrame(historical_data["result"])
            df = df.sort_values(by='time', ascending=True)  # Sort by time in ascending order
            df["datetime"] = pd.to_datetime(df["time"], unit='s')
            df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
            macd_df = ta.macd(df["close"], fast=12, slow=26, signal=9)
            macd_df.columns = ["macd", "hist", "signal"]
            df['ema'] = ta.ema(df["close"], length=200)
            df = pd.concat([df, macd_df], axis=1)
            return df

# get entry signals based on strategy
def entry_signal(df_row, df_prev, entry):
    var = 1 * df_row['atr']
    if (df_row['macd'] > df_row['signal']) and (df_prev['macd'] < df_row['signal']) and df_row['close'] > df_row['ema']:
        sl = entry - var  # SL is atr below entry for buy
        tp = entry + (10 * df_prev['atr']) # TP is 5x atr above entry for buy
        print(f"Buy entry at {entry}, SL: {sl}, TP: {tp}, atr:{df_row['atr']}, var: {var}")
        return "buy",sl,tp

    elif df_row['macd'] < df_row['signal'] and (df_prev['macd'] > df_row['signal']) and df_row['close'] < df_row['ema']:
        sl = entry + var  # SL is atr below entry for buy
        tp = entry - (10 * df_prev['atr'])  # TP is 5x atr above entry for buy
        print(f"Sell entry at {entry}, SL: {sl}, TP: {tp}, atr:{df_row['atr']}, var: {var}")
        return "sell",sl,tp

# order data
def order_data(entry, size, side, sl, tp):
    if side == 'buy':
        bracket_stop_loss = sl + 1
        bracket_take_profit = tp - 1
    elif side == 'sell':
        bracket_stop_loss = sl - 1
        bracket_take_profit = tp + 1
    order = {"product_id": 27,
                  "product_symbol": "BTCUSD",
                  "limit_price": entry,
                  "size": size,
                  "side": side,
                  "order_type": "market_order",
                  "bracket_stop_loss_limit_price": bracket_stop_loss,
                  "bracket_stop_loss_price": sl,
                  "bracket_take_profit_limit_price": bracket_take_profit,
                  "bracket_take_profit_price": tp,
                  "time_in_force": "ioc"}
    return order


def trading_bot():
    entry, current_time = price_fetch(symbol)
    start, end = time_range(current_time)
    df = historical_data(start, end, symbol, timeframe)
    df_row = df.loc[0]
    df_prev = df.loc[1]
    if entry_signal(df_row, df_prev, entry) is not None:
        side, sl, tp = entry_signal(df_row, df_prev, entry)
        order = order_data(entry, size, side, sl, tp)
        method = 'POST'
        endpoint = '/v2/orders'
        body = json.dumps(order, separators=(',', ':'))
        timestamp = generate_timestamp()
        signature_data = method + timestamp + endpoint + body
        signature = generate_signature(api_secret, signature_data)

        headers = {'Accept': 'application/json',
                   'api-key': api_key,
                   'signature': signature,
                   'timestamp': timestamp,
                   'Content-Type': 'application/json'
                   }
        response = requests.post('https://cdn.india.deltaex.org/v2/orders', headers=headers, data=body)
        order_response = response.json()
        print(order_response)
    else:
        print("No Entries")
    print(df.tail())
    print("Running the program at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


while True:
    now = datetime.now()
    # Calculate minutes to the next 15-minute mark
    minutes_to_next = 15 - (now.minute % 15)
    next_run_time = now + timedelta(minutes=minutes_to_next)
    next_run_time = next_run_time.replace(second=0, microsecond=0)

    # Adjust for the 2-second server delay
    adjusted_run_time = next_run_time - timedelta(seconds=0)

    # Sleep until the adjusted time
    time_to_sleep = (adjusted_run_time - now).total_seconds()
    print(f"Sleeping for {time_to_sleep:.2f} seconds until {adjusted_run_time}")

    time.sleep(time_to_sleep)
    trading_bot()
