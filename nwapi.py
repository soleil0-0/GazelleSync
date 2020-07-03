import re
import os
import json
import time
import requests

headers = {
	'Connection': 'keep-alive',
	'Cache-Control': 'max-age=0',
	'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_3)'
	'AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.79'
	'Safari/535.11',
	'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9'
	',*/*;q=0.8',
	'Accept-Encoding': 'gzip,deflate,sdch',
	'Accept-Language': 'en-US,en;q=0.8',
	'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3'}

class LoginException(Exception):
	pass


class RequestException(Exception):
	pass


class NwAPI:
	def __init__(self, username=None, password=None):
		self.session = requests.Session()
		self.session.headers.update(headers)
		self.username = username
		self.password = password
		self.authkey = None
		self.passkey = None
		self.userid = None
		self.userclass = None
		self.tracker = 'http://definitely.notwhat.cd/'
		self.last_request = time.time()
		self.rate_limit = 2.0  # seconds between requests
		self.site = "NWCD"
		self._login()

	def _login(self):
		'''Logs in user and gets authkey from server'''
		loginpage = 'https://notwhat.cd/login.php'
		data = {'username': self.username,
				'password': self.password}
		r = self.session.post(loginpage, data=data)
		if r.status_code != 200:
			raise LoginException
		accountinfo = self.request('index')
		self.authkey = accountinfo['authkey']
		self.passkey = accountinfo['passkey']
		self.userid = accountinfo['id']
		self.userclass = accountinfo['userstats']['class']
		print("Logged in")
		#input()

	def logout(self):
		self.session.get("https://notwhat.cd/logout.php?auth=%s" % self.authkey)

	def request(self, action, **kwargs):
		'''Makes an AJAX request at a given action page'''
		while time.time() - self.last_request < self.rate_limit:
			time.sleep(0.1)

		ajaxpage = 'https://notwhat.cd/ajax.php'
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
		except ValueError:
			raise RequestException

	def release_url(self, group, torrent):
		return "https://notwhat.cd/torrents.php?id=%s&torrentid=%s#torrent%s" % (group['group']['id'], torrent['id'], torrent['id'])

	def permalink(self, torrent):
		return "https://notwhat.cd/torrents.php?torrentid=%s" % torrent['id']

	def get_torrent_info(self, id=None, hash=None):
		if not (hash is None):
			return self.request('torrent', hash=hash)
		else:
			return self.request('torrent', id=id)

	def img(self, url):
		r = self.session.put("https://notwhat.cd/imgupload.php", data=url)
		return r.json()["url"]