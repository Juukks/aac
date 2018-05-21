# Automatic Answer Circuit for SIP using PJSIP
# 2018 Jukka Heikkila <jutsco@gmail.com>

import ConfigParser

#Loading the configuration file
config = ConfigParser.ConfigParser()
configset = config.read('aac.conf')

#If the configuration file weren't able to open will exit the program
if len(configset) != 1:
        print("Error parsing configuration file");
        exit(1)


#Starting the logging
import logging
import logging.config

logging.config.fileConfig('./logging.conf')
logger = logging.getLogger(__name__)

logger.info("AAC started")




#Where the SIP MAGIC BEGINS

import sys
import pjsua as pj
import threading
import time
import wave

#Global variables
current_call = None
recorderid = None
playerid = None
call_slot = None

# Logging callback
def log_cb(level, str, len):
    print("PJSIP Stack: " + str)
    logger.debug(str)

# Account callback

class AacAccountCallback(pj.AccountCallback):
        sem = None
        
        def __init__(self, account):
                pj.AccountCallback.__init__(self,account)
                
        def wait(self):
                self.sem = threading.Semaphore(0)
                self.sem.acquire()
                
        def on_reg_state(self):
                if self.sem:
                        if self.account.info().reg_status >= 200:
                                self.sem.release()
        #When we are receivin call
        def on_incoming_call(self, call):
                global current_call
                if current_call:
                        call.answer(486, "Busy")
                        
                logging.info("Incoming call from " + str(call.info().remote_uri))
                current_call = call
                call_cb = AacCallCallback(current_call)
                current_call.set_callback(call_cb)
                current_call.answer(180)
                logging.info("Answering in " + str(config.get('FEATURES','ANSWER_DELAY')) + " seconds")
                time.sleep( int(config.get('FEATURES','ANSWER_DELAY')) )
                current_call.answer(200)
                play_announcement()
                
def play_announcement():
        playerid = lib.create_player('greeting.wav',loop=False)
        playerslot = lib.player_get_slot(playerid)
        
        #Connecting sound device to wav record file
        lib.conf_connect(0, playerslot)
        lib.conf_connect(call_slot, playerslot)
        
        time.sleep(5)
        pj.Lib.instance().player_destroy(playerid)
        current_call.call.hangup()
                
                

# Callback performed when events happen in the call
class AacCallCallback(pj.CallCallback):
        def __init__(self, call=None):
                pj.CallCallback.__init__(self,call)
        
        #Notification when call state will change
        def on_state(self):
                global current_call
                print "Call with", self.call.info().remote_uri,
                print "is", self.call.info().state_text,
                print "last code =", self.call.info().last_code, 
                print "(" + self.call.info().last_reason + ")"
               
                if self.call.info().state == pj.CallState.DISCONNECTED:
                    current_call = None
                    print 'Current call is', current_call
                    logging.info("Call is disconnected")
                    
        # Notification when call's media state has changed.
        def on_media_state(self):
                global recorderid
                global playerid
                global call_slot
                        
                if self.call.info().media_state == pj.MediaState.ACTIVE:
                        call_slot = self.call.info().conf_slot
                        pj.Lib.instance().conf_connect(call_slot,0)
                        pj.Lib.instance().conf_connect(0,call_slot)
                        lib.set_snd_dev(0, 0)
                        print "Media is now active"
                else:
                        playerslot = lib.player_get_slot(playerid)
                        lib.conf_disconnect(playerslot,0)
                        lib.conf_disconnect(0,recorderslot)
                        lib.conf_disconnect(call_slot, recorderslot)
                        print "Media is inactive"

lib = pj.Lib()

try:
        ua_cfg = pj.UAConfig()
        ua_cfg.user_agent = "AAC 1.0";
        ua_cfg.max_calls = int(config.get('FEATURES','MAX_CALLS'));
        
        lib.init(ua_cfg, log_cfg = pj.LogConfig(level=9, callback=log_cb))
        logger.info("Library initialized")
        
        logger.info("Creating tranport (" + config.get('TRANSPORT','TYPE') + " / " + config.get('TRANSPORT','LOCAL_PORT') + ") to listen")
        transportMethod = getattr(pj.TransportType, config.get('TRANSPORT','TYPE'), pj.TransportConfig( config.get('TRANSPORT','LOCAL_PORT') ) )
        transport = lib.create_transport(transportMethod)
        
        logger.info("Starting the library")
        lib.start();
                
        # Disabled codecs
        lib.set_codec_priority("speex/16000/1",0)
        lib.set_codec_priority("speex/8000/1",0)
        lib.set_codec_priority("speex/32000/1",0)
        lib.set_codec_priority("GSM/8000/1",0)
        lib.set_codec_priority("opus/48000/2",0)
        lib.set_codec_priority("AMR-WB/16000/1",255)
        lib.set_codec_priority("AMR/8000/1",254)
        lib.set_codec_priority("PCMA/8000/1",253)
        lib.set_codec_priority("PCMU/8000/1",252)
        
        logger.info("Available codecs and prioritys:")
        
        codecs = lib.enum_codecs();
        i = 0;
        while i < len(codecs):
                logger.info("Codec:" + codecs[i].name + ", priority: " + str(codecs[i].priority))
                i+= 1
        
        
        logger.info("Configuring and registering account:")
        logger.info("User: " + config.get('ACCOUNT','USER'))
        logger.info("Host: " + config.get('ACCOUNT','HOST'))
        logger.info("Port: " + config.get('ACCOUNT','PORT'))
        
        # Registering account
        account = lib.create_account(pj.AccountConfig( config.get('ACCOUNT','HOST'), config.get('ACCOUNT','USER'), config.get('ACCOUNT','PASSWORD'), config.get('ACCOUNT','DISPLAY'), config.get('ACCOUNT','REGISTRAR'), config.get('ACCOUNT','PROXY') ))
        account_cb = AacAccountCallback(account)
        account.set_callback(account_cb)
        account_cb.wait()
        
        logger.info("Registration complete, status=" + str(account.info().reg_status) + " (" + account.info().reg_reason + ")")
        
        
        while True:
                print "\n\nPress q to quit\n\n"
                input = sys.stdin.readline().rstrip("\r\n")
                if input == "q":
                        break
        
        # Ending program (De-Registering and cleaning up)
        logger.info("De-Registering and closing app")
        
        account.delete()
        account = None
        transport = None
        lib.destroy()
        lib = None
        sys.exit(0)
        
except (pj.Error, KeyboardInterrupt, SystemExit) as e:
        print("Exception: " + str(e))
        logger.error("Exception: " + str(e))
        if account is not None:
                account.delete()
                account = None
        if lib is not None:
                lib.destroy()
                lib = None
        sys.exit(1)
