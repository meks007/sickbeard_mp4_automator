import os
import logging
import json
from _utils import LoggingAdapter
from subprocess import Popen, PIPE
from threading import Timer
from extensions import bad_post_files, bad_post_extensions

class PostProcessor:
    def __init__(self, files, logger=None):
        # Setup Logging
        if logger:
            self.log = logger
        else:
            self.log = LoggingAdapter.getLogger(__name__)

        self.log.debug("Output: %s" % files)

        self.set_script_environment(files)
        self.scripts = self.gather_scripts()

    def set_script_environment(self, files):
        self.log.debug("Setting script environment")
        self.post_process_environment = os.environ.copy()
        self.post_process_environment['MH_FILES'] = json.dumps(files)

    def gather_scripts(self):
        self.log.debug("Gathering scripts")
        current_directory = os.path.dirname(os.path.realpath(__file__))
        post_process_directory = os.path.join(current_directory, 'post_process')
        scripts = []
        for script in os.listdir(post_process_directory):
            if os.path.splitext(script)[1] in bad_post_extensions or os.path.isdir(script) or script in bad_post_files:
                self.log.debug("Skipping %s" % script)
                continue
            else:
                self.log.debug("Script added: %s" % script)
                scripts.append(os.path.join(post_process_directory, script))
        return scripts

    def setTV(self, tvdbid, season, episode):
        self.log.debug("Setting TV metadata")
        self.post_process_environment['MH_TAGGED'] = str(1)
        self.post_process_environment['MH_TVDBID'] = str(tvdbid)
        self.post_process_environment['MH_SEASON'] = str(season)
        self.post_process_environment['MH_EPISODE'] = str(episode)

    def setMovie(self, imdbid):
        self.log.debug("Setting movie metadata")
        self.post_process_environment['MH_TAGGED'] = str(1)
        self.post_process_environment['MH_IMDBID'] = str(imdbid)

    def kill_proc(self, proc, timeout):
        timeout["value"] = True
        proc.kill()

    def do_run(self, cmd, timeout_sec):
        #proc = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc = self.run_script_command(cmd)
        timeout = {"value": False}
        timer = Timer(timeout_sec, self.kill_proc, [proc, timeout])
        timer.start()
        stdout, stderr = proc.communicate()
        timer.cancel()
        return proc.returncode, stdout.decode("utf-8"), stderr.decode("utf-8"), timeout["value"]

    def run_scripts(self):
        self.log.info(">>> Post processing ...")
        for script in self.scripts:
            try:
                #command = self.run_script_command(script)
                self.log.info("Running script '%s'" % (script))
                returncode, stdout, stderr, timeout = self.do_run(script, 60)
                #stdout, stderr = command.communicate()
                #if stdout: 
                #    self.log.debug("Stdout: %s" % stdout)
                if stderr:
                    self.log.debug("Stderr: %s" % stderr)
            except Exception as e:
                self.log.exception("Failed to execute script %s" % script)

    def run_script_command(self, script):
        return Popen([str(script)], shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=self.post_process_environment,
                     close_fds=(os.name != 'nt'))
