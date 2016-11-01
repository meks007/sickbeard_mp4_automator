import logging
import traceback
import os
import sys
import inspect

from logging.config import fileConfig
fileConfig(os.path.join(os.path.dirname(__file__), 'logging.ini'), defaults={'logfilename': os.path.join(os.path.dirname(__file__), 'info.log').replace("\\", "/")})

log = logging.getLogger(__name__)

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
