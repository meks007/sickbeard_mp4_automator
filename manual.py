#!/usr/bin/env python

import sys
import os
import locale
import glob
import argparse
import struct
import guessit
import re
import string
import unicodedata

import logging
from _utils import *
log = LoggingAdapter.getLogger("MANUAL", {})

from readSettings import settingsProvider
from processor import fileProcessor
from tmdb_mp4 import tmdb_mp4, tmdbSearch
from tvdb_mp4 import Tvdb_mp4
from tvdb_api import tvdb_api

if sys.version[0] == "3":
    raw_input = input

parser = argparse.ArgumentParser(description="Manual conversion and tagging script for sickbeard_mp4_automator")

logging.getLogger("subliminal").setLevel(logging.CRITICAL)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("enzyme").setLevel(logging.WARNING)
logging.getLogger("qtfaststart").setLevel(logging.WARNING)

def mediatype():
    print("Select media type:")
    print("1. Movie (via IMDB ID)")
    print("2. Movie (via TMDB ID)")
    print("3. TV")
    print("4. Convert without tagging")
    print("5. Skip file")
    result = raw_input("#: ")
    if 0 < int(result) < 6:
        return int(result)
    else:
        print("Invalid selection")
        return mediatype()

def getValue(prompt, num=False):
    print(prompt + ":")
    value = raw_input("#: ").strip(' \"')
    # Remove escape characters in non-windows environments
    if os.name != 'nt':
        value = value.replace('\\', '')
    try:
        value = value.decode(sys.stdout.encoding)
    except:
        pass
    if num is True and value.isdigit() is False:
        print("Must be a numerical value")
        return getValue(prompt, num)
    else:
        return value


def getYesNo():
    yes = ['y', 'yes', 'true', '1']
    no = ['n', 'no', 'false', '0']
    data = raw_input("# [y/n]: ")
    if data.lower() in yes:
        return True
    elif data.lower() in no:
        return False
    else:
        print("Invalid selection")
        return getYesNo()

def tvdbInfo(guessData, tvdbid=None):
    series = guessData["title"]
    if 'year' in guessData:
        fullseries = series + " (" + str(guessData["year"]) + ")"
    season = guessData["season"]
    episode = guessData["episodeNumber"]
    t = tvdb_api.Tvdb(interactive=False, cache=False, banners=False, actors=False, forceConnect=True, language='en')
    try:
        try:
            tvdbid = str(tvdbid) if tvdbid else t[fullseries]['id']
            series = t[int(tvdbid)]['seriesname']
        except:
            tvdbid = t[series]['id']
        try:
            log.info("Matched TV episode as %s (TVDB ID:%d) S%02dE%02d" % (series.encode(sys.stdout.encoding, errors='ignore'), int(tvdbid), int(season), int(episode)))
        except:
            log.info("Matched TV episode")
        return {'type':3, 'provid':tvdbid, 'season':season, 'episode':episode}
    except:
        log.error("Unable to match against TVDB.")
        return False

def g_guessMeta(inputfile):
    data = processor.getFfprobeData(inputfile)
    try:
        title = data["format"]["tags"]["title"]
        log.debug("Found title %s in file metadata" % title)
    except:
        title = None
        log.debug("No metadata found found in file")
    return title

def g_guessNfo(inputfile):
    if settings.meks_nfosearch:
        log.debug("Tagging: Nfo")
        fpath = os.path.split(inputfile)[0]
        paths = [fpath]
        for path in settings.meks_nfopaths:
            paths.append(os.path.join(fpath, path))
        for path in paths:
            log.debug("Searching for a nfo file in %s" % path)
            for file in os.listdir(path):
                if file.endswith(".nfo"):
                    fullfile = os.path.join(path, file)
                    log.debug("Found nfo file %s" % fullfile)
                    with open(fullfile, 'r') as urls_in:
                        for line in urls_in:
                            links = re.findall(r"((?:http\:\/\/)?www\.imdb\.com/(?:title/)?(tt\d+))", line)
                            if links:
                                log.debug("Extracted IMDB ID %s from %s" % (links[0][1], file))
                                return links[0][1]
        log.debug("No nfo files found")
    return None

def g_guessIt(fileName):
    guesses = {'paths':[]}
    guesses['titles'] = []
    log.debug("Tagging: GuessIt")
    
    realFileName = fileName

    paths = [] 
    meta = g_guessMeta(fileName)   
    if meta is not None:
        meta = meta + ".mp4"
        paths.append(meta)
    paths.extend([fileName, os.path.split(fileName)[0]+".mp4"])
    
    realFileNameBase = os.path.split(realFileName)[1]
    realFileNameBaseClean = filename_clean(realFileNameBase)
    log.debug("Checking Levenshtein distances of titles compared")
    log.debug("  Comparing to: %s" % realFileNameBase)
    for fileName in paths:
        fileNameBase = os.path.split(fileName)[1]
        fileNameBaseClean = filename_clean(fileNameBase)
        distance = levenshtein_distance(realFileNameBaseClean, fileNameBaseClean)
        if distance > 20:
            log.debug("  - %s: %s, title ignored, difference too big" % (fileNameBase, distance))
            paths.remove(fileName)
        else:
            log.debug("  + %s: %s, title ok" % (fileNameBase, distance))
        
    for fileName in paths: 
        #guess = guesses["path_" + fileName] = {}
        guess = {'path':fileName}
        if realFileName == fileName:
            guess['realpath'] =True
        else:
            guess['realpath'] =False
        
        fileName = fileName.replace('-', ' ')
        guessData = guessit.guess_file_info(fileName)
        for key in ['title', 'type', 'season', 'episodeNumber', 'year']:
            if key in guessData:
                guess[key] = guessData[key]
        for key in ['format', 'releaseGroup', 'videoCodec']:
            if key in guessData:
                guesses[key] = guessData[key]
        if 'series' in guessData:
            guess['title'] = guessData['series']
        if 'title' in guess:
            log.debug("Trying to calculate alternative GuessIt titles")
            # init list and add default title as element
            guesses['titles'].append([guess['title'], guess['year'] if 'year' in guess else None])
            
            parts = guess['title'].split(' ')
            # search for year in title if guessit didn't find it.
            for part in parts:
                if part.isdecimal():
                    if len(part) == 4:
                        log.debug("A decimal was found in title = %s" % part)
                        log.debug("This could be a year, splitting year from title and adding alternative title")
                        parts.remove(part)
                        finaltitle = ' '.join(parts)
                        guesses['titles'].append([finaltitle, part])
                        log.debug("Alternative title will be %s from year %s" % (finaltitle, part))
                        break
        guesses['paths'].append(guess)
    return guesses

def getGuessInfo(guess):
    info = None
    if guess['type'] == 'movie':
        log.debug("Guessed movie = %s" % guess['title'])
        log.debug("Determined the following possible movie queries:")
        log.debug(guess['titles'])
        info = searcher.info(guess)
    elif guess['type'] == 'episode':
        log.debug("Guessed TV show = %s S%2dE%2d" % (guess['title'], guess['season'], guess['episodeNumber']))
        info = tvdbInfo(guess)
    return info
    
def guessInfo(fileName, tagdata=None):
    if not settings.fullpathguess:
        fileName = os.path.basename(fileName)
    
    imdbid = None
    info = None
    
    provid = None
    providsearch = 1
    
    ### Arguments ###
    if tagdata is not None:
        log.debug("Provided Tag data: %s" % tagdata)
        provid = tagdata['provid'] #1
        providsearch = tagdata['type'] #0
        log.debug("ID of type %s from Tag data: %s" % (providsearch, provid))
    
    ### NFO ###
    providGuess = g_guessNfo(fileName)
    log.debug("ID of type 1 from Nfo guess: %s" % providGuess)
    provid = providGuess if provid is None else provid
    
    ### GuessIt ###
    guess = g_guessIt(fileName=fileName)

    if provid is not None:
        log.debug("Final ID of type %s from all sources: %s" % (providsearch, provid))
        if providsearch == 1:
           guess['what'] = {'term':provid, 'external_source':'imdb_id'}
           guess['type'] = 'find'    
           guess = searcher.find(guess)
        elif providsearch == 2:
           guess = searcher.load(provid, guess)
       
    log.debug("Guessed data: %s" % guess)
    
    if guess is not None:
        if 'type' not in guess and 'paths' in guess:
            #i = 0
            for process_guess in guess['paths']:
                #if current_guess[:5] == 'path_':
                #process_guess = guess['paths'][current_guess]
                process_guess['titles'] = guess['titles']
                info = getGuessInfo(process_guess)
                if info is not None:
                    break
                else:
                    log.debug("No data found for this query")
        else:
            info = getGuessInfo(guess)
    if info is None:
        log.debug("Unable to guess data. Type or ID invalid?")
    else:
        info['guess'] = guess
    return info

def getinfo(fileName=None, silent=False, tagdata=None):
    # Try to guess the file if guessing is enabled
    guess = None
    if fileName is not None:
        tagdata = guessInfo(fileName, tagdata)
    
    r = {}
    if silent is False:
        if tagdata:
            print("Proceed using guessed identification from filename?")
            if getYesNo():
                return tagdata
        else:
            log.info("Unable to determine identity based on filename, must enter manually")
        m_type = mediatype()
        if m_type is 3:
            provid = getValue("Enter TVDB Series ID", True)
            season = getValue("Enter Season Number", True)
            episode = getValue("Enter Episode Number", True)
            r.update({'type':m_type, 'provid':provid, 'season':season, 'episode':episode})
        elif m_type is 1:
            provid = getValue("Enter IMDB ID")
            r.update({'type':m_type, 'provid':provid})
        elif m_type is 2:
            provid = getValue("Enter TMDB ID", True)
            r.update({'type':m_type, 'provid':provid})
        elif m_type is 4:
            return None
        elif m_type is 5:
            return False
        if tagdata is not None and 'guess' in tagdata:
            r.update({'guess':tagdata['guess']})
        return r
    else:
        if tagdata and settings.tagfile:
            return tagdata
        else:
            return None

def getTagData(filename, args=None):
    if args is None:
        args = vars(parser.parse_args())
    
    tagdata = None
    tagmp4 = None
    provid = None
    
    if settings.tagfile:
        log.info(">>> Tagging file ...")
        
        lang = processor.getPrimaryLanguage(filename)
        searcher.language = lang[0]
        log.debug("Auto-selected tagging language %s based on first audio stream" % lang[1])
        
        # Gather tagdata
        if args is not None:
            log.debug("Tagging: Args")
            if (args['tvdbid'] and not (args['imdbid'] or args['tmdbid'])):
                provid = int(args['tvdbid']) if args['tvdbid'] else None
                season = int(args['season']) if args['season'] else None
                episode = int(args['episode']) if args['episode'] else None
                if (provid and season and episode):
                    log.debug("TvDB show data found in arguments")
                    tagdata = {'type':3, 'provid':provid, 'season':season, 'episode':episode}
            elif ((args['imdbid'] or args['tmdbid']) and not args['tvdbid']):
                if (args['imdbid']):
                    log.debug("IMDB movie data found in arguments")
                    provid = args['imdbid']
                    tagdata = {'type':1, 'provid':provid}
                elif (args['tmdbid']):
                    log.debug("TMDB movie data found in arguments")
                    provid = int(args['tmdbid'])
                    tagdata = {'type':2, 'provid':provid}
        #if args is None or tagdata is None:
        tagdata = getinfo(filename, silent=args['auto'], tagdata=tagdata) # False if user skipped tagging
        if tagdata is not False:
            if tagdata is not None:
                # Evaluate appropriate MP4 handler
                try:
                    if tagdata['type'] is 1:
                        imdbid = tagdata['provid']
                        tagmp4 = tmdb_mp4(imdbid, settings=settings, language=lang[0], guessData=tagdata['guess'])
                    elif tagdata['type'] is 2:
                        tmdbid = tagdata['provid']
                        tagmp4 = tmdb_mp4(tmdbid, True, settings=settings, language=lang[0], guessData=tagdata['guess'])
                    elif tagdata['type'] is 3:
                        tvdbid = int(tagdata['provid'])
                        season = int(tagdata['season'])
                        episode = int(tagdata['episode'])
                        tagmp4 = Tvdb_mp4(tvdbid, season, episode, settings=settings, language=lang[0], guessData=tagdata['guess'])
                except Exception as e:
                    log.exception(e)
                    tagmp4 = None
            
            if tagmp4 is None:
                log.warning("Unknown metadata received, file will not be tagged")
    else:
        log.debug("Tagging is disabled")
    
    return [tagdata, tagmp4]

def processFile(inputfile, fileno=[1,1], relativePath=None):
    execlock.renew()
    
    log.info("")
    log.info("File %s/%s - %s" % (fileno[0], fileno[1], inputfile))
    tagdata, tagmp4 = getTagData(inputfile)
        
    if tagdata is not False:
        # this does everything from here.
        return processor.process(inputfile=inputfile, tagmp4=tagmp4, relativePath=relativePath)
    else:
        log.info("File skipped")
        return False

def walkDir(dir, preserveRelative=False):
    log.debug("Walking directory structure %s" % dir)
    ignore_folder = False
    files = []
    
    log.info(">>> Building list of files to process ...")
    for r, d, f in os.walk(dir):
        f = [fl for fl in f if not fl[0] == '.']
        d[:] = [dr for dr in d if not dr[0] == '.']
        
        if not ignore_folder == False and r.startswith(ignore_folder):
            continue
        ignore_folder = False
        
        if any(x in settings.meks_walk_ignore for x in f):
            log.debug("Folder %s contains ignore file, stepping over folder" % r)
            ignore_folder = r
            continue
        
        for file in f:
            filepath = os.path.join(r, file)
            if processor.validSource(filepath) == True:
                files.append(filepath)
                log.debug("File added to queue: %s" % filepath)
    
    log.info("%s files ready for processing" % len(files))
    
    if len(files) > 0:
        log.debug("The following files were added to the processing queue:")
        
        i = 0
        for filepath in files:
            i = i + 1
            log.debug("%s/%s - %s" % (i, len(files), files[i-1]))
        
        i = 0
        for filepath in files:
            i = i + 1
            if os.path.isfile(filepath):
                try:
                    relative = os.path.split(os.path.relpath(filepath, dir))[0] if preserveRelative else None
                    processFile(filepath, [i, len(files)], relativePath=relative)
                except:
                    log.exception("An unexpected error occurred, processing of this file was not attempted")

def main():
    global settings
    global processor
    global parser
    global searcher
    global execlock
    
    log.debug("")
    log.debug("<<<<<<<<<<<<<<<<<<<<< LAUNCH >>>>>>>>>>>>>>>>>>>>>")
    log.info("Manual processor started - using interpreter %s" % sys.executable)
    
    execlock = executionLocker()
    if not execlock.islocked():
        execlock.lock()
        
        parser.add_argument('-i', '--input', help='The source that will be converted. May be a file or a directory')
        parser.add_argument('-c', '--config', help='Specify an alternate configuration file location')
        parser.add_argument('-a', '--auto', action="store_true", help="Enable auto mode, the script will not prompt you for any further input, good for batch files. It will guess the metadata using guessit")
        parser.add_argument('-tv', '--tvdbid', help="Set the TVDB ID for a tv show")
        parser.add_argument('-s', '--season', help="Specifiy the season number")
        parser.add_argument('-e', '--episode', help="Specify the episode number")
        parser.add_argument('-imdb', '--imdbid', help="Specify the IMDB ID for a movie")
        parser.add_argument('-tmdb', '--tmdbid', help="Specify theMovieDB ID for a movie")
        parser.add_argument('-nm', '--nomove', action='store_true', help="Overrides and disables the custom moving of file options that come from output_dir and move-to")
        parser.add_argument('-nc', '--nocopy', action='store_true', help="Overrides and disables the custom copying of file options that come from output_dir and move-to")
        parser.add_argument('-nd', '--nodelete', action='store_true', help="Overrides and disables deleting of original files")
        parser.add_argument('-nt', '--notag', action="store_true", help="Overrides and disables tagging when using the automated option")
        parser.add_argument('-np', '--nopost', action="store_true", help="Overrides and disables the execution of additional post processing scripts")
        parser.add_argument('-pr', '--preserveRelative', action='store_true', help="Preserves relative directories when processing multiple files using the copy-to or move-to functionality")
        parser.add_argument('-cmp4', '--convertmp4', action='store_true', help="Overrides convert-mp4 setting in autoProcess.ini enabling the reprocessing of mp4 files")
        #parser.add_argument('-m', '--moveto', help="Override move-to value setting in autoProcess.ini changing the final destination of the file")
    
        args = vars(parser.parse_args())
    
        # Setup the silent mode
        silent = args['auto']
    
        log.debug("%sbit Python" % (struct.calcsize("P") * 8))
    
        # Settings overrides
        settings = None
        if(args['config']):
            if os.path.exists(args['config']):
                log.info('Using configuration file "%s"' % (args['config']))
                settings = ReadSettings(os.path.split(args['config'])[0], os.path.split(args['config'])[1])
            elif os.path.exists(os.path.join(os.path.dirname(sys.argv[0]), args['config'])):
                log.info('Using configuration file "%s"' % (args['config']))
                settings = ReadSettings(os.path.dirname(sys.argv[0]), args['config'])
        if settings is None:
            if args['config']:
                log.info('Configuration file "%s" not present, using default configuration' % (args['config']))
            settings = settingsProvider().defaultSettings
        
        if (args['nomove']):
            settings.output_dir = None
            settings.moveto = None
            log.info("No-move enabled")
        #if (args['moveto']):
        #    settings.moveto = args['moveto']
        #    log.info("Overriden move-to to " + args['moveto'])
        if (args['nocopy']):
            settings.copyto = None
            log.info("No-copy enabled")
        if (args['nodelete']):
            settings.delete = False
            log.info("No-delete enabled")
        if (args['convertmp4']):
            settings.processMP4 = True
            log.info("Reprocessing of MP4 files enabled")
        if (args['notag']):
            settings.tagfile = False
            log.info("No-tagging enabled")
        if (args['nopost']):
            settings.postprocess = False
            log.info("No post processing enabled")
    
        processor = fileProcessor(settings=settings)
        searcher = tmdbSearch(settings=settings)
    
        # Establish the path we will be working with
        if (args['input']):
            path = (str(args['input']))
            try:
                path = glob.glob(path)[0]
            except:
                pass
        else:
            path = getValue("Enter path to file")
        
        if os.path.isdir(path):
            walkDir(path, preserveRelative=args['preserveRelative'])
        elif os.path.isfile(path):
            processFile(path)
        elif not os.path.isfile(path) and not os.path.isdir(path):
            log.error("File not found - %s" % (path))
        else:
            try:
                log.error("File is not in the correct format - %s" % (path))
            except:
                log.error("File is not in the correct format")
        log.info("All done!")
    
        execlock.unlock()
    else:
        log.error("Unable to acquire exclusive lock.")
        log.error("Wait until the previous run is finished or a deadlock expires. Remove run.lock to release the lock immediately.")
    log.debug("~~~~~~~~~~~~~~~~~~~~~ FINISH ~~~~~~~~~~~~~~~~~~~~~")
    
if __name__ == '__main__':
    main()
