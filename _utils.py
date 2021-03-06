import logging
import traceback
import os
import sys
import time
import datetime

import string
import unicodedata
import Levenshtein

from mutagen.mp4 import MP4

from logging.config import fileConfig
fileConfig(os.path.join(os.path.dirname(__file__), 'logging.ini'), defaults={'logfilename': os.path.join(os.path.dirname(__file__), 'info.log').replace("\\", "/")})

log = logging.getLogger(__name__)

def filename_clean(filename, real_clean=False):
    if real_clean:
        validFilenameChars = "%s%s" % (string.ascii_letters, string.digits)
    else:
        validFilenameChars = "%s%s" % (string.ascii_letters, string.digits)
    filename_unicode = unicode(filename)
    filename_normalized = unicodedata.normalize('NFKD', filename_unicode).encode('ASCII', 'ignore')
    filename_clean = ''.join(c for c in filename_normalized if c in validFilenameChars)
    return filename_clean

def levenshtein_distance(compare_base, compare_to):
    return Levenshtein.distance(str(compare_base), str(compare_to))
    
def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False
    
class executionLocker():
    def __init__(self):
        self.lockfile = os.path.join(os.path.dirname(__file__), 'run.lock')
        
    def lock(self):
        try:
            log.debug("--- LOCK FILE CREATED ---")
            with open(self.lockfile, 'a'):
                os.utime(self.lockfile, None)
            return True
        except:
            log.debug("!!! FAILED TO ACQUIRE LOCK !!!")
        return False
    
    def renew(self):
        try:
            os.utime(self.lockfile, None)
            return True
        except:
            log.warning("!!! FAILED TO RENEW LOCK !!!")
            return False
    
    def unlock(self):
        try:
            log.debug("--- LOCK FILE REMOVED ---")
            os.remove(self.lockfile)
            return True
        except:
            log.debug("!!! FAILED TO RELEASE LOCK !!!")
        return False
    
    def islocked(self):
        try:
            try:
                lockmt = os.path.getmtime(self.lockfile)
            except OSError as e:
                if e.errno == 2:
                    return False
                else:
                    raise(e)
            lockexp = lockmt + ( 360 * 60 )
            log.info("Found valid lock: %s, expires: %s" % (datetime.datetime.fromtimestamp(lockmt).strftime('%Y-%m-%d %H:%M:%S'), datetime.datetime.fromtimestamp(lockexp).strftime('%Y-%m-%d %H:%M:%S')))
            if lockexp < time.time():
                log.debug("!!! RELEASING DEADLOCK !!!")
                self.unlock()
                return False
            else:
                return True
        except:
            log.exception("!!! FAILED CHECKING FOR LOCK !!!")
            return True
                
class LoggingAdapter(logging.LoggerAdapter):
    @staticmethod
    def indent():
        indents = []
        st = traceback.extract_stack()
        for s in st:
            cmd = s[3][:3]
            if not (cmd == 'if ' or cmd == 'if('):
                indents.append(s)
        indentation_level = len(indents)
        return indentation_level-4  # Remove logging infrastructure frames

    def process(self, msg, kwargs):
        return msg, kwargs
    
    def debugI(self, msg, *args, **kwargs):
        msg, kwargs = self.process(msg, kwargs)
        indents = self.indent()
        msg = '({j}) {i}{m}'.format(j=str.format("%2s" % indents),i='    '*indents, m=msg)
        self.logger.debug(msg, *args, **kwargs)
        
    def debugTrace(self, msg, *args, **kwargs):
        self.debug("-- STACK TRACE DUMP FOLLOWS -- %s" % msg, *args, **kwargs)
        st = traceback.extract_stack()
        for s in st:
            self.logger.debug(s, *args, **kwargs)
    
    @staticmethod
    def getLogger(name=None, kwargs={}):
        if name is None:
            try:
                name = (os.path.split(traceback.extract_stack()[-2][0])[1]).split('.')[0]
            except:
                name = "FIX_MY_NAME"
        log.debug("*** Creating LoggingAdapter for %s ***" % name)
        return LoggingAdapter(logging.getLogger(name), kwargs)


class metadata_stamper:
    @staticmethod
    def stamp_encoder(mp4Path=None, video=None, stamp='untagged', save=True):
        if video is None and mp4Path is not None:
            video_tag = MP4(mp4Path)
        elif video is not None:
            video_tag = video
        else:
            video_tag = None
        
        if video_tag is not None:
            video_tag['\xa9too'] = "meks-ffmpeg %s" % stamp
            if save:
                for i in range(3):
                    try:
                        video_tag.save()
                        return True
                    except IOError as e:
                        time.sleep(5)
                raise IOError
            return video_tag
        raise IOError
