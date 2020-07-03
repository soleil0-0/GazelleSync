# -*-coding=utf-8 -*-

import sys
import hashlib
import re
import os
import json
import time
import requests
import maketorrent
from redapi import RedApi
from whatapi import WhatAPI
from nwapi import NwAPI
from xanaxapi import XanaxAPI
from dicapi import DicAPI
from shutil import copyfile
import bencode
import html
from html.parser import HTMLParser
from configparser import ConfigParser

__version__ = "5.0.4"
#sys.stdout = open('out.txt', 'w')

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


def strip_tags(inp):
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


def sprint(*r):
    try:
        print(*r)
    except:
        try:
            b = list()
            for i in r:
                try:
                    if isinstance(i, unicode):
                        b.append(i.encode(sys.getfilesystemencoding()))
                    else:
                        b.append(str(i))
                except Exception as e:
                    b.append("Failed to encode!")
            print(*b)
        except:
            print("Failed to encode!")


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

    #print(result["to"], result["from"])

    if result["to"] == result["from"]:
        return False

    return (result["to"] in trackers) and (result["from"] in trackers)


def parseArguments(args):
    comp = dict()
    for c in compulsory:
        comp[c] = False

    result = dict()
    sprint("======================")
    for a in args:
        sprint(a)
        sprint("+++")
        for p in possible:
            if a.startswith(p):
                result[p] = a[len(p)+1:]
                #sprint("Matched at", p, result[p])

    for k in result:
        if k in comp:
            comp[k] = True

    allTrue = True
    for c in comp:
        allTrue = allTrue and comp[c]
    #sprint("All true", allTrue)
    if not allTrue:
        print("The following arguments are compulsory")
        for c in compulsory:
            sprint(c)
        raise Exception('Not all arguments are present.')

    if not validateTrackers(result):
        raise Exception("Trackers can only be RED, OPS, NWCD, and DIC")

    if ("tid" in result):
        if not int(result["tid"]):
            raise("gid argument has to be a number")

    return result


def parseLink(link):
    ids = re.findall("id=(\d+)&torrentid=(\d+)", link)
    return ids[0][0], ids[0][1]


def getTorrentHash(path):
    print(path)
    torrent_file = open(path, "rb")
    metainfo = bencode.bdecode(torrent_file.read())
    print("Keys")
    for i in metainfo:
        print(i)
    info = metainfo[b'info']
    return hashlib.sha1(bencode.bencode(info)).hexdigest().upper()


def generateSourceTrackerAPI(tracker):
    if tracker == "red":
        print("Source tracker is RED")
        return RedApi(username=config.get('RED', 'Username'), password=config.get('RED', 'Password'))
    elif tracker == "ops":
        print("Source tracker is OPS")
        return XanaxAPI(username=config.get('OPS', 'Username'), password=config.get('OPS', 'Password'))
    elif tracker == "nwcd":
        print("Source tracker is NWCD")
        return NwAPI(username=config.get('NWCD', 'Username'), password=config.get('NWCD', 'Password'))
    elif tracker == "dic":
        print("Source tracker is DIC")
        return DicAPI(username=config.get('DIC', 'Username'), password=config.get('DIC', 'Password'))


def generateDestinationTrackerAPI(tracker):
    if tracker == "red":
        print("Destination tracker is RED")
        return WhatAPI(username=config.get('RED', 'Username'), password=config.get('RED', 'Password'), tracker="https://flacsfor.me/{0}/announce", url="https://redacted.ch/", site="RED")
    elif tracker == "ops":
        print("Destination tracker is OPS")
        return WhatAPI(username=config.get('OPS', 'Username'), password=config.get('OPS', 'Password'), tracker="https://home.opsfet.ch/{0}/announce", url="https://orpheus.network/", site="OPS")
    elif tracker == "nwcd":
        print("Destination tracker is NWCD")
        return WhatAPI(username=config.get('NWCD', 'Username'), password=config.get('NWCD', 'Password'), tracker="https://definitely.notwhat.cd:443/{0}/announce", url="https://notwhat.cd/", site="NWCD")
    elif tracker == "dic":
        print("Destination tracker is DIC")
        return WhatAPI(username=config.get('DIC', 'Username'), password=config.get('DIC', 'Password'), tracker="http://pt.kshare.club:34000/{0}/announce", url="http://pt.kshare.club/", site="DIC")


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
    for album in ret:
        for t in album["torrents"]:
            rett.append(t)
    return rett


def isSame(first, second, what):
    sprint(what, first[what], second[what], first[what] == second[what])
    return first[what] == second[what]


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
    sprint("Comparing")
    filteredResults = dict()
    for artist in results:
        filteredResults[artist] = filterResults(meta, results[artist])
        # sprint(len(filteredResults[artist]))
        if len(filteredResults[artist]) > 0:
            isDupe = True

    f = open("similarFiltered.json", "w")
    f.write(json.dumps(filteredResults, indent=4))
    f.close()
    return isDupe


def genaratePrettyName(artists, name, year, format, bitrate, media, recordLabel, catalogueNumber, editionTitle):
    artistString = ""
    print("Artists")
    print(artists)
    if len(artists["artists"]) == 1:
        artistString = artists["artists"][0]["name"]
    if len(artists["artists"]) == 2:
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


def moveAlbum(parsedArgs, a, w, source):
    sprint(parsedArgs)
    data = None

    if "hash" in parsedArgs:
        sprint(parsedArgs["hash"], len(parsedArgs["hash"]))
        data = a.get_torrent_info(hash=parsedArgs["hash"])
    else:
        TorrentIDsource = parsedArgs["tid"]
        data = a.get_torrent_info(id=TorrentIDsource)

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
        sprint("Folder:", folder, "====")
    else:
        raise Exception("Failed to find path")

    isDupe = checkForDuplicate(w, data)

    sprint("Duplicate:", isDupe)

    if isDupe:
        return

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

    g_wikiBody = strip_tags(g_group["wikiBody"])  # .replace("<br />", "\n")
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

    sprint(album["album"])

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

    print("New path is", newFolderName)
    # input()

    tpath = newFolderName + ".torrent"

    tpath = tpath.replace("/", "_")
    tpath = tpath.replace("\\", "_")
    tpath = tpath.replace(":", "_")
    tpath = unescape(tpath)

    #tpath = "torrent/"+tpath

    sprint(tpath)
    sprint("Folder", folder)
    #folder = toUnicode(folder)

    sprint("Folder", folder)
    # raw_input()

    t = maketorrent.TorrentMetadata()
    t.set_data_path(folder)
    t.set_comment("Created with GazelleSync")
    t.set_private(True)
    t.set_trackers([[destAPI.tracker]])
    t.set_source(source)
    t.save("torrent/"+tpath)

    w.upload(folder, tempfolder, album, g_tags,
             g_wikiImage, artists, "torrent/"+tpath)

    if config.get("common", "directory") != "":
        copyfile(os.path.join("torrent", tpath), os.path.join(
            config.get("common", "directory"), tpath))


config = ConfigParser()
config.read(os.path.join(os.path.dirname(__file__), 'config.cfg'))

parsedArgs = parseArguments(sys.argv)

# sprint(parsedArgs)

if not ("tid" in parsedArgs):
    if "link" in parsedArgs:
        parsedArgs["gid"], parsedArgs["tid"] = parseLink(
            parsedArgs["link"])
    elif "tpath" in parsedArgs:
        print("Tpath:", parsedArgs["tpath"])
        parsedArgs["hash"] = getTorrentHash(parsedArgs["tpath"])
    elif "tfolder" in parsedArgs:
        pass
    else:
        raise Exception(
            "Houston, we do not have enough information to proceed. Chack your arguments.")

sourceAPI = generateSourceTrackerAPI(parsedArgs["from"])

destAPI = generateDestinationTrackerAPI(parsedArgs["to"])

source = generateSourceFlag(parsedArgs["to"])

# sprint(parsedArgs)
# print(sys.getdefaultencoding())

# raw_input()

if "tfolder" in parsedArgs:
    sprint("Batch mode")
    total = 0
    fails = 0
    for filename in os.listdir(parsedArgs["tfolder"]):
        if filename.endswith(".torrent"):
            total += 1
            try:
                localParsed = dict()
                for i in parsedArgs:
                    localParsed[i] = parsedArgs[i]
                localParsed["tpath"] = os.path.join(
                    localParsed["tfolder"], filename)
                localParsed["hash"] = getTorrentHash(localParsed["tpath"])
                sprint(localParsed)
                moveAlbum(localParsed, sourceAPI, destAPI, source)
            except Exception as e:
                fails += 1
            sprint("Success rate:", 1 - fails/total)
    sprint("Success rate:", 1 - fails/total)
else:
    sprint("Single mode")
    moveAlbum(parsedArgs, sourceAPI, destAPI, source)
