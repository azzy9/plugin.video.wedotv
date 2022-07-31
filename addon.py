import re, json, sys, requests
import xbmc, xbmcgui, xbmcaddon, xbmcplugin
from time import time, sleep
import ssl
import six
from six.moves import urllib, urllib_parse

WEB_URL = "https://en-gb.wedotv.com"
media_types = ["series_1", "movies", "sport"]
media_names = ["Series", "Movies", "Sports"]
media_mode = ["episodes", "play", "episodes"]

base_url = sys.argv[0]
addon_handle = int(sys.argv[1])
addon = xbmcaddon.Addon()
args = urllib_parse.parse_qs(sys.argv[2][1:])

xbmcplugin.setContent(addon_handle, "movies")

PLUGIN_ID = base_url.replace("plugin://","")
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

def fetchURL(url, data=None, extraHeaders=None):
    myHeaders = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml,application/json;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'DNT': '1'
    }
    if extraHeaders:
        myHeaders.update(extraHeaders)

    # At the moment it's a single response cookie, "__cfduid". Other cookies are set w/ Javascript by ads.
    cookieProperty = getRawWindowProperty(PROPERTY_SESSION_COOKIE)
    if cookieProperty:
        cookieDict = dict(pair.split('=') for pair in cookieProperty.split('; '))
    else:
        cookieDict = None

    startTime = time()

    status = 0
    i = -1
    while status != 200 and i < 2:
        if data:
            response = s.post(url, data=data, headers=myHeaders, verify=False, cookies=cookieDict, timeout=10)
        else:
            response = s.get(url, headers=myHeaders, verify=False, cookies=cookieDict, timeout=10)
        status = response.status_code
        if status == 403 and 'cloudflare' in response.headers.get('Expect-CT', ''):
            i += 1
            s.mount(BASEURL, tls_adapters[i])

    # Store the session cookie(s), if any.
    if not cookieProperty and response.cookies:
        setRawWindowProperty(
            PROPERTY_SESSION_COOKIE, '; '.join(pair[0]+'='+pair[1] for pair in response.cookies.get_dict().items())
        )

    elapsed = time() - startTime
    if elapsed < 1.5:
        sleep(1.5 - elapsed)

    return response.text

def construct_request(query):
    return base_url + "?" + urllib_parse.urlencode(query)

xbmc.log(sys.argv[2], xbmc.LOGWARNING)
mode = args.get("mode", None)
if mode is not None:
    mode = mode[0]

if mode is None:

    # Type selection
    for i, variant in enumerate(media_types):
        list_item = xbmcgui.ListItem(media_names[i])
        list_item.setArt({
            "icon":MEDIA_URL + media_names[i] + '.jpg',
            "poster":MEDIA_URL + media_names[i] + '.jpg',
        });
        callback = construct_request({
            "mode": "channels",
            "type": variant,
        })
        xbmcplugin.addDirectoryItem(
            handle = addon_handle,
            url = callback,
            listitem = list_item,
            isFolder = True
        )
    xbmcplugin.endOfDirectory(addon_handle)

elif mode == "channels":

    variant = args.get("type", [""])[0]

    html = fetchURL(WEB_URL + "/" + variant)
    dataStartIndex = html.find(r'class="collections"')

    if dataStartIndex == -1:
        raise Exception(r'list scrape fail: ' + variant)

    result = re.finditer(
        r'''href=\"([^\"]*)\">\s*<div\s*class=\"cover lazy\"\s*style=\"(?:[^\"]+)\"\s*data-lazy=\"([^\"]*)\"''',
        html[dataStartIndex : html.find(r'<footer')]
    )

    for match in result:
        title = match.groups()[0].replace('&amp;','&').replace('/','').replace('-',' ').replace('_',' ').capitalize();
        list_item = xbmcgui.ListItem( title )
        for art_type in ["thumb", "poster", "banner", "fanart","icon"]:
            list_item.setArt({art_type:match.groups()[1]})
        callback = construct_request({
            "url": match.groups()[0],
            "mode": media_mode[ media_types.index(variant) ],
            "title": title,
            "thumb": match.groups()[1],
            "isdirect": False,
        })
        xbmcplugin.addDirectoryItem(
            handle = addon_handle,
            url = callback,
            listitem = list_item,
            isFolder = True
        )
    xbmcplugin.endOfDirectory(addon_handle)

elif mode == "episodes":

    variant = args.get("url", [""])[0]
    title = args.get("title", [""])[0]
    thumb = args.get("thumb", [""])[0]

    html = fetchURL(WEB_URL + variant)
    dataStartIndex = html.find(r'class="dropdowns"')

    if dataStartIndex == -1:
        raise Exception(r'list scrape fail: ' + variant)

    result = re.finditer(
        r'''href=\"([^\"]*)\" name="([^"]+)">\s*<div class="([^"]+)"><img\s*data-lazy=\"([^\"]*)\"''',
        html[dataStartIndex : html.find(r'id="body"')]
    )

    for match in result:

        direct = False
        cclass = match.groups()[2]
        rurl = match.groups()[0]
        title = match.groups()[1].strip().replace('&amp;','&');
        list_item = xbmcgui.ListItem( title )

        for art_type in ["thumb", "poster", "banner", "fanart","icon"]:
            list_item.setArt({art_type:thumb})

        #no point scraping to get the url again since we can already get it
        if r"active" in cclass:
            dataStartIndex = html.find(r'class="logo"')
            #xbmc.log(html, xbmc.LOGWARNING)
            if dataStartIndex == -1:
                raise Exception(r'list scrape fail: ' + variant)
            rurl = re.findall(r'''<source\s*src=\"([^\"]+\.mp4(?:\?[^\"]+)?)\"''', html[dataStartIndex : html.find(r'<footer')])[0]
            direct = True

        if isinstance( rurl, bytes ):
            rurl.decode('utf-8')

        callback = construct_request({
            "url": rurl,
            "mode": "play",
            "title": title,
            "thumb": thumb,
            "isdirect": direct,
        })
        xbmcplugin.addDirectoryItem(
            handle = addon_handle,
            url = callback,
            listitem = list_item,
            isFolder = True
        )
    xbmcplugin.endOfDirectory(addon_handle)

elif mode == "play":

    variant = args.get("url", [""])[0]
    title = args.get("title", [""])[0]
    thumb = args.get("thumb", [""])[0]
    direct = ( args.get("isdirect", [""])[0] == "True" )

    if direct:
        source = variant
    else:
        xbmc.log(WEB_URL + variant, xbmc.LOGWARNING)
        html = fetchURL(WEB_URL + variant)
        dataStartIndex = html.find(r'class="logo"')
        #xbmc.log(html, xbmc.LOGWARNING)
        if dataStartIndex == -1:
            raise Exception(r'list scrape fail: ' + variant)

        source = re.findall(r'''<source\s*src=\"([^\"]+\.mp4(?:\?[^\"]+)?)\"''', html[dataStartIndex : html.find(r'<footer')])[0]

    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    playlist.clear()

    list_item = xbmcgui.ListItem(source)
    list_item.setInfo( type="Video", infoLabels={ "Title": title } )
    list_item.setArt({"thumb":thumb})

    playlist.add( source, list_item )

    xbmcPlayer = xbmc.Player()
    xbmcPlayer.play(playlist)
