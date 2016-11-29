#!/usr/bin/env python
import os
import sys
import json
import locale
import signal
from subprocess import Popen, PIPE

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from readSettings import settingsProvider
from _utils import LoggingAdapter

console_encoding = locale.getdefaultlocale()[1] or 'UTF-8'
log = LoggingAdapter.getLogger()

def probe(ffprobe, filename):
	cmds = [ffprobe, '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', filename]
	
	p = Popen(cmds, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=(os.name != 'nt'), startupinfo=None)
	stdout_data, _ = p.communicate()
	stdout_data = stdout_data.decode(console_encoding, errors='ignore')
	
	data = json.loads(stdout_data)
	return data

def main():
	if 'MH_FILES' in os.environ:
		log.info("FFprobe dump of processed files")
		
		settings = settingsProvider(config_file=os.environ.get('MH_CONFIG')).defaultSettings
		
		files = json.loads(os.environ.get('MH_FILES'))
		for filename in files:
			log.debug("Information for %s" % filename)
			
			info = probe(settings.ffprobe, filename)
			if info is not None:
				if 'streams' in info and 'format' in info:
					log.debug(json.dumps(info, indent=4, sort_keys=True))
				else:
					log.warning("WARNING - No valid video metadata found in file. This is UNUSUAL!")
			else:
				log.error("File appears invalid.")
		log.info("FFprobe finished.")
	else:
		log.info("FFprobe: No processed files submitted.")

if __name__ == "__main__":
    main()
