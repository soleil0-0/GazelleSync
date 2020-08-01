#!/usr/bin/env python3
# -*-coding=utf-8 -*-

# imports: standard
import sys
import hashlib
import re
import os
import json
import time
import html
from html.parser import HTMLParser
import configparser
import logging

# imports: third party
import requests

# imports: custom
import maketorrent
from redapi import RedApi
from whatapi import WhatAPI
from nwapi import NwAPI
from xanaxapi import XanaxAPI
from dicapi import DicAPI
from shutil import copyfile
import bencode

# contants
__version__ = "5.0.6"
# determine if application is a script file or frozen exe
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
elif __file__:
    application_path = os.path.dirname(__file__)

class MyConfigParser(configparser.RawConfigParser):
    def get(self, section, option):
        val = configparser.RawConfigParser.get(self, section, option)
        return val.strip('"')

class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)


def st(inp):
    s = MLStripper()
    s.feed(inp)
    return s.get_data()


def strip_tags(inp, sourceAPI, destAPI):
    HTML2BBCODE_API = None

    if sourceAPI.site == "OPS":
        HTML2BBCODE_API = sourceAPI
    elif destAPI.site == "OPS":
        HTML2BBCODE_API = destAPI

    # 优先使用DIC的HTML2BBCODE服务
    if sourceAPI.site == "DIC":
        HTML2BBCODE_API = sourceAPI
    elif destAPI.site == "DIC":
        HTML2BBCODE_API = destAPI

    if HTML2BBCODE_API is None:
        return st(inp)
    else:
        return HTML2BBCODE_API.HTMLtoBBCODE(inp)


def unescape(inp):
    return html.unescape(inp)


def toUnicode(inp):
    if isinstance(inp, unicode):
        return inp
    else:
        return unicode(inp, sys.getfilesystemencoding())

compulsory = {
    "from",
    "to",
}

trackers = {
    "ops",
    "red",
    "nwcd",
    "dic",
}

possible = {
    "album",
    "from",
    "to",
    "tid",
    "folder",
    "link",
    "tpath",
    "tfolder"
}


def validateTrackers(result):
    result["to"] = result["to"].lower()
    result["from"] = result["from"].lower()

    if result["to"] == result["from"]:
        return False

    return (result["to"] in trackers) and (result["from"] in trackers)

def parseLink(link):
    ids = re.findall("torrentid=(\d+)", link)
    if ids:
        return ids[0]
    else:
        raise Exception("PL Link is not valid. Can't find torrentid in PL link: {}".format(link))

def getTorrentHash(path):
    logging.info(path)
    torrent_file = open(path, "rb")
    metainfo = bencode.bdecode(torrent_file.read())

    logging.info("Keys")
    logging.info(str(metainfo))

    info = metainfo[b'info']
    return hashlib.sha1(bencode.bencode(info)).hexdigest().upper()

def generateSourceTrackerAPI(tracker, username, password, cookie):
    if tracker == "red":
        logging.info("Source tracker is RED")
        return RedApi(username=username, password=password, cookie=cookie)
    elif tracker == "ops":
        logging.info("Source tracker is OPS")
        return XanaxAPI(username=username, password=password, cookie=cookie)
    elif tracker == "nwcd":
        logging.info("Source tracker is NWCD")
        return NwAPI(username=username, password=password, cookie=cookie)
    elif tracker == "dic":
        logging.info("Source tracker is DIC")
        return DicAPI(username=username, password=password, cookie=cookie)


def generateDestinationTrackerAPI(tracker, username, password, cookie):
    if tracker == "red":
        logging.info("Destination tracker is RED")
        return WhatAPI(username=username, password=password, cookie=cookie, tracker="https://flacsfor.me/{0}/announce", url="https://redacted.ch/", site="RED")
    elif tracker == "ops":
        logging.info("Destination tracker is OPS")
        return WhatAPI(username=username, password=password, cookie=cookie, tracker="https://home.opsfet.ch/{0}/announce", url="https://orpheus.network/", site="OPS")
    elif tracker == "nwcd":
        logging.info("Destination tracker is NWCD")
        return WhatAPI(username=username, password=password, cookie=cookie, tracker="https://definitely.notwhat.cd:443/{0}/announce", url="https://notwhat.cd/", site="NWCD")
    elif tracker == "dic":
        logging.info("Destination tracker is DIC")
        return WhatAPI(username=username, password=password, cookie=cookie, tracker="https://tracker.dicmusic.club/{0}/announce", url="https://dicmusic.club/", site="DIC")


def generateSourceFlag(tracker):
    if tracker == "red":
        return "RED"
    elif tracker == "ops":
        return "OPS"
    elif tracker == "nwcd":
        return "nwcd"
    elif tracker == "dic":
        return "DICMusic"


def getReleases(tracker, response, artist_name, group_name):
    ret = list()
    l = len(group_name)

    if len(response["results"]) == 0:
        return ret

    pages = response["pages"]
    if pages > 1:
        for group in response["results"]:
            if len(group["groupName"]) == l:
                ret.append(group)
        for index in range(2, pages+1):
            resp = tracker.request(
                "browse", artistname=artist_name, groupname=group_name, page=index)
            for group in resp["results"]:
                if len(group["groupName"]) == l:
                    ret.append(group)
    else:
        for group in response["results"]:
            if len(group["groupName"]) == l:
                ret.append(group)
    rett = list()
    logging.info(ret)
    for album in ret:
        if "torrents" in album:
            for t in album["torrents"]:
                rett.append(t)
    return rett


def isSame(first, second, what):
    if what in first and what in second:
        logging.info(str((what, first[what], second[what], first[what] == second[what])))
        return first[what] == second[what]
    else:
        logging.info("{} not exist in {} and {} at the same time, treat as same".format(what, first['id'], second['torrentId']))
        return True


def filterResults(meta, ts):
    # has to be equal: encoding, scene, media, format, remastered, remasterRecordLabel, remasterTitle, remasterYear, remasterCatalogueNumber
    # has to be better: logScore, hasCue, hasLog

    tdata = meta["torrent"]
    # isBetterThan

    temp = list()
    for t in ts:
        if isSame(tdata, t, "encoding") and isSame(tdata, t, "scene") and isSame(tdata, t, "media") and isSame(tdata, t, "format") and isSame(tdata, t, "remastered"):
            if tdata["remastered"]:
                if isSame(tdata, t, "remasterYear") and isSame(tdata, t, "remasterCatalogueNumber") and isSame(tdata, t, "remasterRecordLabel") and isSame(tdata, t, "remasterTitle"):
                    temp.append(t)
            else:
                temp.append(t)

    final = list()
    for t in temp:
        if t["logScore"] > tdata["logScore"]:
            final.append(t)
        elif t["logScore"] == tdata["logScore"]:
            if isSame(tdata, t, "hasCue"):
                final.append(t)
            elif t["hasCue"]:
                final.append(t)
    return final


def checkForDuplicate(tracker, meta):
    # find all artists
    # look if they have such a release
    # if one of them has it, it is a duplicate --> also add the artist to the other artists
    # if none does, all is perfect
    rawResults = dict()
    results = dict()

    group_name = meta["group"]["name"]

    for artist_data in meta["group"]["musicInfo"]["artists"]:
        artist_name = artist_data["name"]
        rawResults[artist_name] = tracker.request(
            "browse", artistname=artist_name, groupname=group_name)
        results[artist_name] = getReleases(
            tracker, rawResults[artist_name], artist_name, group_name)

    f = open("similar.json", "w")
    f.write(json.dumps(results, indent=4))
    f.close()

    isDupe = False
    logging.info("Comparing")
    filteredResults = dict()
    for artist in results:
        filteredResults[artist] = filterResults(meta, results[artist])
        if len(filteredResults[artist]) > 0:
            isDupe = True

    f = open("similarFiltered.json", "w")
    f.write(json.dumps(filteredResults, indent=4))
    f.close()
    return isDupe


def genaratePrettyName(artists, name, year, format, bitrate, media, recordLabel, catalogueNumber, editionTitle):
    artistString = ""
    logging.info("Artists")
    logging.info(artists)
    if len(artists["artists"]) == 1:
        artistString = artists["artists"][0]["name"]
    elif len(artists["artists"]) == 2:
        artistString = artists["artists"][0]["name"] + \
            " & " + artists["artists"][1]["name"]
    else:
        artistString = "Various Artists"

    formatString = ""
    if bitrate == "Lossless":
        formatString = "{0} {1}".format(format, media)
    else:
        formatString = "{0} {1} {2}".format(format, bitrate, media)

    base = "{0} - {1} ({2}) [{3}]".format(artistString,
                                          name, year, formatString)

    additionalInfoBuff = list()
    if recordLabel != "" and (not recordLabel is None):
        additionalInfoBuff.append(recordLabel)
    if catalogueNumber != "" and (not catalogueNumber is None):
        additionalInfoBuff.append(catalogueNumber)
    if editionTitle != "" and (not editionTitle is None):
        additionalInfoBuff.append(editionTitle)

    additionalInfo = " - ".join(additionalInfoBuff)

    if additionalInfo != "" and (not additionalInfo is None):
        base = base + " " + "{" + additionalInfo + "}"

    return base


artistImportances = {
    "Main": "1",
    "Guest": "2",
    "Composer": "4",
    "Conductor": "5",
    "DJ / Compiler": "6",
    "Compiler": "6",
    "DJ": "6",
    "Remixer": "3",
    "Producer": "7",
}


def moveAlbum(parsedArgs, sourceAPI, destAPI, source, watch_dir, nolog):
    logging.info(str(parsedArgs))
    data = None

    if "hash" in parsedArgs:
        logging.info(parsedArgs["hash"] + " " + len(parsedArgs["hash"]))
        data = sourceAPI.get_torrent_info(hash=parsedArgs["hash"])
    else:
        TorrentIDsource = parsedArgs["tid"]
        data = sourceAPI.get_torrent_info(id=TorrentIDsource)

    tdata = data["torrent"]
    g_group = data["group"]

    GroupIDsource = g_group["id"]
    TorrentIDsource = tdata["id"]

    if not os.path.exists("meta"):
        os.makedirs("meta")

    f = open(os.path.join("meta", str(TorrentIDsource) + ".json"), "w")
    f.write(json.dumps(data, indent=4))
    f.close()

    folder = ""

    if "album" in parsedArgs:
        folder = parsedArgs["album"]
    elif "folder" in parsedArgs:
        folder = os.path.join(
            parsedArgs["folder"], unescape(tdata["filePath"]))
        logging.info("Folder:", folder, "====")
    else:
        raise Exception("Failed to find path")

    isDupe = checkForDuplicate(destAPI, data)

    logging.info("Duplicate: %s" % isDupe)

    if isDupe:
        sys.exit(1)

    t_media = tdata["media"]
    t_format = tdata["format"]
    t_encoding = tdata["encoding"]
    if tdata["description"] == "":
        t_description = "Uploaded with GazelleSync ("+parsedArgs["from"].upper(
        )+" to "+parsedArgs["to"].upper()+"). Many thanks to the original uploader!"
    else:
        t_description = "Content of the original Description field at " + parsedArgs["from"].upper() + " (it may be empty) : [quote]" + tdata["description"] + \
            "[/quote]" + "\n\nUploaded with GazelleSync ("+parsedArgs["from"].upper(
        )+" to "+parsedArgs["to"].upper()+"). Many thanks to the original uploader!"

    t_remasterYear = tdata["remasterYear"]
    t_remasterCatalogueNumber = tdata["remasterCatalogueNumber"]
    t_remastered = tdata["remastered"]
    t_remasterRecordLabel = tdata["remasterRecordLabel"]
    t_remasterTitle = tdata["remasterTitle"]

    g_artists = g_group["musicInfo"]
    g_name = g_group["name"]
    g_year = g_group["year"]
    g_recordLabel = g_group["recordLabel"]
    g_catalogueNumber = g_group["catalogueNumber"]
    g_releaseType = g_group["releaseType"]
    g_tags = g_group["tags"]
    #g_wikiImage = g_group["wikiImage"]
    # """
    if parsedArgs["to"] != "nwcd":
        g_wikiImage = g_group["wikiImage"]
    else:
        g_wikiImage = destAPI.img(g_group["wikiImage"])
    # """

    g_wikiBody = strip_tags(g_group["wikiBody"], sourceAPI, destAPI)  # .replace("<br />", "\n")
    #g_wikiBody = g_group["wikiBody"]
    g_group["wikiBody"] = g_group["wikiBody"].replace("\r\n", "\n")

    album = dict(
        album=g_name,
        original_year=g_year,
        remaster=t_remastered,
        record_label=g_recordLabel,
        catalogue_number=g_catalogueNumber,
        releasetype=g_releaseType,
        remaster_year=t_remasterYear,
        remaster_title=t_remasterTitle,
        remaster_record_label=t_remasterRecordLabel,
        remaster_catalogue_number=t_remasterCatalogueNumber,
        format=t_format,
        encoding=t_encoding,
        media=t_media,
        description=g_wikiBody,
        rDesc=t_description
    )

    artists = list()
    for i, v in enumerate(g_artists["composers"]):
        artists.append((v["name"], artistImportances.get("Composer", 1)))

    for i, v in enumerate(g_artists["dj"]):
        artists.append((v["name"], artistImportances.get("DJ", 1)))

    for i, v in enumerate(g_artists["artists"]):
        artists.append((v["name"], artistImportances.get("Main", 1)))

    for i, v in enumerate(g_artists["with"]):
        artists.append((v["name"], artistImportances.get("Guest", 1)))

    for i, v in enumerate(g_artists["conductor"]):
        artists.append((v["name"], artistImportances.get("Conductor", 1)))

    for i, v in enumerate(g_artists["remixedBy"]):
        artists.append((v["name"], artistImportances.get("Remixer", 1)))

    for i, v in enumerate(g_artists["producer"]):
        artists.append((v["name"], artistImportances.get("Producer", 1)))

    logging.info(str(album["album"]))

    tempfolder = "torrent"

    if not os.path.exists(tempfolder):
        os.makedirs(tempfolder)

    if t_remastered:
        releaseYear = t_remasterYear
        releaseRecordLabel = t_remasterRecordLabel
        releaseCatNum = t_remasterCatalogueNumber
    else:
        releaseYear = g_year
        releaseRecordLabel = g_recordLabel
        releaseCatNum = g_catalogueNumber

    newFolderName = genaratePrettyName(g_artists, g_name, releaseYear, t_format,
                                       t_encoding, t_media, releaseRecordLabel, releaseCatNum, t_remasterTitle)

    logging.info("New path is %s" % newFolderName)
    # input()

    tpath = newFolderName + ".torrent"

    tpath = tpath.replace("/", "_")
    tpath = tpath.replace("\\", "_")
    tpath = tpath.replace(":", "_")
    tpath = unescape(tpath)

    #tpath = "torrent/"+tpath

    logging.info(tpath)
    logging.info("Folder " + folder)
    #folder = toUnicode(folder)

    logging.info("Folder " + folder)
    # raw_input()

    t = maketorrent.TorrentMetadata()
    t.set_data_path(folder)
    t.set_comment("Created with GazelleSync")
    t.set_private(True)
    t.set_trackers([[destAPI.tracker]])
    t.set_source(source)
    t.save("torrent/"+tpath)

    ret = destAPI.upload(folder, tempfolder, album, g_tags,
             g_wikiImage, artists, "torrent/"+tpath, nolog)
    if not ret:
        sys.exit(1)

    if watch_dir:
        copyfile(
            os.path.join("torrent", tpath),
            os.path.join(watch_dir, tpath)
            )

def main():
    # argparse
    import argparse

    # argparse parser
    parser = argparse.ArgumentParser(
            description='Bring torrents from one Gazelle instance to another'
    )

    parser.add_argument(
        '-v', '--version',
        action='version',
        version='%(prog)s 5.0.6'
    )
    parser.add_argument(
            '-l', '--loglevel',
            metavar='LOGLEVEL',
            default='info',
            choices=['debug', 'info', 'warning', 'error', 'critical'],
            help='loglevel for log file (default: %(default)s)'
    )

    # --from <>
    parser.add_argument(
        '--from',
        choices=trackers,
        required=True,
        dest='from_',
        help="torrents from which Gazelle instance"
    )

    # -to <>
    parser.add_argument(
        "--to",
        choices=trackers,
        required=True,
        help="sync to which Gazelle instance"
    )

    # --album <> / --folder <>
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--album",
        help="the folder of the album"
    )
    group.add_argument(
        "--folder",
        help="the folder that contauins all albums. The album folder will be extracted from the site metadata"
    )

    # --tid <> / --link <> / --tpath <> / --tfolder <>
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--tid",
        help="the torrent ID"
    )
    group.add_argument(
        "--link",
        help="the whole permalinlk. The tool os smart enough to extract it"
    )
    group.add_argument(
        "--tpath",
        help="the path that points towards the .torrent file. The infohash will be computed"
    )
    group.add_argument(
        "--tfolder",
        help="the folder containing all the .torrent files"
    )

    parser.add_argument(
        '--nolog',
        dest='nolog',
        action='store_true',
        help='disable upload of log file'
    )
    parser.set_defaults(nolog = False)

    parser.add_argument(
        '-c', '--config',
        metavar='FILE',
        default=os.path.join(application_path, 'config.cfg'),
        help='config file with login details (default: %(default)s)'
    )

    # print help message when no option is given
    if len(sys.argv) == 1:
        parser.print_help()
        parser.exit()

    # parse arguments
    args = parser.parse_args()

    loglevel = args.loglevel

    gazelle_from = args.from_
    gazelle_to = args.to

    album = args.album
    folder = args.folder

    tid = args.tid
    link = args.link
    tpath = args.tpath
    tfolder = args.tfolder

    nolog = args.nolog
    config_file = args.config

    # set up logging
    numeric_level = getattr(logging, loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % loglevel)
    logging.basicConfig(
            format='%(asctime)s %(levelname)s:%(message)s',
            handlers=[logging.StreamHandler()],
            level=numeric_level
    )

    # TODO [validation] gazelle_from and gazelle_to should not the same
    if gazelle_from == gazelle_to:
        logging.error("Values of \"--from\" and \"--to\" should not be the same")
        exit(1)

    # read config file
    config = MyConfigParser()
    config.read(config_file)

    from_username = config.get(gazelle_from, 'username')
    from_password = config.get(gazelle_from, 'password')
    from_cookie = config.get(gazelle_from, 'cookie')
    to_username = config.get(gazelle_to, 'username')
    to_password = config.get(gazelle_to, 'password')
    to_cookie = config.get(gazelle_to, 'cookie')
    watch_dir = config.get("common", "watch_dir")
    
    sourceAPI = generateSourceTrackerAPI(gazelle_from, from_username, from_password, from_cookie)
    destAPI = generateDestinationTrackerAPI(gazelle_to, to_username, to_password, to_cookie)
    source = generateSourceFlag(gazelle_to)

    # TODO recover previous required data
    parsedArgs = {
        'from': gazelle_from,
        'to': gazelle_to
    }
    if album:
        parsedArgs['album'] = album
    else:
        parsedArgs['folder'] = folder
    if tid:
        parsedArgs['tid'] = tid
    elif link:
        parsedArgs['link'] = link
    elif tpath:
        parsedArgs['tpath'] = tpath
    else:
        parsedArgs['tfolder'] = tfolder

    if not ("tid" in parsedArgs):
        if "link" in parsedArgs:
            parsedArgs["tid"] = parseLink(parsedArgs["link"])
        elif "tpath" in parsedArgs:
            logging.info("Tpath:", parsedArgs["tpath"])
            parsedArgs["hash"] = getTorrentHash(parsedArgs["tpath"])
        elif "tfolder" in parsedArgs:
            pass
        else:
            raise Exception(
                "Houston, we do not have enough information to proceed. Chack your arguments.")

    if tfolder:
        logging.info("Batch mode")
        total = 0
        fails = 0
        for filename in os.listdir(tfolder):
            if filename.endswith(".torrent"):
                total += 1
                try:
                    localParsed = dict()
                    for i in parsedArgs:
                        localParsed[i] = parsedArgs[i]
                    localParsed["tpath"] = os.path.join(
                        localParsed["tfolder"], filename)
                    localParsed["hash"] = getTorrentHash(localParsed["tpath"])
                    logging.info(str(localParsed))
                    moveAlbum(localParsed, sourceAPI, destAPI, source, nolog=nolog)
                except Exception as e:
                    fails += 1
                logging.info("Success rate: %s".format(1 - fails/total))
        logging.info("Success rate: %s".format(1 - fails/total))
    else:
        logging.info("Single mode")
        moveAlbum(parsedArgs, sourceAPI, destAPI, source, watch_dir, nolog)

if __name__ == "__main__":
    main()
