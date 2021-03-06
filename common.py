#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import time
from builtins import open
from future import standard_library
from builtins import hex
from builtins import str
from builtins import range
import os
import random
import stat
import unicodedata
import requests
import shutil
from uuid import getnode as get_mac

try:
    from configparser import ConfigParser as SafeConfigParser
except ImportError:
    from ConfigParser import SafeConfigParser  # ver. < 3.0

standard_library.install_aliases()

version = '0.7'
date = '2019-09-28'
pipe = 'pipe://'
default_group_name = "O2TV"
marhy = 'https://marhycz.github.io/picons/640/', 'https://marhycz.github.io/picons/1024/'
log_file = 'playlist.log'
id_file = 'device_id'
authent_error = 'AuthenticationError'
toomany_error = 'TooManyDevicesError'
nopurch_error = 'NoPurchasedServiceError'
noplaylist_error = 'NoPlaylistError'
nochannels_error = 'NoChannelsError'


def device_id():
    mac = get_mac()
    hexed = hex((mac * 7919) % (2 ** 64))
    return ('0000000000000000' + hexed[2:-1])[16:]


def random_hex16():
    return ''.join([random.choice('0123456789abcdef') for x in range(16)])


def to_string(text):
    if type(text).__name__ == 'unicode':
        output = text.encode('utf-8')
    else:
        output = str(text)
    return output


def logo_name(channel):
    channel = unicodedata.normalize('NFKD', channel)
    channel = channel.lower()
    name = ''
    for char in channel:
        if not unicodedata.combining(char) and (char.isalpha() or char.isdigit()):
            name += char
    return name


def add_param(param, value, cond):
    item = ''
    if cond:
        item = ' %s="%s"' % (param, str(value))
    return item


def write_file(content, name, log=None):
    if log is not None:
        log("Saving file: " + name)
    f = open(name, 'w', encoding="utf-8")
    f.write(content)
    f.close()


def try_exec(name):
    f = name
    try:
        sts = os.stat(f)
        if not (sts.st_mode & stat.S_IEXEC):
            os.chmod(f, sts.st_mode | stat.S_IEXEC)
    except:
        pass


def write_streamer(streamer_file, playlist_file, ffmpeg_cmd, log=None):
    streamer_code = '#! /bin/bash\n' + \
                    'source=$*\n' + \
                    'playlist=' + playlist_file + '\n' + \
                    'playlistpath=$(dirname "${playlist}")"/"\n' + \
                    'stream=$(grep -A 1 "${source}$" $playlist | head -n 2 | tail -n 1)\n' + \
                    'tempplaylist=${playlistpath}${stream##*/}\n' + \
                    'if [ ! -f "${tempplaylist}" ]; then tempplaylist=$(mktemp -u)".m3u8";' + \
                    'curl -L -f ${stream} -o ${tempplaylist}; fi\n' + \
                    'streamcount=$(cat ${tempplaylist} | grep -Eo "(http|https)://[\da-z./?A-Z0-9\D=_-]*" | wc -l)\n' + \
                    'streamcount=$((streamcount-1))\n' + \
                    'if  [ "$streamcount" = "-1" ]; then streamcount=0; fi\n' + \
                    'echo "source: ${source}" >&2\n' + \
                    'echo "stream: ${stream}" >&2\n' + \
                    'echo "tempplaylist: ${tempplaylist}" >&2\n' + \
                    'echo "streamcount: ${streamcount}" >&2\n' + \
                    ffmpeg_cmd + ' -protocol_whitelist file,http,https,tcp,tls -fflags +genpts ' + \
                    '-loglevel warning -i ${tempplaylist} -probesize 32 -reconnect_at_eof 1 -reconnect_streamed 1 ' + \
                    '-c copy -map p:${streamcount}? -f mpegts -tune zerolatency -bsf:v h264_mp4toannexb,dump_extra ' + \
                    '-mpegts_service_type digital_tv pipe:1\n'
    if not os.path.isfile(streamer_file):
        if log is not None:
            log('Saving Streamer: ' + streamer_file)
        write_file(streamer_code, streamer_file + '.sample')
        # _to_file(c.streamer_code, os.path.join(cfg.playlist_path, cfg.playlist_streamer + '.sample'))
        try_exec(streamer_file + '.sample')
        write_file(streamer_code, streamer_file)
        try_exec(streamer_file)
    else:
        if log is not None:
            log('Streamer exists. Ignoring...')


def build_channel_lines(channel, channel_logo, logoname, streamer, group, playlist_type, channel_epg_name,
                        channel_epg_id, channel_group):
    name = channel.name
    logo = channel.logo_url
    url = channel.url()
    epgname = name
    epgid = name
    r = ""
    # číslo programu v epg
    # viz https://www.o2.cz/file_conver/174210/_025_J411544_Razeni_televiznich_programu_O2_TV_03_2018.pdf
    channel_weight = channel.weight
    # logo v mistnim souboru - kdyz soubor neexistuje, tak pouzit url
    if (channel_logo > 1) and (logoname != ""):
        logo = logoname
    if playlist_type == 1:
        r += '#EXTINF:-1'
        r += add_param('tvg-name', epgname, channel_epg_name != 0)
        r += add_param('tvg-id', epgid, channel_epg_id != 0)
        r += add_param('tvg-logo', logo, channel_logo != 0)
        r += add_param('tvg-chno', channel_weight, channel_epg_id != 0)
        r += add_param('group-titles', group, channel_group != 0)
        r += ', %s\n%s\n' % (name, url)
    if (playlist_type == 2) or (playlist_type == 3):
        r += '#EXTINF:-1'
        r += add_param('tvg-id', epgid, channel_epg_id != 0)
        r += add_param('tvg-logo', logo, channel_logo != 0)
        r += add_param('tvg-chno', channel_weight, channel_epg_id != 0)
        r += add_param('group-titles', group, channel_group != 0)
        r += ', %s\n' % name
        if playlist_type == 2:
            r += '%s\n' % url
        if playlist_type == 3:
            r += '%s %s\n' % (streamer, name)
    return r


def is_null_or_whitespace(test_string):
    if test_string and test_string.strip() and not test_string.isspace():
        return False
    else:
        return True


def download_playlist(in_url, out_file, log=None):
    raw = requests.get(in_url, stream=True)
    if os.path.isfile(out_file):
        os.remove(out_file)
    with open(out_file, "wb") as f:
        shutil.copyfileobj(raw.raw, f)
    # uložili jsme prázdný soubor?
    if os.stat(out_file).st_size == 0:
        os.remove(out_file)


def cache_playlist(in_url, out_path, log=None, attempts=5, delay=1000):
    out_file = in_url.split("/")[-1]
    out_file = os.path.join(out_path, out_file)
    if (not out_file.endswith("m3u8")) and (not out_file.endswith("mpd")):
        return None
    if log is not None:
        log("Caching playlist to %s..." % out_file)
    done = False
    start_attempts = attempts
    while not done:
        download_playlist(in_url, out_file, log)
        if os.path.isfile(out_file) and os.stat(out_file).st_size != 0:
            done = True
        else:
            time.sleep(delay / 1000)
        attempts -= 1
        if attempts <= 0:
            done = True
    if attempts < (start_attempts - 1) and log is not None:
        log("Attempts: %d" % (start_attempts - attempts))
    if not os.path.isfile(out_file) and os.stat(out_file).st_size == 0:
        return None
    else:
        return out_file


def set_default_config(config):
    config.add_section('Login')
    config.set('Login', 'username', '')
    config.set('Login', 'password', '')
    config.set('Login', 'device_id', '')
    config.set('Login', 'access_token', '')
    config.set('Login', 'refresh_token', '')
    config.set('Login', 'token_expire_date', '')
    config.add_section('Common')
    config.set('Common', 'playlist_streamer', 'streamer.sh')
    config.set('Common', 'ffmpeg_command', 'ffmpeg')
    config.set('Common', 'my_script', '0')
    config.set('Common', 'my_script_name', 'myscript.sh')
    config.set('Common', 'stream_quality', '1')
    config.set('Common', 'cut_log', '1')
    config.set('Common', 'log_limit', '100')
    config.set('Common', 'log_reduction', '50')
    config.add_section('Playlist')
    config.set('Playlist', 'playlist_path', '')
    config.set('Playlist', 'playlist_src', 'o2tv.generic.m3u8')
    config.set('Playlist', 'playlist_dst', 'o2tv.playlist.m3u8')
    config.set('Playlist', 'cache_playlists', 'False')
    config.set('Playlist', 'playlist_type', '3')
    config.set('Playlist', 'channel_epg_name', '1')
    config.set('Playlist', 'channel_epg_id', '1')
    config.set('Playlist', 'channel_group', '1')
    config.set('Playlist', 'channel_group_name', 'O2TV')
    config.set('Playlist', 'channel_logo', '1')
    config.set('Playlist', 'channel_logo_path', '')
    config.set('Playlist', 'channel_logo_url', '')
    config.set('Playlist', 'channel_logo_name', '0')
    config.set('Playlist', 'channel_logo_github', '0')


def check_config(config):
    path = os.path.dirname(os.path.abspath(__file__))
    if is_null_or_whitespace(config.get('Playlist', 'playlist_path')):
        config.set('Playlist', 'playlist_path', path)
    if config.get('Login', 'username') == '' or config.get('Login', 'password') == '':
        return False
    return True
