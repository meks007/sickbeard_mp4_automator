#!/opt/bin/python
import os
import sys
import json
import locale
import signal
from subprocess import Popen, PIPE
from pprint import pprint

sys.path.append("/opt/share/sickbeard_mp4_automator")
from readSettings import settingsProvider

console_encoding = locale.getdefaultlocale()[1] or 'UTF-8'

def probe(ffprobe, filename):
	cmds = [ffprobe, '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', filename]
	
	p = Popen(cmds, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=(os.name != 'nt'), startupinfo=None)
	stdout_data, _ = p.communicate()
	stdout_data = stdout_data.decode(console_encoding, errors='ignore')
	
	data = json.loads(stdout_data)
	return data

def main():
	print("ffprobe dump of processed files")
	print
	
	settings = settingsProvider().defaultSettings
	
	files = json.loads(os.environ.get('MH_FILES'))
	for filename in files:
		print("Information for %s" % filename)
		
		info = probe(settings.ffprobe, filename)
		if info is not None:
			if 'streams' in info and 'format' in info:
				print(json.dumps(info, indent=4, sort_keys=True))
			else:
				print("WARNING - No valid video metadata found in file. This is UNUSUAL!")
		else:
			print("File appears invalid.")
		
		print

if __name__ == "__main__":
    main()
