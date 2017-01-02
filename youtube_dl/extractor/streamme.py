# coding: utf-8
from __future__ import unicode_literals

from .common import InfoExtractor
from ..utils import (
    int_or_none,
    ExtractorError,
)


class StreamMeIE(InfoExtractor):
    IE_NAME = 'StreamMe:video'
    _API_CHANNEL = 'https://www.stream.me/api-user/v1/%s/channel'
    _API_ARCHIVE = 'https://www.stream.me/api-vod/v1/%s/archives'
    _API_VOD = 'https://www.stream.me/api-vod/v1/vod/%s'
    _VALID_URL_BASE = r'https?://www.stream.me'
    _VALID_URL = r'%s/archive/(?P<channel_id>[^#/]+)/[^/]+/(?P<id>[^/]+)' % _VALID_URL_BASE
    _TEST = {
        'url': 'https://www.stream.me/archive/kombatcup/kombat-cup-week-8-sunday-open/pDlXAj6mYb',
        'md5': 'b32af6fad972d0bcf5854a416b5b3b01',
        'info_dict': {
            'id': 'pDlXAj6mYb',
            'ext': 'mp4',
            'title': 'Kombat Cup Week #8 - Sunday Open',
            'uploader': 'KombatCup',
            'uploader_id': 'kombatcup',
            'timestamp': 1481512102000,
            'thumbnail': 're:https?://.*.jpg$',
            'age_limit': 13,
        }
    }

    def _real_extract(self, url):
        video_id = self._match_id(url)
        data = self._download_json(self._API_VOD % video_id, video_id)

        if len(data['_embedded']['streams']) > 0:
            vod_info = data['_embedded']['streams'][0]
        else:
            raise ExtractorError('Video "%s" not found' % video_id, expected=True)

        manifest_json = self._download_json(vod_info['_links']['manifest']['href'],
                                            video_id, note='Downloading video manifest')

        formats = self._extract_formats(manifest_json['formats'])
        self._sort_formats(formats, 'vbr')
        info = self._extract_info(vod_info)
        info['formats'] = formats
        return info

    def _extract_info(self, info):
        data = {
            'id': info.get('urlId') or info['publicId'],
            # 'formats': self.formats,
            'title': info.get('title') or 'Untitled Broadcast',
            'age_limit': int_or_none(info.get('ageRating')),
            'description': info.get('description'),
            'display_id': info.get('titleSlug'),
            'duration': int_or_none(info.get('duration')),
            'timestamp': int_or_none(info.get('whenCreated')),
            'uploader': info.get('username'),
            'uploader_id': info.get('userSlug'),
            'is_live': True if info.get('active') else False,
        }
        if info.get('stats') and info['stats'].get('raw'):
            stats = info['stats']['raw']
            data.update({
                'like_count': int_or_none(stats.get('likes')),
                'dislike_count': int_or_none(stats.get('dislikes')),
                'view_count': int_or_none(stats.get('views')),
            })
        if info.get('_links') and info['_links'].get('thumbnail'):
            if info['_links']['thumbnail'].get('href'):
                data['thumbnail'] = info['_links']['thumbnail']['href']
        return data

    def _extract_formats(self, fmts):
        formats = []
        for fmt_tag, d in fmts.items():
            # skip websocket and mjpeg we can't handle them anyway
            if fmt_tag in ('mjpeg-lodef', 'mp4-ws',):
                continue
            for fmt_info in d['encodings']:
                formats.append({
                    'url': fmt_info.get('location'),
                    'width': int_or_none(fmt_info.get('videoWidth')),
                    'height': int_or_none(fmt_info.get('videoHeight')),
                    'vbr': int_or_none(fmt_info.get('videoKbps')),
                    'abr': int_or_none(fmt_info.get('audioKbps')),
                    'acodec': d.get('audioCodec'),
                    'vcodec': d.get('videoCodec'),
                    'format_id': "%s%sp" % (fmt_tag, fmt_info.get('videoHeight')),
                    'ext': 'flv' if fmt_tag.split('-')[1] == 'rtmp' else 'mp4',
                    # I don't know all the possible protocols yet.
                    # 'protocol': 'm3u8_native' if fmt_tag == 'mp4-hls' else 'http'
                })
            if d.get('origin') and d['origin'].get('location'):
                fmt_tag = d['origin']['location'].split(':')[0]
                formats.append({
                    'url': d['origin']['location'],
                    'acodec': d['origin'].get('audioCodec'),
                    'vcodec': d['origin'].get('videoCodec'),
                    'format_id': 'Source-' + fmt_tag,
                    'ext': 'flv' if fmt_tag == 'rtmp' else 'mp4',
                    'source_preference': 1,
                })
        return formats


class StreamMeLiveIE(StreamMeIE):
    IE_NAME = 'StreamIE:live'
    _VALID_URL = r'%s/(?P<id>[^#/]+$)' % StreamMeIE._VALID_URL_BASE
    _TEST = {
        'url': 'https://www.stream.me/kombatcup',
        'info_dict': {
            'id': '1246a915-eebe-4ffe-b12e-e4f5332abc4d',
            'ext': 'mp4',
            'title': 'KombatCup\'s Live Stream',
            'age_limit': 13,
            'uploader_id': 'kombatcup',
            'uploader': 'KombatCup',
            'like_count': int,
            'dislike_count': int,
            'thumbnail': 're:https?://.*.jpg$',
            'is_live': True,
        },
        'skip': 'kombatcup is offline',
        'params': {
            # m3u8 download
            'skip_download': True,
        },
    }

    def _real_extract(self, url):
        channel_id = self._match_id(url)
        apiurl = StreamMeIE._API_CHANNEL % channel_id

        data = self._download_json(apiurl, channel_id)
        stream_info = []
        # search for a live stream...
        for stream in data['_embedded']['streams']:
            stream_info = stream
            break   # TODO: add to a list (multi-streams?)

        if not stream_info.get('active'):
            raise ExtractorError('%s is offline' % channel_id, expected=True)

        manifest_json = self._download_json(stream_info['_links']['manifest']['href'],
                                            channel_id, 'Downloading video manifest')

        formats = self._extract_formats(manifest_json['formats'])
        self._sort_formats(formats, 'vbr')
        info = self._extract_info(stream_info)
        info['formats'] = formats
        return info


class StreamMeArchiveIE(StreamMeIE):
    IE_NAME = 'StreamMe:archives'
    _VALID_URL = r'%s/(?P<id>[^#]+)#archive$' % StreamMeIE._VALID_URL_BASE
    _PLAYLIST_TYPE = 'past broadcasts'
    _PLAYLIST_LIMIT = 128
    _TEST = {
        'url': 'https://www.stream.me/kombatcup#archive',
        'info_dict': {
            'id': 'kombatcup',
            'title': 'KombatCup',
        },
        'playlist_mincount': 25,
        'params': {
            'skip_download': True,
        }
    }

    def _real_extract(self, url):
        channel_id = self._match_id(url).split('#')[0]
        apiurl = StreamMeIE._API_ARCHIVE % channel_id
        # TODO: implement paginated downloading
        data = self._download_json(apiurl, channel_id, query={'limit': self._PLAYLIST_LIMIT, 'offset': 0})
        playlist = []

        for vod in data['_embedded']['vod']:
            manifest_json = self._download_json(vod['_links']['manifest']['href'],
                                                vod['urlId'], note='Downloading video manifest')
            formats = self._extract_formats(manifest_json['formats'])
            self._sort_formats(formats, 'vbr')
            info = self._extract_info(vod)
            info['formats'] = formats
            playlist.append(info)

        return self.playlist_result(playlist, channel_id, info.get('uploader'))
