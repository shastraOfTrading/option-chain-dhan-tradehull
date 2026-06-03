from Dhan_Tradehull import Tradehull

# =====================================
# Login
# =====================================

client_id    = "1103610460"
access_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzgwMjk2ODk4LCJpYXQiOjE3ODAyMTA0OTgsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTAzNjEwNDYwIn0.zVIEGTHh3bMAUUVrC8YRAnIMiQbVzqzsRlDOojMXAbCGBt8y5IKjM13V7oN60M1-M_KIZxWKsgc98nfjIZztgw"

tsl = Tradehull(client_id, access_token)

# =====================================
# Get Option Chain
# =====================================

atm, option_chain = tsl.get_option_chain(
    Underlying="NIFTY",
    exchange="INDEX",
    expiry=1,
    num_strikes=10
)
print(option_chain.columns)


print("\n" + "=" * 60)
print(f"ATM STRIKE : {atm}")
print("=" * 60)

# =====================================
# PCR
# =====================================

pcr = option_chain['PE OI'].sum() / option_chain['CE OI'].sum()

print(f"\nPCR : {round(pcr, 2)}")

# =====================================
# Volume PCR
# =====================================

vpcr = option_chain['PE Volume'].sum() / option_chain['CE Volume'].sum()

print(f"Volume PCR : {round(vpcr, 2)}")

# =====================================
# Strongest Support
# =====================================

support = option_chain.loc[
    option_chain['PE OI'].idxmax(),
    'Strike Price'
]

print(f"\nStrong Support : {support}")

# =====================================
# Strongest Resistance
# =====================================

resistance = option_chain.loc[
    option_chain['CE OI'].idxmax(),
    'Strike Price'
]

print(f"Strong Resistance : {resistance}")

# =====================================
# Highest Put Writing
# =====================================

put_writing = option_chain.loc[
    option_chain['PE Chg in OI'].idxmax()
]

print(
    f"\nHighest Put Writing : "
    f"{put_writing['Strike Price']} "
    f"(OI Change = {put_writing['PE Chg in OI']})"
)

# =====================================
# Highest Call Writing
# =====================================

call_writing = option_chain.loc[
    option_chain['CE Chg in OI'].idxmax()
]

print(
    f"Highest Call Writing : "
    f"{call_writing['Strike Price']} "
    f"(OI Change = {call_writing['CE Chg in OI']})"
)

# =====================================
# ATM Greeks
# =====================================

atm_row = option_chain[
    option_chain['Strike Price'] == atm
]

print("\n" + "=" * 60)
print("ATM GREEKS")
print("=" * 60)

print(
    atm_row[
        [
            'CE Delta',
            'CE Gamma',
            'CE Theta',
            'CE Vega',
            'PE Delta',
            'PE Gamma',
            'PE Theta',
            'PE Vega'
        ]
    ]
)

# =====================================
# Top 3 Supports
# =====================================

supports = option_chain.nlargest(
    3,
    'PE OI'
)[['Strike Price', 'PE OI']]

print("\n" + "=" * 60)
print("TOP 3 SUPPORTS")
print("=" * 60)
print(supports)

# =====================================
# Top 3 Resistances
# =====================================

resistances = option_chain.nlargest(
    3,
    'CE OI'
)[['Strike Price', 'CE OI']]

print("\n" + "=" * 60)
print("TOP 3 RESISTANCES")
print("=" * 60)
print(resistances)

# =====================================
# Best Delta Call Strike
# =====================================

call_strike = option_chain.loc[
    option_chain['CE Delta'] > 0.30,
    'Strike Price'
]

if len(call_strike) > 0:
    print(f"\nSuggested CALL Strike : {call_strike.iloc[0]}")

# =====================================
# Best Delta Put Strike
# =====================================

put_strike = option_chain.loc[
    option_chain['PE Delta'] < -0.30,
    'Strike Price'
]

if len(put_strike) > 0:
    print(f"Suggested PUT Strike : {put_strike.iloc[-1]}")

# =====================================
# Full Option Chain Preview
# =====================================

print("\n" + "=" * 60)
print("OPTION CHAIN SNAPSHOT")
print("=" * 60)

print(
    option_chain[
    [
            # ======================
            # CALL SIDE
            # ======================

            'CE Vega',
            'CE Theta',
            'CE Gamma',
            'CE Delta',
            'CE IV',

            'CE Ask Qty',
            'CE Ask',

            'CE Bid',
            'CE Bid Qty',

            'CE Volume',
            'CE Chg in OI',
            'CE OI',

            'CE LTP',

            # ======================
            # CENTER
            # ======================

            'Strike Price',

            # ======================
            # PUT SIDE
            # ======================

            'PE LTP',

            'PE OI',
            'PE Chg in OI',
            'PE Volume',

            'PE Bid Qty',
            'PE Bid',

            'PE Ask',
            'PE Ask Qty',

            'PE IV',
            'PE Delta',
            'PE Gamma',
            'PE Theta',
            'PE Vega'
        ]
    ]
)