#!/usr/bin/env python
import os
import sys
import json
import urllib
import struct

from _utils import LoggingAdapter
log = LoggingAdapter.getLogger("MANUAL", {})
log.info("Sickbeard extra script post processing started.")

from readSettings import ReadSettings
from autoprocess import plex
from tvdb_mp4 import Tvdb_mp4
#from mkvtomp4 import MkvtoMp4
#from post_processor import PostProcessor
from processor import fileProcessor

settings = settingsProvider().defaultSettings
processor = fileProcessor(settings)

if len(sys.argv) > 4:
    inputfile = sys.argv[1]
    original = sys.argv[2]
    tvdb_id = int(sys.argv[3])
    season = int(sys.argv[4])
    episode = int(sys.argv[5])

    log.debug("Input file: %s." % inputfile)
    log.debug("Original name: %s." % original)
    log.debug("TvDB ID: %s." % tvdb_id)
    log.debug("Season: %s Episode: %s." % (season, episode))

    log.info("Processing %s" % inputfile)

    if processor.validSource(inputfile):
        tagmp4 = Tvdb_mp4(tvdb_id, season, episode, original, language=settings.taglanguage, settings=settings)
        return processor.process(inputfile=inputfile, tagmp4=tagmp4, original=original)
        
        #output = converter.process(inputfile, original=original)
        #if output:
        #    # Tag with metadata
        #    if settings.tagfile:
        #        log.info("Tagging %s with ID %s Season %s Episode %s." % (inputfile, tvdb_id, season, episode))
        #        tagmp4 = Tvdb_mp4(tvdb_id, season, episode, original, language=settings.taglanguage)
        #        tagmp4.setHD(output['x'], output['y'])
        #        tagmp4.writeTags(output['output'], settings.artwork, settings.thumbnail)
        # 
        #     # QTFS
        #     if settings.relocate_moov:
        #         converter.QTFS(output['output'])
        # 
        #     # Copy to additional locations
        #    output_files = converter.replicate(output)
        #
        #    # run any post process scripts
        #    if settings.postprocess:
        #        post_processor = PostProcessor(output_files, log)
        #        post_processor.setTV(tvdb_id, season, episode)
        #        post_processor.run_scripts()
        #
        #    try:
        #        refresh = json.load(urllib.urlopen(settings.getRefreshURL(tvdb_id)))
        #        for item in refresh:
        #            log.debug(refresh[item])
        #    except (IOError, ValueError):
        #        log.exception("Couldn't refresh Sickbeard, check your autoProcess.ini settings.")
        #
        #    plex.refreshPlex(settings, 'show', log)

else:
    log.error("Not enough command line arguments present %s." % len(sys.argv))
    sys.exit()
