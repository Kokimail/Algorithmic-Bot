from alpaca.trading.client import TradingClient
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timezone, timedelta
import pandas as pd
import time
import numpy as np

# setting API properties
API_KEY = 'PK2I5CCKUGXSDUMF5729'
API_SECRET = 'R2ETLhRBNHgsFWeI9VfLhT0cijt6hBi0giUuM0jx'
BASE_URL = 'https://paper-api.alpaca.markets/v2'

# initialize the trading and data clients
trading_client = TradingClient(API_KEY,API_SECRET, paper=True)
data_client = CryptoHistoricalDataClient(API_KEY,API_SECRET)

# Define the symbol for Bitcoin and the exchange
symbol = 'BTC/USD'
start_date = '2024-01-01T00:00Z'
end_date = '2024-06-30T23:59:59Z'

# Fetch historical data
test_bar_request = CryptoBarsRequest(
    symbol_or_symbols=symbol,
    timeframe=TimeFrame.Minute,
    start=start_date,
    end=end_date    
)

test_bars = data_client.get_crypto_bars(test_bar_request)

# Convert data to DataFrame
df = pd.DataFrame(test_bars.df)

# Generate a complete datetime index from start to finish at one-minute intervals
start = df.index.get_level_values('timestamp').min()
end = df.index.get_level_values('timestamp').max()
complete_index = pd.date_range(start=start, end=end, freq = 'T') # 'T' for minute frequency

# Reindex btc_df using complete time index
btc_df = df.loc['BTC/USD']
btc_df_reindexed = btc_df.reindex(complete_index)

# Interpolate missing values linearly
df_interpolated = btc_df_reindexed.interpolate(method='linear')

# Resample data to 15-minute intervals
df_15m = df_interpolated.resample('15T').agg({
    'open': 'first',
    'high': 'first',
    'low': 'first',
    'close': 'first',
    'volume': 'first'
})

# Create fields required for strategy execution
df_15m['close_change'] = df_15m['close'].diff()
df_15m['return'] = df_15m['close'].pct_change()
df_15m['previous_return'] = df_15m['return'].shift(1)
df_15m['close_executed'] = 0 # placeholder
df_15m['close_executed_differential'] = 0 # placeholder
df_15m['investment_value'] = 0  # placeholder
df_15m['investment_return_dollar'] = 0 # placeholder
df_15m['investment_return'] = 0 # placeholder

#print(df_15m)
#df_15m.to_csv('test.csv')

# Simulating trading
initial_capital = 1000
cash = initial_capital
btc_held = 0
i = -1
t = 0
last_close_executed = None
investment_purchase = None
investment_value = None
investment_return_dollar = None


for index, row in df_15m.iterrows():
    if row['return'] > 0 and row['previous_return'] > 0 and i == -1: # Buy signal
        btc_held = cash / row['close']
        cash = 0 # Invest all cash
        df_15m.at[index, 'close_executed'] = row['close'] # Update the DataFram directly with the executed price
        last_close_executed = row['close']
        df_15m.at[index, 'investment_value'] = int(investment_value)
        investment_purchase = investment_value
        i *= -1
        t += 1
    elif row['return'] < 0 and row['previous_return'] < 0 and i == 1: # Sell signal
        cash = btc_held * row['close']
        btc_held = 0 # Sell all holdings
        df_15m.at[index, 'close_executed'] = -row['close'] # Update the DataFram directly with the executed price
        df_15m.at[index, 'close_executed_differential'] = int(row['close']-last_close_executed) # Update the DataFram directly with executed return
        investment_value = (1+row['return'])*investment_value
        df_15m.at[index, 'investment_value'] = int(investment_value)
        investment_return_dollar = investment_value - investment_purchase
        df_15m.at[index, 'investment_return_dollar'] = int(investment_return_dollar)
        i *= -1
        t += 1
    else:
        if t == 0:
            investment_value = cash
            df_15m.at[index,'investment_value'] = int(investment_value)
        elif i == 1: 
            investment_value = (1+row['return'])*investment_value
            df_15m.at[index,'investment_value'] = int(investment_value)
        else:
            df_15m.at[index,'investment_value'] = int(investment_value)

df_15m['investment_return'] = df_15m['investment_value'].pct_change()

#print(df_15m)
#df_15m.to_csv('test.csv')

# Calculate the final value of the portfolio
final_value = cash if cash > 0 else btc_held * df_15m.iloc[-1]['close']
final_return = (final_value - initial_capital)/initial_capital
span = end - start
print(f"Final portfolio value: ${final_value:.2f} or {round(final_return*100,2)}% return from an initial capital of ${initial_capital} with {t} transactions in a span of {span}")




# For purpose of analysis
# Sharpe Ratio = (return of the portfolio - risk free rate) / standard deviation of the portfolio's excess returns (volatility)
grouped_day = df_15m.groupby(df_15m.index.date).sum()

#print(grouped_day)
#grouped_day.to_csv('test_2.csv')

grouped_month = df_15m.groupby(pd.Grouper(freq='M')).sum()

#print(grouped_month)
#grouped_month.to_csv('test_3')

# Calculate the necessary metrics
mean_return = grouped_month['investment_return'].mean()
print("Mean Return (monthly): ", mean_return)

# Assume a risk-free rate of 4.23% - long-term average of 10 year treasury rate
risk_free_rate = 0.0423
monthly_risk_free_rate = (1+risk_free_rate)**(1/12)-1
print("Risk-Free Rate (monthly): ", monthly_risk_free_rate)

# Calculate the standard deviation of returns (volatility)
std_dev = grouped_month['investment_return'].std()
print("Standard Deviation: ", std_dev) 

# Calculate the Sharpe Ratio (annualized)
sharpe_ratio = (mean_return - monthly_risk_free_rate) / std_dev

print(f"Sharpe Ratio: {round(sharpe_ratio,2)}")