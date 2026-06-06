from Dhan_Tradehull import Tradehull
CLIENT_ID    = "1103610460"
ACCESS_TOKEN = (
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzgwODYyNTk1LCJpYXQiOjE3ODA3NzYxOTUsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTAzNjEwNDYwIn0.ZYd66AG8Ay_WspmVQIei0Pj9RR21CM1WWN8djNuU3H0cyTezQGdCJbVEGVi7Q8qlhE5aNUgJHlwsTzaNp5I0xg"
)
tsl = Tradehull(CLIENT_ID, ACCESS_TOKEN)
# spot_test.py

from Dhan_Tradehull import Tradehull

tsl = Tradehull(CLIENT_ID, ACCESS_TOKEN)

result = tsl.get_option_chain(
    Underlying="NIFTY",
    exchange="INDEX",
    expiry=0,
    num_strikes=10
)
print(result)
# data = tsl.get_ltp_data(names=['NIFTY', 'SENSEX'], debug="NO")
# print(data)

# print(
#     tsl.get_expiry_list(
#         Underlying="NIFTY",
#         exchange="INDEX"
#     )
# )