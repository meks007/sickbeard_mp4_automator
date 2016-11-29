import os
import sys
try:
    from urllib.request import urlretrieve
except ImportError:
    from urllib import urlretrieve
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
from requests import HTTPError
import tempfile
import time
from _utils import *

import tmdb_api as tmdb
from mutagen.mp4 import MP4, MP4Cover
from extensions import valid_output_extensions, valid_poster_extensions, tmdb_api_key

from mkvtomp4 import MkvtoMp4
from readSettings import settingsProvider

class tmdb_mp4:
    def __init__(self, provid, tmdbid=False, original=None, language=None, logger=None, settings=None, guessData=None):
        if logger:
            self.log = logger
        else:
            self.log = LoggingAdapter.getLogger(__name__)
            
        if settings is not None:
            self.settings = settings
        else:
            self.settings = settingsProvider().defaultSettings

        if language is None:
            language = self.settings.taglanguage

        self.guessData = guessData

        if tmdbid is False and provid.startswith('tt') is not True:
            provid = 'tt' + provid
            self.log.debug("Correcting IMDB ID to %s" % provid)

        if tmdbid:
            self.log.debug("TMDB ID: %s" % provid)
        else:
            self.log.debug("IMDB ID: %s" % provid)
            self.log.debug("Translating IMDB ID to TMDB ID")
            searcher = tmdbSearch(language, self.log, self.settings)
            try:
                provid = searcher.find(provid)['tmdbid']
                tmdbid = True
            except Exception as e:
                self.log.exception("Unable to get TMDB ID, will not tag")
                raise(e)
        
        self.provider = 'tmdb' if tmdbid else 'imdb'
        self.providerid = provid
        
        self.original = original
        for i in range(3):
            try:
                tmdb.API_KEY = tmdb_api_key
                try:
                    
                    self.movie = tmdb.Movies(provid)
                    self.movieInfo = self.movie.info(language=language)
                    self.casts = self.movie.credits()
                    self.releases = self.movie.releases()
                    
                    self.tmdbConfig = tmdb.Configuration().info()
                    
                    self.HD = None
                    self.title = self.movieInfo['title']
                    self.genre = self.movieInfo['genres']
                    self.shortdescription = self.movieInfo['tagline']
                    self.description = self.movieInfo['overview']
                    self.date = self.movieInfo['release_date']
                    
                    # Generate XML tags for Actors/Writers/Directors/Producers
                    self.xml = self.xmlTags()
                    return
                except Exception as e:
                    raise(e)
                break
            #except HTTPError as e:
            #    if e.code == 404:
            #        self.log.exception("Invalid TMDB data received for request.")
            #    else:
            #        self.log.exception("Error occured during movie data scraping.")
            #        raise(e)
            except Exception as e:
                self.log.exception("Failed to connect to TMDB, trying again in 20 seconds")
                time.sleep(20)

    def writeTags(self, mp4Path, artwork=True, thumbnail=False):
        self.log.debug("Tagging file %s" % mp4Path)
        if MkvtoMp4(self.settings).validSource(mp4Path) == True:
            video = MP4(mp4Path)
            try:
                video.delete()
            except IOError:
                self.log.debug("Unable to clear original tags, attempting to proceed")
    
            video["\xa9nam"] = self.title  # Movie title
            #video["desc"] = self.shortdescription  # Short description
            #video["ldes"] = self.description  # Long description
            video["\xa9day"] = self.date  # Year
            #video["stik"] = [9]  # Movie iTunes category
            if self.HD is not None:
                video["hdvd"] = self.HD
            #if self.genre is not None:
            #    genre = None
            #    for g in self.genre:
            #        if genre is None:
            #            genre = g['name']
            #            break
            #        # else:
            #            # genre += ", " + g['name']
            #    video["\xa9gen"] = genre  # Genre(s)
            #video["----:com.apple.iTunes:iTunMOVI"] = self.xml  # XML - see xmlTags method
            #rating = self.rating()
            #if rating is not None:
            #    video["----:com.apple.iTunes:iTunEXTC"] = rating
    
            if artwork:
                path = self.getArtwork(mp4Path)
                if path is not None:
                    cover = open(path, 'rb').read()
                    if path.endswith('png'):
                        video["covr"] = [MP4Cover(cover, MP4Cover.FORMAT_PNG)]  # png poster
                    else:
                        video["covr"] = [MP4Cover(cover, MP4Cover.FORMAT_JPEG)]  # jpeg poster

            #if self.original:
            #    video["\xa9too"] = ("meks-ffmpeg movie [%s-%s]" % (self.provider, self.providerid))
            #else:
            #    video["\xa9too"] = ("meks-ffmpeg movie [%s-%s]" % (self.provider, self.providerid))
            video = metadata_stamper.stamp_encoder(video=video, save=False, stamp=("movie [%s-%s]" % (self.provider, self.providerid)))
            
            for i in range(3):
                try:
                    self.log.debug("Trying to write tags")
                    video.save()
                    self.log.info("Tags written successfully")
                    return True
                except IOError as e:
                    self.log.exception("There was a problem writing the tags. Retrying")
                    time.sleep(5)
        else:
            self.log.error("The file is invalid")
        raise IOError

    def rating(self):
        ratings = { 'G': '100',
                   'PG': '200',
                'PG-13': '300',
                    'R': '400',
                'NC-17': '500'}
        output = None
        mpaa = self.get_mpaa_rating()
        if mpaa in ratings:
            numerical = ratings[mpaa]
            output = 'mpaa|' + mpaa.capitalize() + '|' + numerical + '|'
        return str(output)

    def setHD(self, width, height):
        if width >= 1900 or height >= 1060:
            self.HD = [2]
        elif width >= 1260 or height >= 700:
            self.HD = [1]
        else:
            self.HD = [0]
    
    def xmlTags(self):
        # constants
        header = "<?xml version=\"1.0\" encoding=\"UTF-8\"?><!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\"><plist version=\"1.0\"><dict>\n"
        castheader = "<key>cast</key><array>\n"
        writerheader = "<key>screenwriters</key><array>\n"
        directorheader = "<key>directors</key><array>\n"
        producerheader = "<key>producers</key><array>\n"
        subfooter = "</array>\n"
        footer = "</dict></plist>\n"

        output = StringIO()
        output.write(header)

        # Write actors
        output.write(castheader)
        for a in self.get_cast()[:5]:
            if a is not None:
                output.write("<dict><key>name</key><string>%s</string></dict>\n" % a['name'].encode('ascii', 'ignore'))
        output.write(subfooter)
        # Write screenwriters
        output.write(writerheader)
        for w in self.get_writers()[:5]:
            if w is not None:
                output.write("<dict><key>name</key><string>%s</string></dict>\n" % w['name'].encode('ascii', 'ignore'))
        output.write(subfooter)
        # Write directors
        output.write(directorheader)
        for d in self.get_directors()[:5]:
            if d is not None:
                output.write("<dict><key>name</key><string>%s</string></dict>\n" % d['name'].encode('ascii', 'ignore'))
        output.write(subfooter)
        # Write producers
        output.write(producerheader)
        for p in self.get_producers()[:5]:
            if p is not None:
                output.write("<dict><key>name</key><string>%s</string></dict>\n" % p['name'].encode('ascii', 'ignore'))
        output.write(subfooter)

        # Write final footer
        output.write(footer)
        return output.getvalue()
        output.close()
    # end xmlTags

    def getArtwork(self, mp4Path, filename='cover'):
        # Check for local artwork in the same directory as the mp4
        extensions = valid_poster_extensions
        poster = None
        for e in extensions:
            head, tail = os.path.split(os.path.abspath(mp4Path))
            path = os.path.join(head, filename + os.extsep + e)
            if (os.path.exists(path)):
                poster = path
                self.log.info("Local artwork detected, using %s" % path)
                break
        # Pulls down all the poster metadata for the correct season and sorts them into the Poster object
        if poster is None:
            try:
                poster = urlretrieve(self.get_poster(), os.path.join(tempfile.gettempdir(), "poster-tmdb.jpg"))[0]
            except:
                self.log.error("Exception while retrieving poster %s", str(err))
                poster = None
        return poster
    
    # Sizes = [u'w92', u'w154', u'w185', u'w342', u'w500', u'w780', u'original']
    def get_poster(self, img_size=4):
        return self.tmdbConfig['images']['base_url'] + self.tmdbConfig['images']['poster_sizes'][img_size] + self.movieInfo["poster_path"]

    def get_writers(self):
        l = []
        for r in self.casts['crew']:
            if r['department'] == 'Writing':
                l.append(r)
        return l

    def get_directors(self):
        l = []
        for r in self.casts['crew']:
            if r['department'] == 'Directing':
                l.append(r)
        return l

    def get_producers(self):
        l = []
        for r in self.casts['crew']:
            if r['department'] == 'Production':
                l.append(r)
        return l

    def get_cast(self):
        return sorted(self.casts['cast'], key=lambda x: x['order'])

    def get_mpaa_rating(self, country='US'):
        for r in self.releases['countries']:
            if country.lower() == r['iso_3166_1'].lower():
                return r['certification']
    
class tmdbSearch:
    def __init__(self, language=None, logger=None, settings=None):
        if logger:
            self.log = logger
        else:
            self.log = LoggingAdapter.getLogger("%s.%s" % (__name__, self.__class__.__name__))
            
        if settings is not None:
            self.settings = settings
        else:
            self.settings = settingsProvider().defaultSettings
        
        if language is None:
            self.language = self.settings.taglanguage
        else:
            self.language = language
        
        tmdb.API_KEY = tmdb_api_key
    
    def load(self, provid, guess):
        self.log.debug("Loading TMDB data for ID %s" % provid)
        
        try:
            try:
                movie = tmdb.Movies(provid)
                movieinfo = movie.info(language=self.language)
                return self.guess(info=movieinfo, what="movie", guess=guess)
            except HTTPError as err:
                if err.response.status_code == 404:
                    pass
            
            try:
                tv = tmdb.TV(provid)
                tvinfo = tv.info(language=self.language)
                return self.guess(info=tvinfo, what="tv", guess=guess)
            except HTTPError as err:
                if err.response.status_code == 404:
                    pass
        except:
            self.log.exception("Error occured during tmdb.Movies operation")
        return None
    
    def search(self, title, year):
        self.log.debug("Fetching language-dependent data for %s from TMDB" % title)
        self.log.debug("With filter: (title = %s, year = %s, language = %s)" % (title, year, self.language))
        
        try:
            search = tmdb.Search()
            response = search.movie(query=title, year=year, language=self.language)
        except:
            self.log.exception("Error occured during tmdb.Search operation")
            return None
        return search.results
    
    def guess(self, info, what, guess = {}):
        if what == 'movie':
            guess['type'] = 'movie'
            guess['title'] = info['title']
            guess['release_date'] = info['release_date']
        elif what == 'tv':
            guess['type'] = 'episode'
            guess['title'] = info['name']
            guess['release_date'] = info['first_air_date']
        guess['year'] = guess['release_date'][:4]
        guess['tmdbid'] = info['id']
        guess['vote_count'] = info['vote_count']
        guess['titles'] = [[guess['title'], guess['year']]]
        guess['matched'] = True
        return guess
    
    def find(self, guess, external_source='imdb_id'):
        if 'what' in guess:
            term = guess['what']['term']
            external_source = guess['what']['external_source'] if 'external_source' in guess['what'] else external_source
        else:
            term = guess
            guess = {}
        
        self.log.debug("Finding language-independent data for %s in TMDB" % term)
        self.log.debug("With filter: (external_source = %s)" % external_source)
        
        try:
            find = tmdb.Find(term)
            resp = find.info(external_source=external_source)
        except:
            self.log.exception("Error occured during tmdb.Find operation")
            return None
        
        self.log.debug("Response from TMDB: %s" % resp)
        
        if len(find.movie_results):
            movie = find.movie_results[0]
            return self.guess(info=movie, what="movie", guess=guess)
        elif len(find.tv_results):
            tv = find.tv_results[0]
            return self.guess(info=tv, what="tv", guess=guess)
        return None
    
    def info(self, guess):
        movieinfo = {}
        if not 'tmdbid' in guess:
        #if 1 == 1:
            tmdbid = None
            for guess in reversed(guess['titles']):
            # iterate reversed because year-based entries are at the bottom of the list, but yield better results.
                title = guess[0]
                year = guess[1]
                
                try:
                    movies = self.search(title, year)
                except Exception as e:
                    raise(e)
                
                for movie in movies:
                    # Identify the first movie in the collection that matches exactly the movie title
                    #foundname = ''.join(e for e in movie["title"] if e.isalnum())
                    #origname = ''.join(e for e in title if e.isalnum())
                    
                    #if foundname.lower() == origname.lower():
                    movieinfo = movie
                    tmdbid = movieinfo["id"]
                    break;
                
                if tmdbid is not None:
                    break;
        else:
            tmdbid = guess['tmdbid']
            guess = self.load(tmdbid, guess)
            movieinfo["title"] = guess['title']
            movieinfo["release_date"] = guess['release_date']
            movieinfo["vote_count"] = guess['vote_count']
        
        if tmdbid:
            self.log.info("Matched movie as %s (TMDB ID:%s) %s" % (movieinfo["title"], tmdbid, movieinfo["release_date"]))
            return {'type':2, 'provid':tmdbid}
        
        return None

def main():
    if len(sys.argv) > 2:
        mp4 = str(sys.argv[1]).replace("\\", "\\\\").replace("\\\\\\\\", "\\\\")
        imdb_id = str(sys.argv[2])
        tmdb_mp4_instance = tmdb_mp4(imdb_id)
        if os.path.splitext(mp4)[1][1:] in valid_output_extensions:
            tmdb_mp4_instance.writeTags(mp4)
        else:
            print("Wrong file type")

if __name__ == '__main__':
    main()
