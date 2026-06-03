from Dhan_Tradehull import Tradehull
CLIENT_ID    = "1103610460"
ACCESS_TOKEN = (
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzgwNTU0ODc0LCJpYXQiOjE3ODA0Njg0NzQsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTAzNjEwNDYwIn0.hpXXP7vq0q3GoljLL9DxUNfkmG76MNaApVgGRBC85U_nmiZLv7B0nTjS3xSD2hZvaOgJMg6l0RKZr0gTDr6VcA"
)
tsl = Tradehull(CLIENT_ID, ACCESS_TOKEN)
# spot_test.py

from Dhan_Tradehull import Tradehull

tsl = Tradehull(CLIENT_ID, ACCESS_TOKEN)
print(tsl.get_ltp_data(names=["SENSEX"]))
print("NIFTY")
print(tsl.get_ltp_data(names=["NIFTY"]))

print("BANKNIFTY")
print(tsl.get_ltp_data(names=["BANKNIFTY"]))

print("SENSEX")
print(tsl.get_ltp_data(names=["SENSEX"]))
print(
    tsl.get_expiry_list(
        Underlying="SENSEX",
        exchange="INDEX"
    )
)