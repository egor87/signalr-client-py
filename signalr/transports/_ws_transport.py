import json
import sys

import gevent

if sys.version_info[0] < 3:
    from urlparse import urlparse, urlunparse
else:
    from urllib.parse import urlparse, urlunparse

from websocket import create_connection
from websocket._exceptions import WebSocketException
from ._transport import Transport, TransportException


class WebSocketsTransport(Transport):
    
    max_connect_attempts = 10
    
    def __init__(self, session, connection):
        Transport.__init__(self, session, connection)
        self.ws = None
        self.__requests = {}
        self.connect_attempts = 0

    def _get_name(self):
        return 'webSockets'

    @staticmethod
    def __get_ws_url_from(url):
        parsed = urlparse(url)
        scheme = 'wss' if parsed.scheme == 'https' else 'ws'
        url_data = (scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)

        return urlunparse(url_data)

    def start(self):
        ws_url = self.__get_ws_url_from(self._get_url('connect'))

        self.init_connection(ws_url)

        def _receive():
            while True:
                try:
                    for notification in self.ws:
                        self._handle_notification(notification)
                # websocket._exceptions.WebSocketConnectionClosedException: Connection is already closed
                except WebSocketException:
                    gevent.sleep(10)
                    self.init_connection(ws_url)

        return _receive

    def send(self, data):
        self.ws.send(json.dumps(data))
        gevent.sleep()

    def close(self):
        self.ws.close()

    def accept(self, negotiate_data):
        return bool(negotiate_data['TryWebSockets'])
    
    def init_connection(self, ws_url):
        if self.connect_attempts >= self.max_connect_attempts:
            raise TransportException('Ws max connect attempts {0} exceeded'.format(self.max_connect_attempts))
        try:
            self.ws = create_connection(ws_url,
                                        header=self.__get_headers(),
                                        cookie=self.__get_cookie_str(),
                                        enable_multithread=True)
            self._session.get(self._get_url('start'))
            self.connect_attempts = 0
        except WebSocketException:
            self.connect_attempts += 1
            gevent.sleep(15)
            return self.init_connection()
            

    class HeadersLoader(object):
        def __init__(self, headers):
            self.headers = headers

    def __get_headers(self):
        headers = self._session.headers
        loader = WebSocketsTransport.HeadersLoader(headers)

        if self._session.auth:
            self._session.auth(loader)

        return ['%s: %s' % (name, headers[name]) for name in headers]

    def __get_cookie_str(self):
        return '; '.join([
                             '%s=%s' % (name, value)
                             for name, value in self._session.cookies.items()
                             ])
