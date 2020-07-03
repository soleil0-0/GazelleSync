from __future__ import print_function, division

import sys
import re
import os
import json
import time
import requests
import mechanize
import HTMLParser
from cStringIO import StringIO
import maketorrent
from redapi import RedApi
from whatapi import WhatAPI
from nwapi import NwAPI
from xanaxapi import XanaxAPI

import constants

tempHTML = HTMLParser.HTMLParser()

class MLStripper(HTMLParser.HTMLParser):
	def __init__(self):
		self.reset()
		self.fed = []
	def handle_data(self, d):
		self.fed.append(d)
	def get_data(self):
		return ''.join(self.fed)

def strip_tags(html):
	s = MLStripper()
	s.feed(html)
	return s.get_data()

def unescape(inp):
	return tempHTML.unescape(inp)

def toUnicode(inp):
	if isinstance(inp, unicode):
		return inp
	else:
		return unicode(inp, sys.getfilesystemencoding())


#folder torrentpath TorrentIDRed GroupIDsource AlbumIDApollo


#folder = sys.argv[1]
#TorrentIDsource = sys.argv[2]
#GroupIDsource = sys.argv[3]
#if len(sys.argv) > 4:
#	AlbumIDApollo = sys.argv[4]
#else:
#	AlbumIDApollo = None

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
	"apl",
	"red",
	"nwcd",
}

possible = {
	"album",
	"from",
	"to",
	"tid",
	"gid",
	"folder"
}

def validateTrackers(result):
	result["to"] = result["to"].lower()
	result["from"] = result["from"].lower()

	if result["to"] == result["from"]:
		return False

	return (result["to"] in trackers) and (result["from"] in trackers)

def parseArguments(args):
	comp = dict()
	for c in compulsory:
		comp[c] = False

	result = dict()
	for a in args:
		#sprint(a)
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
	sprint("All true", allTrue)
	if not allTrue:
		print("The following arguments are compulsory")
		for c in compulsory:
			sprint(c)
		raise('Error')
	tr = validateTrackers(result)
	if not tr:
		raise("Trackers can only be RED, APL, and NWCD")

	if ("gid" in result):
		if not int(result["gid"]):
			raise("gid arguemtn has to be number")

	if ("tid" in result):
		if not int(result["tid"]):
			raise("gid arguemtn has to be number")

	return result

def generateSourceTrackerAPI(tracker):
	if tracker == "red":
		print("Source tracker is RED")
		return RedApi(username=constants.RedUsername, password=constants.RedPassword)
	elif tracker == "apl":
		print("Source tracker is APL")
		return XanaxAPI(username=constants.ApolloUsername, password=constants.ApolloPassword)
	elif tracker == "nwcd":
		print("Source tracker is NWCD")
		return NwAPI(username=constants.NWCDUsername, password=constants.NWCDPassword)

def generateDestinationTrackerAPI(tracker):
	if tracker == "red":
		print("Destination tracker is RED")
		return WhatAPI(username=constants.RedUsername, password=constants.RedPassword, tracker = "https://flacsfor.me/", url = "https://redacted.ch/")
	elif tracker == "apl":
		print("Destination tracker is APL")
		return WhatAPI(username=constants.ApolloUsername, password=constants.ApolloPassword, tracker = "https://mars.apollo.rip/", url = "https://apollo.rip/")
	elif tracker == "nwcd":
		print("Destination tracker is NWCD")
		return WhatAPI(username=constants.NWCDUsername, password=constants.NWCDPassword, tracker = "https://definitely.notwhat.cd:443/", url = "https://notwhat.cd/")



def moveAlbum(parsedArgs, a, w):

	TorrentIDsource = parsedArgs["tid"]
	GroupIDsource = parsedArgs["gid"]
	folder = ""

	sprint("Source", a.tracker)
	sprint("Dest", w.tracker)

	tdata = a.get_torrent_info(TorrentIDsource)
	f = open("torrent.json","w")
	f.write(json.dumps(tdata,indent=4))
	f.close()
	
	gdata = a.request("torrentgroup", id=GroupIDsource)
	f = open("group.json","w")
	f.write(json.dumps(gdata,indent=4))
	f.close()

	if "album" in parsedArgs:
		folder = parsedArgs["album"]
	elif "folder" in parsedArgs:
		folder = os.path.join(parsedArgs["folder"], unescape(tdata["filePath"]))
		sprint("Folder:", folder, "====")
	else:
		raise Exception("Failed to find path")
	
	
	
	t_media = tdata["media"]
	t_format = tdata["format"]
	t_encoding = tdata["encoding"]
	t_description = tdata["description"] + "\n\nUploaded with "+parsedArgs["from"].upper()+" to "+parsedArgs["to"].upper()+"."
	t_remasterYear = tdata["remasterYear"]
	t_remasterCatalogueNumber = tdata["remasterCatalogueNumber"]
	t_remastered = tdata["remastered"]
	t_remasterRecordLabel = tdata["remasterRecordLabel"]
	t_remasterTitle = tdata["remasterTitle"]
	
	g_group = gdata["group"]
	g_artists = g_group["musicInfo"]["artists"]
	g_name = g_group["name"]
	g_year = g_group["year"]
	g_recordLabel = g_group["recordLabel"]
	g_catalogueNumber = g_group["catalogueNumber"]
	g_releaseType = g_group["releaseType"]
	g_tags = g_group["tags"]
	#g_wikiImage = g_group["wikiImage"]
	if parsedArgs["to"] != "nwcd":
		g_wikiImage = g_group["wikiImage"]
	else:
		g_wikiImage = "https://art.notwhat.co/bc7b34debc056ee22d69ebdc1f189050.jpg"

	g_wikiBody = strip_tags(g_group["wikiBody"]) #.replace("<br />", "\n")
	g_group["wikiBody"] = g_group["wikiBody"].replace("\r\n", "\n")
	#g_group["wikiBody"] = g_group["wikiBody"].replace("\n\n", "\n")
	#g_group["wikiBody"] = g_group["wikiBody"].replace("\n\n", "\n")
	#g_group["wikiBody"] = g_group["wikiBody"].replace("\n\n", "\n")
	
	album = dict(
		album = g_name,
		original_year = g_year,
		remaster = t_remastered,
		record_label = g_recordLabel,
		catalogue_number = g_catalogueNumber,
		releasetype = g_releaseType,
		remaster_year = t_remasterYear,
		remaster_title = t_remasterTitle,
		remaster_record_label = t_remasterRecordLabel,
		remaster_catalogue_number = t_remasterCatalogueNumber,
		format = t_format,
		encoding = t_encoding,
		media = t_media,
		description = g_wikiBody,
		rDesc = t_description
	)
	
	artists = list()
	count = 0
	for i,v in enumerate(g_artists):
		artists.append(v["name"])
	
	print(album["album"])
	
	tempfolder = "torrent"
	
	if not os.path.exists(tempfolder):
		os.makedirs(tempfolder)
	
	
	artist_name = ""
	
	if len(g_artists) > 2:
		artist_name = "Various Artists"
	elif len(g_artists) == 1:
		artist_name = g_artists[0]["name"]
	else:
		artist_name = g_artists[0]["name"] + " & " + g_artists[1]["name"]
	
	edition = ""
	if t_remastered:
		if t_remasterCatalogueNumber:
			edition = " {" + t_remasterCatalogueNumber + "}"
		else:
			edition = ""
	else:
		if g_catalogueNumber:
			edition = " {" + g_catalogueNumber + "}"
		else:
			edition = ""
	
	name = artist_name+" - "+g_name+" ("+str(g_year)+") ["+t_media+" "+t_format+ " " + t_encoding + "]" + edition
	
	tpath = name+".torrent"
	
	tpath = tpath.replace("/", "_")
	tpath = tpath.replace("\\", "_")
	tpath = tpath.replace(":", "_")
	
	tpath = "torrent/"+tpath
	
	print(tpath)
	print("Folder", folder)
	folder = toUnicode(folder)

	print("Folder", folder)
	#raw_input()
	
	t = maketorrent.TorrentMetadata()
	t.set_data_path(folder)
	t.set_comment("Created with Gazelle to Apollo")
	t.set_private(True)
	t.set_trackers([["https://mars.apollo.rip/"+w.passkey+"/announce"]])
	t.set_source("APL")
	t.save(tpath)
	
	w.upload(folder, tempfolder, album, g_tags, g_wikiImage, artists, tpath)


__version__ = "1.4"
__site_url__ = "https://apollo.rip"
__torrent_url__ = "https://mars.apollo.rip"

parsedArgs = parseArguments(sys.argv)

sourceAPI = generateSourceTrackerAPI(parsedArgs["from"])

destAPI = generateDestinationTrackerAPI(parsedArgs["to"])

sprint(parsedArgs)
print(sys.getdefaultencoding())

#raw_input()

moveAlbum(parsedArgs, sourceAPI, destAPI)