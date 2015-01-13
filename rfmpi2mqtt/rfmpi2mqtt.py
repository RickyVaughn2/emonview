#!/usr/bin/env python

import mosquitto, time, serial
from configobj import ConfigObj
import emonhub_coder as ehc
import struct
import redis
import json

settings = ConfigObj("/home/pi/emonview/rfmpi2mqtt/rfmpi2mqtt.conf", file_error=True)
ehc.nodelist = settings['nodes']
ehc.defaultdatacode = settings['defaultdatacode']

ser = serial.Serial("/dev/ttyAMA0", 9600)

r = redis.Redis(host='localhost', port=6379, db=0)

def log(msg):
    print msg
    mqttc.publish("log",msg)

# On receipt of message on nodetx mqtt topic
def on_message(mosq, obj, msg):

    topic_parts = msg.topic.split("/")
    
    if topic_parts[0]=="tx":
    
        for nodeid in ehc.nodelist:
            if ehc.nodelist[nodeid]["nodename"] == topic_parts[1]:
            
                bytedata = []
                vararray = msg.payload.split(",")
                
                x=0
                for code in ehc.nodelist[nodeid]["codes"]:
                    tmp = struct.pack(code,int(vararray[x])) # fix, add parse float if float
                    for i in range(len(tmp)):
                        bytedata.append(struct.unpack('B', tmp[i])[0])
                    x=x+1
                
                bytestr = ",".join(str(val) for val in bytedata)
                
                ser.write(str(nodeid)+","+bytestr+",s")
                log("O: "+msg.topic+" "+msg.payload+" -> "+str(nodeid)+","+bytestr+",s")
    
def on_readline(line):
    log("I: "+line)
    received = line.split(' ')
    nodeid = received[1]
    bytedata = received[2:]
    
    if nodeid in ehc.nodelist:
    
        decoded = ehc.decode_frame(nodeid,bytedata)
        
        if decoded:
            nodename = ehc.nodelist[nodeid]['nodename']
            
            nodevars = {}
            
            for i in range(len(decoded)):
                varname = ehc.nodelist[nodeid]['names'][i]
                nodevars[varname] = decoded[i]
                log("  rx/"+nodename+"/"+varname+"/value "+str(decoded[i]))
                mqttc.publish("rx/"+nodename+"/"+varname+"/value",decoded[i],retain=True)
                r.set("rx/%s/%s" % (nodename, varname),decoded[i])
            
            # mqttc.publish("rx/"+nodename,json.dumps(nodevars),retain=True)
            # r.set("rx/%s" % (nodename),json.dumps(nodevars))
            # log("  rx/"+nodename+" "+json.dumps(nodevars))
            
        

# Start MQTT (Mosquitto)
mqttc = mosquitto.Mosquitto()
mqttc.on_message = on_message
mqttc.connect("127.0.0.1",1883, 60, True)
mqttc.subscribe("tx/#", 0)

# Rather than use serial.readLine we capture the line's manually
# the readLine method waits for \n character which blocks the main loop
# by capturing the serial data manually we can have the loop continue
# with other things until a newline character is found
# linebuff is the buffer string for this
linebuff = ""

# Main loop
while 1:

    # A 'non blocking' readline 
    w = ser.inWaiting()
    if w:
        charbuf = ser.read(w)
        for char in charbuf:
            if char=='\n':
                on_readline(linebuff)
                linebuff = ""
            else:
                linebuff += char
    
    # A 'non blocking' call to mqtt loop
    mqttc.loop(0)
    
    # Main loop sleep control
    time.sleep(0.1)
