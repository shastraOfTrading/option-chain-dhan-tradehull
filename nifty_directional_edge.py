from Dhan_Tradehull import Tradehull
import tradehull_backtesting_support as tbs

# =====================================
# LOGIN
# =====================================

client_id    = "1103610460"
access_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzgwMjk2ODk4LCJpYXQiOjE3ODAyMTA0OTgsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTAzNjEwNDYwIn0.zVIEGTHh3bMAUUVrC8YRAnIMiQbVzqzsRlDOojMXAbCGBt8y5IKjM13V7oN60M1-M_KIZxWKsgc98nfjIZztgw"

tsl = Tradehull(client_id, access_token)

# =====================================
# SETTINGS
# =====================================

SUPER_PERIOD = 10
SUPER_MULTIPLIER = 2

# =====================================
# FETCH HOURLY DATA
# =====================================

print("Fetching 60 Minute Data...")

df_hour = tsl.get_historical_data(
    tradingsymbol="NIFTY",
    exchange="INDEX",
    timeframe="60"
)

# =====================================
# FETCH DAILY DATA
# =====================================

print("Fetching Daily Data...")

df_day = tsl.get_historical_data(
    tradingsymbol="NIFTY",
    exchange="INDEX",
    timeframe="DAY"
)

# =====================================
# CALCULATE SUPERTREND
# =====================================

df_hour = tbs.supertrend(
    df_hour,
    atr_period=SUPER_PERIOD,
    atr_multiplier=SUPER_MULTIPLIER
)

df_day = tbs.supertrend(
    df_day,
    atr_period=SUPER_PERIOD,
    atr_multiplier=SUPER_MULTIPLIER
)

# =====================================
# SUPPORT / RESISTANCE
# =====================================

df_hour["Resistance"] = df_hour["close"].rolling(5).max()
df_hour["Support"] = df_hour["close"].rolling(5).min()

# =====================================
# LATEST VALUES
# =====================================

st_col = f"STX_{SUPER_PERIOD}_{SUPER_MULTIPLIER}"

hourly = df_hour.iloc[-1]
daily = df_day.iloc[-1]

ltp = hourly["close"]

hourly_trend = hourly[st_col]
daily_trend = daily[st_col]

support = round(df_hour["Support"].iloc[-1], 2)
resistance = round(df_hour["Resistance"].iloc[-1], 2)

# =====================================
# SIGNAL LOGIC
# =====================================

bullish = (
    hourly_trend == "up"
    and daily_trend == "up"
    and ltp >= resistance
)

bearish = (
    hourly_trend == "down"
    and daily_trend == "down"
    and ltp <= support
)

# =====================================
# OUTPUT
# =====================================

print("\n")
print("=" * 60)
print("NIFTY DIRECTIONAL EDGE")
print("=" * 60)

print(f"LTP                : {ltp}")
print(f"Hourly Trend       : {hourly_trend}")
print(f"Daily Trend        : {daily_trend}")
print(f"Support            : {support}")
print(f"Resistance         : {resistance}")

print("\n" + "=" * 60)
print("SIGNAL")
print("=" * 60)

if bullish:

    print("BULLISH BREAKOUT")
    print()
    print("Reason:")
    print("- Daily Supertrend is UP")
    print("- Hourly Supertrend is UP")
    print("- Price is above resistance")

elif bearish:

    print("BEARISH BREAKDOWN")
    print()
    print("Reason:")
    print("- Daily Supertrend is DOWN")
    print("- Hourly Supertrend is DOWN")
    print("- Price is below support")

else:

    print("NO SIGNAL")
    print()
    print("Reason:")
    print("- Trend alignment missing")
    print("- Breakout condition not met")

print("=" * 60)