from Dhan_Tradehull import Tradehull


client_id    = "1103610460"
access_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzgwMjk2ODk4LCJpYXQiOjE3ODAyMTA0OTgsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTAzNjEwNDYwIn0.zVIEGTHh3bMAUUVrC8YRAnIMiQbVzqzsRlDOojMXAbCGBt8y5IKjM13V7oN60M1-M_KIZxWKsgc98nfjIZztgw"
tsl          = Tradehull(client_id, access_token)


atm, option_chain = tsl.get_option_chain(Underlying="NIFTY", exchange="INDEX", expiry=1, num_strikes=10)
print(option_chain)



# 1. Getting PCR Value
pcr = option_chain['PE OI'].sum() / option_chain['CE OI'].sum()


# 2. Getting Volume PCR
vpcr = option_chain['PE Volume'].sum() / option_chain['CE Volume'].sum()



# 3. Ltp based strike Selection
required_strike = option_chain.loc[option_chain['CE LTP'] < 10, 'Strike Price'].iloc[0]



# 4. Delta based strike selection
required_strike = option_chain.loc[option_chain['CE Delta'] < 0.3, 'Strike Price'].iloc[0]





# 5. OI Analysis
df = tsl.get_historical_data(tradingsymbol = 'NIFTY 09 DEC 26200 CALL',exchange = 'NFO' ,timeframe="5")

df['oi_change']        = df['open_interest'].diff()
df['price_change']     = df['close'].diff()
df['oi_analysis']      = None

df.loc[(df['oi_change'] > 0) & (df['price_change'] > 0), 'oi_analysis'] = "long_buildup"
df.loc[(df['oi_change'] > 0) & (df['price_change'] < 0), 'oi_analysis'] = "short_buildup"
df.loc[(df['oi_change'] < 0) & (df['price_change'] > 0), 'oi_analysis'] = "short_covering"
df.loc[(df['oi_change'] < 0) & (df['price_change'] < 0), 'oi_analysis'] = "long_unwinding"






# 6. Support : https://madefortrade.in/

