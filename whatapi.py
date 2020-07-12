#!/usr/bin/env python3
# -*-coding=utf-8 -*-

# imports: standard
import re
import os
import sys
import time
import string
import subprocess
import shutil
import logging

# imports: third party
import requests

headers = {
	'Connection': 'keep-alive',
	'Cache-Control': 'max-age=0',
	'User-Agent': 'RedApi',
	'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
	'Accept-Encoding': 'gzip,deflate,sdch',
	'Accept-Language': 'en-US,en;q=0.8',
	'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3'}

def create_upload_request(auth, album, torrent, logfiles, tags, artwork_url, artists):
	if album["remaster"]:
		logging.info("Is a remaster")
		data = [
			("submit", "true"),  # the submit button
			("auth", auth),  # input name=auth on upload page - appears to not change
			("type", "0"),  # music
			("title", album["album"]),
			("year", str(album["original_year"])),
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
		logging.info("Is not a remaster")
		data = [
			("submit", "true"),  # the submit button
			("auth", auth),  # input name=auth on upload page - appears to not change
			("type", "0"),  # music
			("title", album["album"]),
			("year", str(album["original_year"])),
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
	logging.info(data[4])
	for artist in artists:
		data.append(("artists[]", artist[0]))
		data.append(("importance[]", artist[1]))
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

class LoginException(Exception):
	pass

class RequestException(Exception):
	pass

class WhatAPI:
	def __init__(self, username=None, password=None, tracker=None, url=None, site=None, cookie=None):
		self.session = requests.Session()
		self.session.headers.update(headers)
		self.username = username
		self.password = password
		self.authkey = None
		self.passkey = None
		self.userid = None
		self.last_request = time.time()
		self.rate_limit = 2.0 # seconds between requests
		self.url = url
		self.site = site
		self.api = "WCD"
		self.tracker = tracker
		if cookie:
			self.session.headers['cookie'] = cookie
			try:
				logging.info("use cookie to invoke api of <%s>" % self.site)
				self._auth()
			except RequestException:
				logging.info("cookie invalid, login <%s> with password instead" % self.site)
				del self.session.headers['cookie']
				self._login(tracker)
		else:
			logging.info("login with password")
			self._login(tracker)

	def _auth(self):
		"""Gets auth key from server"""
		accountinfo = self.request("index")
		self.authkey = accountinfo['authkey']
		self.passkey = accountinfo['passkey']
		self.userid = accountinfo['id']

	def _login(self, tracker):
		'''Logs in user and gets authkey from server'''
		loginpage = self.url + '/login.php'
		data = {'username': self.username,
				'password': self.password}
		r = self.session.post(loginpage, data=data)
		if r.status_code != 200 or not r.url.endswith('index.php'):
			raise LoginException("Login <%s> failed, username or password may be incorrect" % self.site)
		try:
			accountinfo = self.request('index')
			self.authkey = accountinfo['authkey']
			self.passkey = accountinfo['passkey']
			self.userid = accountinfo['id']
			self.tracker = tracker.format(self.passkey)
		except Exception as e:
			raise e
			logging.info("unable to log in")
			logging.info(r.text)
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
		try:
			json_response = r.json()
			if json_response["status"] != "success":
				raise RequestException
			return json_response["response"]
		except ValueError:
			raise RequestException

	def upload(self, album_dir, output_dir, album, tags, artwork_url, artists, torrentpath):
		url = self.url + "/upload.php"
		torrent = ('torrent.torrent', open(torrentpath, 'rb'), "application/octet-stream")
		logfiles = locate(album_dir, ext_matcher('.log'))
		logfiles = [(str(i) + '.log', open(logfile, 'rb'), "application/octet-stream") for i, logfile in enumerate(logfiles)]
		r = self.session.get(url)
		auth = re.search('name="auth" value="([^"]+)"', r.text).group(1)
		data, files = create_upload_request(auth, album, torrent, logfiles, tags, artwork_url, artists)
		logging.info(data)
		upload_headers = dict(headers)
		upload_headers["referer"] = url
		upload_headers["origin"] = url.rsplit("/", 1)[0]
		logging.info(album["album"])
		r = self.session.post(url, data=data, files=files, headers=upload_headers)
		if "torrent_comments" not in r.text:
			logging.error("upload failed.")

			self.errmsg(r.text)

			f = open("ret.html", "wb")
			f.write(r.text.encode("utf-8"))
			f.close()

			return False
		else:
			return True

	def errmsg(self, text):
		for line in text.splitlines():
			if '<p style="color: red; text-align: center;">' in line:
				logging.error(re.sub('<[^<]+?>', '', line).strip())

	def release_url(self, group, torrent):
		return self.url + "/torrents.php?id=%s&torrentid=%s#torrent%s" % (group['group']['id'], torrent['id'], torrent['id'])

	def permalink(self, torrent):
		return self.url + "/torrents.php?torrentid=%s" % torrent['id']

	def is_duplicate(self, album):
		# TODO
		return False

	def img(self, url):
		r = self.session.put(self.url + "imgupload.php", data=url)
		return r.json()["url"]

	def HTMLtoBBCODE(self, text):
		while time.time() - self.last_request < self.rate_limit:
			time.sleep(0.1)
		params = {
			"action": "parse_html"
		}
		data = [
			("html", text)
		]
		url = self.url + '/upload.php'
		r = self.session.post(url, data=data, params=params)
		self.last_request = time.time()
		return r.content
