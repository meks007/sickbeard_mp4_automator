from __future__ import unicode_literals
import os
import time
import json
import sys
import shutil
import logging
import locale
import signal
#import pycountry

from subprocess import Popen, PIPE
from random import randint

from converter import Converter, FFMpegConvertError
from extensions import valid_input_extensions, valid_output_extensions, bad_subtitle_codecs, valid_subtitle_extensions, subtitle_codec_extensions
from babelfish import Language
from mutagen.mp4 import MP4, MP4Cover
from _utils import LoggingAdapter

console_encoding = locale.getdefaultlocale()[1] or 'UTF-8'

class MkvtoMp4:
    def __init__(self, settings=None, logger=None):
        if logger:
            self.log = logger
        else:
            self.log = LoggingAdapter.getLogger(__name__)

        self.options = None
        self.deletesubs = set()
        
        if settings is None:
            raise ValueError("Settings not supplied")
        self.settings = settings
        self.converter = Converter(settings.ffmpeg, settings.ffprobe)

    # Process a file from start to finish, with checking to make sure formats are compatible with selected settings
    def process(self, inputfile, reportProgress=False, original=None):
        delete = self.settings.delete
        rename = not delete
        deleted = False
        renamed = False
        deleted_original = False
        options = None
        
        valid = self.validSource(inputfile)
        if valid == False:
            return False
        elif valid == -1:
            self.moveBackAs(inputfile, original, "invalid")
            return False
        
        options = self.generateOptions(inputfile, original=original)

        try:
            if reportProgress:
                self.log.debug(json.dumps(options, sort_keys=False, indent=4))
            else:
                self.log.debug(json.dumps(options, sort_keys=False, indent=4))
        except:
            self.log.exception("Unable to log options")

        finaloutputfile, outputfile, inputfile, processed = self.convert(inputfile, options, reportProgress)
        if not outputfile:
            self.log.debug("Error converting, no outputfile present")
            return False
        
        if not processed:
            try:
                self.log.debug("Outputfile set to %s" % outputfile)
                if not outputfile == inputfile:
                    self.removeFile(outputfile, replacement=inputfile, copyReplace=True)
                else:
                    delete = False
                    rename = False
            except Exception as e:
                self.log.exception("Error moving file to output directory")
                delete = False
                rename = False
        
        if self.validSource(outputfile) == True:
            self.log.info("Successful conversion of %s!" % (inputfile))
            self.log.debug("Conversion successful: %s => %s" % (inputfile, outputfile))
            
            if delete:
                self.log.debug("Attempting to remove %s" % inputfile)
                if self.removeFile(inputfile):
                    deleted = True
            if rename:
                self.log.debug("Attempting to rename %s" % inputfile)
                if self.moveBackAs(inputfile, inputfile, "recoded"):
                    renamed = True
                
            if original is not None:
                self.log.debug("Attempting to remove %s" % original)
                if self.removeFile(original):
                    deleted_original = True
            
            if self.settings.downloadsubs:
                for subfile in self.deletesubs:
                    self.log.debug("Attempting to remove subtitle %s" % subfile)
                    if self.removeFile(subfile):
                        self.log.debug("Subtitle %s deleted" % subfile)
                    else:
                        self.log.debug("Unable to delete subtitle %s" % subfile)
    
            dim = self.getDimensions(outputfile)
            
            return {'input': inputfile,
                    'output': outputfile,
                    'finaloutput': finaloutputfile,
                    'options': options,
                    'input_deleted': deleted,
                    'original_deleted': deleted_original,
                    'x': dim['x'],
                    'y': dim['y']}
        
        else:
            self.log.error("Outputfile probed negative, abort")
            if original is not None:
                self.removeFile(inputfile)
                self.moveBackAs(original, original, "invalid")
            else:
                self.moveBackAs(inputfile, inputfile, "invalid")
            self.removeFile(outputfile)
            return False

    # meks customization - start
    # Determine if a source video file is in a valid format
    def validSource(self, inputfile):
        input_dir, filename, input_extension = self.parseFile(inputfile)
        
        self.log.debug("Check if video file is valid - %s" % inputfile)
        
        # Make sure the input_extension is some sort of recognized extension, and that the file actually exists
        if (input_extension.lower() in valid_input_extensions or input_extension.lower() in valid_output_extensions or self.settings.meks_staging and input_extension.lower() == self.settings.meks_stageext.lower()):
            if (os.path.isfile(inputfile)):
                info = self.converter.probe(inputfile)
                
                if info is not None and info.format.duration > 0:
                    self.log.debug("Video file is valid")
                    return True
                else:
                    self.log.error("Video file probed negative - assuming bad")
                    return -1
            else:
                self.log.debug("Video file was not found")
                return False
        else:
            self.log.debug("Video file extension %s is invalid" % input_extension)
            return False
    # meks customization - end
    
    # Determine if a file meets the criteria for processing
    def needProcessing(self, inputfile):
        input_dir, filename, input_extension = self.parseFile(inputfile)
        
        self.log.debug("Check if video file needs processing - %s" % inputfile)
        
        # Make sure input and output extensions are compatible. If processMP4 is true, then make sure the input extension is a valid output extension and allow to proceed as well
        if (input_extension.lower() in valid_input_extensions or (self.settings.processMP4 is True and input_extension.lower() in valid_output_extensions)) and self.settings.output_extension.lower() in valid_output_extensions:
            self.log.debug("Processing is required")
            return True
        else:
            self.log.debug("Processing is NOT required")
            return False

    # Get values for width and height to be passed to the tagging classes for proper HD tags
    def getDimensions(self, inputfile):
        info = self.converter.probe(inputfile)
        
        if info is not None:
            self.log.debug("Dimensions - Height: %s" % info.video.video_height)
            self.log.debug("Dimensions - Width:  %s" % info.video.video_width)
    
            return {'y': info.video.video_height,
                    'x': info.video.video_width}
        return { 'y': 0, 'x': 0 }
           
    # Estimate the video bitrate
    def estimateVideoBitrate(self, info):
        total_bitrate = info.format.bitrate
        audio_bitrate = 0
        for a in info.audio:
            audio_bitrate += a.bitrate

        self.log.debug("Total bitrate is %s" % info.format.bitrate)
        self.log.debug("Total audio bitrate is %s" % audio_bitrate)
        self.log.debug("Estimated video bitrate is %s" % (total_bitrate - audio_bitrate))
        return ((total_bitrate - audio_bitrate) / 1000) * .95

    # Generate a list of options to be passed to FFMPEG based on selected settings and the source file parameters and streams
    def generateOptions(self, inputfile, original=None):
        # Get path information from the input file
        input_dir, filename, input_extension = self.parseFile(inputfile)

        info = self.converter.probe(inputfile)

        # Video stream
        self.log.info("Reading video stream")
        self.log.info("Video codec detected: %s" % info.video.codec)

        try:
            vbr = self.estimateVideoBitrate(info)
        except:
            vbr = info.format.bitrate / 1000

        if info.video.codec.lower() in self.settings.vcodec and self.settings.meks_copysamevcodec:
            vcodec = 'copy'
        else:
            vcodec = self.settings.vcodec[0]
        vbitrate = self.settings.vbitrate if self.settings.vbitrate else vbr

        self.log.debug("Pix Fmt: %s" % info.video.pix_fmt)
        if self.settings.pix_fmt and info.video.pix_fmt.lower() not in self.settings.pix_fmt:
            vcodec = self.settings.vcodec[0]

        if self.settings.vbitrate is not None and vbr > self.settings.vbitrate:
            self.log.debug("Overriding video bitrate. Codec cannot be copied because video bitrate is too high.")
            vcodec = self.settings.vcodec[0]
            vbitrate = self.settings.vbitrate

        if self.settings.vwidth is not None and self.settings.vwidth < info.video.video_width:
            self.log.debug("Video width is over the max width, it will be downsampled. Video stream can no longer be copied.")
            vcodec = self.settings.vcodec[0]
            vwidth = self.settings.vwidth
        else:
            vwidth = None

        if '264' in info.video.codec.lower() and self.settings.h264_level and info.video.video_level and (info.video.video_level / 10 > self.settings.h264_level):
            self.log.info("Video level %0.1f" % (info.video.video_level / 10))
            vcodec = self.settings.vcodec[0]

        self.log.debug("Video codec: %s" % vcodec)
        self.log.debug("Video bitrate: %s" % vbitrate)

        # Audio streams
        self.log.info("Reading audio streams")

        overrideLang = True
        for a in info.audio:
            try:
                if a.metadata['language'].strip() == "" or a.metadata['language'] is None:
                    a.metadata['language'] = 'und'
            except KeyError:
                a.metadata['language'] = 'und'
            if (a.metadata['language'] == 'und' and self.settings.adl) or (self.settings.awl and a.metadata['language'].lower() in self.settings.awl):
                overrideLang = False
                break

        if overrideLang:
            self.settings.awl = None
            self.log.info("No audio streams detected in any appropriate language, relaxing restrictions so there will be some audio stream present.")

        audio_settings = {}
        l = 0
        for a in info.audio:
            try:
                if a.metadata['language'].strip() == "" or a.metadata['language'] is None:
                    a.metadata['language'] = 'und'
            except KeyError:
                a.metadata['language'] = 'und'

            self.log.info("Audio detected for stream #%s: %s [%s]" % (a.index, a.codec, a.metadata['language']))

            # Set undefined language to default language if specified
            if self.settings.adl is not None and a.metadata['language'] == 'und':
                self.log.debug("Undefined language detected, defaulting to [%s]" % self.settings.adl)
                a.metadata['language'] = self.settings.adl

            # Proceed if no whitelist is set, or if the language is in the whitelist
            if self.settings.awl is None or a.metadata['language'].lower() in self.settings.awl:
                # Create iOS friendly audio stream if the default audio stream has too many channels (iOS only likes AAC stereo)
                if self.settings.iOS and a.audio_channels > 2:
                    iOSbitrate = 256 if (self.settings.abitrate * 2) > 256 else (self.settings.abitrate * 2)
                    self.log.debug("Creating audio stream %s from source audio stream %s [iOS-audio]" % (str(l), a.index))
                    self.log.debug("Audio codec: %s" % self.settings.iOS[0])
                    self.log.debug("Channels: 2")
                    self.log.debug("Filter: %s" % self.settings.iOSfilter)
                    self.log.debug("Bitrate: %s" % iOSbitrate)
                    self.log.debug("Language: %s" % a.metadata['language'])
                    if l == 0:
                        disposition = 'default'
                        self.log.debug("Audio track is number %s setting disposition to %s" % (str(l), disposition))
                    else:
                        disposition = 'none'
                        self.log.debug("Audio track is number %s setting disposition to %s" % (str(l), disposition))
                    audio_settings.update({l: {
                        'map': a.index,
                        'codec': self.settings.iOS[0],
                        'channels': 2,
                        'bitrate': iOSbitrate,
                        'filter': self.settings.iOSfilter,
                        'language': a.metadata['language'],
                        'disposition': disposition,
                    }})
                    l += 1
                # If the iOS audio option is enabled and the source audio channel is only stereo, the additional iOS channel will be skipped and a single AAC 2.0 channel will be made regardless of codec preference to avoid multiple stereo channels
                self.log.debug("Creating audio stream %s from source stream %s" % (str(l), a.index))
                if self.settings.iOS and a.audio_channels <= 2:
                    self.log.debug("Overriding default channel settings because iOS audio is enabled but the source is stereo [iOS-audio]")
                    acodec = 'copy' if a.codec in self.settings.iOS else self.settings.iOS[0]
                    audio_channels = a.audio_channels
                    afilter = self.settings.iOSfilter
                    abitrate = a.audio_channels * 128 if (a.audio_channels * self.settings.abitrate) > (a.audio_channels * 128) else (a.audio_channels * self.settings.abitrate)
                else:
                    # If desired codec is the same as the source codec, copy to avoid quality loss
                    acodec = 'copy' if a.codec.lower() in self.settings.acodec and self.settings.meks_copysameacodec else self.settings.acodec[0]
                    # Audio channel adjustments
                    if self.settings.maxchannels and a.audio_channels > self.settings.maxchannels:
                        audio_channels = self.settings.maxchannels
                        if acodec == 'copy':
                            acodec = self.settings.acodec[0]
                        abitrate = self.settings.maxchannels * self.settings.abitrate
                    else:
                        audio_channels = a.audio_channels
                        abitrate = a.audio_channels * self.settings.abitrate
                    # Bitrate calculations/overrides
                    if self.settings.abitrate is 0:
                        self.log.debug("Attempting to set bitrate based on source stream bitrate")
                        try:
                            abitrate = a.bitrate / 1000
                        except:
                            self.log.warning("Unable to determine audio bitrate from source stream %s, defaulting to 256 per channel" % a.index)
                            abitrate = a.audio_channels * 256
                    afilter = self.settings.afilter

                self.log.debug("Audio codec: %s" % acodec)
                self.log.debug("Channels: %s" % audio_channels)
                self.log.debug("Bitrate: %s" % abitrate)
                self.log.debug("Language: %s" % a.metadata['language'])
                self.log.debug("Filter: %s" % afilter)

                # If the iOSFirst option is enabled, disable the iOS option after the first audio stream is processed
                if self.settings.iOS and self.settings.iOSFirst:
                    self.log.debug("Not creating any additional iOS audio streams")
                    self.settings.iOS = False

                # Set first track as default disposition
                if l == 0:
                    disposition = 'default'
                    self.log.debug("Audio Track is number %s setting disposition to %s" % (a.index, disposition))
                else:
                    disposition = 'none'
                    self.log.debug("Audio Track is number %s setting disposition to %s" % (a.index, disposition))

                audio_settings.update({l: {
                    'map': a.index,
                    'codec': acodec,
                    'channels': audio_channels,
                    'bitrate': abitrate,
                    'filter': afilter,
                    'language': a.metadata['language'],
                    'disposition': disposition,
                }})

                if acodec == 'copy' and a.codec == 'aac' and self.settings.meks_adtstoasc:
                    audio_settings[l]['bsf'] = 'aac_adtstoasc'
                l = l + 1

        # Subtitle streams
        subtitle_settings = {}
        l = 0
        self.log.debug("Reading subtitle streams")
        for s in info.subtitle:
            try:
                if s.metadata['language'].strip() == "" or s.metadata['language'] is None:
                    s.metadata['language'] = 'und'
            except KeyError:
                s.metadata['language'] = 'und'

            self.log.info("Subtitle detected for stream #%s: %s [%s]" % (s.index, s.codec, s.metadata['language']))

            # Set undefined language to default language if specified
            if self.settings.sdl is not None and s.metadata['language'] == 'und':
                self.log.debug("Undefined language detected, defaulting to [%s]" % self.settings.sdl)
                s.metadata['language'] = self.settings.sdl
            # Make sure its not an image based codec
            if s.codec.lower() not in bad_subtitle_codecs and self.settings.embedsubs:

                # Proceed if no whitelist is set, or if the language is in the whitelist
                if self.settings.swl is None or s.metadata['language'].lower() in self.settings.swl:
                    subtitle_settings.update({l: {
                        'map': s.index,
                        'codec': self.settings.scodec[0],
                        'language': s.metadata['language'],
                        'encoding': self.settings.subencoding,
                        # 'forced': s.sub_forced,
                        # 'default': s.sub_default
                    }})
                    self.log.debug("Creating subtitle stream %s from source stream %s" % (l, s.index))
                    l = l + 1
            elif s.codec.lower() not in bad_subtitle_codecs and not self.settings.embedsubs:
                if self.settings.swl is None or s.metadata['language'].lower() in self.settings.swl:
                    for codec in self.settings.scodec:
                        ripsub = {0: {
                            'map': s.index,
                            'codec': codec,
                            'language': s.metadata['language']
                        }}
                        options = {
                            'format': codec,
                            'subtitle': ripsub,
                        }

                        try:
                            extension = subtitle_codec_extensions[codec]
                        except:
                            self.log.info("Wasn't able to determine subtitle file extension, defaulting to '.srt'")
                            extension = 'srt'

                        forced = ".forced" if s.sub_forced else ""

                        input_dir, filename, input_extension = self.parseFile(inputfile)
                        output_dir = input_dir if self.settings.output_dir is None else self.settings.output_dir
                        outputfile = os.path.join(output_dir, filename + "." + s.metadata['language'] + forced + "." + extension)

                        i = 2
                        while os.path.isfile(outputfile):
                            self.log.debug("%s exists, appending %s to filename" % (outputfile, i))
                            outputfile = os.path.join(output_dir, filename + "." + s.metadata['language'] + forced + "." + str(i) + "." + extension)
                            i += 1
                        try:
                            self.log.info("Ripping %s subtitle from source stream %s into external file" % (s.metadata['language'], s.index))
                            conv = self.converter.convert(inputfile, outputfile, options, timeout=None)
                            for timecode in conv:
                                    pass

                            self.log.info("%s created" % outputfile)
                        except:
                            self.log.exception("Unabled to create external subtitle file for stream %s" % (s.index))

        # Attempt to download subtitles if they are missing using subliminal
        languages = set()
        try:
            if self.settings.downloadsubs:
                if self.settings.swl:
                    for alpha3 in self.settings.swl:
                        languages.add(Language(alpha3))
                elif self.settings.sdl:
                    languages.add(Language(self.settings.sdl))
                else:
                    self.settings.downloadsubs = False
                    self.log.error("No valid subtitle language specified, cannot download subtitles")
        except:
            self.log.exception("Unable to verify subtitle languages for download")
            self.settings.downloadsubs = False

        if self.settings.downloadsubs:
            import subliminal
            self.log.info("Attempting to download subtitles")

            # Attempt to set the dogpile cache
            try:
                subliminal.region.configure('dogpile.cache.memory')
            except:
                pass

            try:
                video = subliminal.scan_video(os.path.abspath(inputfile), subtitles=True, embedded_subtitles=True)
                subtitles = subliminal.download_best_subtitles([video], languages, hearing_impaired=False, providers=self.subproviders)
                try:
                    subliminal.save_subtitles(video, subtitles[video])
                except:
                    # Support for older versions of subliminal
                    subliminal.save_subtitles(subtitles)
                    self.log.info("Please update to the latest version of subliminal")
            except Exception as e:
                self.log.info("Unable to download subtitles", exc_info=True)
                self.log.debug("Unable to download subtitles", exc_info=True)
        # External subtitle import
        if self.settings.embedsubs:  # Don't bother if we're not embeddeding any subtitles
            src = 1  # FFMPEG input source number
            for dirName, subdirList, fileList in os.walk(input_dir):
                for fname in fileList:
                    subname, subextension = os.path.splitext(fname)
                    # Watch for appropriate file extension
                    if subextension[1:] in valid_subtitle_extensions:
                        x, lang = os.path.splitext(subname)
                        lang = lang[1:]
                        # Using bablefish to convert a 2 language code to a 3 language code
                        if len(lang) is 2:
                            try:
                                babel = Language.fromalpha2(lang)
                                lang = babel.alpha3
                            except:
                                pass
                        # If subtitle file name and input video name are the same, proceed
                        if x == filename:
                            self.log.info("External %s subtitle file detected" % lang)
                            if self.settings.swl is None or lang in self.settings.swl:

                                self.log.info("Creating subtitle stream %s by importing %s" % (l, fname))

                                subtitle_settings.update({l: {
                                    'path': os.path.join(dirName, fname),
                                    'source': src,
                                    'map': 0,
                                    'codec': 'mov_text',
                                    'language': lang}})

                                self.log.debug("Path: %s" % os.path.join(dirName, fname))
                                self.log.debug("Source: %s" % src)
                                self.log.debug("Codec: mov_text")
                                self.log.debug("Langauge: %s" % lang)

                                l = l + 1
                                src = src + 1

                                self.deletesubs.add(os.path.join(dirName, fname))

                            else:
                                self.log.info("Ignoring %s external subtitle stream due to language %s" % (fname, lang))

        # Collect all options
        options = {
            'format': self.settings.output_format,
            'video': {
                'codec': vcodec,
                'map': info.video.index,
                'bitrate': vbitrate,
                'level': self.settings.h264_level,
                'id3v2vers': self.settings.meks_id3v2vers
            },
            'audio': audio_settings,
            'subtitle': subtitle_settings,
            'preopts': ['-fix_sub_duration'],
            'postopts': [],
        }

        # in h264, drop the constant bitrate and use the recommended quality settings.  ffmpeg default is 23 but our default is 20.
        if vcodec == "h264" or vcodec == "h264qsv":
            del options['video']['bitrate']
            options['video']['quality'] = self.settings.meks_video_quality if self.settings.meks_video_quality else 23
            options['video']['preset'] = self.settings.meks_h264_preset if self.settings.meks_h264_preset else 'medium'
            if self.settings.vbitrate is not None:
                options['video']['maxbitrate'] = self.settings.vbitrate

        # If using h264qsv, add the codec in front of the input for decoding
        if vcodec == "h264qsv" and info.video.codec.lower() == "h264" and self.settings.qsv_decoder and (info.video.video_level / 10) < 5:
            options['preopts'].extend(['-vcodec', 'h264_qsv'])
        if vcodec == "h264qsv" and (info.video.video_level / 10) < 5:
            options['video']['look_ahead'] = self.settings.meks_qsv_lookahead
            if self.settings.meks_qsv_lookahead > 0:
                del options['video']['quality']

        if self.settings.meks_metadata:
            options['video']['metadata'] = self.settings.meks_metadata
        
        # Add width option
        if vwidth:
            options['video']['width'] = vwidth

        # Add pix_fmt
        if self.settings.pix_fmt:
            options['video']['pix_fmt'] = self.settings.pix_fmt[0]
        
        self.options = options

        return options

    # Encode a new file based on selected options, built in naming conflict resolution
    def convert(self, inputfile, options, reportProgress=False):
        self.log.info(">>> Converting ...")
        
        processed = False
        input_dir, filename, input_extension = self.parseFile(inputfile)
        output_dir = input_dir if self.settings.output_dir is None else self.settings.output_dir
        try:
            outputfile = os.path.join(output_dir.decode(sys.getfilesystemencoding()), filename.decode(sys.getfilesystemencoding()) + "." + self.settings.output_extension).encode(sys.getfilesystemencoding())
        except:
            outputfile = os.path.join(output_dir, filename + "." + self.settings.output_extension)
        
        if os.path.isfile(outputfile):
            self.log.debug("Output file exists - randomizing file name")
            f, e = os.path.splitext(outputfile)
            outputfile = f + "_" + str(randint(1000,9999)) + e
        
        self.log.debug("  Input directory: %s" % input_dir)
        self.log.debug("  File name: %s" % filename)
        self.log.debug("  Input extension: %s" % input_extension)
        self.log.debug("  Output directory: %s" % output_dir)
        if self.settings.meks_staging:
            finaloutputfile = outputfile
            outputfile = outputfile + "." + self.settings.meks_stageext
            self.log.debug("  Staging file: %s" % outputfile)
            self.log.debug("  Output file: %s" % finaloutputfile)
        else:
            finaloutputfile = None
            self.log.debug("  Output file: %s" % outputfile)
        
        if os.path.abspath(inputfile) == os.path.abspath(outputfile):
            try:
                self.log.debug("Renaming original file to %s" % inputfile)
                os.rename(inputfile, inputfile + ".original")
                inputfile = inputfile + ".original"
            except:
                i = 2
                while os.path.isfile(outputfile):
                    outputfile = os.path.join(output_dir, filename + "(" + str(i) + ")." + self.settings.output_extension)
                    i += i
                self.log.debug("Unable to rename input file. Setting output file name to %s" % outputfile)
    
        if self.needProcessing(inputfile):
            conv = self.converter.convert(inputfile, outputfile, options, timeout=None, preopts=options['preopts'], postopts=options['postopts'])
    
            try:
                for timecode in conv:
                    if reportProgress:
                        try:
                            sys.stdout.write('\r')
                            sys.stdout.write('[{0}] {1}%'.format('#' * (timecode / 10) + ' ' * (10 - (timecode / 10)), timecode))
                        except:
                            sys.stdout.write(str(timecode))
                        sys.stdout.flush()
    
                self.log.info("%s created" % outputfile)
    
                try:
                    os.chmod(outputfile, self.settings.permissions)  # Set permissions of newly created file
                except:
                    self.log.exception("Unable to set new file permissions")
                
                processed = True
            except FFMpegConvertError as e:
                self.log.exception("Error converting file, FFMPEG error")
                self.log.error(e.cmd)
                self.log.error(e.output)
                if os.path.isfile(outputfile):
                    self.removeFile(outputfile)
                    self.log.error("%s deleted" % outputfile)
                outputfile = None

        return finaloutputfile, outputfile, inputfile, processed

    # Break apart a file path into the directory, filename, and extension
    def parseFile(self, path):
        path = os.path.abspath(path)
        input_dir, filename = os.path.split(path)
        filename, input_extension = os.path.splitext(filename)
        input_extension = input_extension[1:]
        return input_dir, filename, input_extension

    # Process a file with QTFastStart, removing the original file
    def QTFS(self, inputfile):
        input_dir, filename, input_extension = self.parseFile(inputfile)
        temp_ext = '.QTFS'
        # Relocate MOOV atom to the very beginning. Can double the time it takes to convert a file but makes streaming faster
        if self.parseFile(inputfile)[2] in valid_output_extensions and os.path.isfile(inputfile) and self.settings.relocate_moov:
            from qtfaststart import processor, exceptions

            self.log.info("Relocating MOOV atom to start of file")

            try:
                outputfile = inputfile.decode(sys.getfilesystemencoding()) + temp_ext
            except:
                outputfile = inputfile + temp_ext

            # Clear out the temp file if it exists
            if os.path.exists(outputfile):
                self.removeFile(outputfile, 0, 0)

            try:
                processor.process(inputfile, outputfile)
                try:
                    os.chmod(outputfile, self.settings.permissions)
                except:
                    self.log.exception("Unable to set file permissions")
                # Cleanup
                if self.removeFile(inputfile, replacement=outputfile):
                    return outputfile
                else:
                    self.log.error("Error cleaning up QTFS temp files")
                    return False
            except exceptions.FastStartException:
                self.log.warning("QT FastStart did not run - perhaps moov atom was at the start already")
                return inputfile

    def transitionStaging(self, outputfile, finaloutputfile, forceStaging=False):
        if (forceStaging or self.settings.meks_staging) and outputfile is not None and finaloutputfile is not None:
            if not outputfile == finaloutputfile:
                try:
                    if self.removeFile(finaloutputfile, 2, 10, outputfile):
                        outputfile = finaloutputfile
                        self.log.info("Transitioned staging file to output file %s" % outputfile)
                    else:
                        self.log.error("Something happened during transition")
                        return False
                except:
                    self.log.exception("Unable to transition to final output file")
                    return False
        return outputfile
    
    def getFfprobeData(self, inputfile):
        cmds = [self.settings.ffprobe, '-v', 'quiet', '-print_format', 'json', '-show_streams', '-show_format', inputfile]
        p = Popen(cmds, shell=False, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=(os.name != 'nt'), startupinfo=None)
        stdout_data, _ = p.communicate()
        stdout_data = stdout_data.decode(console_encoding, errors='ignore')
        data = json.loads(stdout_data)
        return data
    
    def getPrimaryLanguage(self, inputfile, iso='alpha2'):
        lang = self.settings.taglanguage
        data = self.getFfprobeData(inputfile)
        
        if iso not in ['alpha2','alpha3']:
            log.error("Language conversion to %s is not supported. Falling back to alpha2." % iso)
            iso = 'alpha2'
        
        try:
            if not self.settings.meks_taglangauto:
                raise Exception
            
            for stream in data["streams"]:
                if stream['index'] == 1 and stream['codec_type'] == 'audio':
                    metalang = stream["tags"]["language"]
                    lang = metalang if not metalang == 'und' else lang
                    
                    try:
                        l = Language.fromalpha3t(lang)
                    except:
                        try:
                            l = Language.fromalpha3b(lang)
                        except:
                            try:
                                l = Language.fromalpha2(lang)
                            except:
                                raise Exception
                    
                    if iso == 'alpha2':
                        lang = [l.alpha2, l.name]
                    elif iso == 'alpha3':
                        lang = [l.alpha3, l.name]
                    
                    self.log.debug("Primary audio language is %s (%s)" % tuple(reversed(lang)))
                    return lang
        except:
            lang = self.settings.taglanguage
            self.log.debug("Unable to determine audio language or auto-detect is disabled, falling back to %s" % lang)
            pass
        return [lang, Language.fromalpha2(lang).name]
    
    def tvOrMovie(self, inputfile):
        data = self.getFfprobeData(inputfile)
        try:
            if "encoder" in data["format"]["tags"]:
                if "imdb" in data["format"]["tags"]["encoder"]:
                    self.log.debug("Identified video as movie with IMDB ID")
                    return 1, ["movie", "all"]
                elif "tmdb" in data["format"]["tags"]["encoder"]:
                    self.log.debug("Identified video as movie with TMDB ID")
                    return 2, ["movie", "all"]
                elif "tvdb" in data["format"]["tags"]["encoder"]:
                    self.log.debug("Identified video as TV show with TvDB ID")
                    return 3, ["tv", "all"]
            elif "show" in data["format"]["tags"]:
                self.log.debug("Identified video as TV show without ID")
                return 3, ["tv", "all"]
            self.log.debug("Unable to properly identify type of video, falling back to unknown")
        except:
            self.log.exception("Error determining if file is TV or Movie, falling back to unknown")
        self.log.info("No type-based Copy-to operations will be executed, file is not tagged.")
        return 0, ["all"]
    
    def tagRename(self, outputfile, finaloutput, tmkey, tagmp4):
        import guessit
        
        staging = False
        l = []
        
        if self.settings.meks_tagrename:
            if self.settings.meks_staging:
                o = finaloutput
            else:
                o = outputfile
            
            lang = self.getPrimaryLanguage(o)
            if tmkey == 1 or tmkey == 2:
                l = [tagmp4.title, tagmp4.date[:4], lang[1], self.settings.output_extension]
                f = "%s (%s) %s.%s" % tuple(l)
                g = guessit.guess_file_info(f)
                f = ("%s %s %s.%s" % (g['title'], g['year'], lang[1], self.settings.output_extension)).replace(' ', '.')
            elif tmkey == 3:
                l = [tagmp4.show, tagmp4.airdate[:4], str(tagmp4.season).zfill(2), str(tagmp4.episode).zfill(2), tagmp4.title, lang[1], self.settings.output_extension]
                f = "%s (%s) S%sE%s %s %s.%s" % tuple(l)
                g = guessit.guess_file_info(f)
                f = ("%s %s S%sE%s %s %s.%s" % (g['series'], g['year'], str(g['season']).zfill(2), str(g['episodeNumber']).zfill(2), g['title'], lang[1], self.settings.output_extension)).replace(' ', '.')
            if len(l):
                self.log.debug("Temporarily enabled staging due to tag rename operation")
                staging = True
                
                od = os.path.split(o)[0]
                finaloutput = os.path.join(od, f)
                self.log.debug("Queued rename:")
                self.log.debug("  Previous final output file: %s" % o)
                self.log.debug("  New final output file: %s" % finaloutput)
        return [staging, finaloutput]
        
    def cptoDestinations(self, cptypes):
        cpto = []
        for cptype in cptypes:
            cpto.extend(self.settings.copyto[cptype] if cptype in self.settings.copyto else [])
            self.log.debug("Appended Copy-to destinations for %s" % cptype)
        cpto = set(cpto)
        self.log.debug("Copy-to destinations for types %s: %s" % (", ".join(cptypes), ", ".join(cpto)))
        return cpto
    
    # Makes additional copies of the input file in each directory specified in the copy_to option
    def replicate(self, process_output, relativePath=None):
        self.log.info(">>> Replicating ...")
        
        tmkey, cptypes = self.tvOrMovie(process_output['output'])
        cpdests = self.cptoDestinations(cptypes)
        
        forceStaging, finaloutput  = self.tagRename(process_output['output'], process_output['finaloutput'], tmkey, process_output['tag'])
        
        # transition from staging to final just before replication.
        # best time to transition since all conversions are already done at this point.
        try:
            inputfile = self.transitionStaging(process_output['output'], finaloutput, forceStaging=forceStaging)
            if not inputfile:
                return [process_output['output']]
        except:
            raise TypeError("invalid output data")
        
        files = [inputfile]
        if len(cpdests):
            self.log.debug("Copy-to option is enabled")
            for cpdest in cpdests:
                self.log.debug("Copy %s to %s" % (inputfile, cpdest))
                if (relativePath):
                    cpdest = os.path.join(cpdest, relativePath)
                    if not os.path.exists(cpdest):
                        os.makedirs(cpdest)
                copytofile = os.path.join(cpdest, os.path.split(inputfile)[1])
                if not inputfile == copytofile and not copytofile in files:
                    try:
                        self.removeFile(copytofile, 2, 10, inputfile, True)
                        files.append(copytofile)
                        self.log.info("Copied output file to final destination %s" % cpdest)
                    except Exception as e:
                        raise(e)
                else:
                    self.log.error("Unable to copy over input file")

        if self.settings.moveto and len(cpdests):
            self.log.debug("Move-to option is enabled")
            if len(files) > 1:
                try:
                    self.removeFile(files[0], 2, 10, None)
                    del files[0]
                    self.log.info("Copy operation was executed as Move.")
                except Exception as e:
                    raise(e)
            else:
                self.log.error("No file copies were recorded, refusing to relocate output file")
        
        for filename in files:
            self.log.debug("Final output file: %s" % filename)
        
        return files

    # Robust file removal function, with options to retry in the event the file is in use, and replace a deleted file
    def removeFile(self, filename, retries=2, delay=10, replacement=None, copyReplace=False):
        if filename is not None:
            for i in range(retries + 1):
                if os.path.isfile(filename):
                    try:
                        # Make sure file isn't read-only
                        os.chmod(filename, int("0777", 8))
                    except:
                        pass
                        
                    try:
                        os.remove(filename)
                        self.log.debug("File removed = %s" % filename)
                        i = 0
                    except:
                        self.log.exception("Unable to remove file")
                
                if not os.path.isfile(filename):
                    if replacement is not None:
                        if os.path.isfile(replacement):
                            try:
                                if copyReplace:
                                    self.log.debug("Replacing by copying replacement = %s" % replacement)
                                    shutil.copy(replacement, filename)
                                else:
                                    self.log.debug("Replacing by moving replacement = %s" % replacement)
                                    os.rename(replacement, filename)
                                
                                self.log.debug("File replaced = %s" % filename)
                                filename = replacement
                                break
                            except:
                                self.log.exception("Unable to replace file")
                    else:
                        break
                else:
                    self.log.error("File still exists")
                
                if delay > 0:
                    self.log.debug("Something happened - delaying for %s seconds before retrying" % delay)
                    time.sleep(delay)
        
        return False if os.path.isfile(filename) else True
    
    def moveBackAs(self, inputfile, original, addExtension="bad"):
        if not type(addExtension) in (unicode, str):
            addExtension = "bad"
        if original is None:
            badfile = inputfile
        else:
            badfile = original
        badfile = badfile + "." + addExtension
        
        self.log.info("Moving input file to original location and marking as %s" % addExtension)
        self.log.debug("  Source:      %s" % inputfile)
        self.log.debug("  Destination: %s" % badfile)
        try:
            self.removeFile(badfile, 2, 10, inputfile)
        except Exception as e:
            raise(e)
