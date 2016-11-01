#!/opt/bin/python
import os
import sys
import json
import urllib

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from readSettings import settingsProvider
from _utils import LoggingAdapter

cpconfig = settingsProvider().defaultSettings.CP
log = LoggingAdapter.getLogger()

def apiPostProcess():
	log.info("Triggering CouchPotato Renamer")
	api_url = getApiUrl() + "renamer.scan"
	refresh = json.load(urllib.urlopen(api_url))
	if refresh["success"]:
		log.debug("Renamer was triggered.")
		return True
	else:
		log.error("Something went wrong, output was:")
		log.error(json.dumps(refresh, indent=4))
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
		if 'MH_IMDBID' in os.environ:
			log.info("CouchPotato Post Processor started.")
			apiPostProcess()
			log.info("CouchPotato finished.")
		else:
			log.debug("CouchPotato: Not a movie.")
	else:
		log.info("CouchPotato: No processed files submitted.")
	
if __name__ == "__main__":
    main()
