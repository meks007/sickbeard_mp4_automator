#!/usr/bin/env python

import sys
import os
import guessit
import locale
import glob
import argparse
import struct
from pprint import pformat

import logging
from _utils import LoggingAdapter
log = LoggingAdapter.getLogger("MANUAL", {})
log.info("Manual processor started - using interpreter %s" % sys.executable)

from readSettings import settingsProvider
from tvdb_mp4 import Tvdb_mp4
from tmdb_mp4 import tmdb_mp4
from tvdb_api import tvdb_api
import tmdb_api as tmdb
from extensions import tmdb_api_key
from processor import fileProcessor

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


def getinfo(fileName=None, silent=False, tag=True, tvdbid=None):
    log.debug("Trying to fetch metadata information for file ...")
    
    tagdata = None
    
    # Try to guess the file if guessing is enabled
    if fileName is not None:
        tagdata = guessInfo(fileName, tvdbid)
        
    if silent is False:
        if tagdata:
            print("Proceed using guessed identification from filename?")
            if getYesNo():
                return tagdata
        else:
            log.info("Unable to determine identity based on filename, must enter manually")
        m_type = mediatype()
        if m_type is 3:
            tvdbid = getValue("Enter TVDB Series ID", True)
            season = getValue("Enter Season Number", True)
            episode = getValue("Enter Episode Number", True)
            return m_type, tvdbid, season, episode
        elif m_type is 1:
            imdbid = getValue("Enter IMDB ID")
            return m_type, imdbid
        elif m_type is 2:
            tmdbid = getValue("Enter TMDB ID", True)
            return m_type, tmdbid
        elif m_type is 4:
            return None
        elif m_type is 5:
            return False
    else:
        if tagdata and tag:
            return tagdata
        else:
            return None

def guessPrepare(guessData):
    if 'title' in guessData:
        log.debug("Trying to calculate alternative GuessIt titles.")
        # init list and add default title as element
        guessData['titles'] = []
        guessData['titles'].append([guessData['title'], None])
        
        parts = guessData['title'].split(' ')
        # search for year in title if guessit didn't find it.
        for part in parts:
            if part.isdecimal():
                log.debug("A decimal was found in title = %s" % part)
                if len(part) == 4:
                    log.debug("This could be a year, splitting year from title and adding alternative title.")
                    parts.remove(part)
                    finaltitle = ' '.join(parts)
                    guessData['titles'].append([finaltitle, part])
                    log.debug("Alternative title will be %s from year %s" % (finaltitle, part))
                    break
            else:
                log.debug("string in title found = %s" % part)
    
    return guessData

def guessInfo(fileName, tvdbid=None):
    log.debug("Trying to find data via GuessIt.")
    if not settings.fullpathguess:
        fileName = os.path.basename(fileName)
    guess = guessit.guess_file_info(fileName)
    try:
        if guess['type'] == 'movie':
            log.debug("GuessIt returned movie = %s" % guess['title'])
            guess = guessPrepare(guess)
            log.debug("GuessIt returned the following possible movie queries:")
            log.debug(pformat(guess['titles']))
            return tmdbInfo(guess)
        elif guess['type'] == 'episode':
            log.debug("GuessIt returned TV show = %s S%2dE%2d" % (guess['title'], guess['season'], guess['episode']))
            return tvdbInfo(guess, tvdbid)
        else:
            log.debug("GuessIt was unable to guess data.")
            return None
    except:
        log.exception("Error while guessing")
        return None

def tmdbSearch(title, year, language):
    log.info("Fetching data for %s from TMDB." % title)
    tmdb.API_KEY = tmdb_api_key
    search = tmdb.Search()
    response = search.movie(query=title, year=year, language=language)
    return search.results

def tmdbInfo(guessData):
    for guess in reversed(guessData['titles']):
    # iterate reversed because year-based entries are at the bottom of the list, but yield better results.
        title = guess[0]
        year = guess[1]

        movies = tmdbSearch(title, year, settings.taglanguage)
        for movie in movies: 
            # Identify the first movie in the collection that matches exactly the movie title
            foundname = ''.join(e for e in movie["title"] if e.isalnum())
            origname = ''.join(e for e in title if e.isalnum())
            
            if foundname.lower() == origname.lower():
                tmdbid = movie["id"]
                log.info("Matched movie title:")
                log.info("  Title: %s" % movie["title"].encode(sys.stdout.encoding, errors='ignore'))
                log.info("  Release date: %s" % movie["release_date"])
                log.info("  TMDB ID: %s" % tmdbid)
                return 2, tmdbid
    return None

def tvdbInfo(guessData, tvdbid=None):
    series = guessData["series"]
    if 'year' in guessData:
        fullseries = series + " (" + str(guessData["year"]) + ")"
    season = guessData["season"]
    episode = guessData["episodeNumber"]
    t = tvdb_api.Tvdb(interactive=False, cache=False, banners=False, actors=False, forceConnect=True, language='en')
    try:
        tvdbid = str(tvdbid) if tvdbid else t[fullseries]['id']
        series = t[int(tvdbid)]['seriesname']
    except:
        tvdbid = t[series]['id']
    try:
        log.info("Matched TV episode as %s (TVDB ID:%d) S%02dE%02d" % (series.encode(sys.stdout.encoding, errors='ignore'), int(tvdbid), int(season), int(episode)))
    except:
        log.info("Matched TV episode")
    return 3, tvdbid, season, episode

def getTagData(filename, args=None):
    if args is None:
        args = vars(parser.parse_args())
    
    tagdata = None
    tagmp4 = None
    provid = None
    
    if settings.tagfile:
        log.debug("Tagging is enabled.")
        
        # Gather tagdata
        if args is not None:
            if (args['tvdbid'] and not (args['imdbid'] or args['tmdbid'])):
                provid = int(args['tvdbid']) if args['tvdbid'] else None
                season = int(args['season']) if args['season'] else None
                episode = int(args['episode']) if args['episode'] else None
                if (provid and season and episode):
                    log.debug("TvDB show data found in arguments.")
                    tagdata = [3, provid, season, episode]
            elif ((args['imdbid'] or args['tmdbid']) and not args['tvdbid']):
                if (args['imdbid']):
                    log.debug("IMDB movie data found in arguments.")
                    provid = args['imdbid']
                    tagdata = [1, imdbid]
                elif (args['tmdbid']):
                    log.debug("TMDB movie data found in arguments.")
                    provid = int(args['tmdbid'])
                    tagdata = [2, tmdbid]
        if args is None or tagdata is None:
            log.debug("No or incorrect tagging arguments were passed, analyzing file.")
            tagdata = getinfo(filename, silent=args['auto'], tvdbid=provid)
            # False if user skipped tagging
        
        if tagdata is not False:
            # Evaluate appropriate MP4 handler
            if tagdata[0] is 1:
                log.debug("IMDB movie data is valid.")
                imdbid = tagdata[1]
                tagmp4 = tmdb_mp4(imdbid, language=settings.taglanguage, settings=settings)
            elif tagdata[0] is 2:
                log.debug("TMDB movie data is valid.")
                tmdbid = tagdata[1]
                tagmp4 = tmdb_mp4(tmdbid, True, language=settings.taglanguage, settings=settings)
            elif tagdata[0] is 3:
                log.debug("TvDB show data is valid.")
                tvdbid = int(tagdata[1])
                season = int(tagdata[2])
                episode = int(tagdata[3])
                tagmp4 = Tvdb_mp4(tvdbid, season, episode, language=settings.taglanguage, settings=settings)    
            else:
                log.warning("Unknown metadata tagging group found, ignoring.")
        else:
            log.debug("Skiping file.")
    else:
        log.debug("Tagging is disabled.")
    
    return [tagdata, tagmp4]

def processFile(inputfile, relativePath=None):
    log.info("Attempting to process file %s" % inputfile)
    
    tagdata, tagmp4 = getTagData(inputfile)
    if tagdata is not False:
        # this does everything from here.
        return processor.process(inputfile=inputfile, tagmp4=tagmp4, relativePath=relativePath)
    else:
        return False

def walkDir(dir, preserveRelative=False):
    log.debug("Walking directory structure %s" % dir)
    ignore_folder = False
    files = []
    
    log.info("Building list of files to process ...")
    for r, d, f in os.walk(dir):
        f = [fl for fl in f if not fl[0] == '.']
        d[:] = [dr for dr in d if not dr[0] == '.']
        
        if not ignore_folder == False and r.startswith(ignore_folder):
            continue
        ignore_folder = False
        
        if any(x in settings.meks_walk_ignore for x in f):
            log.debug("Folder %s contains ignore file, stepping over folder." % r)
            ignore_folder = r
            continue
        
        for file in f:
            filepath = os.path.join(r, file)
            if processor.validSource(filepath) == True:
                files.append(filepath)
                log.debug("File added to queue: %s" % filepath)
    
    log.info("%s files ready for processing." % len(files))
    for filepath in files:
        if os.path.isfile(filepath):
            try:
                relative = os.path.split(os.path.relpath(filepath, dir))[0] if preserveRelative else None
                processFile(filepath, relativePath=relative)
            except:
                log.exception("An unexpected error occurred, processing of this file was not attempted.")

def main():
    global settings
    global processor
    global parser
    
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
    tag = True

    log.debug("%sbit Python." % (struct.calcsize("P") * 8))

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

    # Establish the path we will be working with
    if (args['input']):
        path = (str(args['input']))
        try:
            path = glob.glob(path)[0]
        except:
            pass
    else:
        path = getValue("Enter path to file")

    processor = fileProcessor(settings)

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
    
if __name__ == '__main__':
    main()
