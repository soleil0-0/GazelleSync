#!/usr/bin/env python
from __future__ import division, unicode_literals, print_function
import re
import os
import sys
import time
import string
import requests
import subprocess
import shutil
#import dottorrent

def sprint(*r):
    try:
        print(*r)
    except:
        try:
            b = list()
            for i in r:
                try:
                    if isinstance(i, unicode):
                        b.append(i.encode("utf-8"))
                    else:
                        b.append(str(i))
                except Exception as e:
                    b.append("Failed to encode!")
            print(*b)
        except:
            print("Failed to encode!")

headers = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_3)'\
        'AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.79'\
        'Safari/535.11',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9'\
        ',*/*;q=0.8',
    'Accept-Encoding': 'gzip,deflate,sdch',
    'Accept-Language': 'en-US,en;q=0.8',
    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3'}

# gazelle is picky about case in searches with &media=x
media_search_map = {
    'cd': 'CD',
    'dvd': 'DVD',
    'vinyl': 'Vinyl',
    'soundboard': 'Soundboard',
    'sacd': 'SACD',
    'dat': 'DAT',
    'web': 'WEB',
    'blu-ray': 'Blu-ray'
}

lossless_media = set(media_search_map.keys())

def album_artists(album):
    return list(set(track.artist for track in album.tracks))

description_template = string.Template("""
[url=https://musicbrainz.org/release-group/$musicbrainz_id]MusicBrainz[/url]

Country: $country
Tracks: $num_tracks

Track list:
$track_list
""".strip())

track_template = string.Template("[#]$title")

def album_description(album):
    track_list = "\n".join([track_template.substitute(title=track.title) for track in album.tracks])
    return description_template.substitute(
        musicbrainz_id=album.releasegroup_id,
        country=album.country,
        num_tracks=len(album.tracks),
        track_list=track_list
    )

def album_release_type(album):
    return {
        "album": 1,
        "soundtrack": 3,
        "ep": 5,
        "compilation": 7,
        "single": 9,
        "live": 11,
        "remix": 13,
        "other": 1,
        None: 1
    }[album.albumtype]

def album_media(album):
    return {
        "CD": "CD",
        "CD-R": "CD",
        "Enhanced CD": "CD",
        "HDCD": "CD",
        "DualDisc": "CD",
        "Copy Control CD": "CD",
        "Vinyl": "Vinyl",
        "12\" Vinyl": "Vinyl",
        "Digital Media": "WEB",
        "SACD": "SACD",
        "Hybrid SACD": "SACD",
        "Cassette": "Cassette",
        None: "CD",
    }[album.media]

def remaster_status(album):
    if album.original_year is None:
        return None
    if album.original_year == album.year:
        return None
    return "on"

def create_upload_request(auth, album, torrent, logfiles, tags, artwork_url, artists):
    #artists = album_artists(album)
    #remaster = remaster_status(album)
    if album["remaster"]:
        sprint("Is a remaster")
        data = [
            ("submit", "true"),  # the submit button
            ("auth", auth),  # input name=auth on upload page - appears to not change
            ("type", "0"),  # music
            ("title", album["album"]),
            ("year", str(album["original_year"]).encode("utf-8").decode("utf-8")),
            ("record_label", album["record_label"]),  # optional
            ("catalogue_number", album["catalogue_number"]),  # optional
            ("releasetype", album["releasetype"]),
            ("remaster", album["remaster"]),  # if it's a remaster, excluded otherwise
            ("remaster_year", str(album["remaster_year"])),
            ("remaster_title", album["remaster_title"]),  # optional
            ("remaster_record_label", album["remaster_record_label"]),  # optional
            ("remaster_catalogue_number", album["remaster_catalogue_number"]),  # optional
            ("format", album["format"]),  # TODO: analyze files
            ("bitrate", album["encoding"]),  # TODO: analyze files
            ("other_bitrate", ""),  # n/a
            ("media", album["media"]),  # or WEB, Vinyl, etc.
            ("genre_tags", tags[0]),  # blank - this is the dropdown of official tags
            ("tags", ", ".join(tags)),  # classical, hip.hop, etc. (comma separated)
            ("image", artwork_url),  # optional
            ("album_desc", album["description"]),
            ("release_desc", album["rDesc"])
    ]
    else:
        sprint("Is not a remaster")
        data = [
            ("submit", "true"),  # the submit button
            ("auth", auth),  # input name=auth on upload page - appears to not change
            ("type", "0"),  # music
            ("title", album["album"]),
            ("year", str(album["original_year"]).encode("utf-8").decode("utf-8")),
            ("record_label", album["record_label"]),  # optional
            ("catalogue_number", album["catalogue_number"]),  # optional
            ("releasetype", album["releasetype"]),  # if it's a remaster, excluded otherwise
            ("format", album["format"]),  # TODO: analyze files
            ("bitrate", album["encoding"]),  # TODO: analyze files
            ("other_bitrate", ""),  # n/a
            ("media", album["media"]),  # or WEB, Vinyl, etc.
            ("genre_tags", tags[0]),  # blank - this is the dropdown of official tags
            ("tags", ", ".join(tags)),  # classical, hip.hop, etc. (comma separated)
            ("image", artwork_url),  # optional
            ("album_desc", album["description"]),
            ("release_desc", album["rDesc"])
        ]
    sprint(data[4])

    for artist in artists:
        importance = 1
        if " feat. " in artist:
            artist = artist.split(" feat. ")[1]
            importance = 2
        data.append(("artists[]", artist))
        data.append(("importance[]", importance))
    files = []
    for logfile in logfiles:
        files.append(("logfiles[]", logfile))
    files.append(("file_input", torrent))
    return data, files

def locate(root, match_function, ignore_dotfiles=True):
    '''
    Yields all filenames within the root directory for which match_function returns True.
    '''
    for path, dirs, files in os.walk(root):
        for filename in (os.path.abspath(os.path.join(path, filename)) for filename in files if match_function(filename)):
            if ignore_dotfiles and os.path.basename(filename).startswith('.'):
                pass
            else:
                yield filename

def ext_matcher(*extensions):
    '''
    Returns a function which checks if a filename has one of the specified extensions.
    '''
    return lambda f: os.path.splitext(f)[-1].lower() in extensions
''''
def make_torrent(input_dir, output_dir, tracker, passkey):
    torrent = os.path.join(output_dir, os.path.basename(input_dir)) + ".torrent"
    if os.path.exists(torrent):
        os.remove(torrent)
    if not os.path.exists(os.path.dirname(torrent)):
        os.path.makedirs(os.path.dirname(torrent))
    tracker_url = '%(tracker)s%(passkey)s/announce' % {
        'tracker' : tracker,
        'passkey' : passkey,
    }

    command = ["mktorrent", "-p", "-s", "PTH", "-a", tracker_url, "-o", torrent, input_dir]
    subprocess.check_output(command, stderr=subprocess.STDOUT)
    return torrent
'''
def make_torrent(path, output_dir):
    base = os.path.basename(path)
    new = output_dir + "/" + base
    shutil.copyfile(path, new)
    f = open(new, "rb")
    data = f.read()
    f.close()
    newData = data[0:-5]+ b"APLee"
    g = open(new, "wb")
    g.write(newData)
    g.close()
    return new


class LoginException(Exception):
    pass

class RequestException(Exception):
    pass

class WhatAPI:
    def __init__(self, username=None, password=None, tracker=None, url=None):
        self.session = requests.Session()
        self.session.headers.update(headers)
        self.username = username
        self.password = password
        self.authkey = None
        self.passkey = None
        self.userid = None
        self.tracker = tracker
        self.last_request = time.time()
        self.rate_limit = 2.0 # seconds between requests
        self.url = url
        self._login()

    def _login(self):
        '''Logs in user and gets authkey from server'''
        loginpage = self.url + '/login.php'
        data = {'username': self.username,
                'password': self.password}
        r = self.session.post(loginpage, data=data)
        if r.status_code != 200:
            raise LoginException
        try:
            accountinfo = self.request('index')
            self.authkey = accountinfo['authkey']
            self.passkey = accountinfo['passkey']
            self.userid = accountinfo['id']
        except:
            sprint("unable to log in")
            sprint(r.text)
            sys.exit(1)

    def logout(self):
        self.session.get(self.url + "/logout.php?auth=%s" % self.authkey)

    def request(self, action, **kwargs):
        '''Makes an AJAX request at a given action page'''
        while time.time() - self.last_request < self.rate_limit:
            time.sleep(0.1)

        ajaxpage = self.url + '/ajax.php'
        params = {'action': action}
        if self.authkey:
            params['auth'] = self.authkey
        params.update(kwargs)
        r = self.session.get(ajaxpage, params=params, allow_redirects=False)
        self.last_request = time.time()
        response = r.json()
        if response['status'] != 'success':
            raise RequestException
        return response['response']

    def get_artist(self, id=None, format='MP3', best_seeded=True):
        res = self.request('artist', id=id)
        torrentgroups = res['torrentgroup']
        keep_releases = []
        for release in torrentgroups:
            torrents = release['torrent']
            best_torrent = torrents[0]
            keeptorrents = []
            for t in torrents:
                if t['format'] == format:
                    if best_seeded:
                        if t['seeders'] > best_torrent['seeders']:
                            keeptorrents = [t]
                            best_torrent = t
                    else:
                        keeptorrents.append(t)
            release['torrent'] = list(keeptorrents)
            if len(release['torrent']):
                keep_releases.append(release)
        res['torrentgroup'] = keep_releases
        return res

    def snatched(self, skip=None, media=lossless_media):
        if not media.issubset(lossless_media):
            raise ValueError('Unsupported media type %s' % (media - lossless_media).pop())

        # gazelle doesn't currently support multiple values per query
        # parameter, so we have to search a media type at a time;
        # unless it's all types, in which case we simply don't specify
        # a 'media' parameter (defaults to all types).

        if media == lossless_media:
            media_params = ['']
        else:
            media_params = ['&media=%s' % media_search_map[m] for m in media]

        url = self.url + '/torrents.php?type=snatched&userid=%s&format=FLAC' % self.userid
        for mp in media_params:
            page = 1
            done = False
            pattern = re.compile('torrents.php\?id=(\d+)&amp;torrentid=(\d+)')
            while not done:
                content = self.session.get(url + mp + "&page=%s" % page).text
                for groupid, torrentid in pattern.findall(content):
                    if skip is None or torrentid not in skip:
                        yield int(groupid), int(torrentid)
                done = 'Next &gt;' not in content
                page += 1

    def upload(self, album_dir, output_dir, album, tags, artwork_url, artists, torrentpath):
        url = self.url + "/upload.php"
        torrent = ('torrent.torrent', open(torrentpath, 'rb'), "application/octet-stream")
        logfiles = locate(album_dir, ext_matcher('.log'))
        logfiles = [(str(i) + '.log', open(logfile, 'rb'), "application/octet-stream") for i, logfile in enumerate(logfiles)]
        r = self.session.get(url)
        auth = re.search('name="auth" value="([^"]+)"', r.text).group(1)
        data, files = create_upload_request(auth, album, torrent, logfiles, tags, artwork_url, artists)
        upload_headers = dict(headers)
        upload_headers["referer"] = url
        upload_headers["origin"] = url.rsplit("/", 1)[0]
        sprint(album["album"])
        r = self.session.post(url, data=data, files=files, headers=upload_headers)
        if "torrent_comments" not in r.text:
            from pprint import pprint
            sprint("upload failed.")
            sprint(data)
            f = open("ret.html", "w")
            f.write(r.text)
            f.close()
            return False
        else:
            return True

    def release_url(self, group, torrent):
        return self.url + "/torrents.php?id=%s&torrentid=%s#torrent%s" % (group['group']['id'], torrent['id'], torrent['id'])

    def permalink(self, torrent):
        return self.url + "/torrents.php?torrentid=%s" % torrent['id']

    def is_duplicate(self, album):
        # TODO
        return False
