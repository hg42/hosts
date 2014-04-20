#!/usr/bin/env python

# Script by Ben Limmer
# https://github.com/l1m5
#
# This simple Python script will combine all the host files you provide
# as sources into one, unique host file to keep you internet browsing happy.

import os
import platform
import re
import string
import subprocess
import sys
import tempfile
import urllib2

# Project Settings
BASEDIR_PATH = os.path.dirname(os.path.realpath(__file__))
DATA_PATH = BASEDIR_PATH + '/data'
DATA_FILENAMES = 'hosts'
UPDATE_URL_FILENAME = 'update.info'
SOURCES = os.listdir(DATA_PATH)
README_TEMPLATE = BASEDIR_PATH + '/readme_template.md'
README_FILE = BASEDIR_PATH + '/readme.md'

# Exclusions
EXCLUSION_PATTERN = '([a-zA-Z\d-]+\.){0,}' #append domain the end

# Common domains to exclude
COMMON_EXCLUSIONS = ['hulu.com']

# Global vars
exclusionRegexs = []
numberOfRules = 0

def main():
  updateAllSources()
  gatherExclusions()
  mergeFile = createInitialFile()
  finalFile = removeDups(mergeFile)
  finalizeFile(finalFile)
  updateReadme(numberOfRules)
  printSuccess('hosts file contains ' + str(numberOfRules) + ' unique entries.')
  moveHostsFileIntoPlace(finalFile)

def promptForExclusions():
  response = query_yes_no("Do you want to exclude any domains?\n" +
              "For example, hulu.com video streaming must be able to access " +
              "its tracking and ad servers in order to play video.")
  if (response == "yes"):
    displayExclusionOptions()
  else:
    print 'OK, we won\'t exclude any domains.'


# Exclusion logic

def gatherExclusions():
  with open("exclude.lst") as file:
    for line in file.readlines():
      print "exclude", line
      excludeDomain(line)

def excludeDomain(domain):
  exclusionRegexs.append(re.compile(EXCLUSION_PATTERN + domain))

def matchesExclusions(strippedRule):
  strippedDomain = strippedRule.split()[1]
  for exclusionRegex in exclusionRegexs:
    if exclusionRegex.search(strippedDomain):
      return True
  return False
# End Exclusion Logic

# Update Logic
def updateAllSources():
  for source in SOURCES:
    updateURL = getUpdateURLFromFile(source)
    if (updateURL == None):
      continue;
    print 'Updating source ' + source + ' from ' + updateURL
    updatedFile = urllib2.urlopen(updateURL)
    updatedFile = updatedFile.read()
    updatedFile = string.replace( updatedFile, '\r', '' ) #get rid of carriage-return symbols

    dataFile   = open(DATA_PATH + '/' + source + '/' + DATA_FILENAMES, 'w')
    dataFile.write(updatedFile)
    dataFile.close()

def getUpdateURLFromFile(source):
  pathToUpdateFile = DATA_PATH + '/' + source + '/' + UPDATE_URL_FILENAME
  if os.path.exists(pathToUpdateFile):
    updateFile = open(pathToUpdateFile, 'r')
    retURL = updateFile.readline().strip()
    updateFile.close()
  else:
    retURL = None
    printFailure('Warning: Can\'t find the update file for source ' + source + '\n' +
           'Make sure that there\'s a file at ' + pathToUpdateFile)
  return retURL
# End Update Logic

# File Logic
def createInitialFile():
  mergeFile = tempfile.NamedTemporaryFile()
  for source in SOURCES:
    curFile = open(DATA_PATH + '/' + source +'/' + DATA_FILENAMES, 'r')
    mergeFile.write('\n# Begin ' + source + '\n')
    mergeFile.write(curFile.read())
    mergeFile.write('\n# End ' + source + '\n')
  return mergeFile

def removeDups(mergeFile):
  global numberOfRules

  finalFile = open(BASEDIR_PATH + '/hosts', 'w+b')
  mergeFile.seek(0) # reset file pointer

  rules_seen = set()
  for line in mergeFile.readlines():
    if line[0].startswith("#") or line[0] == '\n':
      finalFile.write(line) #maintain the comments for readability
      continue
    strippedRule = stripRule(line) #strip comments
    if matchesExclusions(strippedRule):
      continue
    if strippedRule not in rules_seen:
      finalFile.write(line)
      rules_seen.add(strippedRule)
      numberOfRules += 1

  mergeFile.close()

  return finalFile

def finalizeFile(finalFile):
  writeOpeningHeader(finalFile)
  finalFile.close()

# Some sources put comments around their rules, for accuracy we need to strip them
# the comments are preserved in the output hosts file
def stripRule(line):
  splitLine = line.split()
  if (len(splitLine) < 2) :
    printFailure('A line in the hostfile is going to cause problems because it is nonstandard\n' +
           'The line reads ' + line + ' please check your data files. Maybe you have a comment without a #?')
    sys.exit()
  return splitLine[0] + ' ' + splitLine[1]

def writeOpeningHeader(finalFile):
  global numberOfRules
  finalFile.seek(0) #reset file pointer
  fileContents = finalFile.read(); #save content
  finalFile.seek(0) #write at the top
  finalFile.write('# This file is a merged collection of hosts from reputable sources,\n')
  finalFile.write('# with a dash of crowd sourcing via Github\n#\n')
  finalFile.write('# Project home page: https://github.com/StevenBlack/hosts\n#\n')
  finalFile.write('# Current sources:\n')
  for source in SOURCES:
    finalFile.write('#    ' + source + '\n')
  finalFile.write('#\n')
  finalFile.write('# Merging these sources produced ' + str(numberOfRules) + ' unique entries\n')
  finalFile.write('# ===============================================================\n')
  finalFile.write(fileContents)

def updateReadme(numberOfRules):
  with open(README_FILE, "wt") as out:
    for line in open(README_TEMPLATE):
      out.write(line.replace('@NUM_ENTRIES@', str(numberOfRules)))

def moveHostsFileIntoPlace(finalFile):
  if (os.name == 'posix'):
    print 'Moving the file requires administrative privileges. You might need to enter your password.'
    if(subprocess.call(["/usr/bin/sudo", "cp", os.path.abspath(finalFile.name), "/etc/hosts"])):
      printFailure("Moving the file failed.")
    print 'Flushing the DNS Cache to utilize new hosts file...'
    if (platform.system() == 'Darwin'):
      if(subprocess.call(["/usr/bin/sudo", "killall", "-HUP", "mDNSResponder"])):
        printFailure("Flushing the DNS Cache failed.")
    else:
      if(subprocess.call(["/usr/bin/sudo", "/etc/rc.d/init.d/nscd", "restart"])):
        printFailure("Flushing the DNS Cache failed.")
  elif (os.name == 'nt'):
    etchosts = os.environ["SystemRoot"] + r"\system32\drivers\etc\hosts"
    if(subprocess.call(["cmd.exe", "/c", "copy", os.path.abspath(finalFile.name), etchosts])):
      printFailure("Moving the file failed.")
    else:
      subprocess.call(["cmd.exe", "/c", "dir", etchosts])
      printSuccess("host file moved to " + etchosts)

# End File Logic

# Helper Functions

def isValidDomainFormat(domain):
  if (domain == ''):
    print "You didn\'t enter a domain. Try again."
    return False
  domainRegex = re.compile("www\d{0,3}[.]|https?")
  if (domainRegex.match(domain)):
    print "The domain " + domain + " is not valid. Do not include www.domain.com or http(s)://domain.com. Try again."
    return False
  else:
    return True

# Colors
class colors:
    if 0:
      PROMPT 	= '\033[94m'
      SUCCESS = '\033[92m'
      FAIL 	= '\033[91m'
      ENDC 	= '\033[0m'
    else:
      PROMPT 	= ''
      SUCCESS = ''
      FAIL 	= ''
      ENDC 	= ''

def colorize(text, color):
  return color + text + colors.ENDC

def printSuccess(text):
  print colorize(text, colors.SUCCESS)

def printFailure(text):
  print colorize(text, colors.FAIL)
# End Helper Functions

if __name__ == "__main__":
  main()
