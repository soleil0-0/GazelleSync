#!/usr/bin/env python3
import re
import os
import json
import time
import requests

headers = {
	'Connection': 'keep-alive',
	'Cache-Control': 'max-age=0',
	'User-Agent': 'RedApi',
	'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
	'Accept-Encoding': 'gzip,deflate,sdch',
	'Accept-Language': 'en-US,en;q=0.8',
	'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3'}

class LoginException(Exception):
	pass


class RequestException(Exception):
	pass

class RedApi:
	def __init__(self, username=None, password=None):
		self.session = requests.Session()
		self.session.headers.update(headers)
		self.session.headers['User-Agent'] += ' [{}]'.format(username)
		self.username = username
		self.password = password
		self.authkey = None
		self.passkey = None
		self.userid = None
		self.tracker = "https://flacsfor.me/"
		self.last_request = time.time()
		self.rate_limit_cool_down = 10
		self.rate_limit_max = 5
		self._rate_limit_table = []
		self.site = "RED"
		self._login()

	def _rate_limit(self):
		"""This method is blocking"""
		self._rate_limit_update()
		if self.rate_limit_max <= len(self._rate_limit_table):
			sleep_time = min(self._rate_limit_table) + self.rate_limit_cool_down
			sleep_time -= time.time()
			time.sleep(sleep_time)
			self._rate_limit()  # should sleep again if needed. In practice this should never happen

		self._rate_limit_table.append(time.time())
		return True

	def _rate_limit_update(self):
		self._rate_limit_table = list(filter(
			lambda x: x + self.rate_limit_cool_down > time.time(),
			self._rate_limit_table
		))

	def _login(self):
		"""Logs in user and gets authkey from server"""
		loginpage = 'https://redacted.ch/login.php'
		data = {'username': self.username,
				'password': self.password}
		r = self.session.post(loginpage, data=data)
		if r.status_code != 200:
			raise LoginException
		accountinfo = self.request('index')
		self.authkey = accountinfo['authkey']
		self.passkey = accountinfo['passkey']
		self.userid = accountinfo['id']

	def logout(self):
		self.session.get("https://redacted.ch/logout.php?auth=%s" % self.authkey)

	def request(self, action, **kwargs):
		"""Makes an AJAX request at a given action page"""
		self._rate_limit()

		ajaxpage = 'https://redacted.ch/ajax.php'
		params = {'action': action}
		if self.authkey:
			params['auth'] = self.authkey
		params.update(kwargs)
		r = self.session.get(ajaxpage, params=params, allow_redirects=False)
		self.last_request = time.time()
		try:
			parsed = json.loads(r.content.decode())
			print(parsed["status"])
			if parsed['status'] != 'success':
				raise RequestException
			return parsed['response']
		except ValueError:
			raise RequestException

	def request_html(self, action, **kwargs):
		self._rate_limit()

		ajaxpage = 'https://redacted.ch/' + action
		#print "Requesting", ajaxpage
		if self.authkey:
			kwargs['auth'] = self.authkey
		r = self.session.get(ajaxpage, params=kwargs, allow_redirects=False)
		self.last_request = time.time()
		return r.content

	def get_torrent(self, torrent_id):
		"""Downloads the torrent at torrent_id using the authkey and passkey"""
		self._rate_limit()

		torrentpage = 'https://redacted.ch/torrents.php'
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