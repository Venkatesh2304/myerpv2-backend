from django.db import connection
from app.sql import engine
import pandas as pd

#Check for party ids in sales which are not present in party master
party_sql_query = """
SELECT distinct party_id from app_sales
WHERE party_id NOT IN (SELECT code FROM app_party)
"""
df_missing_party_id = pd.read_sql(party_sql_query,engine)

#Check for stock ids in inventory which are not present in stock master
#Note : Exclude the stock with 4 letters these are stocks from claimservice
stock_sql_query = """
SELECT distinct stock_id from app_inventory
WHERE stock_id NOT IN (SELECT name FROM app_stock)
"""
df_stock_id = pd.read_sql(stock_sql_query,engine)
print(df_stock_id)
exit(0)