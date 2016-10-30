#!/opt/bin/python
import os
import sys
import json
import urllib

from pprint import pprint

sys.path.append("/opt/share/sickbeard_mp4_automator")
from readSettings import settingsProvider

srconfig = settingsProvider().defaultSettings.Sickrage

def apiPostProcess():
	print("Triggering Sickrage Post Process")
	api_url = getApiUrl() + "cmd=postprocess"
	refresh = json.load(urllib.urlopen(api_url))
	print("  %s - %s" % (refresh["message"], refresh["result"]))
	if resultToBool(refresh["result"]):
		print "Post Process was initiated."
		return True
	else:
		print "Something went wrong, check output."
	return False

def getApiUrl():
	protocol = "http://"  # SSL
	try:
		if srconfig["ssl"]:
			protocol = "https://"
	except:
		pass
	host = srconfig["host"]
	port = srconfig["port"]
	api_key = srconfig["api_key"]
	web_root = srconfig["web_root"]
	api_url = protocol + host + ":" + port + web_root + "/api/" + api_key + "/?"
	return api_url

def resultToBool(result):
	if result == "success":
		return True
	return False

def main():
	print("Sickrage Post Processor started")
	
	apiPostProcess()
	print("Finished")

if __name__ == "__main__":
    main()
