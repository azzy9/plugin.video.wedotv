import ssl

import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin

import sys
import re

import json
import requests

import datetime
from time import time, sleep

import six
from six.moves import urllib, urllib_parse

WEB_URL = 'https://api-applicaster.wedo.tv'
media_types = ['series', 'movies', 'sports', 'getLiveChannels', 'search']
media_names = ['Series', 'Movies', 'Sports', 'Live', 'Search']
media_mode = ['episodes', 'play', 'episodes', 'play', 'search']
search_types = ['serie', 'movie', '', '', '']
play_endpoint = ['getSeason', 'getMovie', 'getSportEvent', 'getLiveChannel', 'getSearchTitle']

base_url = sys.argv[0]
addon_handle = int(sys.argv[1])
addon = xbmcaddon.Addon()
args = urllib_parse.parse_qs(sys.argv[2][1:])

xbmcplugin.setContent(addon_handle, 'movies')

PLUGIN_ID = base_url.replace('plugin://','')
MEDIA_URL = 'special://home/addons/{0}/resources/media/'.format(PLUGIN_ID)

PROPERTY_SESSION_COOKIE = 'wedotv.cookie'

# Disable urllib3's "InsecureRequestWarning: Unverified HTTPS request is being made" warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

from urllib3.poolmanager import PoolManager
from requests.adapters import HTTPAdapter

class TLS11HttpAdapter(HTTPAdapter):
    # "Transport adapter" that allows us to use TLSv1.1
    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize,
            block=block, ssl_version=ssl.PROTOCOL_TLSv1_1)


class TLS12HttpAdapter(HTTPAdapter):
    # "Transport adapter" that allows us to use TLSv1.2
    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize,
            block=block, ssl_version=ssl.PROTOCOL_TLSv1_2)


s = requests.session()
tls_adapters = [TLS12HttpAdapter(), TLS11HttpAdapter()]

def getRawWindowProperty(prop):
    window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
    return window.getProperty(prop)

def setRawWindowProperty(prop, data):
    window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
    window.setProperty(prop, data)

def fetch_url(url, data=None, extra_headers=None):

    """ fetches data from URL """

    my_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:107.0) Gecko/20100101 Firefox/107.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml,application/json;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'DNT': '1'
    }

    if extra_headers:
        my_headers.update(extra_headers)

    cookie_property = getRawWindowProperty(PROPERTY_SESSION_COOKIE)
    if cookie_property:
        cookie_dict = dict(pair.split('=') for pair in cookie_property.split('; '))
    else:
        cookie_dict = None

    start_time = time()

    status = 0
    i = -1
    while status != 200 and i < 2:
        if data:
            response = s.post(
                url, data=data, headers=my_headers, verify=False, cookies=cookie_dict, timeout=10
            )
        else:
            response = s.get(
                url, headers=my_headers, verify=False, cookies=cookie_dict, timeout=10
            )
        status = response.status_code
        i += 1
        if status == 403 and 'cloudflare' in response.headers.get('Expect-CT', ''):
            s.mount(WEB_URL, tls_adapters[i])

    # Store the session cookie(s), if any.
    if not cookie_property and response.cookies:
        setRawWindowProperty(
            PROPERTY_SESSION_COOKIE, '; ' . \
            join(pair[0]+'='+pair[1] for pair in response.cookies.get_dict().items())
        )

    elapsed = time() - start_time
    if elapsed < 0.5:
        sleep(0.5 - elapsed)

    return response

def construct_request(query):

    """ Constructs Query """

    return base_url + "?" + urllib_parse.urlencode(query)

def keyboard_input(heading='', message=''):

    """ Requests for keyboard input """

    search_string = None
    keyboard = xbmc.Keyboard(message, heading)
    keyboard.doModal()
    if keyboard.isConfirmed():
        search_string = keyboard.getText()
    return search_string

def video_meta( data, return_data, variant='' ):

    """ extract appropriate data from API call """

    try:
        return_data['genre'] = data['extensions']['genre']
    except Exception:
        pass

    try:
        return_data['country'] = data['extensions']['country']
    except Exception:
        pass

    if variant == 'getLiveChannels':
        return_data['year'] = datetime.date.today().year
    else:
        try:
            return_data['year'] = data['extensions']['year']
        except Exception:
            pass

    if 'setid' not in return_data.keys() and 'id' in data.keys():
        return_data['setid'] = data['id']

    try:
        return_data['rating'] = data['extensions']['imdb_score'].replace('Imdb Rating:','').strip()
    except Exception:
        pass

    try:
        return_data['director'] = data['extensions']['director']
    except Exception:
        pass

    try:
        return_data['plot'] = data['extensions']['description']
    except Exception:
        pass

    try:
        return_data['plotoutline'] = data['summary']
    except Exception:
        pass

    if 'title' not in return_data.keys() and 'title' in data.keys():
        return_data['title'] = data['title']

    try:
        return_data['duration'] = data['extensions']['duration']
    except Exception:
        pass

    try:
        return_data['mediatype'] = data['type']['value']
    except Exception:
        pass

    return return_data

# get args
mode = args.get('mode', [''])[0]
id = args.get('id', [''])[0]
variant = args.get('type', [''])[0]
title = args.get('title', [''])[0]
thumb = args.get('thumb', [''])[0]
isdirect = args.get('isdirect', [''])[0]

if mode == '':

    # Type selection
    for i, variant in enumerate(media_types):
        list_item = xbmcgui.ListItem(media_names[i])
        list_item.setArt({
            'icon':MEDIA_URL + media_names[i] + '.jpg',
            'poster':MEDIA_URL + media_names[i] + '.jpg',
        })
        callback = construct_request({
            'mode': 'list',
            'type': variant,
        })
        xbmcplugin.addDirectoryItem(
            handle = addon_handle,
            url = callback,
            listitem = list_item,
            isFolder = True
        )
    xbmcplugin.endOfDirectory(addon_handle)

elif mode == 'list':

    is_search = False
    extra_params = ''

    if variant == 'search':
        is_search = True
        term = keyboard_input('Search')
        if term:
            extra_params = '?keyword=' + term

    # we want all the movies
    if variant == 'movies':
        extra_params = '?limit=9999'

    list_data = fetch_url( WEB_URL + '/' + variant + extra_params ).json()

    for item in list_data[ 'entry' ]:

        if is_search:
            variant = media_types[ search_types.index(item['type']['value']) ]
            xbmc.log( variant, xbmc.LOGWARNING )

        title = item['title']
        list_item = xbmcgui.ListItem( title )
        mode = media_mode[ media_types.index(variant) ]

        thumbnail = ''
        background = ''

        # check & set thumbnail
        if item['media_group']:
            for media in item['media_group']:
                if media['type'] == 'image':
                    for media_item in media['media_item']:
                        if 'portrait' in media_item['key']:
                            thumbnail = media_item['src']
                        else:
                            background = media_item['src']

        # if no thumbnail
        if thumbnail == '':
            thumbnail = background

        # if no background
        if background == '':
            background = thumbnail

        # set thumbnails
        if thumbnail:
            for art_type in ['thumb', 'poster', 'icon']:
                list_item.setArt({art_type:thumbnail})

        # set background
        if background:
            for art_type in ['banner', 'fanart']:
                list_item.setArt({art_type:background})

        if mode == 'play':

            infoLabels={ 'title': title }
            infoLabels = video_meta( item, infoLabels, variant )

            list_item.setInfo( 'Video', infoLabels )
            list_item.setProperty('IsPlayable', 'true')
            is_folder = False
        else:
            is_folder = True

        callback = construct_request({
            'id': item['id'],
            'type': variant,
            'mode': mode,
            'title': title,
            'thumb': thumbnail,
        })

        xbmcplugin.addDirectoryItem(
            handle = addon_handle,
            url = callback,
            listitem = list_item,
            isFolder = is_folder
        )

    xbmcplugin.endOfDirectory(addon_handle)

elif mode == 'episodes':

    seasons = fetch_url( WEB_URL + '/' + 'getSeasonTabs?series_id=' + id ).json()

    for season in seasons[ 'entry' ]:

        try:
            season_number = season['title'].replace('Season','').strip()
        except Exception:
            season_number = '1'

        episodes = fetch_url( WEB_URL + '/' + 'getSeason?season_id=' + season['id'] ).json()

        # year is set per season
        year = ''

        for episode in episodes[ 'entry' ]:

            episode_title = episode['title']
            list_item = xbmcgui.ListItem( episode_title )
            mode = media_mode[ media_types.index(variant) ]

            thumbnail = ''
            background = ''

            # check & set thumbnail
            if episode['media_group']:
                for media in episode['media_group']:
                    if media['type'] == 'image':
                        for media_item in media['media_item']:
                            if 'portrait' in media_item['key']:
                                thumbnail = media_item['src']
                            else:
                                background = media_item['src']

            # if no thumbnail
            if thumbnail == '':
                thumbnail = background

            # if no background
            if background == '':
                background = thumbnail

            # set thumbnails
            if thumbnail:
                for art_type in ['thumb', 'poster', 'icon']:
                    list_item.setArt({art_type:thumbnail})

            # set background
            if background:
                for art_type in ['banner', 'fanart']:
                    list_item.setArt({art_type:background})

            infoLabels={ 'title': episode_title, 'season': season_number, 'mediatype': 'episode', 'tvshowtitle': title }
            infoLabels = video_meta( episode, infoLabels, variant )

            list_item.setInfo( 'Video', infoLabels )
            list_item.setProperty('IsPlayable', 'true')

            callback = construct_request({
                'id': episode['id'],
                'url': episode['content']['src'],
                'type': variant,
                'mode': 'play',
                'title': episode_title,
                'thumb': thumbnail,
                'isdirect': True,
            })
            xbmcplugin.addDirectoryItem(
                handle = addon_handle,
                url = callback,
                listitem = list_item,
                isFolder = False
            )

    xbmcplugin.endOfDirectory(addon_handle)

elif mode == 'play':

    if isdirect:
        video = args.get("url", [""])[0]
    else:
        video = fetch_url(
            WEB_URL + '/' + play_endpoint[ media_types.index(variant) ] + '?id=' + id
        ).json()

    if video:

        infoLabels={ 'setid': id }

        if isdirect:
            source = video
            infoLabels['title'] = title
        else:
            source = video['entry'][0]['content']['src']
            infoLabels = video_meta( video['entry'][0], infoLabels, variant )

        list_item = xbmcgui.ListItem(title, path=source)
        list_item.setInfo( 'Video', infoLabels )
        list_item.setArt({'thumb':thumb})

        xbmcplugin.setResolvedUrl(addon_handle, True, list_item)
    else:
        xbmc.okDialog( 'Error', 'No Video Found' )
