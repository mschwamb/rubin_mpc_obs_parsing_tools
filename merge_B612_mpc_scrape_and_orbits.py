import pooch
import os
import numpy as np
import json
import sqlite3
import pandas as pd
from astropy.time import Time

# need to also install tqdm python package
    


def retrieve_files():
    
    # defining the files and their web locations for download

    urls={
        "mpcorb_extended.json.gz": "https://minorplanetcenter.net/Extended_Files/mpcorb_extended.json.gz",
        "rubin.sqlite.gz":"https://storage.googleapis.com/asteroid-institute-public/production/rubin/mpc/obs_sbn/sqlite/rubin.sqlite.gz",
        "cometels.json.gz": "https://www.minorplanetcenter.net/Extended_Files/cometels.json.gz"
    }
    
    reg ={}
    
    for u in urls.keys():
        reg[u]=None
    

    # set up pooch so it gran these files
    receiver= pooch.create(
    path=pooch.os_cache("rubin"),
    base_url="",
    registry=reg,
    # Now specify custom URLs for some of the files in the registry.
    urls=urls,
    retry_if_failed=5
)
    
    
    # delete any files already in there because we want a fresh set
    cache_path=str(receiver.path)
    
    fnames=np.asarray([], dtype=str)
    
    for u in urls.keys():
    
      # delete the older version of the file if it's already there because we want a fresh set

      try: os.remove(cache_path+'/'+u)
     
     
      except Exception as e:
        print('Failed to delete %s. Reason: %s' % (u, e))
        
      # now download a new one
      
      fname = receiver.fetch(u, progressbar=True, processor=pooch.Decompress(name=str.split(u,".gz")[0]))
      fnames=np.append(fnames,fname)
      

    return fnames

   
def tisserand(planet_a, data ):
    
    tisserand_p=[]
                         
    for ast in data:
        t=planet_a/ast['a']+2*np.sqrt((ast['a']/planet_a)*(1-ast['e']**2))*np.cos(np.radians(ast['i']))
        tisserand_p.append(t)
        
    return tisserand_p
    
def main():
    
    # download the files from MPC and B612 Foundation
    
    fnames= retrieve_files()
    
    # For debugging and development
    #fnames=['/Users/mschwamb/Library/Caches/rubin/mpcorb_extended.json', '/Users/mschwamb/Library/Caches/rubin/rubin.sqlite', '/Users/mschwamb/Library/Caches/rubin/cometels.json']
    
    print(fnames)
    

    file = open(fnames[0], 'r')
    data = json.load(file)


    a_J= 5.2 # Jupiter's semimajor axis in au 
    # get Tisserand parameters with respect to Jupiter

    tisserand_J = tisserand(a_J, data)

    print(data[0].keys())
    conn = sqlite3.connect(fnames[1])  
    cursor = conn.cursor()
    
       
    # remove things that are in the ITF ( Isolated Tracklet File) because 
    # we don't what object these observations belong to
    
    print("removing ITF observations")
    cmd="delete from obs_sbn where status='I'"
    cursor.execute(cmd)
    conn.commit()
    
    # some entries within the obs_sbn do not have a provid but do have a permid.
    # take the permid and grab the provid from the MPC file
      
    cmd="select distinct permid from obs_sbn where provid IS NULL"
    missing_prov_ids=pd.read_sql_query(cmd, conn)
    print(f"Number of observation entires missing a provid {len(missing_prov_ids)}")

    missing_prov_ids = missing_prov_ids['permid'].to_numpy()

    counter=0 
    
    print('if there is no provid entry in the observations table add the permid of the object from the mpc orbits\n')

 
    for i in np.arange(len(data)):
        if 'Number' in data[i].keys():

            number=data[i]['Number'][1:-1]
            index=np.argwhere(number==missing_prov_ids)
            if (len(missing_prov_ids[index]) ==1):
               # print(i, data[i]['Number'], number)
                cmd='update obs_sbn set provid="'+str(data[i]['Principal_desig'])+'" where permid='+"'"+number+"'"
                cursor.execute(cmd)
              #  print(cmd)

                counter=counter+1
        
                if (counter >=50000):
                    conn.commit()
                    counter=0
                    
    conn.commit()
        
    
    #get stats on the Rubin observations and number of planetoids observed
    
    cmd="select count(distinct provid) from obs_sbn"
        
    obj_count=pd.read_sql_query(cmd, conn)
    obj_count=obj_count['count(distinct provid)'][0]
        
    cmd="select count(*) from obs_sbn"

    obs_count=pd.read_sql_query(cmd, conn)
    obs_count=obs_count['count(*)'][0]
    
    print(f"Number of Rubin observed planetoids {obj_count} with {obs_count} Rubin observations")

    
    # make table and set up the indexes 
    
    cmd='drop table if exists mpc_orbits'
    
    cursor.execute(cmd)
    conn.commit()
    
    cmd = """create table if not exists mpc_orbits (id  INTEGER PRIMARY KEY AUTOINCREMENT, fullDesignation varchar(255), mpcH float, a float, q float, e float, incl float, node float, peri float, t_p float, epoch float, nopp float, tisserand_J float)"""
    
    cursor.execute(cmd)
    conn.commit()


    cmd="create index  name_idx ON mpc_orbits(fullDesignation)"
    cursor.execute(cmd)
    conn.commit()
    
    cmd="create index  H_idx ON mpc_orbits(mpcH)"
    cursor.execute(cmd)
    conn.commit()
    
    cmd="create index  a_idx ON mpc_orbits(a)"
    cursor.execute(cmd)
    conn.commit()
   
    cmd="create index  inc_idx ON mpc_orbits(incl)"
    cursor.execute(cmd)
    conn.commit()
    
       
    cmd="create index  q_idx ON mpc_orbits(q)"
    cursor.execute(cmd)
    conn.commit()
    
       
    cmd="create index  e_idx ON mpc_orbits(e)"
    cursor.execute(cmd)
    conn.commit()
    
    
    cmd="create index  nopp_idx ON mpc_orbits(nopp)"
    cursor.execute(cmd)
    conn.commit()
    
      
    cmd="create index  tisserand_idx ON mpc_orbits(tisserand_J)"
    cursor.execute(cmd)
    conn.commit()
    
    
    counter = 0
    
    addToRubinDb= False
    
    print("replacing observation provsisional id with the main principal designation if alternate ID shows up in the obs entry\n")




    for i in np.arange(len(data)):
      # print(i, data[i]['Principal_desig'])
        
        
        cmd="select count(*) from obs_sbn where obs_sbn.provid='"+str( data[i]['Principal_desig'])+"'"
        
        count=pd.read_sql_query(cmd, conn)
        if(count['count(*)'][0]>0):
            addToRubinDb= True
        else:
            addToRubinDb= False
            
        # sometimes the original designation has been swapped to a previous two nighter discovery
        # so we go in and switch MPC desingations in to the obs_sbn database to match what's the
        # primary designation in the MPCORB files
        
        if 'Other_desigs' in data[i].keys():
            for altID in data[i]['Other_desigs']:
               # print(altID)
                cmd="select count(*) from obs_sbn where obs_sbn.provid='"+str(altID)+"'"
                
                count=pd.read_sql_query(cmd, conn)
                if(count['count(*)'][0]>0):
                    #print("other desigs name found")
                    cmd='update obs_sbn set provid="'+str(data[i]['Principal_desig'])+'" where provid='+"'"+str(altID)+"'"
                    cursor.execute(cmd)
                
                    addToRubinDb=True
                    
                   # conn.commit()
  
        # insert the relevant info into an MPC table in the database 


        if (addToRubinDb & ('H' in data[i].keys())):
            cmd = "insert into mpc_orbits(fullDesignation, mpcH, a, q, e, incl, node, peri, t_p, epoch, nopp, tisserand_J)" +" values('"+data[i]['Principal_desig']+"',"+str(data[i]['H'])+","+str(data[i]['a'])+","+str(data[i]['Perihelion_dist'])+","+str(data[i]['e'])+","+str(data[i]['i'])+","+str(data[i]['Node'])+","+str(data[i]['Peri'])+","+str(data[i]['Tp'])+","+str(data[i]['Epoch'])+","+str(data[i]['Num_opps'])+","+str(tisserand_J[i])+")"
            #print(cmd)
            cursor.execute(cmd)

            if (data[i]['a'] =='' or np.isnan(data[i]['a'])):
                print('no a')
    

        counter=counter+1
        
        if (counter >=50000):
            conn.commit()
            counter=0
            

    conn.commit()
    
        
    
    del data 
    
    
    
    # there are a few comets that have been observed. Currently they are not in the MPCORB.dat
    
    # need to update their provids first 
    
    cmd="select distinct permid from obs_sbn where provid is NULL and permid is NOT NULL"
    comets=pd.read_sql_query(cmd, conn)
    cometids = comets.to_numpy() 

    
    counter =0 
    if(len(cometids) > 0): 
        cometids=np.concatenate(cometids)        
        for cometname in cometids: 
            print(cometname, cometname[-1], cometname[0:-1])
            if (cometname[-1] in  ['C', 'P']):        
                cmd=f'update obs_sbn set provid="{cometname}" where permid="{cometname}"'   
                conn.execute(cmd) 
                
                counter=counter+1
                
                if (counter >=5000):
                    conn.commit()
                    counter=0
                    
        conn.commit()
    
    
        counter=0
        
        # open comets file if there are comets in the observations database
            
        file = open(fnames[2], 'r')
        data = json.load(file)
    
        for i in np.arange(len(data)):
            if "Comet_num" in data[i].keys() and "Orbit_type" in data[i].keys():
                c=f"{data[i]['Comet_num']}{data[i]['Orbit_type']}"
                w= c== cometids
                if (len(cometids[w]) > 0):
                    print(c) 
                    print(f'{data[i]['H']}, {data[i]['Perihelion_dist']}, {data[i]['e']}, {data[i]['i']}, {data[i]['Node']}')
               
                    epoch =  Time({'year': int(data[i]['Epoch_year']), 'month': int(data[i]['Epoch_month']), 'day': int(data[i]['Epoch_day']),'hour': 0, 'minute': 0, 'second': 0}, scale='tt') 
                    epoch= epoch.mjd
                    
                    # time of perihelion is given with decimal days
                    
                    hours=float(data[i]['Day_of_perihelion']) - np.floor(data[i]['Day_of_perihelion'])
                    hours=hours*24
                    minutes= (hours-np.floor(hours))*60
                    seconds=int((minutes-np.floor(minutes))*60)
                    hours=int(hours)
                    minutes=int(minutes)
        
                    
                    tp= Time({'year': int(data[i]['Year_of_perihelion']), 'month': int(data[i]['Month_of_perihelion']), 'day': int(data[i]['Day_of_perihelion']),'hour': hours, 'minute': minutes, 'second': seconds}, scale='tt') 
                    tp= tp.mjd
                    
                    print(epoch, tp)
                    if (data[i]['e']>=1): 
                        cmd = "insert into mpc_orbits(fullDesignation, mpcH, q, e, incl, node, peri, t_p, epoch)" +" values('"+c+"',"+str(data[i]['H'])+","+str(data[i]['Perihelion_dist'])+","+str(data[i]['e'])+","+str(data[i]['i'])+","+str(data[i]['Node'])+","+str(data[i]['Peri'])+","+str(tp)+","+str(epoch)+")"
                    else:
                        a=data[i]['Perihelion_dist']/(1-data[i]['e'])
                        data[i]['a']=a
                        tisserand_J = tisserand(a_J, [data[i]])
                        cmd = "insert into mpc_orbits(fullDesignation, mpcH, a, q, e, incl, node, peri, t_p, epoch, tisserand_J)" +" values('"+c+"',"+str(data[i]['H'])+","+str(a)+","+str(data[i]['Perihelion_dist'])+","+str(data[i]['e'])+","+str(data[i]['i'])+","+str(data[i]['Node'])+","+str(data[i]['Peri'])+","+str(tp)+","+str(epoch)+","+str(tisserand_J[0])+")"

                    print(cmd)
                    
                    cursor.execute(cmd)
                    
                    counter=counter+1
                
                    if (counter >=50000):
                        conn.commit() 
                        counter=0
                            
    
    
        del data 
    
       
    # There is no mjd in the mpc database just a date string. Let's add in mjd
    # Also early LSST fitlers didn't have the l in front of the filter (band) name
    
    cmd="select id, provid, obstime, band from obs_sbn"
       
    dfobs=pd.read_sql_query(cmd, conn)
    
    dates=np.asarray(dfobs['obstime'], dtype=str)
    mjd=  Time(dates, format='isot', scale='utc').mjd
   
    cmd= "alter table obs_sbn add mjd_utc float"
    cursor.execute(cmd)
    conn.commit()
    
    counter=0
    for i in np.arange(len(dfobs)):
       # print(dfobs.iloc[i].id)
        
        if (dfobs.iloc[i].band.find('L')==0):
            cmd="update obs_sbn set mjd_utc="+str(mjd[i])+" where id="+str(dfobs.iloc[i].id)
        else:
            cmd="update obs_sbn set mjd_utc="+str(mjd[i])+", band='L"+dfobs.iloc[i].band+"' where id="+str(dfobs.iloc[i].id)

       # print(cmd)
        cursor.execute(cmd)
            
  
        counter=counter+1
        
        if (counter >=50000):
            conn.commit()
            counter=0
        
    
    
    conn.commit()
    
    
    conn.close()
    
    file.close()


   # os.system(f"tar zcvf {fnames[1]}.tgz {fnames[1]}")    
   # os.system(f"bzip-9 {fnames[1]}")  
    #os.system(f"{os.environ['RSPSYNC_PATH'] }/rsp_sync.sh {fnames[1]} mschwamb@rsp:/home/mschwamb/RubinSSPviaMPC/rubin_obs_orbits.sqlite")
  
    #os.system(f"rsync -avz {fnames[1]}.tgz ~/Dropbox/prompt_data_products_database_bandaid/.") 
    print(f"Number of Rubin observed planetoids {obj_count} with {obs_count} Rubin observations")

if __name__ == "__main__":
    main()
