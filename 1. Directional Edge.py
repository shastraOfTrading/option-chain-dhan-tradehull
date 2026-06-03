# Update codebase as well
import pandas as pd
from rich import print
import tradehull_backtesting_support as tbs
import datetime
import pdb

supertrend_period     = 10
supertrend_multiplier = 2

df               = pd.read_csv('Historical Data/NIFTY 60 mins.csv')
df               = tbs.supertrend(df, atr_period=supertrend_period, atr_multiplier=supertrend_multiplier)
df               = df.set_index('timestamp')
df['resistance'] = df['close'].rolling(5).max()
df['support']    = df['close'].rolling(5).min()
df               = df['2021-03-01 09:15:00+05:30':]
st_col           = f'STX_{supertrend_period}_{supertrend_multiplier}'
st_val           = f'ST_{supertrend_period}_{supertrend_multiplier}'
current_order    = {'name':None, 'date':None , 'entry_time': None, 'entry_price': None, 'buy_sell': None, 'qty': None, 'sl': None, 'exit_time': None, 'exit_price': None, 'pnl': None, 'remark': None, 'traded':None}
final_result     = []

pdb.set_trace()
df_day           = pd.read_csv('Historical Data/NIFTY DAY.csv')
all_dates        = df_day['timestamp'].unique().tolist()

df_day           = df_day.set_index('timestamp')
df_day           = tbs.supertrend(df_day, atr_period=supertrend_period, atr_multiplier=supertrend_multiplier)


for datetimex, candle_data in df.iterrows():

	# ----------------------------------------- Entry Block -----------------------------------------
	try:
		previous_date = all_dates[all_dates.index(candle_data.name[:10])-1]

		bc1 = candle_data[st_col] == "up"                 # trend is green on 1 hour
		bc2 = current_order['traded'] is None             # No running trade
		bc3 = df_day.loc[previous_date][st_col] == "up"	  # Previous day trend is green
		bc4 = candle_data['close'] >= candle_data['resistance']

		sc1 = candle_data[st_col] == "down"               # trend is red on 1 hour
		sc2 = current_order['traded'] is None             # No rnning trade
		sc3 = df_day.loc[previous_date][st_col] == "down" # Previous day trend is red
		sc4 = candle_data['close'] <= candle_data['support']


	except Exception as e:
		continue


	if bc1 and bc2 and bc3 and bc4:
		print(f"Buy condition hit for NIFTY on {datetimex}")


		if len(final_result) == 21:
			pdb.set_trace()


		current_order['name']        = 'NIFTY'
		current_order['date']        = datetimex[:10]
		current_order['entry_time']  = datetimex[11:16]
		current_order['entry_price'] = candle_data['close']
		current_order['buy_sell']    = "BUY"
		current_order['qty']         = 75
		current_order['sl']          = candle_data[st_val]
		current_order['traded']      = "yes"
		continue

	if sc1 and sc2 and sc3 and sc4:
		print(f"Sell condition hit for NIFTY on {datetimex}")
		current_order['name']        = 'NIFTY'
		current_order['date']        = datetimex[:10]
		current_order['entry_time']  = datetimex[11:16]
		current_order['entry_price'] = candle_data['close']
		current_order['buy_sell']    = "SELL"
		current_order['qty']         = 75
		current_order['sl']          = candle_data[st_val]
		current_order['traded']      = "yes"
		continue



	# ----------------------------------------- Exit Block -----------------------------------------
	if current_order['traded'] == "yes":

		bought = current_order['buy_sell'] == "BUY"
		sold    = current_order['buy_sell'] == "SELL"


		if bought:

			buy_tsl_hit  = candle_data[st_col] == "down"
			if buy_tsl_hit:
				current_order['exit_time']  = datetimex[:16]
				current_order['exit_price'] = candle_data['close']
				current_order['remark']     = "buy_tsl_hit"
				current_order['pnl']        = round((current_order['exit_price'] - current_order['entry_price'])*current_order['qty'], 2)
				final_result.append(current_order)
				current_order = {'name':None, 'date':None , 'entry_time': None, 'entry_price': None, 'buy_sell': None, 'qty': None, 'sl': None, 'exit_time': None, 'exit_price': None, 'pnl': None, 'remark': None, 'traded':None}
				continue


		if sold:

			sell_tsl_hit  = candle_data[st_col] == "up"
			if sell_tsl_hit:
				current_order['exit_time']  = datetimex[:16]
				current_order['exit_price'] = candle_data['close']
				current_order['remark']     = "sell_tsl_hit"
				current_order['pnl']        = round((current_order['entry_price'] -current_order['exit_price'])*current_order['qty'], 2)
				final_result.append(current_order)
				current_order = {'name':None, 'date':None , 'entry_time': None, 'entry_price': None, 'buy_sell': None, 'qty': None, 'sl': None, 'exit_time': None, 'exit_price': None, 'pnl': None, 'remark': None, 'traded':None}
				continue


print()
final_result = pd.DataFrame(final_result)
final_result.to_excel('Results/7. NIFTY 60 mins positional multimeframe Range Breakout.xlsx', index=False)


