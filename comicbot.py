#! /usr/bin/python

from PIL import Image, ImageDraw, ImageFont

import textwrap
import os
import random
import json
import time
import threading
import irclib
import sys
import re

irclib.DEBUG = True


class ComicMaker():

    def __init__(self, templateDirectory, outputDirectory):
        self.templateDirectory = templateDirectory
        self.outputDirectory = outputDirectory


    def drawText(self, text, x, y):
        image = Image.new("RGB", (x,y), "#FFFFFF")
        draw = ImageDraw.Draw(image)
        numLines = 1
        fontSize = 40
        currentlyFits = False
        while not currentlyFits and fontSize > 3:
            font = ImageFont.truetype('MONACO.TTF', fontSize)
            # things will mess up here if you don't use a monospaced font
            charSize = draw.textsize('a', font=font)
            maxLen = x/charSize[0]
            lines = textwrap.wrap(text, maxLen)
            if len(lines)*charSize[1] < y:
                currentlyFits = True
                for i in range(len(lines)):
                    draw.text((0, i*charSize[1]+0.5*i), lines[i], font=font, fill="#000000")
                return image
            else:
                fontSize -= 1
        return False

    def makeComic(self, previousLines):
        try:
            path, dirs, files = os.walk(self.templateDirectory).next()
            comicChoices = [x for x in files if x.endswith('.json')]
            comicDataFile = open(os.path.join(self.templateDirectory, comicChoices[random.randint(0, len(comicChoices)-1)]))
            comicData = json.load(comicDataFile)
            comic = Image.open(os.path.join(self.templateDirectory, comicData['backgroundImage']))
            previousLines = previousLines[-len(comicData['bubbles']):]
            for i in range(len(comicData['bubbles'])):
                xSize, ySize = comicData['bubbles'][i]['size']
                bubbleText = self.drawText(previousLines[i], xSize, ySize)
                if not bubbleText:
                    print("Tried to make comic, text placing failed")
                    return None
                comic.paste(bubbleText, tuple(comicData['bubbles'][i]['position']))
            font = ImageFont.truetype('MONACO.TTF', 10)
            draw = ImageDraw.Draw(comic)
            draw.text(tuple(comicData['datestampPos']), time.ctime(), font=font, fill="#000000")

            comicName = 'comic-%i.png' % int(time.time())

            comic.save(os.path.join(self.outputDirectory, comicName))

            return comicName
        except Exception as e:
            print("Exception occurred: {exception}".format(exception=e))
            return None


class inputThread(threading.Thread):
    def __init__(self, exitCallback):
        self.exitCallback = exitCallback
        threading.Thread.__init__(self)
    def run(self):
        self.contineRunning = True
        while self.contineRunning:
            message = raw_input().strip()
            if message == "quit":
                print("Exiting")
                self.exitCallback()
                self.contineRunning = False
                sys.exit()

            if re.search(r"(?<=^join )#\w+", message):
                print("Joining channel %s" % message.split(" ")[1])
                self.parent.server.join(message.split(" ")[1])

            if re.search(r"(?<=^part )#\w+", message):
                print("Parting from channel %s" % message.split(" ")[1])
                self.parent.server.part(message.split(' ')[1], "Leaving on command")


class IRCclient():

    def __init__(self, server, nick, password, channels, comicMaker, triggers, comicPrefix, timeDelay):
        self.serverAddress = server
        self.comicMaker = comicMaker
        self.triggers = triggers
        self.nick = nick
        self.password = password
        self.channels = channels
        self.lastMessageTime = time.time()
        self.lastMessage = ""
        self.lastComicTime = 0
        self.messageTracker = {}
        self.linesSinceComic = 0
        self.comicPrefix = comicPrefix
        self.timeDelay = timeDelay
        self.contineRunning = True


    def authenticate(self, ircClient, username, password):
        ircClient.privmsg("AuthServ@Services.GameSurge.net", "AUTH %s %s" % (username, password))

    def joinChannels(self, channelList):
        for channel in channelList:
            self.server.join(channel)
            self.messageTracker[channel] = []

    def sendMessage(self, recipient, message):
        while time.time() - self.lastMessageTime < 2:
            time.sleep(0.5)
        if message != self.lastMessage:
            self.server.privmsg(recipient, message)
            self.lastMessage = message
        else:
            self.server.privmsg(recipient, "Please don't repeat the last request; BTW the current time is: %s"
                               % (time.ctime()))
        self.lastMessageTime = time.time()


    def handlePrivNotice(self, connection, event):
            # Login stuff is here because gamesurge chucks a fit if you try and do
            # anything before the motd finishes coming through.

            if "END OF MESSAGE(S) OF THE DAY" in event.arguments()[0]:
            #    self.authenticate(connection, self.nick, self.password)
            #    print "\nTrying to authenticate\n"
            #
            #if "I recognize you" in event.arguments()[0]:
                self.joinChannels(self.channels)

    def handlePubMsg(self, connection ,event):
        message = event.arguments()[0]
        firstWord = message.split(' ', 1)[0]
        sendingNick = event.source().split('!')[0]
        sendingHostmask = event.source().split("@")[1].strip()
        channel = event.target().strip()

        if firstWord.lower() == ".quit":
            if sendingNick == "forty_two":
                if sendingHostmask == "no.dolphins.here.forty-two.nu" or \
                    sendingHostmask == "forty_two.staff.reddit-minecraft":
                        sys.exit()
        else:
            self.checkMessage(channel, message, sendingNick)

    def checkMessage(self, channel, message, sendingNick):
        self.messageTracker[channel].append(message)
        self.linesSinceComic += 1
        if sendingNick == "ChanServ":
            return
        try:
            message = message.decode('utf-8', 'ignore')
            for trigger in self.triggers:
                if self.linesSinceComic > 10:
                    if time.time() - self.lastComicTime > self.timeDelay:
                        if trigger['separate'].search(message):
                            comicName = self.comicMaker.makeComic(self.messageTracker[channel][:-1])
                            self.linesSinceComic = 0
                            if comicName:
                                self.sendMessage(channel, "New comic: "+self.comicPrefix+comicName)
                                self.lastComicTime = time.time()
                        elif trigger['inLine'].search(message):
                            self.messageTracker[channel].append(message)
                            comicName = self.comicMaker.makeComic(self.messageTracker[channel][:-1])
                            self.linesSinceComic = 0
                            if comicName:
                                self.sendMessage(channel, "New comic: "+self.comicPrefix+comicName)
                                self.lastComicTime = time.time()

            if len(self.messageTracker[channel]) > 51:
                self.messageTracker[channel] = self.messageTracker[channel][-50:]
        except:
            ignore = "IRC's unicode handling"

    def handleCTCP(self, connection, event):
        type = event.arguments()[0]
        sendingNick = event.source().split('!')[0]
        channel = event.target().strip()
        if type == "ACTION":
            message = "*%s %s" % (sendingNick, event.arguments()[1])
            self.checkMessage(channel, message)

        if type == "VERSION":
            self.server.notice(sendingNick, "pyComicBot 0.1")


    def connect(self):

        irc = irclib.IRC()

        irc.add_global_handler('privnotice', self.handlePrivNotice)
        irc.add_global_handler('pubmsg', self.handlePubMsg)
        irc.add_global_handler('ctcp', self.handleCTCP)

        self.server = irc.server()
        self.server.connect(self.serverAddress, 6667, self.nick, ircname=self.nick)

        self.consoleInput = inputThread(self.exit)
        self.consoleInput.start()

        while self.contineRunning:
            irc.process_once(0.2)

    def exit(self):
        self.consoleInput.contineRunning = False
        self.contineRunning = False
        sys.exit()


def loadConfig(filename):
    defaultConfig = {
                     'IRCsettings': {'active'  : True,
                                     'nick'    : 'ComicBot',
                                     'password': 'swordfish',
                                     'server'  : 'irc.gamesurge.net',
                                     'port'    : 6667,
                                     'channels': ['#ComicBot'],
                                     'imagePrefix' : 'http://example.com/comicbot/'
                                    },
                     'triggers'   : ['lol', 'haha', 'hehe', 'rofl'],
                     'templateDirectory' : 'templates',
                     'outputDirectory' : 'comics',
                     'triggerTimePeriod': 3600,
                    }
    if os.path.isfile(filename):
        return json.load(open(filename))
    else:
        f = open(filename, 'w')
        f.write(json.dumps(defaultConfig, indent = 4))
        f.close()
        return defaultConfig

def main():
    config = loadConfig('comicbotConfig.json')
    server = config['IRCsettings']['server']
    nick = config['IRCsettings']['nick']
    password = config['IRCsettings']['password']
    channels = config['IRCsettings']['channels']
    triggers = [{'inLine'  : re.compile('(^| )'+x+'[\!\?]* | '+x+'[\!\?]*$', re.I),
                 'separate': re.compile('^'+x+'[\!\?]*$', re.I)} for x in config['triggers']]

    comicPrefix = config['IRCsettings']['imagePrefix']

    timeDelay = config['triggerTimePeriod']

    comicMaker = ComicMaker(config['templateDirectory'], config['outputDirectory'])

    irc = IRCclient(server, nick, password, channels, comicMaker, triggers, comicPrefix, timeDelay)
    irc.connect()


if __name__ == '__main__':
    main()