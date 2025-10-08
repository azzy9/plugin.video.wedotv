# -*- coding: utf-8 -*-

import datetime

import xbmc
import xbmcaddon
import xbmcgui

import requests

import six
from six.moves.urllib.parse import quote, unquote, urlencode, parse_qsl

ADDON = xbmcaddon.Addon()
KODI_VERSION = float(xbmcaddon.Addon('xbmc.addon').getAddonInfo('version')[:4])

#language
__language__ = ADDON.getLocalizedString

dialog = xbmcgui.Dialog()
reqs = requests.session()

def request_get( url, data=None, extra_headers=None, return_json=True ):

    """ makes a request """

    try:

        # headers
        my_headers = {
            'Accept-Language': 'en-gb,en;q=0.5',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Content-type': 'application/x-www-form-urlencoded',
            'Referer': url,
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'DNT': '1'
        }

        # add extra headers
        if extra_headers:
            my_headers.update(extra_headers)

        # make request
        if data:
            response = reqs.post(url, data=data, headers=my_headers, timeout=10)
        else:
            response = reqs.get(url, headers=my_headers, timeout=10)

        if return_json:
            return response.json()
        return response.text

    except Exception:
        return ''

def pack_uri(query):

    """
    Helper function to build a Kodi xbmcgui.ListItem URL.
    :param query: Dictionary of url parameters to put in the URL.
    :returns: A formatted and urlencoded URL string.
    """

    return urlencode({k: v.encode('utf-8') if isinstance(v, six.text_type) else v for k, v in query.items()})

def unpack_uri(uri):

    """
    Helper function to build a Kodi xbmcgui.ListItem URL.
    :param query: Dictionary of url parameters to put in the URL.
    :returns: A formatted and urlencoded URL string.
    """

    return dict(parse_qsl(uri, keep_blank_values=True))


def serialize_uri(item):

    """ all uris passed via kodi's routing system must be urlquoted """

    return quote(six.ensure_str(item))

def deserialize_uri(item):

    """ all uris passed via kodi's routing system must be urlquoted """

    return unquote(item)

def item_set_info( line_item, properties ):

    """ line item set info """

    if KODI_VERSION > 19.8:
        vidtag = line_item.getVideoInfoTag()
        if properties.get( 'year' ):
            vidtag.setYear( int( properties.get( 'year' ) ) )
        if properties.get( 'episode' ):
            vidtag.setEpisode( properties.get( 'episode' ) )
        if properties.get( 'season' ):
            vidtag.setSeason( properties.get( 'season' ) )
        if properties.get( 'plot' ):
            vidtag.setPlot( properties.get( 'plot' ) )
        if properties.get( 'title' ):
            vidtag.setTitle( properties.get( 'title' ) )
        if properties.get( 'studio' ):
            vidtag.setStudios([ properties.get( 'studio' ) ])
        if properties.get( 'writer' ):
            vidtag.setWriters([ properties.get( 'writer' ) ])
        if properties.get( 'duration' ):
            vidtag.setDuration( int( properties.get( 'duration' ) ) )
        if properties.get( 'tvshowtitle' ):
            vidtag.setTvShowTitle( properties.get( 'tvshowtitle' ) )
        if properties.get( 'mediatype' ):
            vidtag.setMediaType( properties.get( 'mediatype' ) )
        if properties.get('premiered'):
            vidtag.setPremiered( properties.get( 'premiered' ) )

    else:
        line_item.setInfo('video', properties)

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

def keyboard_input(heading='', message=''):

    """ Requests for keyboard input """

    search_string = None
    keyboard = xbmc.Keyboard(message, heading)
    keyboard.doModal()
    if keyboard.isConfirmed():
        search_string = keyboard.getText()
    return search_string
