#!/opt/bin/python
import os
import sys
import json
import urllib

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from readSettings import settingsProvider
from _utils import LoggingAdapter

srconfig = settingsProvider().defaultSettings.Sickrage
log = LoggingAdapter.getLogger()

def apiPostProcess():
	log.info("Triggering Sickrage Post Process")
	api_url = getApiUrl() + "cmd=postprocess&is_priority=1"
	refresh = json.load(urllib.urlopen(api_url))
	if resultToBool(refresh["result"]):
		log.debug("Post Process was initiated.")
		return True
	else:
		log.error("Something went wrong, output was:")
		log.error(json.dumps(refresh, indent=4))
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
		if 'MH_TVDBID' in os.environ:
			log.info("Sickrage Post Processor started.")
			apiPostProcess()
			log.info("Sickrage finished.")
		else:
			log.debug("Sickrage: Not a TV show.")
	else:
		log.info("Sickrage: No processed files submitted.")

if __name__ == "__main__":
    main()
