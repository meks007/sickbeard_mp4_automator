import os
import json
import sys
import logging

from _utils import LoggingAdapter
from mkvtomp4 import MkvtoMp4
from post_processor import PostProcessor

class fileProcessor:
    def __init__(self, settings=None, logger=None):
        if logger:
            self.log = logger
        else:
            self.log = LoggingAdapter.getLogger(__name__)
        
        if settings is None:
            raise ValueError("Settings not supplied")
        self.settings = settings
        self.converter = MkvtoMp4(settings)
    
    def validSource(self, inputfile):
        if self.settings.meks_trans_ignore_s > 0:
            fsize = os.path.getsize(inputfile)
            if fsize < self.settings.meks_trans_ignore_s:
                self.log.debug("File = %s, size = %s, lower limit = %s, skipped" % (inputfile, fsize, self.settings.meks_trans_ignore_s))
                return False
        if self.settings.meks_trans_ignore_n is not None:
            fname = os.path.split(inputfile)[1].lower()
            for i in self.settings.meks_trans_ignore_n:
                if i.lower() in fname:
                    self.log.debug("File = %s, ignore pattern match = %s, skipped" % (inputfile, i))
                    return False
        return self.converter.validSource(inputfile)
    
    def getFfprobeData(self, inputfile):
        return self.converter.getFfprobeData(inputfile)
    def getPrimaryLanguage(self, inputfile):
        return self.converter.getPrimaryLanguage(inputfile)
        
    def tagInfo(self, tagmp4):
        if tagmp4 is not None:
            if tagmp4.provider == "imdb" or tagmp4.provider == "tmdb":
                try:
                    self.log.info(">>> Processing movie - %s ..." % (tagmp4.title.encode(sys.stdout.encoding, errors='ignore')))
                except:
                    self.log.info(">>> Processing movie ...")
            elif tagmp4.provider == "tvdb":
                try:
                    self.log.info(">>> Processing TV show - %s S%02dE%02d - %s ..." % (tagmp4.show.encode(sys.stdout.encoding, errors='ignore'), int(tagmp4.season), int(tagmp4.episode), tagmp4.title.encode(sys.stdout.encoding, errors='ignore')))
                except:
                    self.log.info(">>> Processing TV episode ...")
        else:
            self.log.info(">>> Processing file ...")
    
    def process(self, inputfile, tagmp4=None, relativePath=None, original=None):
        output_files = []
        
        if self.converter.validSource(inputfile) == True:
            self.tagInfo(tagmp4)
            
            output = self.converter.process(inputfile=inputfile, reportProgress=True, original=original)
            if output:
                # TAG
                if tagmp4 is not None:
                    try:
                        tagmp4.setHD(output['x'], output['y'])
                        tagmp4.writeTags(output['output'], self.settings.artwork, self.settings.thumbnail)
                    except:
                        self.log.exception("There was an error tagging the file")
                
                # OPTIMIZE
                #if self.settings.relocate_moov:
                #    self.converter.QTFS(output['output'])
                
                # REPLICATE
                output['tag'] = tagmp4
                output_files = self.converter.replicate(output, relativePath=relativePath)            
                
                # FINALIZE
                if self.settings.postprocess:
                    post_processor = PostProcessor(output_files)
                    if tagmp4 is not None:
                        if tagmp4.provider == "imdb" or tagmp4.provider == "tmdb":
                            post_processor.setMovie(tagmp4.providerid)
                        elif tagmp4.provider == "tvdb":
                            post_processor.setTV(tagmp4.providerid, tagmp4.season, tagmp4.episode)
                    post_processor.run_scripts()
        
        return output_files