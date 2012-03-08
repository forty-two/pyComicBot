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
        while not currentlyFits and fontSize > 5:
            font = ImageFont.truetype('MONACO.TTF', fontSize)
            # things will mess up here if you don't use a monospaced font
            charSize = draw.textsize('a', font=font)
            maxLen = x/charSize[0]
            lines = textwrap.wrap(text, maxLen)
            if len(lines)*charSize[1] < y:
                currentlyFits = True
                for i in range(len(lines)):
                    draw.text((0, i*charSize[1]+1*i), lines[i], font=font, fill="#000000")
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
                print previousLines
                print previousLines[i]
                bubbleText = self.drawText(previousLines[i], xSize, ySize)
                if not bubbleText:
                    return False
                comic.paste(bubbleText, tuple(comicData['bubbles'][i]['position']))
            font = ImageFont.truetype('MONACO.TTF', 10)
            draw = ImageDraw.Draw(comic)
            draw.text(tuple(comicData['datestampPos']), time.ctime(), font=font, fill="#000000")

            comicName = 'comic-%i.png' % int(time.time())

            comic.save(os.path.join(self.outputDirectory, comicName))

            return comicName
        except:
            return None


class inputThread(threading.Thread):
    def __init__(self, parent):
        self.parent = parent
        threading.Thread.__init__(self)
    def run(self):
        self.running = True
        while self.running:
            message = raw_input().strip()
            if message == "quit":
                print("Exiting")
                self.parent.exit()
                sys.exit()

            if re.search(r"(?<=^join )#\w+", message):
                print("Joining channel %s" % message.split(" ")[1])
                self.parent.server.join(message.split(" ")[1])

            if re.search(r"(?<=^part )#\w+", message):
                print("Parting from channel %s" % message.split(" ")[1])
                self.parent.server.part(message.split(' ')[1], "Leaving on command")


class IRCclient():

    def __init__(self, server, nick, password, channels, comicMaker, triggers, comicPrefix):
        self.serverAddress = server
        self.comicMaker = comicMaker
        self.triggers = triggers
        self.nick = nick
        self.password = password
        self.channels = channels
        self.lastMessageTime = time.time()
        self.lastMessage = ""
        self.messageTracker = {}
        self.linesSinceComic = 0
        self.comicPrefix = comicPrefix


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
            self.checkMessage(channel, message)

    def checkMessage(self, channel, message):
        self.messageTracker[channel].append(message)
        self.linesSinceComic += 1
        try:
            for trigger in self.triggers:
                if trigger in message and self.linesSinceComic > 3:
                    comicName = self.comicMaker.makeComic(self.messageTracker[channel][:-1])
                    self.linesSinceComic = 0
                    if comicName:
                        self.sendMessage(channel, "New comic: "+self.comicPrefix+comicName)
        except UnicodeDecodeError:
            self.checkMessage(channel, message.decode('utf-8'))






    def connect(self):

        irc = irclib.IRC()

        irc.add_global_handler('privnotice', self.handlePrivNotice)
        irc.add_global_handler('pubmsg', self.handlePubMsg)

        self.server = irc.server()
        self.server.connect(self.serverAddress, 6667, self.nick, ircname=self.nick)

        self.consoleInput = inputThread(self)
        self.consoleInput.start()

        irc.process_forever()

    def exit(self):
        self.consoleInput.running = False
        self.consoleInput._Thread__stop()
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
    triggers = config['triggers']
    comicPrefix = config['IRCsettings']['imagePrefix']

    comicMaker = ComicMaker(config['templateDirectory'], config['outputDirectory'])

    irc = IRCclient(server, nick, password, channels, comicMaker, triggers, comicPrefix)
    irc.connect()


if __name__ == '__main__':
    main()