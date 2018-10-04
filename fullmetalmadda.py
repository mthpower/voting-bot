#FullMetalMadda bot version 1.1
#Functionality to be added:
#1. Auto-response functionality based on stored lists/dicts in memory, with file backup.
#
#v1.1 Madda - 15 Oct 2011
# - Added asynchronous message processing, bot no longer stutters when asked to send several messages.
#
#v1.0 Madda - 23 Sep 2010
#To contact Madda with any recommendations, bug reports, etc, find him on:
#irc.frosthome.net:6667 in #dirigible or #thezeppelin
#If he's not around, ask one of the regulars to pass on a message.
#
#Following is the Simple BSD (2 clause) license.
#Summarised: Do what you want with the code, just make sure the copyright is included,
#and if something breaks because of this software then that's terribly unfortunate, but
#not my problem.
#
#Copyright 2010 Sandy Walker. All rights reserved.
#
#Redistribution and use in source and binary forms, with or without modification, are
#permitted provided that the following conditions are met:
#
#   1. Redistributions of source code must retain the above copyright notice, this list of
#      conditions and the following disclaimer.
#
#   2. Redistributions in binary form must reproduce the above copyright notice, this list
#      of conditions and the following disclaimer in the documentation and/or other materials
#      provided with the distribution.
#
#THIS SOFTWARE IS PROVIDED BY Sandy Walker ``AS IS'' AND ANY EXPRESS OR IMPLIED
#WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
#FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> OR
#CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
#CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
#ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
#NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
#ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#The views and conclusions contained in the software and documentation are those of the
#authors and should not be interpreted as representing official policies, either expressed
#or implied, of Sandy Walker.

import socket
import sys
import time
import datetime
from multiprocessing import Process,Queue
from queue import Empty
from select import select

timing = False

def print_timing(func):
  def wrapper(*arg):
    if(timing):
      t1 = time.time()
    res = func(*arg)
    if(timing):
      t2 = time.time()
      print('%s took %0.3f ms' % (func.__name__,(t2-t1)*1000.0))
    return res
  return wrapper

#Maintains connection to server
#Allows messages to be sent by other methods/classes
class irc_connection:
  @print_timing
  def __init__(self, configfile):
    self.servers = configfile.get_parameter("servers")
    self.connection = socket.socket ( socket.AF_INET, socket.SOCK_STREAM )
    self.remnant = bytes("", 'ascii') #Variable for storing partial messages recieved at the end of a buffer
    self.messages = Queue()
      
    try:
      self.logger = irclogger(configfile.get_parameter("logfile")[0])
    except IndexError:
      #No logfile was specified, so logging must be disabled
      configfile.set_parameter("logging", ["no"])
      
    self.get_logging_state(configfile)
    
    if(len(self.servers) == 0):
      #No servers? What do you want the poor bot to do?
      print("No servers found in fullmetalmadda.cfg.")
      print("Servers line of file should read:")
      print("servers=irc.something.net:6667;irc.somethingelse.net:6667;irc.andsoon.etc:6667")
      sys.exit(2)
    
    for server in self.servers:
      try:
        #Are we connected?
        if(self.connection.getpeername()):
          #Yes, we don't need to keep trying
          break
      except:
        #No, we should try to connect to this server
#        try:
        server = server.rstrip("\n").split(":")
        self.connection.connect( (server[0], int(server[1])) )
#        except: 
          #We can't connect to this server. Move on.
          #pass

  @print_timing
  def readbuffer(self, message_queue):
    while(True):
      data = self.connection.recv(32)

      messages = ""
      
      data = self.remnant + data
      self.remnant = bytes("", 'ascii')
      
      while(messages == ""):
        try:
          messages = str(data, 'ascii').split("\n") 
        except UnicodeDecodeError as error:
          #Unicode was used in one of the messages. We'll strip out the offending character.
          error = str(error)
          error_position = int(error.partition("position ")[2].partition(":")[0])
          data = data[:error_position] + data[(error_position + 1):]
        except MemoryError as error:
          print(str(error))
          print(messages)
          print(str(data))

      if(messages[len(messages) - 1].find("\r") == -1):
        self.remnant = bytes(messages[len(messages) - 1], 'ascii')
        messages.pop(len(messages) - 1)

      message_queue.put(messages)

  @print_timing
  def close(self):
    self.connection.close()
    self.messages = Queue()

  def sendraw(self,message):
    #Send a raw message- must be sent as bytes
    try:
      self.connection.send(message)
      message = str(message, 'ascii')
    except:
      #Probably not encoded correctly, attempt a fix
      self.connection.send(bytes(message, 'ascii'))

    if(self.logging):
      self.logger.log_raw("->", message)

  @print_timing      
  def sendaction(self, target, message):
    message = bytes("PRIVMSG " + target + " :\x01ACTION " + message + "\x01\r\n", 'ascii')
    self.connection.send(message)
    
    if(self.logging):
      self.logger.log_outbound(str(message, 'ascii'))

  @print_timing
  def send(self,messagetype, target, subtarget, message):
    #Variable set to bypass logging if nothing is sent
    valid_message = True
  
    #Send a message of a specific type
    if(messagetype == "PONG"):
      message = bytes(messagetype + " " + message + "\r\n", 'ascii')
    elif(messagetype == "JOIN"):
      message = bytes(messagetype + " :" + target + "\r\n", 'ascii')
    elif(messagetype == "KICK"):
      message = bytes(messagetype + " " + target + " " + subtarget + " :" + message + " \r\n", 'ascii')
    elif(messagetype == "PART"):
      message = bytes(messagetype + " " + target + " :" + message + "\r\n", 'ascii')
    elif(messagetype == "QUIT"):
      message = bytes(messagetype + " :" + message + "\r\n", 'ascii')
    elif(messagetype == "PRIVMSG" or messagetype == "NOTICE"):
      message = bytes(messagetype + " " + target + " :" + message + "\r\n", 'ascii')
    elif(messagetype == "INVITE"):
      #Peculiar format to this one- INVITE user :#channel
      message = bytes(messagetype + " " + subtarget + " :" + target + "\r\n", 'ascii')
    elif(messagetype == "NICK"):
      message = bytes(messagetype + " " + target + "\r\n", 'ascii')
    elif(messagetype == "USER"):
      message = bytes(messagetype + " " + target + " " + subtarget + " * :" + message + "\r\n", 'ascii')
    elif(messagetype == "MODE"):
      message = bytes(messagetype + " " + target + " " + message + " " + subtarget + "\r\n", 'ascii')
    elif(messagetype == "WHO"):
      message = bytes(messagetype + " " + target + "\r\n", 'ascii')
    elif(messagetype == "WHOIS"):
      #Yes, we could check to make sure it's not a channel, but they'll get the message.
      message = bytes(messagetype + " " + target + "\r\n", 'ascii')
    elif(messagetype == "LIST"):
      #LIST can be called with a specific channel, so we'll accept a target
      message = bytes(messagetype + " " + target + "\r\n", 'ascii')
    elif(messagetype == "TOPIC"):
      message = bytes(messagetype + " " + target + " :" + message + "\r\n", 'ascii')
    else:
      #Either a message type we don't handle yet or a typo. For the moment we'll just silently ignore it
      valid_message = False
      pass
    
    if(valid_message):
      self.connection.send(message)
      if(self.logging):
        self.logger.log_outbound(str(message, 'ascii'))
 
  def get_logging_state(self, configfile):
    try:
      if(configfile.get_parameter("logging")[0] == "yes"):
        self.logging = True
      else:
        self.logging = False
    except IndexError:
      #Someone specified a logfile name but then didn't specify whether logging should be enabled
      #We'll assume it should be
      self.logging = True
 
#Class for logging data sent and received.
class irclogger:
  @print_timing
  def __init__(self, filename):
    #Append the date and time to the logfile name to avoid overwriting existing logs.
    self.filename = filename.rstrip().rstrip(".log") + time.strftime("%Y%b%d%H%M%S",datetime.datetime.now().timetuple()) + ".log"
    self.filehandle = open(self.filename, "w")
    self.filehandle.write("I/O,Nickname,Usermask,Type,Target,Channel,Message\n")

  @print_timing    
  def log_inbound(self, data):
    entry = "<-:" + data.rstrip() + "\n"
    self.filehandle.write(entry)

  @print_timing    
  def log_outbound(self, data):
    entry = "->:" + data.rstrip() + "\n"
    self.filehandle.write(entry)

  @print_timing    
  def log_raw(self, direction, data):
    entry = direction + ":" + data.rstrip() + "\n"
    self.filehandle.write(entry)

  @print_timing    
  def close(self):
    self.filehandle.close()
 
#Class for processing config file
class config_file:
  @print_timing
  def __init__(self, filename):
    self.parameters = {}
    self.filename = filename
    
    #Process the file
    self.parse()
  
  #Method to parse config file on startup or changes
  @print_timing
  def parse(self):
    conf = open(self.filename, 'r')
    
    for line in conf.readlines():
      line = line.partition("=")
      parameter = line[0]
      value = line[2].rstrip().split(";") #Any variables that take multiple parameters are split using ;
      self.parameters[parameter] = value
    
    conf.close()

  @print_timing
  def reparse(self):
    self.parse()

  @print_timing
  def save(self):
    conf = open(self.filename,'w')
    
    for parameter in self.parameters:
      if(isinstance(self.parameters[parameter], list)):
        conf.write(parameter + "=" + ";".join(self.parameters[parameter]) + "\n")
      else:
        #Someone changed a parameter without using the updateparam function
        #And to make matters better, they didn't make it a list. Aren't people annoying?
        conf.write(parameter + "=" + self.parameters[parameter] + "\n")
    
    conf.close()

  @print_timing
  def set_parameter(self, parameter, newvalue):
    if(not isinstance(newvalue, list)):
      #Something that isn't a list was supplied. Fix this, assuming it's a single value.
      try:
        newvalue = newvalue.split()
      except AttributeError:
        try:
          newvalue = str(newvalue, 'ascii').split()
        except TypeError:
          newvalue = str(newvalue).split()
 
    self.parameters[parameter] = newvalue

  @print_timing
  def get_parameter(self, parameter):
    try:
      return list(self.parameters[parameter]) #Return a copy so that the config file only gets modified when set_parameter is called
    except KeyError:
      return []
 
#Class for processing messages from IRC  
class irc_message:  
  #Method to initialise message processing class
  @print_timing
  def __init__(self, data, conn, mynick):
    self.data = {"nickname":"","fullname":"","hostmask":"","type":"","message":"","target":"","channel":""}
    self.data["raw"] = data.rstrip("\r").rstrip("\n")
    self.irc_connection = conn
    self.my_nickname = mynick
    self.whois_data = []
    self.list_channel = {"name":"","topic":"","users":"","modes":""}
    self.who_data = []
    self.channel_members = []
    self.away = []
    
    procdata = data.partition(" ")
    
    #Get the details of the message sender
    userdetails = procdata[0].partition("!")
    if(userdetails[1] == ""):
      #Server, use placeholders for nickname and fullname
      self.data["nickname"] = "#:SERVER:#"
      self.data["fullname"] = self.data["nickname"]
      self.data["hostmask"] = userdetails[2].rstrip().lstrip(":")
    else:
      #User, get full details
      self.data["nickname"] = userdetails[0].lstrip(":").rstrip()
      self.userdetails = userdetails[2].partition("@")
      self.data["fullname"] = userdetails[0].rstrip()
      self.data["hostmask"] = userdetails[2].rstrip()
    
    #Get the message type- PING is a special case
    if(procdata[0].rstrip() == "PING"):
      self.data["type"] = "PING"
    else:
      procdata = procdata[2].partition(" ")
      self.data["type"] = procdata[0].rstrip()
    
    #Process the message based on its type    
    if(self.data["type"] == "PING"):
      #Server checking client is still responsive.
      self.data["message"] = procdata[2].rstrip()
      self.data["target"] = "#:SELF:#"
      self.data["channel"] = self.data["target"]
    elif(self.data["type"] == "433"):
      #Server response indicating nickname already in use.
      self.data["message"] = procdata[2].rstrip()
      self.data["target"] = "#:SELF:#"
      self.data["channel"] = self.data["target"]
    elif(self.data["type"] == "001"):
      #Server response indicating that the network has been joined successfully
      self.data["message"] = procdata[2].rstrip()
      self.data["target"] = "#:SELF:#"
      self.data["channel"] = self.data["target"]
    elif(self.data["type"] == "JOIN"):
      #Someone joined a channel
      self.data["message"] = ""
      self.data["target"] = procdata[2].lstrip(":").rstrip()
      self.data["channel"] = self.data["target"]
    elif(self.data["type"] == "KICK"):
      #Someone got kicked
      procdata = procdata[2].partition(" ")
      self.data["message"] = procdata[2].partition(":")[2].rstrip()
      self.data["target"] = procdata[2].partition(":")[0].rstrip()
      self.data["channel"] = procdata[0].rstrip()
    elif(self.data["type"] == "NICK"):
      self.data["message"] = ""
      self.data["target"] = procdata[2].lstrip(":").rstrip()
      self.data["channel"] = "#:PRIVATE:#"
    elif(self.data["type"] == "QUIT" or self.data["type"] == "PART"):
      #Someone left a channel or the network
      procdata = procdata[2].partition(" ")
      self.data["message"] = procdata[2].lstrip(":").rstrip()
      self.data["target"] = "#:PRIVATE:#" #QUIT messages are sent with a target/channel of :Quit:. We'll label them PRIVATE.
      self.data["channel"] = self.data["target"]
    elif(self.data["type"] == "PRIVMSG" or self.data["type"] == "NOTICE"):
      #Someone is communicating with the client or a channel
      procdata = procdata[2].partition(" ")
      self.data["message"] = procdata[2].lstrip(":").rstrip()
      self.data["target"] = procdata[0].rstrip()
      if(self.data["target"].find("#") > -1 or self.data["target"].find("&") > -1):
        #It's public communication on a channel
        self.data["channel"] = self.data["target"]
      else:
        #It's private communication
        self.data["channel"] = "#:PRIVATE:#"
    elif(self.data["type"] == "INVITE"):
      #Someone has sent an invite to somewhere
      procdata = procdata[2].partition(" ")
      self.data["message"] = ""
      self.data["target"] = procdata[0].rstrip()
      self.data["channel"] = procdata[2].lstrip(":").rstrip()
    elif(self.data["type"] == "352"):
      #A response to a 'WHO'
      procdata = procdata[2].partition(" ")
      self.data["target"] = procdata[0].rstrip()
      procdata = procdata[2].partition(" ")
      self.data["channel"] = procdata[0].rstrip()
      #So that this can be responded to within the main loop- but we'll process it here for our purposes
      self.data["message"] = procdata[2].rstrip()
      procdata = procdata[2].split(" ")
      memberof = self.data["channel"]
      user = procdata[3]
      self.who_data = [user, memberof]
    elif(self.data["type"] == "317"):
      #The message is a response to a WHOIS, indicating the idle time and sign-on time of the user
      procdata = procdata[2].partition(" ")
      self.data["target"] = procdata[0].rstrip()
      self.data["channel"] = "#:PRIVATE:#" #Responses to WHOIS messages are sent direct to the initiating user.
      self.data["message"] = procdata[2].rstrip()
      try:
        procdata = procdata[2].split(" ")
        #Return a list containing: [Username, int(idletime), int(signontime)]
        self.whois_data = [procdata[0].rstrip(), int(procdata[1].rstrip()), int(procdata[2].rstrip())]
      except ValueError:
        self.whois_data = ["#:INVALID:#", -1, -1]
    elif(self.data["type"] == "319"):
      #The message is a response to a WHOIS, providing a list of (visible) channels the user is a member of
      #Note that this also provides the user status in the channel where applicable (e.g. op, owner, voice, etc)
      procdata = procdata[2].partition(" ")
      self.data["target"] = procdata[0].rstrip()
      self.data["channel"] = "#:PRIVATE:#" #Responses to WHOIS messages are sent direct to the initiating user.
      self.data["message"] = procdata[2].rstrip()
      procdata = procdata[2].split(" ")
      self.whois_data.append(procdata[0].rstrip())
      self.whois_data.append(procdata[1].rstrip().lstrip(":")) #The first channel is preceded by a :
      for channel in range(2,len(procdata)):
        chan_name = procdata[channel].rstrip()
        if(chan_name != ""):
          self.whois_data.append(chan_name)
    elif(self.data["type"] == "312"):
      #The message is a response to a WHOIS, providing the server the user is connected to, and the server description
      procdata = procdata[2].partition(" ")
      self.data["target"] = procdata[0].rstrip()
      self.data["channel"] = "#:PRIVATE:#" #Responses to WHOIS messages are sent direct to the initiating user.
      self.data["message"] = procdata[2].rstrip()
      procdata = procdata[2].partition(" ")
      self.whois_data.append(procdata[0].rstrip()) #Username
      procdata = procdata[2].partition(" ")
      self.whois_data.append(procdata[0].rstrip()) #Server name
      self.whois_data.append(procdata[2].rstrip().lstrip(":"))
    elif(self.data["type"] == "307"):
      #The message is a response to a WHOIS, indicating whether the user is registered (better to use nickserv status privmsg)
      procdata = procdata[2].partition(" ")
      self.data["target"] = procdata[0].rstrip()
      self.data["channel"] = "#:PRIVATE:#" #Responses to WHOIS messages are sent direct to the initiating user.
      self.data["message"] = procdata[2].rstrip()
      procdata = procdata[2].partition(" ")
      self.whois_data.append(procdata[0].rstrip())
      if(procdata[2].lstrip().rstrip() == ":is a registered nick"):
        self.whois_data.append(True)
      else:
        self.whois_data.append(False)
    elif(self.data["type"] == "311"):
      #The message is a response to a WHOIS, providing user full name, hostmask, etc
      procdata = procdata[2].partition(" ")
      self.data["target"] = procdata[0].rstrip()
      self.data["channel"] = "#:PRIVATE:#" #Responses to WHOIS messages are sent direct to the initiating user.
      self.data["message"] = procdata[2].rstrip()
      procdata = procdata[2].partition(" ")
      self.whois_data.append(procdata[0].rstrip()) #Username (as with all WHOIS responses)
      procdata = procdata[2].partition(" ")
      self.whois_data.append(procdata[0].rstrip()) #Full name
      procdata = procdata[2].partition(" ") 
      self.whois_data.append(procdata[0].rstrip()) #Hostmask- procdata[2] will be a *
      procdata = procdata[2].partition(" ") #We don't want the *
      self.whois_data.append(procdata[2].rstrip().lstrip(":")) #User description
    elif(self.data["type"] == "322"):
      #The message is a response to a LIST, providing channel name, number of members, modes, and topic
      procdata = procdata[2].partition(" ")
      self.data["target"] = procdata[0].rstrip()
      self.data["channel"] = "#:PRIVATE:#" #Responses to LIST messages are sent direct to the initiating user.
      self.data["message"] = procdata[2].rstrip()
      procdata = procdata[2].partition(" ")
      self.list_channel["name"] = procdata[0].rstrip()
      procdata = procdata[2].partition(" ")
      self.list_channel["users"] = procdata[0].rstrip()
      procdata = procdata[2].partition(" ")
      self.list_channel["modes"] = procdata[0].rstrip().lstrip(":").strip("[").strip("]")
      self.list_channel["topic"] = procdata[2].rstrip()
    elif(self.data["type"] == "353"):
      #This message is sent to us after we join a channel, and contains a list of users of the channel
      procdata = procdata[2].partition(" ")
      self.data["target"] = procdata[0].rstrip()
      procdata = procdata[2].partition(" ") # Drop the = sign
      procdata = procdata[2].partition(" ")
      self.data["channel"] = procdata[0].rstrip() #This will be populated with the channel to which it refers
      self.data["message"] = procdata[2].lstrip(":").rstrip()
      self.channel_members = self.data["message"].split(" ")
    elif(self.data["type"] == "332"):
      #This message is sent to us after we join a channel, and contains the topic.
      procdata = procdata[2].partition(" ")
      self.data["target"] = procdata[0].rstrip()
      procdata = procdata[2].partition(" ")
      self.data["channel"] = procdata[0].rstrip()
      self.data["message"] = procdata[2].lstrip(":")
    elif(self.data["type"] == "333"):
      #This message is sent to us after we join a channel, and contains the channel owner and timestamp (of founding?)
      procdata = procdata[2].partition(" ")
      self.data["target"] = procdata[0].rstrip()
      procdata = procdata[2].partition(" ")
      self.data["channel"] = procdata[0].rstrip()
      self.data["message"] = procdata[2].lstrip(":")
    elif(self.data["type"] == "TOPIC"):
      #Someone changed the topic on a channel we're in
      procdata = procdata[2].partition(" ")
      self.data["message"] = procdata[2].lstrip(":").rstrip()
      self.data["target"] = procdata[0].rstrip()
      self.data["channel"] = self.data["target"]
    elif(self.data["type"] == "301"):
      #A user is away (WHOIS or response to a message sent to them)
      procdata = procdata[2].partition(" ")
      self.data["target"] = procdata[0].rstrip()
      self.data["channel"] = "#:PRIVATE:#" #Response to WHOIS messages are sent direct to the initiating user.
      self.data["message"] = procdata[2].rstrip()
      procdata = procdata[2].partition(" ")
      self.whois_data.append(procdata[0].rstrip()) #Username
      self.whois_data.append(procdata[2].lstrip(":").rstrip()) #Away message
      self.away = self.whois_data
    elif(self.data["type"] == "313"):
      #The user we sent a WHOIS on is an IRCOP
      procdata = procdata[2].partition(" ")
      self.data["target"] = procdata[0].rstrip()
      self.data["channel"] = "#:PRIVATE:#" #Response to WHOIS messages are sent direct to the initiating user.
      self.data["message"] = procdata[2].rstrip()
      self.whois_data.append(procdata[2].split(" ")[0].rstrip()) #Username
    elif(self.data["type"] == "401"):
      #The user we sent a WHOIS or a private message doesn't exist
      procdata = procdata[2].partition(" ")
      self.data["target"] = procdata[0].rstrip()
      self.data["channel"] = "#:PRIVATE:#" #Response to WHOIS messages are sent direct to the initiating user.
      self.data["message"] = procdata[2].rstrip()
      self.whois_data.append(procdata[2].split(" ")[0].rstrip()) #Username
    elif(self.data["type"] == "671"):
      #The user we sent a WHOIS on is on a secure connection
      procdata = procdata[2].partition(" ")
      self.data["target"] = procdata[0].rstrip()
      self.data["channel"] = "#:PRIVATE:#" #Response to WHOIS messages are sent direct to the initiating user.
      self.data["message"] = procdata[2].rstrip()
      self.whois_data.append(procdata[2].split(" ")[0].rstrip()) #Username
    else:
      #This message type is unknown
      self.data["message"] = procdata[2].rstrip()
      self.data["target"] = "#:UNKNOWN:#"
      self.data["channel"] = self.data["target"]
  
    if(conn.logging):
      conn.logger.log_inbound(self.data["raw"])

  @print_timing      
  def replyaction(self,response):
    #Define how to use an action in response to a message.
    if(self.data["type"] == "NOTICE"):
      #These should not be subject to an auto-reply, so we will not define a reply method for them
      #If they are to be replied to, it must be done explicitly as a new message
      pass
    elif(self.data["type"] == "KICK"):
      if(self.data["target"] == self.my_nickname):
        #Someone just kicked the client. A reply should rejoin then send an action to the channel
        self.irc_connection.send("JOIN", self.data["channel"], "", "")
        self.irc_connection.sendaction(self.data["channel"], response + " " + self.data["nickname"])
      else:
        #Someone else just got kicked from a channel. Our default response will be an action to the channel
        self.irc_connection.sendaction(self.data["channel"], response + " " + self.data["nickname"])
    elif(self.data["type"] == "PRIVMSG"):
      #Someone is talking to us or to a channel we're in. Respond to them/the channel
      if(self.data["channel"] == "#:PRIVATE:#"):
        self.irc_connection.sendaction(self.data["nickname"], response + " you")
      else:
        self.irc_connection.sendaction(self.data["target"], response + " " + self.data["nickname"])
    elif(self.data["type"] == "JOIN"):
      #We saw someone join a channel, respond to the channel they're on
      self.irc_connection.sendaction(self.data["nickname"], response + " " + self.data["nickname"])
    elif(self.data["type"] == "PART"):
      #We saw someone leave a channel we can see, respond to the channel they were in.
      self.irc_connection.sendaction(self.data["channel"], response + " " + self.data["nickname"])
    elif(self.data["type"] == "INVITE"):
      #We saw an invite to a channel
      #Just in case some quirk of our status or the server allows us to see other invites,
      #we check to make sure the invite is to us
      if(self.data["target"] == self.my_nickname):
        #Default response is to join te channel then send a message
        self.irc_connection.send("JOIN", self.data["channel"], "", "")
        self.irc_connection.sendaction(self.data["channel"], response + " " + self.data["nickname"])
    elif(self.data["type"] == "TOPIC"):
      #We saw a topic change in the channel.
      #We'll perform an action in the channel, referring to the user who made the change
      self.irc_connection.sendaction(self.data["channel"], response + " " + self.data["nickname"])

  @print_timing      
  def reply(self,response):
    #Define how to respond to each type of action
    if(self.data["type"] == "NOTICE"):
      #These should not be subject to an auto-reply, so we will not define a reply method for them
      #If they are to be replied to, it must be done explicitly as a new message
      pass
    elif(self.data["type"] == "KICK"):
      if(self.data["target"] == self.my_nickname):
        #Someone just kicked the client. A reply should rejoin then send a message to the channel
        self.irc_connection.send("JOIN", self.data["channel"], "", "")
        self.irc_connection.send("PRIVMSG", self.data["channel"], "", response)
      else:
        #Someone else just got kicked from a channel. Our default response will be a message to the channel
        self.irc_connection.send("PRIVMSG", self.data["channel"], "", response)
    elif(self.data["type"] == "PRIVMSG"):
      #Someone is talking to us or to a channel we're in. Respond to them/the channel
      if(self.data["channel"] == "#:PRIVATE:#"):
        self.irc_connection.send("PRIVMSG", self.data["nickname"], "", response)
      else:
        self.irc_connection.send("PRIVMSG", self.data["target"], "", response)
    elif(self.data["type"] == "JOIN"):
      #We saw someone join a channel, respond to the channel they're on
      self.irc_connection.send("PRIVMSG", self.data["nickname"], "", response)
    elif(self.data["type"] == "PART"):
      #We saw someone leave a channel we can see, respond to the channel they were in.
      self.irc_connection.send("PRIVMSG", self.data["channel"], "", response)
    elif(self.data["type"] == "INVITE"):
      #We saw an invite to a channel
      #Just in case some quirk of our status or the server allows us to see other invites,
      #we check to make sure the invite is to us
      if(self.data["target"] == self.my_nickname):
        #Default response is to join te channel then send a message
        self.irc_connection.send("JOIN", self.data["channel"], "", "")
        self.irc_connection.send("PRIVMSG", self.data["channel"], "", response)
    elif(self.data["type"] == "TOPIC"):
      #Someone changed the topic. We'll reply by changing it ourself.
      self.irc_connection.send("TOPIC", self.data["channel"], "", response)

class FMM_IRCConnectionException(Exception):
  @print_timing
  def __init__(self, value):
    self.error = value

  @print_timing
  def __str__(self):
    return repr(self.error)
        
class FMM_IRCConnectionManager:
  @print_timing
  def __init__(self,configfilename):
    self.messagequeue = []
    self.configfile = config_file(configfilename)
    self.irc_connection = None
    self.irc_conn_reader = None
    self.nickname_set = False
    self.channels_joined = False
    self.nickname_index = 0
    self.mynick = ""
    self.oldnick = ""
    self.nicknames = self.configfile.get_parameter("nicknames")
    self.channels = self.configfile.get_parameter("channels")
    self.bot_ops = self.configfile.get_parameter("botops")
    self.connected = False
    self.registered_users = {}
    self.if_registered_send_queue = []
    self.if_registered_action_queue = []
    self.if_registered_raw_queue = []
    self.if_registered_exec_queue = []
    self.quit_sent = False
    #Dictionary containing a list of the members of each channel, as this gets populated
    #This will be populated either by running a 'WHO' generally or on a specific channel,
    #Or when a channel is joined, and will be maintained automatically on noticing part or quit messages
    self.channel_members = {}
    
    if(len(self.nicknames) == 0):
      #No nickname? Sadly we can't be the nameless one.
      raise FMM_IRCConnectionException("No nicknames set in " + self.configfile.filename + ".")
 
    #We'll automatically connect when we're instantiated.
    self.connect()
    
  #For usability we'll define a 'reconnect' method, though it'll just call connect()
  @print_timing
  def reconnect(self):
    self.connect()
    
  @print_timing
  def connect(self):
    if(self.connected):
      #We're already connected. Let's disconnect first.
      self.connected = False
      self.nickname_set = False
      self.channels_joined = False
      self.nickname_index = 0
      self.mynick = ""
      self.irc_connection.send("QUIT","","","Reconnecting.")
      time.sleep(3) #Wait for QUIT message to be processed.
      self.irc_connection.close() #Now make sure the connection is closed
    
    #Open a new connection
    self.irc_connection = irc_connection(self.configfile)
    self.irc_conn_reader = Process(target=self.irc_connection.readbuffer,args=(self.irc_connection.messages,))
    self.irc_conn_reader.start()
 
    #We haven't quit this connection yet
    self.quit_sent = False
  
    #Check to make sure we have some channels to join, unless a parameter has been set so that we don't care
    if(len(self.channels) == 0 and not self.configfile.get_parameter("nochannelwarn")[0] == "no"):
      #No channels defined. Non-critical, but raise exception
      raise FMM_IRCConnectionException("No channels specified in " + self.configfile.filename + ". Specify channel or set nochannelwarn=no")
    
      #Either way, we don't need to worry about connecting again
      channels_joined = True
    
    nickname_sent = False
    
    while(not self.connected):
      #On each pass we want to make sure we've got any new messages from the buffer and messagified them
      try:
        data = self.irc_connection.messages.get_nowait()
        for msg in data:
          msg.rstrip("\r")
          if(msg != ""):
            self.messagequeue.append(irc_message(msg, self.irc_connection, self.mynick))
      except Empty:
        #No new messages, don't cry about it.
        pass
      
      queuelength = len(self.messagequeue)

      #Don't try to set anything until we've connected.
      #Standard connections seem to result in two messages from the server before it accepts messages
      if(queuelength > 1):
        for message in self.messagequeue:
          if(message.data["type"] == "433" and message.data["target"] == "#:SELF:#"):
            #The nickname we selected is in use, we'll move on to the next one.
            self.nickname_index+=1
            self.nickname_set = False
            self.username_set = False
            nickname_sent = False
            if(len(self.channels) > 0):
              self.channels_joined = False
            if(self.nickname_index > len(self.nicknames) - 1):
              #All nicknames specified in config file are in use, bomb out
              raise FMM_IRCConnectionException("All nicknames specified in " + self.configfile.filename + " are in use.")
            #Mark this as processed
            message.data["target"] = "#-SELF-#"
            
          if(message.data["type"] == "PING" and message.data["target"] == "#:SELF:#"):
            self.irc_connection.send("PONG","","",message.data["message"])
            #Mark this PING as processed so that we don't respond to it again.
            message.data["target"] = "#-SELF-#"
          
          if(message.data["type"] == "001" and message.data["target"] == "#:SELF:#"):
            self.nickname_set = True
            message.data["target"] = "#-SELF-#"
          
        if(not nickname_sent):
          self.irc_connection.send("NICK", self.nicknames[self.nickname_index], "", "")
          self.mynick = self.nicknames[self.nickname_index]
          self.oldnick = self.mynick
          nickname_sent = True
          self.irc_connection.send("USER", self.mynick, "8", "Python IRC bot")
          self.username_set = True
        elif(self.nickname_set and not self.channels_joined):
          for channel in self.channels:
            self.join(channel)
          self.channels_joined = True
          self.connected = True
        elif(self.nickname_set and self.channels_joined):
          #We have no channels to join, let's finish connecting
          self.connected = True

        if(nickname_sent and not self.nickname_set):
          time.sleep(0.1)
          
  @print_timing          
  def disconnect(self):
    #Close the connection
    self.connected = False
    self.irc_connection.connection.close()
 
  @print_timing 
  def process_messages(self):
    #A queue of messages that hasn't been processed yet
    messagequeue_preproc = []
    queuelength = len(self.messagequeue)
    
    #On each pass we want to make sure we've got any new messages from the buffer and messagified them
    try:
      data = self.irc_connection.messages.get_nowait()
      for msg in data:
        msg.rstrip("\r")
        if(msg != ""):
          messagequeue_preproc.append(irc_message(msg, self.irc_connection, self.mynick))
    except Empty:
      #No new messages, don't cry about it.
      pass
    
    #Now we perform any steps on the messages required to maintain connection state information
    #(e.g. channel membership listing)
    #After that, we add it to the messagequeue for general use      
    while(len(messagequeue_preproc) > 0):
      message = messagequeue_preproc.pop()
    
      #Keep track of membership for channels we're in
      #If messages arrive out of order then we might find ourselves with an inaccurate list of members
      if(message.data["type"] == "QUIT"):
        for channel in self.channel_members:
          #We'll call the rem_channel_members method for this nickname on every channel
          #It'll perform the same comparison we'd have to perform here inside of the method
          self.rem_channel_member(channel, message.data["nickname"])
      if(message.data["type"] == "PART" and message.data["channel"] in self.channel_members):
        self.rem_channel_member(message.data["channel"], message.data["nickname"])
      elif(message.data["channel"] in self.channel_members):
        #We should make sure that the user is in the member list if we see them speak (or join)
        if(message.data["nickname"] not in self.channel_members[message.data["channel"]]):
          self.add_channel_member(message.data["channel"], message.data["nickname"])
      #If someone is kicked we should remove them
      if(message.data["type"] == "KICK" and message.data["channel"] in self.channel_members):
        #Unless it's the bot being kicked in which case we should stop monitoring this channel
        if(message.data["target"] == self.mynick):
          del self.channel_members[message.data["channel"]]
        else:
          self.rem_channel_member(message.data["channel"], message.data["target"])
      
      if(message.data["type"] == "PING"):
        #Let's respond before we get booted off the network
        self.irc_connection.send("PONG", "", "", message.data["message"])
      
      #If we've just joined a channel, we should check the membership list
      elif(message.data["type"] == "353" and message.data["channel"] in self.channel_members):
        self.channel_members[message.data["channel"]] = [round(time.time(), 0)]
        for member in message.channel_members:
          self.add_channel_member(message.data["channel"], member)
          
      #If we're receiving a response to 'WHO' we should add the user to the channel membership list, where applicable
      elif(message.data["type"] == "352" and message.who_data[1] in self.channel_members):
        if(round(time.time(), 0) - self.channel_members[message.who_data[1]][0] > 30):
          #It's been more than 30 seconds since our last 'WHO' on this channel, refresh the channel members list completely
          self.channel_members[message.who_data[1]] = [round(time.time(), 0)]
          self.add_channel_member(message.who_data[1], message.who_data[0])
        elif(message.who_data[0] not in self.channel_members[message.who_data[1]]):
          #If we don't have the user in the list already then we should add them
          self.add_channel_member(message.who_data[1], message.who_data[0])
      
      elif(message.data["nickname"] == "NickServ" and message.data["type"] == "NOTICE"):
        #If we receive a request to identify, we should do so
        if(message.data["message"].find("This nickname is registered") > -1):
          passwords = self.configfile.get_parameter("passwords")
          nicknames = self.configfile.get_parameter("nicknames")
          if(len(passwords) == len(nicknames)):
            #If we have the same amount of passwords specified as we have nicknames, we'll select the corresponding password to our nickname
            self.send("PRIVMSG", "NickServ", "", "IDENTIFY " + passwords[self.nickname_index])
          elif(len(passwords) == 0):
            #We have no passwords. We can't identify. This likely means we'll be renamed.
            pass
          else:
            #Otherwise, we'll send the first password listed.
            self.send("PRIVMSG", "NickServ", "", "IDENTIFY " + passwords[0])
           
          #Once we've identified, we'll make sure we have op status where appropriate
          try:
            if(self.configfile.get_parameter("autoop")[0] == "yes"):
              self.send("PRIVMSG", "ChanServ", "", "OP")
          except IndexError:
            #autoop hasn't been specified, so we won't op ourselves
            pass
        #Our password may be set incorrectly
        elif(message.data["message"] == "Password incorrect."):
          if(self.nickname_index < len(self.nicknames) - 1):
            #Try the next nickname in our config if we have any left
            self.nickname_index += 1
            self.nick(self.nicknames[self.nickname_index])
          else:
            #We'll just have to wait to be renamed. Inform the botops that our password is wrong
            for op in self.bot_ops:
              self.send("PRIVMSG", op, "", "My NickServ password for " + self.mynick + " is wrong and I am about to be renamed.")
        
        elif(message.data["message"].find("STATUS") == 0):
          temp_queue = []
          #This is a response to a request for nickserv ID status
          status = message.data["message"].split(" ")
          if(int(status[2]) > 1):
            #The user is registered
            self.registered_users[status[1]] = [True, round(time.time(), 0), status[2]]
            while(len(self.if_registered_send_queue) > 0):
              item = self.if_registered_send_queue.pop()
              if(item[0] == status[1]):
                if(item[1] != ""): #We won't send if we have no message type
                  self.send(item[1], item[2], item[3], item[4])
              else:
                temp_queue.append(item)
            self.if_registered_send_queue = temp_queue
            
            temp_queue = []
            while(len(self.if_registered_action_queue) > 0):
              item = self.if_registered_action_queue.pop()
              if(item[0] == status[1]):
                if(item[2] != ""): #We don't want to send if there is no action message
                  self.sendaction(item[1], item[2])
              else:
                temp_queue.append(item)
            self.if_registered_action_queue = temp_queue
            
            temp_queue = []
            while(len(self.if_registered_raw_queue) > 0):
              item = self.if_registered_raw_queue.pop()
              if(item[0] == status[1]):
                if(item[1] != ""): #We won't send if we have nothing to send
                  self.sendraw(item[1])
              else:
                temp_queue.append(item)
            self.if_registered_raw_queue = temp_queue
              
            temp_queue = []
            while(len(self.if_registered_exec_queue) > 0):
              item = self.if_registered_exec_queue.pop()
              if(item[0] == status[1]):
                if(item[1] == "add_temp_bot_op"):
                  self.add_temp_bot_op(item[2][0])
                elif(item[1] == "add_bot_op"):
                  self.add_bot_op(item[2][0])
                elif(item[1] == "reparse_config"):
                  self.reparse_config()
                elif(item[1] == "update_config"):
                  self.update_config(item[2][0], item[2][1])
                elif(item[1] == "set_logging_state"):
                  self.set_logging_state(item[2][0])
                elif(item[1] == "rem_temp_bot_op"):
                  self.rem_temp_bot_op(item[2][0])
                elif(item[1] == "rem_bot_op"):
                  self.rem_bot_op(item[2][0])
              else:
                temp_queue.append(item)
            self.if_registered_exec_queue = temp_queue
          else:
            self.registered_users[status[1]] = [False, round(time.time(), 0), status[2]]
            while(len(self.if_registered_send_queue) > 0):
              item = self.if_registered_send_queue.pop()
              if(item[0] == status[1]):
                if(item[5] != ""): #We won't send if we have no message type
                  self.send(item[5], item[6], item[7], item[8])
              else:
                temp_queue.append(item)
            self.if_registered_send_queue = temp_queue
            
            temp_queue = []
            while(len(self.if_registered_action_queue) > 0):
              item = self.if_registered_action_queue.pop()
              if(item[0] == status[1]):
                if(item[4] != ""): #We don't want to send if there is no action message
                  self.sendaction(item[3], item[4])
              else:
                temp_queue.append(item)
            self.if_registered_action_queue = temp_queue
            
            temp_queue = []
            while(len(self.if_registered_raw_queue) > 0):
              item = self.if_registered_raw_queue.pop()
              if(item[0] == status[1]):
                if(item[2] != ""): #We won't send if we have nothing to send
                  self.sendraw(item[2])
              else:
                temp_queue.append(item)
            self.if_registered_raw_queue = temp_queue
        
            temp_queue = []
            while(len(self.if_registered_exec_queue) > 0):
              item = self.if_registered_exec_queue.pop()
              if(item[0] == status[1]):
                #User not registered, so we won't execute the action.
                pass
              else:
                temp_queue.append(item)
            self.if_registered_exec_queue = temp_queue
        
      #If we receive a 'nickname in use' message that wasn't gained during the logon, revert what we think our nickname is
      elif(message.data["type"] == 433 and message.data["target"] == "#:SELF:#"):
        self.mynick = self.oldnick
        
      elif(message.data["type"] == "NICK" and message.data["nickname"] == self.mynick):
        #We've just been renamed- that's the only circumstances in which we'll receive this
        self.oldnick = self.mynick
        self.mynick = message.data["target"]
        
      #That's all the pre-processing done, add it to the messagequeue
      self.messagequeue.append(message)

  @print_timing
  def add_channel_member(self, channel, member):
    if(member.find("#:") == 0):
      #This is not a real user, don't add them
      return
      
    #If for some reason it doesn't exist let's add it rather than crashing
    if(channel not in self.channel_members):
      self.channel_members[channel] = [round(time.time(), 0)]
      #Now let's make sure its contents are accurate
      self.send("WHO", channel, "", "")
      
    #Let's make sure they don't have any status markers
    member = member.lstrip("~").lstrip("@").lstrip("%").lstrip("+")
    
    #Now we can add them, if they're not in there already
    if(member not in self.channel_members[channel]):
      self.channel_members[channel].append(member)
    
  def rem_channel_member(self, channel, member):
    if(member.find("#:") == 0):
      #This is not a real user, ignore them
      return
      
    #If for some reason it doesn't exist then we don't need to remove anything from it. Let's be efficient...
    if(channel not in self.channel_members):
      return
    
    #Let's make sure there are no status markers
    member = member.lstrip("~").lstrip("@").lstrip("%").lstrip("+")    
    
    #Now we can remove them if they're in there
    if(member in self.channel_members[channel]):
      self.channel_members[channel].remove(member)
      
  @print_timing
  def if_registered_send(self, user, registered, notregistered):
    if(len(registered) != 4 and len(notregistered) != 4):
      #We are to send nothing. Let's not do anything, because it all feels a bit futile.
      return
    else:
      if(len(registered) != 4):
        #Either a syntax error or nothing to send
        registered = ["", "", "", ""]
      if(len(notregistered) != 4):
        #Either a syntax error or nothing to send
        notregistered = ["", "", "", ""]
      
      item = [user]
      item.extend(registered)
      item.extend(notregistered)
      self.if_registered_send_queue.append(item)
      
      self.is_registered(user)
  
  @print_timing
  def if_registered_action(self, user, registered, notregistered):
    if(len(registered) != 2 and len(notregistered) != 2):
      #We are to send nothing. Let's not do anything, because it all feels a bit futile.
      return
    else:
      if(len(registered) != 2):
        #Either a syntax error or nothing to send
        registered = ["", ""]
      if(len(notregistered) != 2):
        #Either a syntax error or nothing to send
        notregistered = ["", ""]
      
      item = [user]
      item.extend(registered)
      item.extend(notregistered)
      self.if_registered_action_queue.append(item)
  
      self.is_registered(user)
  
  @print_timing
  def if_registered_raw(self, user, registered, notregistered):
    if(len(registered) != 1 and len(notregistered) != 1):
      #We are to send nothing. Let's not do anything, because it all feels a bit futile.
      return
    else:
      if(len(registered) != 1):
        #Either a syntax error or nothing to send
        registered = ["", ""]
      if(len(notregistered) != 1):
        #Either a syntax error or nothing to send
        notregistered = ["", ""]
      
      item = [user]
      item.extend(registered)
      item.extend(notregistered)
      self.if_registered_raw_queue.append(item)
      
      self.is_registered(user)
      
  @print_timing
  def if_registered_exec(self, user, method, arguments, registered_response, not_registered_response):
    if(method == ""):
      #If the user is registered do nothing? We can optimise this.
      return
    else:
      if(method == "add_temp_bot_op" or method == "rem_temp_bot_op"):
        if(len(arguments) != 1):
          #There should only be one argument for this command
          return
      elif(method == "add_bot_op" or method == "rem_bot_op"):
        if(len(arguments) != 1):
          #There should only be one argument for this command
          return
      elif(method == "reparse_config"):
        if(len(arguments) != 0):
          #There should be no arguments for this command
          return
      elif(method == "update_config"):
        if(len(arguments) != 2):
          #There should be two arguments for this command
          return
      elif(method == "set_logging_state"):
        if(len(arguments) != 1):
          #There should only be one argument for this command
          return
        elif(not isinstance(arguments[0], bool)):
          #This should be a boolean, we don't want to crash
          return
      else:
        #We're being asked to do something we can't do. Let's try our hardest...
        return
        #...oh dear. We failed.
        
    #If we got to here hen it's valid. Add it to the queue.
    self.if_registered_exec_queue.append([user, method, arguments])
    self.if_registered_send(user, registered_response, not_registered_response)
      
    self.is_registered(user)
      
  @print_timing
  def is_registered(self, user):
    try:
      if(time.time() - self.registered_users[user][1] > 0.1):
        self.send("PRIVMSG", "NickServ", "", "STATUS " + user)
        return None
      else:
        return self.registered_users[user][0]
    except:
      self.send("PRIVMSG", "NickServ", "", "STATUS " + user)
      return None
      
  @print_timing      
  def join(self, channel):
    #First, join the channel
    self.irc_connection.send("JOIN", channel, "", "")
    
    #Now, make sure we can keep track of who is in it (
    self.channel_members[channel] = []

  @print_timing    
  def part(self, channel, message):
    #We're leaving the channel. First remove our listing for it
    del self.channel_members[channel]
    
    #Now leave the channel
    self.irc_connection.send("PART", channel, "", message)
   
  def nick(self, newnick):
    #First, store the old nickname. If we receive a 433 we'll revert our 'mynick' setting to this.
    self.oldnick = self.mynick
    
    #Now let's send a nick update message and hope our new nickname holds
    self.irc_connection.send("NICK", newnick, "", "")
    self.mynick = newnick
   
  @print_timing    
  def send(self, messagetype, target, subtarget, message):
    if(messagetype == "JOIN"):
      self.join(target)
    elif(messagetype == "PART"):
      self.part(target, message)
    elif(messagetype == "NICK"):
      self.nick(target)
    else:
      self.irc_connection.send(messagetype, target, subtarget, message)
      
    if(messagetype == "QUIT"):
      self.quit_sent = True
      self.channel_members = {}

  @print_timing      
  def sendaction(self, target, message):
    self.irc_connection.sendaction(target, message)

  @print_timing    
  def sendraw(self, message):
    self.irc_connection.sendraw(message)

  @print_timing    
  def get_message(self):
    if(len(self.messagequeue) > 0):
      return self.messagequeue.pop()
    else:
      self.process_messages()
      if(len(self.messagequeue) > 0):
        return self.messagequeue.pop()
      else:
        return None
  
  @print_timing
  def set_logging_state(self, state):
    if(state):
      self.configfile.set_parameter("logging", ["yes"])
    else:
      self.configfile.set_parameter("logging", ["no"])
    
    #Make sure the new setting applies
    self.irc_connection.get_logging_state(self.configfile)
    
    self.configfile.save()
  

  @print_timing  
  def update_config(self, parameter, value):
    self.configfile.set_parameter(parameter, value)
    
    self.configfile.save()
    
    #In case the logging has been enabled or disabled
    self.irc_connection.get_logging_state(self.configfile)
    #In case the bot ops list has changed
    self.bot_ops = self.configfile.get_parameter("botops")
    
  @print_timing
  def reparse_config(self):
    #So that we don't mess up any temp ops, but do remove ones who have been removed manually from the config
    old_config_bot_ops = self.configfile.get_parameter("botops")
    
    self.configfile.reparse()
    
    #In case the logging has been enabled or disabled
    self.irc_connection.get_logging_state(self.configfile)
    #In case the bot ops list has changed, we'll make sure we add any new ones, while keeping the temp ones
    current_bot_ops = self.bot_ops
    new_bot_ops = self.configfile.get_parameter("botops")
    for op in current_bot_ops:
      if(op not in new_bot_ops):
        if(op in old_config_bot_ops):
          #This op was removed from the config. We'll leave them out
          pass
        else:
          #They're a temp bot op
          new_bot_ops.append(op)
    self.bot_ops = new_bot_ops
    
    self.nicknames = self.configfile.get_parameter("nicknames")
    try:
      self.nickname_index = self.nicknames.index(self.mynick)
    except ValueError:
      #We'll set it to this so that it can be used if a nickserv message regarding failure to authenticate is received
      self.nickname_index = 0
    
  @print_timing
  def add_temp_bot_op(self, nick):
    if(nick not in self.bot_ops):
      self.bot_ops.append(nick)

  @print_timing
  def rem_temp_bot_op(self, nick):
    try:
      self.bot_ops.remove(nick)
    except ValueError:
      #We can't remove what isn't there, but it was probably a typo so we won't crash
      pass
    
  @print_timing  
  def add_bot_op(self, nick):    
    #First we add the new op to the active ops list
    self.bot_ops.append(nick)
    
    #Then we want to make sure we don't disturb any temporary bot ops, or make them permanent.
    config_bot_ops = self.configfile.get_parameter("botops")
    
    if(nick not in config_bot_ops):
      config_bot_ops.append(nick)
    
      self.configfile.set_parameter("botops", config_bot_ops)
      self.configfile.save()
      
  @print_timing
  def rem_bot_op(self, nick):
    try:
      self.bot_ops.remove(nick)
    except ValueError:
      #Probably a typo, but let's not crash
      pass
    
    #Now we want to avoid making any temp bot ops permanent, while removing the one who has fallen from grace from the config
    current_bot_ops = self.configfile.get_parameter("botops")
    
    try:
      current_bot_ops.remove(nick)
      
      self.configfile.set_parameter("botops", current_bot_ops)
      self.configfile.save()
    except ValueError:
      #The typo returns
      pass
      
