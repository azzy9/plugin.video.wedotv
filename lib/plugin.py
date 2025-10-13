import sys

import routing

import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin

import six
from six.moves import urllib_parse

from lib.exception import PluginException
from lib.general import *

WEB_URL = 'https://api-applicaster.wedo.tv'
MEDIA_TYPES = ['series', 'movies', 'sports', 'getLiveChannels', 'search']
MEDIA_NAMES = ['Series', 'Movies', 'Sports', 'Live', 'Search']
MEDIA_MODE = ['episodes', 'play', 'episodes', 'play', 'search']
MEDIA_REGIONS = [ '', '', 'gb', 'us' ]
SEARCH_TYPES = ['serie', 'movie', '', '', '']
PLAY_ENDPOINT = ['getSeason', 'getMovie', 'getSportEvent', 'getLiveChannel', 'getSearchTitle']

plugin = routing.Plugin()

BASE_URL = sys.argv[0]
ADDON_HANDLE = int(sys.argv[1])
ADDON = xbmcaddon.Addon()
args = urllib_parse.parse_qs(sys.argv[2][1:])

ADDON_REGION = int(ADDON.getSetting('region'))

xbmcplugin.setContent(ADDON_HANDLE, 'movies')

PLUGIN_ID = BASE_URL.replace('plugin://','')
MEDIA_URL = 'special://home/addons/{0}/resources/media/'.format(PLUGIN_ID)

@plugin.route('/')
def menu():

    """ main menu list """

    # Type selection
    for i, variant in enumerate(MEDIA_TYPES):
        list_item = xbmcgui.ListItem(MEDIA_NAMES[i])
        list_item.setArt({
            'icon': MEDIA_URL + MEDIA_NAMES[i] + '.jpg',
            'poster': MEDIA_URL + MEDIA_NAMES[i] + '.jpg',
        })
        callback = {
            'variant': variant,
        }
        xbmcplugin.addDirectoryItem(
            handle = ADDON_HANDLE,
            url = plugin.url_for(list_cat, uri=pack_uri(callback)),
            listitem = list_item,
            isFolder = True
        )

    list_item = xbmcgui.ListItem(get_string(5))
    list_item.setArt({
        'icon': MEDIA_URL + 'blank.jpg',
        'poster': MEDIA_URL + 'blank.jpg',
    })
    xbmcplugin.addDirectoryItem(
        handle = ADDON_HANDLE,
        url = plugin.url_for(settings),
        listitem = list_item,
        isFolder = True
    )
    xbmcplugin.endOfDirectory(ADDON_HANDLE)

@plugin.route('/list/<uri>')
def list_cat(uri):

    """ list categories """

    params = unpack_uri( uri )
    variant = params.get( 'variant', '' )
    title = params.get( 'title', '' )

    is_search = False
    extra_params = ''
    extra_params_list = []

    if variant == 'search':
        is_search = True
        term = keyboard_input( 'Search' )
        if term:
            extra_params_list.append( 'keyword=' + term )

    # we want all the movies
    if variant == 'movies':
        extra_params_list.append( 'limit=9999' )

    if ADDON_REGION > 0:
        extra_params_list.append( 'country=' + MEDIA_REGIONS[ ADDON_REGION ] )

    if extra_params_list:
        extra_params = '?' + '&'.join( extra_params_list )

    list_data = request_get( WEB_URL + '/' + variant + extra_params, return_json=True )

    # Make sure there is data to loop
    if list_data and list_data.get( 'entry', False ):

        # loop the data
        for item in list_data[ 'entry' ]:

            if is_search:
                variant = MEDIA_TYPES[ SEARCH_TYPES.index(item['type']['value']) ]

            title = item['title']
            list_item = xbmcgui.ListItem( title )
            mode = MEDIA_MODE[ MEDIA_TYPES.index(variant) ]

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

            if thumbnail == '':
                # if no thumbnail
                thumbnail = background
            elif background == '':
                # if no background
                background = thumbnail

            # set thumbnails
            if thumbnail:
                for art_type in ['thumb', 'poster', 'icon']:
                    list_item.setArt({art_type:thumbnail})

            # set background
            if background:
                for art_type in ['banner', 'fanart']:
                    list_item.setArt({art_type:background})

            is_folder = True
            if mode == 'play':

                list_item.setProperty('IsPlayable', 'true')

                info_labels={ 'title': title }
                info_labels = video_meta( item, info_labels, variant )
                item_set_info( list_item, info_labels )

                is_folder = False

            callback = {
                'id': item['id'],
                'variant': variant,
                'title': title,
                'thumb': thumbnail,
            }

            xbmcplugin.addDirectoryItem(
                handle = ADDON_HANDLE,
                url = plugin.url_for(globals()[mode], uri=pack_uri(callback)),
                listitem = list_item,
                isFolder = is_folder
            )

    xbmcplugin.endOfDirectory(ADDON_HANDLE)

@plugin.route('/episodes/<uri>')
def episodes(uri):

    """ retrieves episodes """

    params = unpack_uri( uri )
    season_id = params.get( 'season_id', '1' )
    variant = params.get( 'variant', '' )
    title = params.get( 'title', '' )

    seasons = request_get( WEB_URL + '/' + 'getSeasonTabs?series_id=' + season_id, return_json=True )

    # Make sure there is data to loop
    if seasons and seasons.get( 'entry', False ):

        # loop the seasons
        for season in seasons[ 'entry' ]:

            try:
                season_number = season['title'].replace('Season','').strip()
            except Exception:
                season_number = '1'

            episodes = request_get( WEB_URL + '/' + 'getSeason?season_id=' + season['id'], return_json=True )

            # Make sure there is data to loop
            if episodes and episodes.get( 'entry', False ):

                for episode in episodes[ 'entry' ]:

                    episode_title = episode['title']
                    list_item = xbmcgui.ListItem( episode_title )

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

                    if thumbnail == '':
                        # if no thumbnail
                        thumbnail = background
                    elif background == '':
                        # if no background
                        background = thumbnail

                    # set thumbnails
                    if thumbnail:
                        for art_type in ['thumb', 'poster', 'icon']:
                            list_item.setArt({art_type:thumbnail})

                    # set background
                    if background:
                        for art_type in ['banner', 'fanart']:
                            list_item.setArt({art_type:background})

                    info_labels = {
                        'title': episode_title,
                        'season': season_number,
                        'mediatype': 'episode',
                        'tvshowtitle': title,
                    }

                    list_item.setProperty('IsPlayable', 'true')
                    info_labels = video_meta( episode, info_labels, variant )
                    item_set_info( list_item, info_labels )

                    callback = {
                        'id': episode['id'],
                        'type': variant,
                        'title': episode_title,
                        'thumb': thumbnail,
                    }
                    url = plugin.url_for(play, uri=pack_uri(callback))
                    xbmcplugin.addDirectoryItem(
                        handle = ADDON_HANDLE,
                        url = url,
                        listitem = list_item,
                        isFolder = False
                    )

    xbmcplugin.endOfDirectory(ADDON_HANDLE)

def subtitles_select( subtitles_in ):

    subtitles = []
    selected_index = -1

    subtitles_tmp = []
    for key in subtitles_in:
        subtitles_tmp.append((key, subtitles_in[ key ]))

    if ADDON.getSetting('subtitles_select') == 'true' and len( subtitles_tmp ) > 1:
        selected_index = xbmcgui.Dialog().select(
            'Select Subtitle', [(lang[0] or '?') for lang in subtitles_tmp]
        )

    if selected_index != -1:
        subtitles.append( subtitles_tmp[selected_index][1] )
    else:
        for subs in subtitles_tmp:
            subtitles.append( subs[1] )

    return subtitles

@plugin.route('/play/<uri>')
def play(uri):

    """ plays video """

    params = unpack_uri( uri )
    video_url = False
    video_id = params.get( 'id', '' )
    variant = params.get( 'variant', '' )
    title = params.get( 'title', '' )
    thumb = params.get( 'thumb', '' )

    info_labels={}

    if video_id:
        video = request_get(
            WEB_URL + '/' + PLAY_ENDPOINT[ MEDIA_TYPES.index(variant) ] + '?id=' + video_id,
            return_json=True
        )

        info_labels['setid'] = video_id
        entry = video['entry'][0]
        video_url = entry['content']['src']
        subtitles = entry['extensions'].get('subtitles', {}).get('srt', False)
        info_labels = video_meta( entry, info_labels, variant )

    if video_url:

        info_labels['title'] = title

        list_item = xbmcgui.ListItem(title, path=video_url)

        # set subtitles if available & enabled
        if subtitles and ADDON.getSetting('subtitles_enabled') == 'true':
            subtitles = subtitles_select( subtitles )
            if subtitles:
                list_item.setSubtitles( subtitles )


        list_item.setArt({'thumb': thumb })
        item_set_info( list_item, info_labels )

        xbmcplugin.setResolvedUrl(ADDON_HANDLE, True, list_item)
    else:
        xbmc.okDialog( 'Error', 'No Video Found' )

@plugin.route('/settings')
def settings():

    """ Method to open settings menu """

    ADDON.openSettings()

def run():

    """ Run the plugin """

    try:
        plugin.run()
    except PluginException as err:
        xbmc.log("PluginException: " + str( err ))
