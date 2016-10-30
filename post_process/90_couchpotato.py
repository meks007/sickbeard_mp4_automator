#!/opt/bin/python
import os
import sys
import json
import urllib

from pprint import pprint

sys.path.append("/opt/share/sickbeard_mp4_automator")
from readSettings import settingsProvider

cpconfig = settingsProvider().defaultSettings.CP

def apiPostProcess():
	print("Triggering CouchPotato Renamer")
	api_url = getApiUrl() + "renamer.scan"
	refresh = json.load(urllib.urlopen(api_url))
	if refresh["success"]:
		print "Renamer was triggered."
		return True
	else:
		print "Something went wrong, output was:"
		print(json.dumps(refresh, indent=4))
	return False

def getApiUrl():
	protocol = "http://"  # SSL
	try:
		if cpconfig["ssl"]:
			protocol = "https://"
	except:
		pass
	host = cpconfig["host"]
	port = cpconfig["port"]
	api_key = cpconfig["apikey"]
	web_root = cpconfig["web_root"]
	api_url = protocol + host + ":" + port + web_root + "/api/" + api_key + "/"
	return api_url

def main():
	if 'MH_FILES' in os.environ:
		if 'IMDBID' in os.environ:
			print("CouchPotato Post Processor started.")
			apiPostProcess()
			print("CouchPotato finished.")
		else:
			print("CouchPotato: Not a movie.")
	else:
		print("CouchPotato: No processed files submitted.")
	
if __name__ == "__main__":
    main()
