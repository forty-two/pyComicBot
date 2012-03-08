#! /usr/bin/python


import sys
import re
import json
import os


BACKGROUND_REGEX = re.compile(r'^background = (?P<filename>.+)')
DATESTAMP_REGEX = re.compile(r'^datestamp = (?P<x>\d+),(?P<y>\d+)')
BUBBLE_REGEX = re.compile(r'^bubble(?P<bubbleNum>\d+) = (?P<xPos>\d+),(?P<yPos>\d+),(?P<xSize>\d+),(?P<ySize>\d+)')


def processFile(filename):
    comicData = {}
    comicData['bubbles'] = []
    f = open(filename)
    for line in f:
        if BACKGROUND_REGEX.match(line):
            comicData['backgroundImage'] = BACKGROUND_REGEX.match(line).group('filename').strip()

        if DATESTAMP_REGEX.match(line):
            m = DATESTAMP_REGEX.match(line)
            comicData['datestampPos'] = (int(m.group('x')), int(m.group('y'))-10)

        if BUBBLE_REGEX.match(line):
            m = BUBBLE_REGEX.match(line)
            comicData['bubbles'].append({'position' : (int(m.group('xPos')), int(m.group('yPos'))),
                                                 'size'     : (int(m.group('xSize')), int(m.group('ySize')))
                                                })
    dir, name = os.path.split(filename)
    name = name.split('.')[0]
    output = open(os.path.join(dir, name+'.json'), 'w')
    output.write(json.dumps(comicData, indent = 4))
    output.close()



if len(sys.argv) != 2:
    print "please give a config file name"
    sys.exit()

if os.path.isdir(sys.argv[1]):
    path, dirs, files = os.walk(sys.argv[1]).next()
    files = [x for x in files if x.endswith('.ini')]
    for file in files:
        processFile(os.path.join(path, file))

elif os.path.isfile(sys.argv[1]):
    processFile(sys.argv[1])
