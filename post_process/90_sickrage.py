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
	if resultToBool(refresh["result"]):
		print "Post Process was initiated."
		return True
	else:
		print "Something went wrong, output was:"
		print(json.dumps(refresh, indent=4))
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
	if 'MH_FILES' in os.environ:
		if 'TVDBID' in os.environ:
			print("Sickrage Post Processor started.")
			apiPostProcess()
			print("Sickrage finished.")
		else:
			print("Sickrage: Not a TV show.")
	else:
		print("Sickrage: No processed files submitted.")

if __name__ == "__main__":
    main()
