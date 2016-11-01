MP4 Conversion/Tagging Automation Script.
==============
Modifications to mdhiggins' version:

NOTE:
--------------
This is work in progress.
A lot of what I think is useful FOR MY NEEDS is implemented. The following is an incomplete list of things open:
- If launched directly from Sickrage during PostProcess via postConversion.py things are not working as expcted just yet. This is mainly due to the Staging logic not properly implemented in postConversion.py just yet. 
- DO NOT RUN postConversion.py. Rather schedule manual.py and use the Sickrage post_process plugin to trigger TORNADO processing via SR API (you only need to configure Sickrage in autoProcess.ini as usual, everything else happens on it's own)
- If using the CouchPotato plugin things are not working as expected, rather use manual.py.
- Generally speaking my ultimate usage pattern is to have manual.py on schedule, scavenge all new files, process them and make them available to Sickrage and CouchPotato via a 'release' folder that these 2 can monitor. As soon as manual.py finishes converting a file a trigger should fire PostProcessing in Sickrage and CouchPotato using API calls. I'm no fan of having SR and CP trigger mp4 conversions themselves in an uncontrolled fashion.

That being said here goes the changes so far:

Staging
--------------
Convert an input-file to a part-file and only transition to mp4 just before replication (Copy-To/Move-To)
This allows to exclude files from 3rd party apps while they're being converted.
The part file will be transitioned after all write operations are finished (that is after conversion, tagging, relocate atoms, ...).

Staging can be defined in autoProcess.ini using:
- `meks-staging = True|False` (default: True; make use of the staging logic or revert to traditional processing)
- `meks-staging-extension = part` (default: part; extension to append during staging)

Staging workflow:
- Input file 
- Conversion => Outputfile + ".part" 
- Write operations => Tagging on part-File => Atom operations (MOOV) on part-File 
- Transition => Rename to final mp4 file
- Replication => Copy-To => Move-To

h264 Preset and Quality
--------------
There are 2 new options in autoProcess.ini available for specifying preset and quality during conversions:
- `meks-video-quality = 20`
- `meks-h264-preset = medium`

Note: If video-bitrate was specified then this turns into ffmpeg -maxrate. See https://trac.ffmpeg.org/wiki/Encode/H.264

Recursive mass-processing
--------------
The manual processor (manual.py) has an option to specify an input folder rather than a file (nothing new).
However the processor walks the complete hierarchy below of this folder.

If you are like me and have all sorts of stuff in your incoming/download folder and don't want to have the converter attempt to process eg ISO images or EXE files, then a full hierarchy walk is pointless.

Therefore autoProcess.ini now supports specifying:
- `meks-walk-ignore = <ignore-files>` (eg: recode.ignore,ignore.part,ignore.skip)
During hierarchy walk the processor automatically skips a folder and all of it's subfolders and files if a file was found that matches <ignore-files>.

Example, say you have the following situation:
- `meks-walk-ignore = ignore.part,recode.skip`
- Hierarchy as follows:
`Download
Download/Apps - ['ignore.part']
Download/Videos
Download/ISO - ['recode.skip']`
- A hierarchy walk would then skip all files and subfolders in Apps/* and ISO/* and only allow processing of files directly in Download as well as Videos/*

Copy-To and Move-To by file type
--------------
Suppose you use this converter for converting and tagging movies as well as TV shows. Further down the chain, after conversion is finished and the file is ready for post processing by SR/CP, it might be useful to separate the output files in folders for movies and TV shows. Originally this was not possible as you could either copy all files or move all files to one or multiple folders, but you would end up with all files in the same folder.
You could (and still can) specify "multi-purpose" folders using `copy-to = /path/to/folder1|/path/to/folder2|/path/to/folderX`

This was changed so that Copy-to now allows the following syntax for folders by *type*:
`copy-to = movie:/path/to/moviefolder|tv:/path/to/tvfolder|/path/to/generic/folder`
This would result in all files which were tagged as movies to be copied to /path/to/moviefolder and /path/to/generic/folder
Consequently all TV shows would be copied to /path/to/tvfolder and /path/to/generic/folder
If a movie or TV show could not be tagged, then all type-folders will be ignored and only the "multi-purpose" generic folders are taken into account. If no generics are defined then Copy-to would behave as if it wasn't set at all.

Furthermore I saw no need in being able to specify Move-to. The Move-to option originally behaved the same as Copy-to but would delete (read: move away) the file from the original output location during replication, whereas Copy-to would only create copies and leave the file in the output original.
So since both options are roughly the same, I made `move-to = True|False` instead of String. By specifying `move-to = True` all Copy-to operations transform into Move-to. So if you specified a type-folder for movies and enabled move-to then all your converted and tagged movie files would first be copied to the movie type folder and deleted after copy was successful.

Post processing scripts extended:
--------------
- Fire CouchPotato Renamer using API (only fire if file was tagged as movie)
- Fire Sickrage PostProcessor using API (only fire if file was tagged as TV show)
- Dump ffprobe data to log after conversion (for keeping a log of conversions)
- All scripts were enabled to properly utilize logging facilities and no longer send to stdout but rather send output using loggers.

Editing of Metadata
--------------
Using `meks-metadata = <metadata-options>` in autoProcess.ini ffmpeg can be called using -metadata to edit/change metadata during conversion.

Change of TMDB API
--------------
This fork uses Celia Okley's [tmdbsimple](https://github.com/celiao/tmdbsimple), a completely different TMDB API which enables greater flexibility in searches (e.g. include year in search)
This is a drop-in replacement on the extension side as all methods from tmdb_mp4.py are still the same. However if you accessed the original TMDB API then those things would need to be adapted.
Due to this switch the whole GuessIt parsing features have improved too.

Misc changes
--------------
- Access to autoSettings.ini is unified:
`from readSettings import settingsProvider`
`settingsProvider().defaultSettings`
This can be extended using multiple providers for multiple configurations (say: different configs for Movies and TV shows)
eg: `settingsProvder().settingsMovies` or `settingsProvider().settingsTV`
- Similarily, access to logging is unified, eg:
`sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from _utils import LoggingAdapter
log = LoggingAdapter.getLogger()
anotherlog = LoggingAdapter.getLogger("testLogger")`
- manual.py adapted to Python logging rather than print()
- Media file validation unified to MkvtoMp4().validSource(), takes into account ffprobe information rather than just file extensions
- If an input file was detected as bad then move it out of the way by renaming it to ".bad"
- If `delete_original = False` then a rename operation automatically kicks in that appends ".recoded" to the input file. It's either delete or rename, leaving it untouched is no option.

Bugs/Caveats
--------------
- Deluge, uTorrent, NZBGET, SABNZBD, Sonarr are problably not working - not tested though (don't use them)
- Plex refresh works, however personally I have set SR and CP to handle Plex so I don't make use of the Plex interface.

MP4 Conversion/Tagging Automation Script.
==============

**Automatically converts media files downloaded by various programs to mp4 files, and tags them with the appropriate metadata from theTVDB or TMDB.**

Works on Windows, OSX, and Linux

Media Managers Supported:
- Sickbeard
- SickRage
- CouchPotato
- Sonarr

Downloaders Supported:
- SABNZBD
- NZBGet
- uTorrent
- Deluge Daemon

Requirements
--------------
- Python 2.7
- Python 3 beta support has arrived. Feel free to begin testing and report bugs
- FFMPEG and FFPROBE binaries
- Python setup_tools
- See PIP packages for additional requirements

Default Settings
--------------
1. Video - H264
2. Audio - AAC 2.0 with additional AC3 track when source has >2 channels (ex 5.1)
3. Subtitles - mov_text

Prerequesite PIP Package Installation Instructions
--------------
Note: Windows users should enter commands in Powershell - using '<' doesn't work in cmd
- `VC for Python 2.7` (Windows Users Only) - Download and install - http://www.microsoft.com/en-us/download/details.aspx?id=44266
- `setup_tools` - https://pypi.python.org/pypi/setuptools#installation-instructions
- `requests` - Run `pip install requests`
- `requests security package` - Run `pip install requests[security]`
- `requests-cache` - Run `pip install requests-cache`
- `babelfish` - Run `pip install babelfish`
- `guessit` - Run `pip install "guessit<2"` to use manual.py (requires guessit version 1, version 2 is a complete rewrite, still in alpha, and not backwards compatible)
- `subliminal`- Run `pip install "subliminal<2"` to enable automatically downloading subtitles
- `stevedore` - Run `pip install stevedore` (this will be automatically installed with subliminal)
- `dateutil` - Run `pip install python-dateutil` (this will be automatically installed with subliminal)
- `deluge-client` Run `pip install deluge-client` if you plan on using Deluge
- `qtfaststart` Run `pip install qtfaststart` to enable moving moov atom

General MP4 Configuration
--------------
1. Rename autoProcess.ini.sample to autoProcess.ini
2. Set the MP4 variables to your desired output
    - `ffmpeg` = Full path to FFMPEG.exe
    - `ffprobe` = Full path to FFPROBE.exe
    - `threads` = Number of threads for FFMPEG to use, default "auto"
    - `output_directory` = you may specify an alternate output directory. Leave blank to use the same directory that the source file is in. All processing will be done in this location. (Do not use for 'Automatically Add to iTunes' folder, iTunes will add prematurely, use `move_to`)
    - `copy_to` = you may specify additional directories for the final product to be replicated to. This will be the last step performed so the file copied will be fully processed. Directories may be separated with a `|` character
    - `move_to` = you may specify one final directory to move the completed file. (Use this option for the 'Automatically Add to iTunes' folder)
    - `output_extension` = mp4/m4v (must be one of these 2)
    - `output_format` = mp4/mov (must be one of these 2, mov provides better compatibility with iTunes/Apple, mp4 works better with other mobile devices)
    - `delete_original` = True/False
    - `relocate_moov` = True/False - relocates the MOOV atom to the beginning of the file for better streaming
    - `ios-audio` = creates a 2nd copy of an audio stream that will be iOS compatible (AAC Stereo) if the normal output will not be. If a stereo source stream is detected with this option enabled, an AAC stereo stream will be the only one produced (essentially overriding the codec option) to avoid multiple stereo audio stream copies in different codecs. Instead of 'true' you may also set this option to a specific codec to override the default.
    - `ios-first-track-only` = Applies the `ios-audio` option only to the first audio track encountered in the source video file. This prevents making dual audio streams for additional alternative language codecs or commentary tracks that may be present in the source file.
    - `ios-audio-filter` = Applies FFMPEG audio filter option to ONLY the iOS audio channels created by the script. iOS audio counterpart to the `audio-filter` option below.
    - `max-audio-channels` = Sets a maximum number of audio channels. This may provide an alternative to the iOS audio option, where instead users can simply select the desired output codec and the max number of audio channels without the creation of an additional audio track.
    - `video-codec` = set your desired video codecs. May specify multiple comma separated values (ex: h264, x264). The first value specified will be the default conversion choice when an undesired codec is encountered; any codecs specified here will be remuxed/copied rather than converted.
    - `video-bitrate` = allows you to set a maximum video bitrate in Kbps. If the source file exceeds the video-bitrate it will be transcoded to the specified video-bitrate, even if they source file is already in the correct video codec. If the source file is in the correct video codec and does not exceed the video-bitrate setting, then it will be copied without transcoding. Leave blank to disable this setting.
    - `video-max-width` = set a max video width to downsize higher resolution video files. Aspect ratio will be preserved.
    - `h264-max-level` = set your max h264 level. Use the decimal format. Levels lower than the specified value, if otherwise appropriate, will be copied without transcoding. Example - `4.0`.
    - `pix_fmt` = set the video pix_fmt. If you don't know what this is just leave it blank.
    - `audio-codec` = set your desired audio codecs. May specify multiple comma separated values (ex: ac3, aac). The first value specified will be the default conversion choice when an undesired codec is encountered; any codecs specified here will be remuxed/copied rather than converted.
    - `audio-channel-bitrate` = set the bitrate for each audio channel. Default is 256. Setting this value to 0 will attempt to mirror the bitrate of the audio source, but this can be unreliable as bitrates vary between different codecs.
    - `audio-language` = 3 letter language code for audio streams you wish to copy. Leave blank to copy all. Separate multiple audio streams with commas (ex: eng,spa)
    - `audio-default-language` = If an audio stream with an unidentified/untagged language is detected, you can default that language tag to whatever this value is (ex: eng). This is useful for many single-audio releases which don't bother to tag the audio stream as anything
    - `audio-filter` = Applies FFMPEG audio filter. Make sure you specify all parameters are you would using the `-af` option with FFMPEG command line
    - `subtitle-codec` = set your desired subtitle codec. If you're embedding subs, `mov_text` is the only option supported. If you're creating external subtitle files, `srt` or `webvtt` are accepted.
    - `subtitle-language` = same as audio-language but for subtitles. Set to `nil` to disable copying of subtitles.
    - `subtitle-language-default` = same as audio-language-default but for subtitles
    - `convert-mp4` = forces the script to reprocess and convert mp4 files as though they were mkvs. Good if you have old mp4's that you want to match your current codec configuration.
    - `fullpathguess` = True/False - When manually processing a file, enable to guess metadata using the full path versus just the file name. (Files shows placed in a 'Movies' folder will be recognized as movies, not as TV shows for example.)
    - `tagfile` = True/False - Enable or disable tagging file with appropriate metadata after encoding.
    - `tag-language` = en - Set your tag language for TMDB/TVDB entries metadata retrieval. Use either 2 or 3 character language codes.
    - `download-artwork` = Poster/Thumbnail/False - Enabled downloading and embeddeding of Season or Movie posters and embeddeding of that image into the mp4 as the cover image. For TV shows you may choose between the season artwork or the episode thumbnail by selecting the corresponding option.
    - `embed-subs` = True/False - Enabled by default. Embeds subtitles in the resulting MP4 file that are found embedded in the source file as well as external SRT/VTT files. Disabling embed-subs will cause the script to extract any subtitles that meet your language criteria into external SRT/VTT files. The script will also attempt to download SRT files if possible and this feature is enabled.
    - `download-subs` = True/False - When enabled the script will attempt to download subtitles of your specified languages automatically using subliminal and merge them into the final mp4 file.
    **YOU MUST INSTALL SUBLIMINAL AND ITS DEPENDENCIES FOR THIS TO WORK.** You must run `pip install subliminal` in order for this feature to be enabled.
    - `sub-providers` = Comma separated values for potential subtitle providers. Must specify at least 1 provider to enable `download-subs`. Providers include `podnapisi` `thesubdb` `opensubtitles` `tvsubtitles` `addic7ed`

Sick Beard Setup
--------------
1. Open Sickbeard's config.ini in Sick Beard installation folder
    - Set "extra_scripts" value in the general section to the full path to "python postConversion.py" using double backslashes
        - Example: `C:\\Python27\\python C:\\Scripts\\postConversion.py`
        - Make sure this is done while Sick Beard is not running or it will be reverted
2. Set the SickBeard variables in autoProcess.ini under the [Sickbeard] section:
    - `host` - default `localhost` - Sick Beard host address
    - `port` - default `8081` - Sick Beard port
    - `ssl` - `0`/`1`
    - `api_key` - Set this to your Sickbeard API key (options -> general, enable API in Sick Beard to get this key)
    - `web_root` - Set your Sickbeard webroot
    - `user` - Username
    - `password` - Password

SickRage Setup
--------------
1. Open the configuration page in Sickrage and scroll down to the option labelled "Extra Scripts". Here enter the path to python followed by the full script path. Examples:
    - `C:\\Python27\\python.exe C:\\sickbeard_mp4_automator\\postConversion.py`
    - `/usr/bin/python /home/user/sickbeard_mp4_automator/postConversion.py`
2. Set the Sickrage variables in autoProcess.ini under the [Sickrage] section:
    - `host` - default `localhost` - Sickrage host address (localhost)
    - `port` - default `8081` Sickrage port
    - `ssl` - `1` if enabled, `0` if not
    - `api_key` - Set this to your Sickrage API key
    - `web_root` - Set your Sickrage webroot
    - `user` - Username
    - `password` - Password

Sonarr Setup
--------------
1. Set your Sonarr settings in the autoProcess.ini file
    - `host` = Sonarr host address (localhost)    #Settings/General/Start-Up
    - `port` = Sonarr port (8989)                 #Settings/General/Start-Up
    - `ssl` = 1 if enabled, 0 if not              #Settings/General/Security
    - `apikey` = Sonarr API Key (required)        #Settings/General/Security
    - `web_root` = URL base empty or e.g. /tv     #Settings/General/Start-Up
2. Browse to the Settings>Download Client tab and enable advanced settings [Show].
3. Set the Drone Factory Interval' to 0 to disable it, and disable 'Completed Download Handling' in Sonarr settings. The script will trigger a specific path re-scan, allowing the mp4 conversion to be completed before Sonarr starts moving stuff around. This step is optional if you do not desire any processing between the downloading by whichever downloader you choose (NZB or Torrent), but is required if you wish to convert the file to an MP4 before it is handed back to Sonarr.
4. Setup the postSonarr.py script via Settings > Connect > Connections > + (Add)
    - `name` - postSonarr
    - `On Grab` - No
    - `On Download` - Yes
    - `On Upgrade` - Yes
    - `On Rename` - No
    - Filter Series Tags - optional
    - Windows Users
      - `Path` - Full path to your python executable
      - `Arguments` - Full path to `postSonarr.py`
    - Nonwindows Users
      - `Path` - Full path to `postSonarr.py`
      - `Arguments` - Leave blank

Couch Potato Setup
--------------
1. Set your Couch Potato settings to the autoProcess.ini file
    - `host` - default `localhost` - Couch Potato host address
    - `port` - default `5050` - Couch Potato port (5050)
    - `ssl` - `1` if enabled, `0` if not
    - `api_key` - Couch Potato API Key
    - `username` - your Couch Potato username
    - `password` - your Couch Potato password
2. Edit `main.py` in the `setup\PostProcess` folder
    - Set the path variable to the script location
    - By default it points to `C:\\Scripts\\`
    - Use double backslahses
2. Copy the PostProcess directory from the setup folder included with this script to the Couch Potato `custom_plugins` directory
    - Navigate to the About page in Couch Potato, where the installation directory is displayed.
    - Go to this folder and copy the PostProcess folder (the whole folder, not just the contents) to the Couch Potato `custom_plugins` directory
    - Delete any `.pyc` files you find.
    - Restart Couch Potato
    - Verify in Couch Potato logs that PostProcess was loaded.
3. If you're using one of the post download scripts ([SAB|NZBGet|uTorrent|deluge]PostProcess.py), disable automatic checking of the renamer folder, the script will automatically notify Couch Potato when it is complete to check for new videos to be renamed and relocated. Leaving this on may cause conflicts and CouchPotato may try to relocate/rename the file before processing is completed.
    - Set `Run Every` to `0`
    - Set `Force Every` to `0`
    - If you aren't using one of these scripts and are using an unsupported downloader, you will need to have CouchPotato periodically check the folder for files, otherwise the post downloader scripts will manually trigger a renamer scan. Using manual triggers is helpful because it prevents a coincidental renamer scan during other processing events.
4. Configure Downloaders
    - In `Settings > Downloaders` configure your labels or categories to match what you have configured in your respective downloader.

NZBGet Setup
--------------
1. Copy the script NZBGetPostProcess.py to NZBGet's script folder.
    - Default location is ~/downloads/scripts/
2. Start/Restart NZBGet
3. Configure NZBGETPOSTPROCESS
    - Access NZBGet's WebUI
        - Default `localhost:6789`
    - Go to `Settings`
    - Select `NZBGETPOSTPROCESS` option at the bottom of the left hand navigation panel and configure the options
        - `MP4_FOLDER` - default `~/sickbeard_mp4_automator/` - Location of the script. Use full path with trailing backslash.
        - `SHOULDCONVERT` - `True`/`False` - Convert file before passing to destination
        - `CP_CAT` - default `couchpotato` - category of downloads that will be passed to CouchPotato
        - `SONARR_CAT` - default `sonarr` - category of downloads that will be passed to Sonarr
        - `SICKBEARD_CAT` - default `sickbeard` - category of downloads that will be passed to Sickbeard
        - `SICKRAGE_CAT` - default `sickrage` - category of downloads that will be passed to Sickrage
        - `BYPASS_CAT` - default `bypass` - category of downloads that may be converted but won't be passed on further
    - Save changes
    - Reload NZBGet
4. Verify that whatever media manager you are using is assigning the category to match the label settings specified here so that file will be passed back to the appropriate location

SABNZBD Setup
--------------
1. Configure `SABNZBD` section of `autoProcess.ini`
    - `convert` - `True`/`False` - Allows for conversion of files before passing back to the respective download manager.
    - `sickbeard-category` - default `sickbeard` -  category that will be sent to Sickbeard for additional processing when download is complete
    - `sickrage-category` - default `sickrage` - category that will be sent to Sickrage for additional processing when download is complete
    - `couchpotato-category` - default `couchpotato` - category that will be sent to Couch Potato for additional processing when download is complete
    - `sonarr-category` - default `sonarr` - category that will be sent to Sonarr for additional processing when download is complete
    - `byapss-category` - default `bypass` - category that should be assigned to torrents that will not be sent anywhere when download is complete. Useful if you wish to convert files without additional processing
2. Point SABNZBD's script directory to the root directory where you have extract the script.
3. Configure categories. Categories will determine where the download is sent when it is finished
    - `Settings > Categories`
    - Configure `name` to match the settings from the `SABNZBD` section of `autoProcess.ini`
        - Default `sickbeard`
        - Default `sickrage`
        - Default `couchpotato`
        - Default `sonarr`
        - Default `bypass`
    - Select the SABPostProcess.py script
    - Save EACH category
4. Verify that whatever media manager you are using is assigning the label to match the label settings specified here so that file will be passed back to the appropriate location

uTorrent Setup
--------------
1. Verify that you have installed the **Requests library**
    - `pip install requests`
2. Launch uTorrent
3. Set `Run Program` option
    - Go to `Options > Preferences > Advanced > Run Program`
    - Point to `uTorrentPostProcess.py` with command line parameters: `%L %T %D %K %F %I %N` in that exact order.
3. Set your uTorrent settings in autoProcess.ini
    - `convert` - `True`/`False`. Allows for conversion of files before passing back to the respective download manager.
    - `sickbeard-label` - default `sickbeard` - uTorrent label that should be assigned to torrents that will be sent to Sickbeard for additional processing when download is complete.
    - `sickrage-label - default `sickrage` - uTorrent label that should be assigned to torrents that will be sent to Sickrage for additional processing when download is complete.
    - `couchpotato-label` - default `couchpotato` - uTorrent label that should be assigned to torrents that will be sent to Couch Potato for additional processing when download is complete.
    - `sonarr-label` - default `sonarr` - uTorrent label that should be assigned to torrents that will be sent to Sonarr for additional processing when download is complete.
    - `bypass-label` - default `bypass` - label that should be assigned to torrents that will not be sent anywhere when download is complete. Useful if you wish to convert files without additional processing.
    - `webui` - `True`/`False`. If `True` the script can change the state of the torrent.
    - `action_before` - stop/pause or any other action from http://help.utorrent.com/customer/portal/articles/1573952-actions---webapi
    - `action_after` - start/stop/pause/unpause/remove/removedata or any other action from http://help.utorrent.com/customer/portal/articles/1573952-actions---webapi
    - `hostname` - your uTorrent Web UI URL, eg `http://localhost:8080/` including the trailing slash.
    - `username` - your uTorrent Web UI username.
    - `password` - your uTorrent Web UI password.
4. Verify that whatever media manager you are using is assigning the label to match the label settings specified here so that file will be passed back to the appropriate location

Deluge Daemon
--------------
1. Verify that you have installed the **Gevent library**
    - `pip install gevent`
    - Windows users will need to also install the Microsoft Visual C++ Compiler for Python 2.7 for gevent to work. http://www.microsoft.com/en-us/download/details.aspx?id=44266
2. Create username and password for deluge daemon
    - Navigate to your deluge configuration folder
        - `%appdata%\Roaming\Deluge` in Windows
        - `/var/lib/deluge/.config/deluge/` in Linux
    - Open the `auth` file
    - Add a username and password in the format `<username>:<password>:<level>`. Replace <username> and <password> with your choice and level with your desired authentication level. Default level is `10`. Save auth.
        - Ex: `sampleuser:samplepass:10`
3. Start/Restart deluged
    - *deluged* not <i>deluge</i>
4. Access the WebUI
    - Default port is `8112`
    - Default password is `deluge`
5. Enabled the `Execute` plugin
    - Add event for `Torrent Complete`
    - Set path to the full path to `delugePostProcess.py` or `delugePostProcess.bat` for Windows users.
6. Configure the deluge options in `autoProcess.ini`
    - `sickbeard-label` - Deluge label that should be assigned to torrents that will be sent to Sickbeard for additional processing when download is complete.
    - `sickrage-label - Deluge label that should be assigned to torrents that will be sent to Sickrage for additional processing when download is complete.
    - `couchpotato-label` - Deluge label that should be assigned to torrents that will be sent to Couch Potato for additional processing when download is complete.
    - `sonarr-label` - Deluge label that should be assigned to torrents that will be sent to Sonarr for additional processing when download is complete.
    - `bypass-label` - label that should be assigned to torrents that will not be sent anywhere when download is complete. Useful if you wish to convert files without additional processing.
    - `convert` - `True`/`False`. Allows for conversion of files before passing back to the respective download manager.
    - `host` - your Deluge hostname. Default is `localhost`
    - `port` - Deluge daemon port. Default is `58846`. Do not confuse this with your WebUI port, which is different.
    - `username` - your Deluge username that you previously added to the `auth` file.
    - `password` - your Deluge password that you previously added to the `auth` file.
7. Verify that whatever downloader you are using is assigning the label to match the label settings specified here so that file will be passed back to the appropriate location

Plex Notification
--------------
Send a Plex notification as the final step when all processing is completed. This feature prevents a file from being flagged as "in use" by Plex before processing has completed.
1. Disable automatic refreshing on your Plex server
    - `Settings > Server > Library` and disable `Update my library automatically` and `Update my library periodically`.
2. Configure autoProcess.ini
    - `refresh` - `True`/`False` - Enable or disable the feature
    - `host` - Plex hostname. Default `localhost`
    - `port` - Plex port. Default `32400`
    - `token` - Plex Home Token

Post Process Scripts
--------------
The script suite supports the ability to write your own post processing scripts that will be executed when all the final processing has been completed. All scripts in the `./post_process` directory will be executed if the `post-process` option is set to `True` in `autoProcess.ini`. Scripts within the `./post_process/resources` directory are protected from execution if additional script resources are required.

The following environmental variables are available for usage:
- `MH_FILES` - JSON Array of all files created by the post processing script. The first file in the array is the primary file, and any additional files are copies created by the copy-to option
- `MH_TVDBID` - TVDB ID if file processed was a TV show and this information is available
- `MH_SEASON` - Season number if file processed was a TV show
- `MH_EPISODE` - Episode number if files processed was a TV show
- `MH_IMDBID` - IMDB ID if file processed was a movie
A sample script as well as an OS X 'Add to iTunes' script (`iTunes.py`) have been provided.
*Special thanks to jzucker2 for providing much of the initial code for this feature*

Manual Script Usage
--------------
To run the script manually, simply run the manual.py file and follow the prompts it presents.
If you wish to run it via the command line (good for batch operations) follow this format:

```
Help output
manual.py -h
usage: manual.py [-h] [-i INPUT] [-a] [-tv TVDBID] [-s SEASON] [-e EPISODE]
                 [-imdb IMDBID] [-tmdb TMDBID] [-nm] [-nc] [-nd]

Manual conversion and tagging script for sickbeard_mp4_automator

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        The source that will be converted. May be a file or a
                        directory
  -a, --auto            Enable auto mode, the script will not prompt you for
                        any further input, good for batch files. It will guess
                        the metadata using guessit
  -tv TVDBID, --tvdbid TVDBID
                        Set the TVDB ID for a tv show
  -s SEASON, --season SEASON
                        Specifiy the season number
  -e EPISODE, --episode EPISODE
                        Specify the episode number
  -imdb IMDBID, --imdbid IMDBID
                        Specify the IMDB ID for a movie
  -tmdb TMDBID, --tmdbid TMDBID
                        Specify theMovieDB ID for a movie
  -nm, --nomove         Overrides and disables the custom moving of file
                        options that come from output_dir and move-to
  -m, --moveto          Override move-to value setting in autoProcess.ini
                        changing the final destination of the file
  -nc, --nocopy         Overrides and disables the custom copying of file
                        options that come from output_dir and move-to
  -nt, --notag          Overrides and disables tagging when using the
                        automated option
  -nd, --nodelete       Overrides and disables deleting of original files
  -pr, --preserveRelative
                        Preserves relative directories when processing
                        multiple files using the copy-to or move-to
                        functionality
  -cmp4, --convertmp4   Overrides convert-mp4 setting in autoProcess.ini
                        enabling the reprocessing of mp4 files
```

Examples
```
Movies (using IMDB ID):
manual.py -i mp4path -m imdbid
Example: manual.py -i 'C:\The Matrix.mkv' -imdb tt0133093

Movies (using TMDB ID)
manual.py -i mp4path -tmdb tmdbid
Example: manual.py -i 'C:\The Matrix.mkv' -tmdb 603

TV
manual.py -i mp4path -tv tvdbid -s season -e episode
Example: manual.py -i 'C:\Futurama S03E10.mkv' -tv 73871‎ -s 3 -e 10

Auto Single File (will gather movie ID or TV show ID / season / spisode from the file name if possible)
manual.py -i mp4path -silent
Example: manual.py -i 'C:\Futurama S03E10.mkv' -a

Directory (you will be prompted at each file for the type of file and ID)
manual.py -i directory_path
Example: manual.py -i C:\Movies

Automated Directory (The script will attempt to figure out appropriate tagging based on file name)
manual.py -i directory_path -a
Example: manual.py -i C:\Movies -a

Process a directory but manually specific TVDB ID (Good for shows that don't correctly match using the guess)
manual.py -i directory -a -tv tvdbid
Example: manual.py -i C:\TV\Futurama\ -a -tv 73871
```
You may also simply run `manual.py -i 'C:\The Matrix.mkv'` and the script will prompt you for the missing information or attempt to guess based on the file name.
You may run the script with a `--auto` or `-a` switch, which will let the script guess the tagging information based on the file name, avoiding any need for user input. This is the most ideal option for large batch file operations.
The script may also be pointed to a directory, where it will process all files in the directory. If you run the script without the `-silent` switch, you will be prompted for each file with options on how to tag, to convert without tagging, or skip.

External Cover Art
--------------
To use your own cover art instead of what the script pulls from TMDB or TVDB, simply place an image file named cover.jpg or cover.png in the same directory as the input video before processing and it will be used.

Import External Subtitles
--------------
To import external subtitles, place the .srt file in the same directory as the file to be processed. The srt must have the same name as the input video file, as well as the 3 character language code for which the subtitle is. Subtitle importing obeys the langauge rules set in autoProcess.ini, so languages that aren't whitelisted will be ignored.

Naming example:
```
input mkv - The.Matrix.1999.mkv
subtitle srt - The.Matrix.1999.eng.srt
```

Common Errors
--------------
- `ImportError: No module named pkg_resources` - you need to install setuptools for python. See here: https://pypi.python.org/pypi/setuptools#installation-instructions
- Problems moving from downloader back to manager - you most likely haven't set up your categories correctly. The category options designated by SB/SR/CP/Sonarr need to match the ones set in your downloader either in the plugin options or in autoProcess.ini, and these categories ALL need to execute either SABPostProcess.py for SAB or NZBGetPostProcess.py for NZBGet. Make sure they match.

Credits
--------------
This project makes use of the following projects:
- http://www.sickbeard.com/
- http://couchpota.to/
- http://sabnzbd.org/
- http://github.com/senko/python-video-converter
- http://github.com/dbr/tvdb_api
- http://code.google.com/p/mutagen/
- http://imdbpy.sourceforge.net/
- http://github.com/danielgtaylor/qtfaststart
- http://github.com/clinton-hall/nzbToMedia
- http://github.com/wackou/guessit
- http://github.com/Diaoul/subliminal

Enjoy
