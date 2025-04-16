import pandas as pd
import talib

def backtest_macd_atr_strategy(csv_file):
    # Load data
    df = pd.read_csv(csv_file)
    df['time'] = pd.to_datetime(df['datetime'])
    df.set_index('time', inplace=True)

    # Calculate MACD
    df['MACD'], df['Signal'], _ = talib.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
    df['EMA'] = talib.EMA(df['close'],200)
    # Calculate ATR
    df['ATR'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)

    # Define strategy parameters
    trades = []
    position = None  # Stores (entry_price, sl, tp, direction)

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i - 1]

        if position is None:
            # Entry conditions
            if prev_row['MACD'] < prev_row['Signal'] and row['MACD'] > row['Signal'] and row['close'] > row['EMA']:
                entry_price = row['close']
                sl = entry_price - (1 * row['ATR'])
                tp = entry_price + 10 * row['ATR']
                position = (entry_price, sl, tp, 'long')
            elif prev_row['MACD'] > prev_row['Signal'] and row['MACD'] < row['Signal'] and row['close'] < row['EMA']:
                entry_price = row['close']
                sl = entry_price + (1 * row['ATR'])
                tp = entry_price - 10 * row['ATR']
                position = (entry_price, sl, tp, 'short')
        else:
            # Check for stop loss or take profit
            entry_price, sl, tp, direction = position

            if direction == 'long':
                if row['low'] <= sl or row['high'] >= tp:
                    result = 'win' if row['high'] >= tp else 'loss'
                    pnl = tp - entry_price if result == 'win' else sl - entry_price
                    trades.append((entry_price, sl, tp, direction, result, pnl))
                    position = None
            else:  # Short trade
                if row['high'] >= sl or row['low'] <= tp:
                    result = 'win' if row['low'] <= tp else 'loss'
                    pnl = entry_price - tp if result == 'win' else entry_price - sl
                    trades.append((entry_price, sl, tp, direction, result, pnl))
                    position = None

# Calculate results
    total_trades = len(trades)
    wins = sum(1 for t in trades if t[4] == 'win')
    losses = total_trades - wins
    win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
    total_pnl = sum(t[5] for t in trades)
    max_profit = max(t[5] for t in trades) if trades else 0
    min_loss = min(t[5] for t in trades) if trades else 0
    print(f'Total Trades: {total_trades}')
    print(f'Wins: {wins}, Losses: {losses}')
    print(f'Win Rate: {win_rate:.2f}%')
    print(f'Total PnL: {total_pnl:.2f}')
    print(f'Max Profit: {max_profit:.2f}, Min Loss: {min_loss:.2f}')

    return trades

# Example usage
backtest_macd_atr_strategy('hist_15m.csv')
