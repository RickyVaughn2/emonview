#!/usr/bin/env python

import mosquitto
import time
import redis
from configobj import ConfigObj
from pyfina import pyfina

settings = ConfigObj("/home/pi/emonview/emonhub.conf", file_error=True)
config = settings["nodes"]

pyfina = pyfina("/home/pi/data/store/")

r = redis.Redis(host='localhost', port=6379, db=0)

start = time.time()

def on_message(mosq, obj, msg):

    key = msg.topic.split("/")
    
    if key[0]=="api" and key[2]=="values":
        nodeid = str(key[1])
        now = int(time.time())
        values = msg.payload.split(",")
        
        # Check that node exists in config
        if nodeid in config:
            
            # check that there is a record entry
            if "record" in config[nodeid]:
            
                # for each variable in mqtt packet
                for vid in range(len(values)):
                    pyfina.padding_mode = "null"
                
                    # check if there is record entry
                    if len(config[nodeid]["record"])>vid:
                    
                        interval = int(config[nodeid]["record"][vid])
                        
                        # only record if interval is more than 0
                        if interval>0:
                        
                            # RECORD
                            value = float(values[vid])
                            feedname = str(nodeid)+"_"+str(vid)
                            
                            # ACCUMULATOR
                            if "accumulate" in config[nodeid]:
                                if config[nodeid]["accumulate"][vid] is "1":
                                    key = "accumulator:"+str(nodeid)+":"+str(vid)
                                    total = pyfina.lastvalue(feedname)
                                    diff = 0
                                    if r.exists(key):
                                        lastval = float(r.get(key))
                                        diff = value - lastval
                                        if diff<0: diff = 0
                                    r.set(key, value)
                                    value = total + diff
                                    pyfina.padding_mode = "join"
                                    
                            print "-- queue for write "+feedname+" "+str(value)
                            
                            if not pyfina.prepare(feedname,now,value):
                                # if a feed does not exist then create
                                # with interval given by record value
                                pyfina.create(feedname,interval)
                                
    
# Start MQTT (Mosquitto)
mqttc = mosquitto.Mosquitto()
mqttc.on_message = on_message
mqttc.connect("127.0.0.1",1883, 60, True)
mqttc.subscribe("api/#", 0)

lasttime = time.time()
last_write_time = time.time()

if __name__ == '__main__':    
    while True:
        # reload config
        if (time.time()-lasttime)>5.0:
            lasttime = time.time()
            settings = ConfigObj("/home/pi/emonview/emonhub.conf", file_error=True)
            config = settings["nodes"]
        
        # Every 60s write data to disk
        # buffered writing in this way can reduce write load considerably
        if (time.time()-last_write_time)>60.0:
            last_write_time = time.time()
            print "bytes written: "+str(pyfina.save())
        
        mqttc.loop(0)
        time.sleep(0.1)
