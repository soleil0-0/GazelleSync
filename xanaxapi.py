#!/usr/bin/env python2.7
import re
import os
import json
import time
import requests

__site_url__ = "https://orpheus.network/"
__torrent_url__ = "https://home.opsfet.ch/"

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

class LoginException(Exception):
	pass

class RequestException(Exception):
	pass

class XanaxAPI:
	def __init__(self, username=None, password=None):
		self.session = requests.Session()
		self.session.headers.update(headers)
		self.username = username
		self.password = password
		self.authkey = None
		self.passkey = None
		self.userid = None
		self.tracker = __torrent_url__ + "/"
		self.last_request = time.time()
		self.rate_limit = 2.0 # seconds between requests
		self.site = "APL"
		self._login()

	def _login(self):
		'''Logs in user and gets authkey from server'''
		loginpage = __site_url__ + '/login.php'
		data = {'username': self.username,
				'password': self.password}
		r = self.session.post(loginpage, data=data)
		if r.status_code != 200:
			raise LoginException
		accountinfo = self.request('index')
		self.authkey = accountinfo['authkey']
		self.passkey = accountinfo['passkey']
		self.userid = accountinfo['id']

	def limit(self):
		while time.time() - self.last_request < self.rate_limit:
			time.sleep(0.1)

	def logout(self):
		self.session.get("%s/logout.php?auth=%s" % (__site_url__, self.authkey))

	def request(self, action, **kwargs):
		'''Makes an AJAX request at a given action page'''
		self.limit()

		ajaxpage = __site_url__ + '/ajax.php'
		params = {'action': action}
		if self.authkey:
			params['auth'] = self.authkey
		params.update(kwargs)
		r = self.session.get(ajaxpage, params=params, allow_redirects=False)
		self.last_request = time.time()
		try:
			parsed = json.loads(r.content.decode())
			if parsed['status'] != 'success':
				raise RequestException
			return parsed['response']
		except ValueError as e:
			raise RequestException(e)

	def request_html(self, action, **kwargs):
		self.limit()

		ajaxpage = __site_url__ + '/' + action
		if self.authkey:
			kwargs['auth'] = self.authkey
		r = self.session.get(ajaxpage, params=kwargs, allow_redirects=False)
		self.last_request = time.time()
		return r.content

	def get_torrent(self, torrent_id):
		'''Downloads the torrent at torrent_id using the authkey and passkey'''
		self.limit()

		torrentpage = __site_url__ + '/torrents.php'
		params = {'action': 'download', 'id': torrent_id}
		if self.authkey:
			params['authkey'] = self.authkey
			params['torrent_pass'] = self.passkey
		r = self.session.get(torrentpage, params=params, allow_redirects=False)

		self.last_request = time.time() + 2.0
		if r.status_code == 200 and 'application/x-bittorrent' in r.headers['content-type']:
			return r.content
		return None

	def get_torrent_info(self, id=None, hash=None):
		if not (hash is None):
			return self.request('torrent', hash=hash)
		else:
			return self.request('torrent', id=id)

	def HTMLtoBBCODE(self, text):
		self.limit()

		params = {
			"action": "parse_html"
		}
		data = [
			("html", text)
		]
		url = __site_url__ + '/upload.php'
		r = self.session.post(url, data=data, params=params)
		self.last_request = time.time()
		return r.content
