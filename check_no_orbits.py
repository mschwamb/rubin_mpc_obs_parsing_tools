import numpy as np
import pandas as pd
import sqlite3

con = sqlite3.connect('/Users/mschwamb/Library/Caches/rubin/rubin.sqlite')  

cursor = con.cursor()

print('starting')
cmd = 'select distinct (obs_sbn.provid) from obs_sbn left join mpc_orbits on  obs_sbn.provid=mpc_orbits.fullDesignation where mpc_orbits.fullDesignation is NULL'
df=pd.read_sql_query(cmd, con)

missing=df.to_numpy()
for x in missing:
    print(x[0])