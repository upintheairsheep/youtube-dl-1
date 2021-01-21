# coding: utf-8
from __future__ import unicode_literals

import json
import datetime
import re
import subprocess
import asyncio
import websockets
import _thread
import queue
import concurrent.futures


from .common import InfoExtractor, SearchInfoExtractor
from ..compat import (
    compat_parse_qs,
    compat_urlparse,
)
from ..utils import (
    check_executable,
    determine_ext,
    dict_get,
    ExtractorError,
    int_or_none,
    float_or_none,
    parse_duration,
    parse_iso8601,
    remove_start,
    try_get,
    unified_timestamp,
    urlencode_postdata,
    compat_urllib_parse_unquote_plus,
    get_element_by_class,
    replace_extension,
    xpath_text,
    xpath_element,
)

from ..postprocessor.ffmpeg import (
    FFmpegPostProcessor
)


class NiconicoIE(InfoExtractor):
    IE_NAME = 'niconico'
    IE_DESC = 'ニコニコ動画'

    _TESTS = [{
        'url': 'http://www.nicovideo.jp/watch/sm22312215',
        'md5': 'd1a75c0823e2f629128c43e1212760f9',
        'info_dict': {
            'id': 'sm22312215',
            'ext': 'mp4',
            'title': 'Big Buck Bunny',
            'thumbnail': r're:https?://.*',
            'uploader': 'takuya0301',
            'uploader_id': '2698420',
            'upload_date': '20131123',
            'timestamp': int,  # timestamp is unstable
            'description': '(c) copyright 2008, Blender Foundation / www.bigbuckbunny.org',
            'duration': 33,
            'view_count': int,
            'comment_count': int,
        },
        'skip': 'Requires an account',
    }, {
        # File downloaded with and without credentials are different, so omit
        # the md5 field
        'url': 'http://www.nicovideo.jp/watch/nm14296458',
        'info_dict': {
            'id': 'nm14296458',
            'ext': 'swf',
            'title': '【鏡音リン】Dance on media【オリジナル】take2!',
            'description': 'md5:689f066d74610b3b22e0f1739add0f58',
            'thumbnail': r're:https?://.*',
            'uploader': 'りょうた',
            'uploader_id': '18822557',
            'upload_date': '20110429',
            'timestamp': 1304065916,
            'duration': 209,
        },
        'skip': 'Requires an account',
    }, {
        # 'video exists but is marked as "deleted"
        # md5 is unstable
        'url': 'http://www.nicovideo.jp/watch/sm10000',
        'info_dict': {
            'id': 'sm10000',
            'ext': 'unknown_video',
            'description': 'deleted',
            'title': 'ドラえもんエターナル第3話「決戦第3新東京市」＜前編＞',
            'thumbnail': r're:https?://.*',
            'upload_date': '20071224',
            'timestamp': int,  # timestamp field has different value if logged in
            'duration': 304,
            'view_count': int,
        },
        'skip': 'Requires an account',
    }, {
        'url': 'http://www.nicovideo.jp/watch/so22543406',
        'info_dict': {
            'id': '1388129933',
            'ext': 'mp4',
            'title': '【第1回】RADIOアニメロミックス ラブライブ！～のぞえりRadio Garden～',
            'description': 'md5:b27d224bb0ff53d3c8269e9f8b561cf1',
            'thumbnail': r're:https?://.*',
            'timestamp': 1388851200,
            'upload_date': '20140104',
            'uploader': 'アニメロチャンネル',
            'uploader_id': '312',
        },
        'skip': 'The viewing period of the video you were searching for has expired.',
    }, {
        # video not available via `getflv`; "old" HTML5 video
        'url': 'http://www.nicovideo.jp/watch/sm1151009',
        'md5': '8fa81c364eb619d4085354eab075598a',
        'info_dict': {
            'id': 'sm1151009',
            'ext': 'mp4',
            'title': 'マスターシステム本体内蔵のスペハリのメインテーマ（ＰＳＧ版）',
            'description': 'md5:6ee077e0581ff5019773e2e714cdd0b7',
            'thumbnail': r're:https?://.*',
            'duration': 184,
            'timestamp': 1190868283,
            'upload_date': '20070927',
            'uploader': 'denden2',
            'uploader_id': '1392194',
            'view_count': int,
            'comment_count': int,
        },
        'skip': 'Requires an account',
    }, {
        # "New" HTML5 video
        # md5 is unstable
        'url': 'http://www.nicovideo.jp/watch/sm31464864',
        'info_dict': {
            'id': 'sm31464864',
            'ext': 'mp4',
            'title': '新作TVアニメ「戦姫絶唱シンフォギアAXZ」PV 最高画質',
            'description': 'md5:e52974af9a96e739196b2c1ca72b5feb',
            'timestamp': 1498514060,
            'upload_date': '20170626',
            'uploader': 'ゲスト',
            'uploader_id': '40826363',
            'thumbnail': r're:https?://.*',
            'duration': 198,
            'view_count': int,
            'comment_count': int,
        },
        'skip': 'Requires an account',
    }, {
        # Video without owner
        'url': 'http://www.nicovideo.jp/watch/sm18238488',
        'md5': 'd265680a1f92bdcbbd2a507fc9e78a9e',
        'info_dict': {
            'id': 'sm18238488',
            'ext': 'mp4',
            'title': '【実写版】ミュータントタートルズ',
            'description': 'md5:15df8988e47a86f9e978af2064bf6d8e',
            'timestamp': 1341160408,
            'upload_date': '20120701',
            'uploader': None,
            'uploader_id': None,
            'thumbnail': r're:https?://.*',
            'duration': 5271,
            'view_count': int,
            'comment_count': int,
        },
        'skip': 'Requires an account',
    }, {
        'url': 'http://sp.nicovideo.jp/watch/sm28964488?ss_pos=1&cp_in=wt_tg',
        'only_matching': True,
    }]

    _VALID_URL = r'https?://(?:www\.|secure\.|sp\.)?nicovideo\.jp/watch/(?P<id>(?:[a-z]{2})?[0-9]+)'
    _NETRC_MACHINE = 'niconico'

    def _real_initialize(self):
        self._login()

    def _login(self):
        username, password = self._get_login_info()
        # No authentication to be performed
        if not username:
            return True

        # Log in
        login_ok = True
        login_form_strs = {
            'mail_tel': username,
            'password': password,
        }
        urlh = self._request_webpage(
            'https://account.nicovideo.jp/api/v1/login', None,
            note='Logging in', errnote='Unable to log in',
            data=urlencode_postdata(login_form_strs))
        if urlh is False:
            login_ok = False
        else:
            parts = compat_urlparse.urlparse(urlh.geturl())
            if compat_parse_qs(parts.query).get('message', [None])[0] == 'cant_login':
                login_ok = False
        if not login_ok:
            self._downloader.report_warning('unable to log in: bad username or password')
        return login_ok

    def _extract_format_for_quality(self, api_data, video_id, audio_quality, video_quality):
        def yesno(boolean):
            return 'yes' if boolean else 'no'

        def extract_video_quality(video_quality):
            try:
                # Example: 480p | 0.9M
                r = re.match('^.*\| ([0-9]*\.?[0-9]*[MK])', video_quality)
                if r is None:
                    # Maybe conditionally throw depending on the settings?
                    return 0

                vbr_with_unit = r.group(1)
                unit = vbr_with_unit[-1]
                video_bitrate = float(vbr_with_unit[:-1])

                if unit == 'M':
                    video_bitrate *= 1000000
                elif unit == 'K':
                    video_bitrate *= 1000

                return video_bitrate
            except:
                # Should at least log or something here
                return 0

        session_api_data = api_data['video']['dmcInfo']['session_api']
        session_api_endpoint = session_api_data['urls'][0]

        format_id = '-'.join(map(lambda s: remove_start(s['id'], 'archive_'), [video_quality, audio_quality]))

        session_response = self._download_json(
            session_api_endpoint['url'], video_id,
            query={'_format': 'json'},
            headers={'Content-Type': 'application/json'},
            note='Downloading JSON metadata for %s' % format_id,
            data=json.dumps({
                'session': {
                    'client_info': {
                        'player_id': session_api_data['player_id'],
                    },
                    'content_auth': {
                        'auth_type': session_api_data['auth_types'][session_api_data['protocols'][0]],
                        'content_key_timeout': session_api_data['content_key_timeout'],
                        'service_id': 'nicovideo',
                        'service_user_id': session_api_data['service_user_id']
                    },
                    'content_id': session_api_data['content_id'],
                    'content_src_id_sets': [{
                        'content_src_ids': [{
                            'src_id_to_mux': {
                                'audio_src_ids': [audio_quality['id']],
                                'video_src_ids': [video_quality['id']],
                            }
                        }]
                    }],
                    'content_type': 'movie',
                    'content_uri': '',
                    'keep_method': {
                        'heartbeat': {
                            'lifetime': session_api_data['heartbeat_lifetime']
                        }
                    },
                    'priority': session_api_data['priority'],
                    'protocol': {
                        'name': 'http',
                        'parameters': {
                            'http_parameters': {
                                'parameters': {
                                    'http_output_download_parameters': {
                                        'use_ssl': yesno(session_api_endpoint['is_ssl']),
                                        'use_well_known_port': yesno(session_api_endpoint['is_well_known_port']),
                                    }
                                }
                            }
                        }
                    },
                    'recipe_id': session_api_data['recipe_id'],
                    'session_operation_auth': {
                        'session_operation_auth_by_signature': {
                            'signature': session_api_data['signature'],
                            'token': session_api_data['token'],
                        }
                    },
                    'timing_constraint': 'unlimited'
                }
            }).encode())

        # get heartbeat info
        heartbeat_url = session_api_endpoint['url'] + '/' + session_response['data']['session']['id'] + '?_format=json&_method=PUT'
        heartbeat_data = json.dumps(session_response['data']).encode()
        # interval, convert milliseconds to seconds, then halve to make a buffer.
        heartbeat_interval = session_api_data['heartbeat_lifetime'] / 8000

        resolution = video_quality.get('resolution', {})
        vidQuality = video_quality.get('bitrate')
        is_low = 'low' in video_quality['id']

        return {
            'url': session_response['data']['session']['content_uri'],
            'format_id': format_id,
            'format_note': 'DMC ' + video_quality['label'],
            'ext': 'mp4',  # Session API are used in HTML5, which always serves mp4
            'acodec': 'aac',
            'vcodec': 'h264', # As far as I'm aware DMC videos can only serve h264/aac combinations
            'abr': float_or_none(audio_quality.get('bitrate'), 1000),
            # So this is kind of a hack; sometimes, the bitrate is incorrectly reported as 0kbs. If this is the case,
            # extract it from the rest of the metadata we have available
            'vbr': float_or_none(vidQuality if vidQuality > 0 else extract_video_quality(video_quality.get('label')), 1000),
            'height': resolution.get('height'),
            'width': resolution.get('width'),
            'quality': -2 if is_low else None,
            'heartbeat_url': heartbeat_url,
            'heartbeat_data': heartbeat_data,
            'heartbeat_interval': heartbeat_interval,
        }

    def _real_extract(self, url):
        video_id = self._match_id(url)
        
        video_info_xml = self._download_xml(
            'http://ext.nicovideo.jp/api/getthumbinfo/' + video_id,
            video_id, note='Downloading video info page')

        def get_video_info(items):
            if not isinstance(items, list):
                items = [items]
            for item in items:
                ret = xpath_text(video_info_xml, './/' + item)
                if ret:
                    return ret


        extension = get_video_info('movie_type') or 'mp4'

        formats = []

        def getWebpage(video_id, note=False):
            webpage, handle = self._download_webpage_handle(
                'http://www.nicovideo.jp/watch/' + video_id, video_id, note=note)
            if video_id.startswith('so'):
                video_id = self._match_id(handle.geturl())

            return webpage

        if extension in ['swf', 'flv']:
            # Source video is a flash video
            self._set_cookie('nicovideo.jp', 'watch_flash', '1')

            flv_info_api = self._download_webpage(
                'http://flapi.nicovideo.jp/api/getflv/' + video_id + '?as3=1',
                video_id, 'Downloading flv info')

            flv_info = compat_urlparse.parse_qs(flv_info_api)

            webpage = getWebpage(video_id, note='Downloading flash player webpage')

            watch_api_data_string = self._html_search_regex(
                r'<div[^>]+id="watchAPIDataContainer"[^>]+>([^<]+)</div>',
                webpage, 'watch api data', default=None)
            
            if watch_api_data_string == None:

                self._downloader.report_warning('Could not get flv info as it requires logging in, or the endpoint has been decommissioned')

            else:

                watch_api = json.loads(watch_api_data_string)
                player_flv_info = compat_parse_qs(compat_urllib_parse_unquote_plus(compat_urllib_parse_unquote_plus(watch_api['flashvars']['flvInfo'])))

                if 'url' not in player_flv_info:
                    if 'deleted' in flv_info:
                        raise ExtractorError('The video has been deleted.',
                                            expected=True)
                    elif 'closed' in flv_info:
                        self._downloader.report_warning('Could not get flv info as it requires logging in, or the endpoint has been decommissioned')
                    elif 'error' in flv_info:
                        raise ExtractorError('%s reports error: %s' % (
                            self.IE_NAME, flv_info['error'][0]), expected=True)
                    else:
                        raise ExtractorError('Unable to find flv URL')

                else:
                    
                    for video_url in player_flv_info['url']:
                        is_source = not video_url.endswith('low')

                        flash_cookies = self._get_cookies('http://nicovideo.jp')

                        formats.append({
                            'url': video_url,
                            'ext': extension,
                            'format_id': 'source' if is_source else 'flash_low',
                            'format_note': 'Source flash video' if is_source else 'Low quality flash video',
                            'acodec': 'mp3',
                            'container': extension,
                            'http_headers': {'Cookie': flash_cookies.output(header='', sep=';')},
                            'quality': 10 if is_source else -2
                        })
        
        # Either source video is a mp4 (DMC or smile), or we're grabbing other qualities alongside the flash video
        self._set_cookie('nicovideo.jp', 'watch_flash', '0')

        # Get video webpage. We are not actually interested in it for normal
        # cases, but need the cookies in order to be able to download the
        # info webpage
        webpage = getWebpage(video_id, note='Downloading HTML5 player webpage')

        api_data = self._parse_json(self._html_search_regex(
            'data-api-data="([^"]+)"', webpage,
            'API data', default='{}'), video_id)

        dmc_info = api_data['video'].get('dmcInfo')
        if dmc_info:  # "New" HTML5 videos
            quality_info = dmc_info['quality']
            for audio_quality in quality_info['audios']:
                for video_quality in quality_info['videos']:
                    if not audio_quality['available'] or not video_quality['available']:
                        continue
                    formats.append(self._extract_format_for_quality(
                        api_data, video_id, audio_quality, video_quality))

        
        if api_data['video'].get('smileInfo'):  # "Old" HTML5 videos
            video_url = api_data['video']['smileInfo']['url']
            is_quality = not video_url.endswith('low')


            # Invoking ffprobe to determine resolution

            pp = FFmpegPostProcessor(self._downloader)
            cookies = self._get_cookies('https://nicovideo.jp').output(header='', sep='; path=/; domain=nicovideo.jp;\n')
            
            self.to_screen('%s: %s' % (video_id, 'Checking smile format with ffprobe'))
            
            metadata = pp.get_metadata_object(video_url, ['-cookies', cookies])


            v_stream, a_stream = (metadata['streams'][0], metadata['streams'][1]) \
                if metadata['streams'][0]['codec_type'] == 'video' \
                else (metadata['streams'][1], metadata['streams'][0])

            ext = 'mp4' if 'mp4' in metadata['format']['format_name'] \
                else metadata['format']['format_name']

            # Community restricted videos seem to have issues with the thumb API not returning anything at all
            filesize = int(
                (get_video_info('size_high') if is_quality else get_video_info('size_low'))
                or metadata['format']['size']
            )

            

            timestamp = (
                parse_iso8601(get_video_info('first_retrieve'))
                or unified_timestamp(get_video_info('postedDateTime'))
                or unified_timestamp(api_data['video'].get('postedDateTime'))
            )

            smile_threshold_timestamp = unified_timestamp('2016/11/30 00:00:00')

            formats.append({
                'url': video_url,
                'ext': ext,
                'format_id': 'smile_high' if is_quality else 'smile_low',
                'format_note': 'High quality smile video' if is_quality else 'Low quality smile video',
                'container': ext,

                'vcodec': v_stream['codec_name'],
                'acodec': a_stream['codec_name'],
                'width': int(v_stream['width']),
                'height': int(v_stream['height']),
                'tbr': int(metadata['format'].get('bit_rate', None)) / 1000,
                'abr': int_or_none(a_stream.get('bit_rate', None), scale=1000),
                'vbr': int_or_none(v_stream.get('bit_rate', None), scale=1000),

                # According to compconf and my personal research, smile videos from pre-2017 are always better quality than their DMC counterparts
                'source_preference': 5 if is_quality else -2,
                'quality': 5 if timestamp < smile_threshold_timestamp and is_quality else None,

                'filesize': filesize,
            })
            
        self._sort_formats(formats, ['quality', 'height', 'width', 'tbr', 'abr', 'source_preference', 'format_id'])

        # Start extracting information
        title = (
            get_video_info('title')
            or api_data['video'].get('title')
            or self._og_search_title(webpage, default=None)
            or self._html_search_regex(
                r'<span[^>]+class="videoHeaderTitle"[^>]*>([^<]+)</span>',
                webpage, 'video title')
        )

        watch_api_data_string = self._html_search_regex(
            r'<div[^>]+id="watchAPIDataContainer"[^>]+>([^<]+)</div>',
            webpage, 'watch api data', default=None)
        watch_api_data = self._parse_json(watch_api_data_string, video_id) if watch_api_data_string else {}
        video_detail = watch_api_data.get('videoDetail', {})

        thumbnail = (
            self._html_search_regex(r'<meta property="og:image" content="([^"]+)">', webpage, 'thumbnail data', default=None)
            or api_data['video'].get('largeThumbnailURL')
            or api_data['video'].get('thumbnailURL')
            or get_video_info(['largeThumbnailURL', 'thumbnail_url', 'thumbnailURL'])
            or self._html_search_meta('image', webpage, 'thumbnail', default=None)
            or video_detail.get('thumbnail')
        )

        description = (
            api_data['video'].get('description')
            or get_video_info('description') # this cannot go infront of the json API check as on community videos the description is simply "community"
        )

        if not timestamp:
            match = self._html_search_meta('datePublished', webpage, 'date published', default=None)
            if match:
                timestamp = parse_iso8601(match.replace('+', ':00+'))
        if not timestamp and video_detail.get('postedAt'):
            timestamp = parse_iso8601(
                video_detail['postedAt'].replace('/', '-'),
                delimiter=' ', timezone=datetime.timedelta(hours=9))

        view_count = int_or_none(
            get_video_info(['view_counter', 'viewCount'])
            or api_data['video'].get('viewCount')
        )

        if not view_count:
            match = self._html_search_regex(
                r'>Views: <strong[^>]*>([^<]+)</strong>',
                webpage, 'view count', default=None)
            if match:
                view_count = int_or_none(match.replace(',', ''))

        view_count = view_count or video_detail.get('viewCount')

        comment_count = (
            int_or_none(get_video_info('comment_num'))
            or video_detail.get('commentCount')
            or try_get(api_data, lambda x: x['thread']['commentCount'])
        )

        if not comment_count:
            match = self._html_search_regex(
                r'>Comments: <strong[^>]*>([^<]+)</strong>',
                webpage, 'comment count', default=None)
            if match:
                comment_count = int_or_none(match.replace(',', ''))

        duration = (
            parse_duration(
                get_video_info('length')
                or self._html_search_meta('video:duration', webpage, 'video duration', default=None)
            )
            or video_detail.get('length')
            or api_data['video'].get('duration')
            or get_video_info('duration'))

        webpage_url = get_video_info('watch_url') or url

        # Note: cannot use api_data.get('owner', {}) because owner may be set to "null"
        # in the JSON, which will cause None to be returned instead of {}.
        owner = try_get(api_data, lambda x: x.get('owner'), dict) or {}
        uploader_id = get_video_info(['ch_id', 'user_id']) or owner.get('id') or api_data.get('community', {}).get('id')
        uploader = get_video_info(['ch_name', 'user_nickname']) or owner.get('nickname') or api_data.get('community', {}).get('name')

        # Get the comments
        get_comments : bool = self._downloader.params.get('getcomments', False)
        write_subs : bool = self._downloader.params.get('writesubtitles', False)

        raw_comments : dict = None
        comments : dict = None
        subtitles : dict = None


        if get_comments or write_subs:
            # first need to get the thread ID from the html
            thread_ids = list(set(re.findall(r'threadIds&quot;:\[{&quot;id&quot;:([0-9]*)', webpage)))
            root_thread_id = 0 # thread_ids[0]

            # make API calls
            raw_comments = {
                'en': self._extract_all_comments(video_id, thread_ids, 1),
                'jp': self._extract_all_comments(video_id, thread_ids, 0),
                'cn': self._extract_all_comments(video_id, thread_ids, 2),
            }
            
            subtitles = {
                'eng': [{
                    'ext': 'ass',
                    'data': NiconicoIE.CreateDanmaku(json.dumps(raw_comments['en']))
                }],
                'jpn': [{
                    'ext': 'ass',
                    'data': NiconicoIE.CreateDanmaku(json.dumps(raw_comments['jp']))
                }],
                'zh': [{
                    'ext': 'ass',
                    'data': NiconicoIE.CreateDanmaku(json.dumps(raw_comments['cn']))
                }]
            }

            comments = self._process_raw_comments(raw_comments['en'], root_thread_id, 'en') \
                    + self._process_raw_comments(raw_comments['jp'], root_thread_id, 'jp') \
                    + self._process_raw_comments(raw_comments['cn'], root_thread_id, 'cn')


        tags_nodes = video_info_xml.findall('.//tags/tag')
        tags = list(map(lambda x: x.text, tags_nodes))

        if len(tags) == 0:
            tags = api_data['video'].get('tags') or []
        
        genre = get_video_info('genre')

        return {
            'id': video_id,
            'title': title,
            'original_title': api_data['video'].get('originalTitle'),
            'formats': formats,
            'thumbnails': [
                {
                    'url': thumbnail,
                    'ext': 'jpg'
                }
            ],
            'description': description,
            'original_description': api_data['video'].get('originalDescription'),
            'uploader': uploader,
            'timestamp': timestamp,
            'uploader_id': uploader_id,
            'view_count': view_count,
            'tags': tags,
            'genre': genre,
            'comment_count': comment_count,
            'raw_comments': raw_comments,
            'comments': comments,
            'subtitles': subtitles,
            'duration': duration,
            'webpage_url': webpage_url,
        }

    @staticmethod
    def CreateDanmaku(raw_comments_list, commentType='NiconicoJson', x=640, y=360):
        temp_io = io.StringIO()
        comment_io = io.StringIO(raw_comments_list)
        Danmaku2ASS([comment_io], commentType, temp_io, x, y)
        danmaku_content = temp_io.getvalue()

        temp_io.close()
        comment_io.close()

        return danmaku_content


    def _process_raw_comments(self, raw_comments_list, root_thread_id, language):
        comments = []

        for raw_comment in raw_comments_list:
            if 'chat' not in raw_comment:
                continue

            raw_comment = raw_comment['chat']

            comments.append({
                'parent': 'root' if raw_comment.get('parent') == root_thread_id else raw_comment.get('parent'),
                'id': raw_comment.get('no'),
                'author_id': raw_comment.get('user_id'),
                'text': raw_comment.get('content'),
                'timestamp': raw_comment.get('date'),
                'language' : language
            })
        
        return comments

    def _extract_all_comments(self, video_id, thread_ids, language_id):

        i = 0
        raw_json = []

        for thread_id in thread_ids:

            i += 1
            raw_json += self._download_json(
                'https://nmsg.nicovideo.jp/api.json/',
                video_id,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; rv:68.0) Gecko/20100101 Firefox/68.0',
                    'Accept': '*/*',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Referer': 'https://www.nicovideo.jp/watch/sm%s' % video_id,
                    'Content-Type': 'text/plain;charset=UTF-8',
                    'Origin': 'https://www.nicovideo.jp',
                    'Connection': 'keep-alive'
                },
                data=json.dumps([
                        { "ping": {"content": "rs:0" } },
                        { "ping": {"content": "ps:0" } },
                        { "thread": {
                            "thread": thread_id,
                            "version": "20090904",
                            "fork": 0,
                            "language": 0,
                            "user_id": "",
                            "with_global": 0,
                            "scores": 1,
                            "nicoru": 3
                        }},
                        { "ping": {"content": "pf:0" } },
                        { "ping": {"content": "ps:1" } },
                        { "thread_leaves": {
                            "thread": thread_id,
                            "language": language_id,
                            "user_id": "",
                            "content": "0-999999:999999,999999", # format is "<bottom of minute range>-<top of minute range>:<comments per minute>,<total last comments"
                                                                 # unfortunately NND limits (deletes?) comment returns this way, so you're only able to grab the last 1000 per language
                            "scores": 1,
                            "nicoru": 3
                        }},
                        { "ping": {"content": "pf:1" } },
                        { "ping": {"content": "rf:0" } }
                    ]).encode(),
                note='Downloading comments from thread %s/%s (%s)' % (i, len(thread_ids), 'en' if language_id == 1 else
                                                                                          'jp' if language_id == 0 else
                                                                                          'cn' if language_id == 2 else 
                                                                                          'unknown')
            )

        return raw_json


class NiconicoPlaylistIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?nicovideo\.jp/mylist/(?P<id>\d+)'

    _TEST = {
        'url': 'http://www.nicovideo.jp/mylist/27411728',
        'info_dict': {
            'id': '27411728',
            'title': 'AKB48のオールナイトニッポン',
        },
        'playlist_mincount': 225,
    }

    def _real_extract(self, url):
        list_id = self._match_id(url)
        webpage = self._download_webpage(url, list_id)

        entries_json = self._search_regex(r'Mylist\.preload\(\d+, (\[.*\])\);',
                                          webpage, 'entries')
        entries_raw = json.loads(entries_json)
        entries = [{
            '_type': 'url',
            'ie_key': NiconicoIE.ie_key(),
            'url': ('http://www.nicovideo.jp/watch/%s' %
                    entry['item_data']['video_id']),
        } for entry in entries_raw]

        return {
            '_type': 'playlist',
            'title': self._search_regex(r'\s+name: "(.*?)"', webpage, 'title'),
            'description': self._search_regex(r'\s+description: "(.*?)"', webpage, 'description'),
            'user_id': self._search_regex(r'\s+user_id: (\d*?)', webpage, 'user_id'),
            'create_time': self._search_regex(r'\s+create_time: (\d*?)', webpage, 'create_time'),
            'update_time': self._search_regex(r'\s+update_time: (\d*?)', webpage, 'update_time'),
            'id': list_id,
            'entries_metadata': entries_raw,
            'entries': entries,
        }

# USAGE: youtube-dl "nicosearch<NUMBER OF ENTRIES>:<SEARCH STRING>"
class NicovideoIE(SearchInfoExtractor):
    IE_DESC = 'Nico video search'
    _MAX_RESULTS = 1000000
    _SEARCH_KEY = 'nicosearch'
    _START_DATE = datetime.date(2007, 1, 1)
    _MAX_NUMBER_OF_PAGES = 50
    _RESULTS_PER_PAGE = 32

    def _get_n_results(self, query, n):
        """Get a specified number of results for a query"""
        entries = []
        currDate = datetime.datetime.now().date()

        search_url = "http://www.nicovideo.jp/search/%s" % query
        r = self._get_entries_for_span(search_url, query, self._START_DATE, currDate)

        # did we gather more entries than were asked for? If so, only add as many as are needed to reach the desired number.
        m = n - len(entries)
        entries += r[0:min(m, len(r))]

        return {
            '_type': 'playlist',
            'id': query,
            'entries': entries
        }

    def _get_results_until(self, query, last_video):
        entries = []
        currDate = datetime.datetime.now().date()

        search_url = "http://www.nicovideo.jp/search/%s" % query
        r = self._get_entries_for_date(search_url, query, self._START_DATE, currDate)

        final_index = self._MAX_RESULTS

        for i in range(len(r)):
            try:
                if(r[i]['url'].split("/")[-1] == last_video):
                    final_index = i
                    break
            except ValueError:
                continue

        # if we marked the final index, only add videos until we hit it
        entries += r[0:min(final_index, len(r))]

        return {
            '_type': 'playlist',
            'id': query,
            'entries': entries
        }

    def _get_entries_for_span(self, url, query, startDate, endDate):
        # This page 50 request will be duplicated in the else case; not ideal
        page_50_results = self._get_entries_for_date(url, query, startDate, endDate=endDate, pageNumber=50)
        entries = []
        # If the page 50 results return 32 videos, we need to break down the query interval to ensure we've captured all videos
        if (len(page_50_results) == self._RESULTS_PER_PAGE and startDate != endDate):
            midpoint = startDate + (endDate - startDate)/2
            right = self._get_entries_for_span(url, query, startDate, midpoint)
            left = self._get_entries_for_span(url, query, midpoint, endDate)
            entries = left + right
        else:
            entries = self._get_entries_for_date(url, query, startDate, endDate=endDate)

        return entries


    def _get_entries_for_date(self, url, query, startDate, endDate=None, pageNumber=1):
        if endDate is None:
            endDate = startDate

        entries = []
        while True:
            link = url + "?page=" + str(pageNumber) + "&start=" + str(startDate) + "&end=" + str(endDate) + "&sort=f&order=d"
            results = self._download_webpage(link, "None", query={"Search_key": query}, note='Extracting results from page %s for date %s to %s' % (pageNumber, startDate, endDate))
            r = re.findall(r'(?<=data-video-id=)["\']?(?P<videoid>.*?)(?=["\'])', results)

            for item in r:
                e = self.url_result("http://www.nicovideo.jp/watch/" + item, 'Niconico', item)
                entries.append(e)

            # each page holds a maximum of 32 entries. If we've seen 32 entries on the current page,
            # it's possible there may be another, so we can check. It's a little awkward, but it works.
            if(len(r) < self._RESULTS_PER_PAGE or pageNumber == self._MAX_NUMBER_OF_PAGES):
                break

            pageNumber += 1

        return entries


class NiconicoLiveIE(InfoExtractor):
    _VALID_URL = r'https?://live2?.nicovideo\.jp/watch/(?P<id>lv\d+)'
    
    _NETRC_MACHINE = 'niconico'

    _TEST = {} # fuck tests

    def _real_initialize(self):
        self._login()

    def _login(self):
        username, password = self._get_login_info()
        # No authentication to be performed
        if not username:
            return True

        # Log in
        login_ok = True
        login_form_strs = {
            'mail_tel': username,
            'password': password,
        }
        urlh = self._request_webpage(
            'https://account.nicovideo.jp/api/v1/login', None,
            note='Logging in', errnote='Unable to log in',
            data=urlencode_postdata(login_form_strs))
        if urlh is False:
            login_ok = False
        else:
            parts = compat_urlparse.urlparse(urlh.geturl())
            if compat_parse_qs(parts.query).get('message', [None])[0] == 'cant_login':
                login_ok = False
        if not login_ok:
            self._downloader.report_warning('unable to log in: bad username or password')
        return login_ok

    async def handle_comment_websocket(self, uri, thread_id, stream_start_timestamp, stream_end_timestamp):
        cookies_header = {'Cookie': self._get_cookies(uri).output(header='', sep=';')}

        comments = []

        async with websockets.connect(uri, extra_headers=cookies_header) as websocket:

            try:
                current_timestamp = stream_start_timestamp
                current_res = -200 # unknown
                current_rs = 1 # unknown
                current_ps = 5 # unknown

                while current_timestamp < stream_end_timestamp:

                    initial_frame = [
                        { "ping": { "content": "rs:%s" % (current_rs) } },
                        { "ping": { "content": "ps:%s" % (current_ps) } },
                        { "thread": {
                            "thread": thread_id,
                            "version": "20061206",
                            "when": current_timestamp,
                            "user_id": "guest",
                            "res_from": current_res,
                            "with_global": 1,
                            "scores": 1,
                            "nicoru": 0,
                            "waybackkey": ""
                        }},
                        { "ping": { "content":"pf:%s" % (current_rs) } },
                        { "ping": { "content":"rf:%s" % (current_ps) } }
                    ]
                    
                    await websocket.send(json.dumps(initial_frame))

                    while True:
                        frame = json.loads(await websocket.recv())
                        frame_type = list(frame.keys())[0]

                        if frame_type == "ping":
                            if 'rf' in frame['ping']['content']:
                                # end of results

                                if self._downloader.params.get('verbose', False):
                                    self.to_screen('Downloaded %s comments (%s seconds to go)' % (len(comments), stream_end_timestamp - current_timestamp))

                                # these are numbers that i've determined from analyzing the websocket in firefox
                                # i have no clue why they're the numbers they are
                                current_rs += 1
                                current_ps += 5
                                current_timestamp += 15

                                break

                        if frame_type == "chat":
                            chat_obj = frame['chat']
                            chat_obj.pop('thread', None)
                            chat_obj['date'] -= stream_start_timestamp

                            comments.append(chat_obj)

                        elif frame_type == "thread":
                            if 'last_res' not in frame['thread']:
                                continue

                            current_res = int(frame['thread']['last_res']) + 1

            except websockets.exceptions.ConnectionClosed:
                self.to_screen("Connection was closed. Exiting...")

        return comments

    async def stream_heartbeat(self, websocket, heartbeat_interval):
        heartbeat_frame = json.dumps({'type': 'keepSeat'})
        while True:
            await websocket.send(heartbeat_frame)
            await asyncio.sleep(heartbeat_interval)

    async def open_stream_websocket(self, uri, best_quality, loop, queue):
        cookies_header = {'Cookie': self._get_cookies(uri).output(header='', sep=';')}

        async with websockets.connect(uri, extra_headers=cookies_header) as websocket:
            initial_frame = {
                "type": "startWatching",
                "data": {
                    "stream": {
                        "quality": best_quality,
                        "protocol": "hls",
                        "latency": "high",
                        "chasePlay": False,
                    },
                    "room": {
                        "protocol": "webSocket",
                        "commentable": True,
                    },
                },
            }
            
            await websocket.send(json.dumps(initial_frame))

            heartbeat = None
            try:
                while True:
                    frame = json.loads(await websocket.recv())
                    frame_type = frame["type"]

                    if frame_type == "stream":
                        stream_url = frame["data"]["uri"]
                        queue.put(stream_url)

                    if frame_type == "room":
                        chat_websocket_url = frame["data"]["messageServer"]["uri"]
                        chat_thread_id = frame["data"]["threadId"]
                        queue.put((chat_websocket_url, chat_thread_id))

                    elif frame_type == "seat":
                        if heartbeat:
                            heartbeat.cancel()
                        heartbeat = loop.create_task(self.stream_heartbeat(websocket, frame["data"]["keepIntervalSec"]))

                    elif frame_type == "ping":
                        await websocket.send("""{"type":"pong","body":{}}""")

            except websockets.exceptions.ConnectionClosed:
                self.to_screen("Connection was closed. Exiting...")
                if heartbeat:
                    heartbeat.cancel()
                return

    def start_heartbeat(self, websocket_url, best_quality, queue):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.open_stream_websocket(websocket_url, best_quality, loop, queue))

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)

        embedded_data_raw = self._html_search_regex(r'id\s*=\s*"embedded-data"[^>]*data-props\s*=\s*"([^"]+)"',
            webpage, 'embedded-data', default=None, fatal=False)

        if embedded_data_raw is not None:
            # After March 2019
            # HLS based stream

            self.to_screen('Detected post-March 2019 HLS-based stream')

            embedded_data = json.loads(embedded_data_raw)

            websocket_url = embedded_data['site']['relive']['webSocketUrl']
            best_quality = embedded_data['program']['stream']['maxQuality']

            if websocket_url is None or websocket_url == '':
                raise ExtractorError('Unable to find stream media URL. Is the stream private or unavailable?', expected=True)

            q = queue.Queue(maxsize=0)

            _thread.start_new_thread(self.start_heartbeat, (websocket_url, best_quality, q))

            playlistUrl = q.get()
            commentData = q.get()

            comments = None
            subtitles = None

            if self._downloader.params.get('getcomments', False) or self._downloader.params.get('writesubtitles', False):

                self.to_screen("Downloading comments")

                pool = concurrent.futures.ThreadPoolExecutor()

                comments = pool.submit(asyncio.run, 
                    self.handle_comment_websocket(commentData[0], commentData[1], int(embedded_data['program']['openTime']), int(embedded_data['program']['endTime']))
                ).result()

                if self._downloader.params.get('writesubtitles', False):
                    self.to_screen("Converting comments to .ass format")

                    subtitles = {
                        'jpn': [{
                            'ext': 'ass',
                            'data': NiconicoIE.CreateDanmaku(json.dumps(comments))
                        }]
                    }

            
            thumbnails = []

            if 'small' in embedded_data['program']['thumbnail']:
                thumbnails.append({
                    'id': 'small',
                    'width': 80,
                    'height': 80,
                    'url': embedded_data['program']['thumbnail']['small']
                })

            if 'large' in embedded_data['program']['thumbnail']:
                thumbnails.append({
                    'id': 'large',
                    'width': 192,
                    'height': 144,
                    'url': embedded_data['program']['thumbnail']['large']
                })

            if 'huge' in embedded_data['program']['thumbnail']:
                for k, huge_url in embedded_data['program']['thumbnail']['huge'].items():
                    width, height = k.lstrip('s').split('x')

                    thumbnails.append({
                        'id': 'huge_%sx%s' % (width, height),
                        'width': int(width),
                        'height': int(height),
                        'url': huge_url
                    })

            
            nicoApi = dict(
                (k, v) for k, v in embedded_data.items()
                    if k in ['program', 'socialGroup', 'channel'])
                

            formats = self._extract_m3u8_formats(playlistUrl, video_id, ext='mp4')

            return {
                'id': video_id,
                'formats': formats,
                'title': embedded_data['program']['title'],
                'view_count': embedded_data['program']['statistics']['watchCount'],
                'comment_count': embedded_data['program']['statistics']['commentCount'],
                'description': embedded_data['program']['description'],
                'uploader': embedded_data['program']['supplier']['name'],
                'channel': embedded_data['socialGroup']['name'],
                'channel_id': embedded_data['socialGroup']['id'],
                'channel_url': embedded_data['socialGroup']['socialGroupPageUrl'],
                'timestamp': int(embedded_data['program']['openTime']),
                'begin_time': int(embedded_data['program']['beginTime']),
                'end_time': int(embedded_data['program']['endTime']),
                'comments': comments,
                'subtitles': subtitles,
                'thumbnails': thumbnails,
                'nicoApi': nicoApi
            }

        else:
            # Before March 2019
            # RTMP based stream

            self.to_screen('Detected pre-March 2019 RTMP-based timeshift stream')

            playerstatus_raw = self._html_search_regex(r'"value_by_gps"\s*:\s*"([^"]+)"',
                                            webpage, 'entries')

            playerstatus_xml = self._parse_xml(compat_urlparse.unquote(playerstatus_raw), video_id)

            rtmp_url = xpath_text(playerstatus_xml, './rtmp/url')
            rtmp_ticket = xpath_text(playerstatus_xml, './rtmp/ticket')

            if rtmp_url is None or rtmp_url == '':
                raise ExtractorError('Unable to find stream media URL. Is the stream private or unavailable?', expected=True)

            que_sheet_nodes = playerstatus_xml.findall('./stream/quesheet/que')
            que_sheet = list(map(lambda x: x.text, que_sheet_nodes))

            published_urls = {}
            raw_formats = {}

            for que in que_sheet:
                if que.startswith("/publish"):
                    split_publish = que.split(' ')
                    published_urls[split_publish[1]] = split_publish[2]
                
                elif que.startswith("/play"):
                    split_play = que.split(' ')[1].split(',')

                    for raw_format in split_play:
                        split_format = raw_format.split(':')
                        
                        raw_formats[split_format[0]] = split_format[-1]


            title = xpath_text(playerstatus_xml, './stream/title')
            description = xpath_text(playerstatus_xml, './stream/description')
            view_count = int(xpath_text(playerstatus_xml, './stream/watch_count'))
            comment_count = int(xpath_text(playerstatus_xml, './stream/comment_count'))
            uploader_id = int(xpath_text(playerstatus_xml, './stream/owner_id'))

            timestamp = int(xpath_text(playerstatus_xml, './stream/open_time'))
            end_time = int(xpath_text(playerstatus_xml, './stream/end_time'))
            duration = end_time - timestamp

            provider_type = xpath_text(playerstatus_xml, './stream/provider_type')

            formats = []

            for raw_format in raw_formats:
                if raw_format not in ['default', 'premium']:
                    continue

                if provider_type in ['channel', 'official']:
                    url = rtmp_url + '/mp4:' + published_urls[raw_formats[raw_format]]
                elif provider_type == "community":
                    raise ExtractorError('Unable to download old timeshift community streams as they require an unfinalized custom build of rtmpdump. (https://github.com/ydixon/rtmpdump-ksv-nicolive/tree/nicolive)', expected=True)
                else:
                    raise ExtractorError('Unknown provider type: "%s"' % provider_type, expected=True)


                formats.append({
                    'url': url,
                    'format_id': raw_format,
                    'protocol': 'rtmp',
                    'quality': 10 if raw_format == 'premium' else -1,
                    'ext': 'flv',
                    'rtmp_conn': 'S:' + rtmp_ticket
                })

            self._sort_formats(formats)

            return {
                'id': video_id,
                'title': title,
                'formats': formats,
                'description': description,
                'timestamp': timestamp,
                'uploader_id': uploader_id,
                'view_count': view_count,
                'comment_count': comment_count,
                'duration': duration,
                'webpage_url': url,
            }



# The original author of this program, Danmaku2ASS, is StarBrilliant.
# This file is released under General Public License version 3.
# You should have received a copy of General Public License text alongside with
# this program. If not, you can obtain it at http://gnu.org/copyleft/gpl.html .
# This program comes with no warranty, the author will not be resopnsible for
# any damage or problems caused by this program.

# You can obtain a latest copy of Danmaku2ASS at:
#   https://github.com/m13253/danmaku2ass
# Please update to the latest version before complaining.

import argparse
import calendar
import gettext
import io
import json
import logging
import math
import os
import random
import re
import sys
import time
import xml.dom.minidom

#gettext.install('danmaku2ass', os.path.join(os.path.dirname(os.path.abspath(os.path.realpath(sys.argv[0] or 'locale'))), 'locale'))

def _(s):
    #util.to_screen(s)
    return s


def SeekZero(function):
    def decorated_function(file_):
        file_.seek(0)
        try:
            return function(file_)
        finally:
            file_.seek(0)
    return decorated_function


def EOFAsNone(function):
    def decorated_function(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except EOFError:
            return None
    return decorated_function

#
# ReadComments**** protocol
#
# Input:
#     f:         Input file
#     fontsize:  Default font size
#
# Output:
#     yield a tuple:
#         (timeline, timestamp, no, comment, pos, color, size, height, width)
#     timeline:  The position when the comment is replayed
#     timestamp: The UNIX timestamp when the comment is submitted
#     no:        A sequence of 1, 2, 3, ..., used for sorting
#     comment:   The content of the comment
#     pos:       0 for regular moving comment,
#                1 for bottom centered comment,
#                2 for top centered comment,
#                3 for reversed moving comment
#     color:     Font color represented in 0xRRGGBB,
#                e.g. 0xffffff for white
#     size:      Font size
#     height:    The estimated height in pixels
#                i.e. (comment.count('\n')+1)*size
#     width:     The estimated width in pixels
#                i.e. CalculateLength(comment)*size
#
# After implementing ReadComments****, make sure to update ProbeCommentFormat
# and CommentFormatMap.
#


def ReadCommentsNiconico(f, fontsize):
    NiconicoColorMap = {'red': 0xff0000, 'pink': 0xff8080, 'orange': 0xffcc00, 'yellow': 0xffff00, 'green': 0x00ff00, 'cyan': 0x00ffff, 'blue': 0x0000ff, 'purple': 0xc000ff, 'black': 0x000000, 'niconicowhite': 0xcccc99, 'white2': 0xcccc99, 'truered': 0xcc0033, 'red2': 0xcc0033, 'passionorange': 0xff6600, 'orange2': 0xff6600, 'madyellow': 0x999900, 'yellow2': 0x999900, 'elementalgreen': 0x00cc66, 'green2': 0x00cc66, 'marineblue': 0x33ffcc, 'blue2': 0x33ffcc, 'nobleviolet': 0x6633cc, 'purple2': 0x6633cc}
    dom = xml.dom.minidom.parse(f)
    comment_element = dom.getElementsByTagName('chat')
    for comment in comment_element:
        try:
            c = str(comment.childNodes[0].wholeText)
            if c.startswith('/'):
                continue  # ignore advanced comments
            pos = 0
            color = 0xffffff
            size = fontsize
            for mailstyle in str(comment.getAttribute('mail')).split():
                if mailstyle == 'ue':
                    pos = 1
                elif mailstyle == 'shita':
                    pos = 2
                elif mailstyle == 'big':
                    size = fontsize * 1.44
                elif mailstyle == 'small':
                    size = fontsize * 0.64
                elif mailstyle in NiconicoColorMap:
                    color = NiconicoColorMap[mailstyle]
            yield (max(int(comment.getAttribute('vpos')), 0) * 0.01, int(comment.getAttribute('date')), int(comment.getAttribute('no')), c, pos, color, size, (c.count('\n') + 1) * size, CalculateLength(c) * size)
        except (AssertionError, AttributeError, IndexError, TypeError, ValueError):
            # logging.warning(_('Invalid comment: %s') % comment.toxml())
            continue


def ReadCommentsNiconicoJson(f, fontsize):
    NiconicoColorMap = {'red': 0xff0000, 'pink': 0xff8080, 'orange': 0xffcc00, 'yellow': 0xffff00, 'green': 0x00ff00, 'cyan': 0x00ffff, 'blue': 0x0000ff, 'purple': 0xc000ff, 'black': 0x000000, 'niconicowhite': 0xcccc99, 'white2': 0xcccc99, 'truered': 0xcc0033, 'red2': 0xcc0033, 'passionorange': 0xff6600, 'orange2': 0xff6600, 'madyellow': 0x999900, 'yellow2': 0x999900, 'elementalgreen': 0x00cc66, 'green2': 0x00cc66, 'marineblue': 0x33ffcc, 'blue2': 0x33ffcc, 'nobleviolet': 0x6633cc, 'purple2': 0x6633cc}
    dom = json.load(f)

    for comment_dom in dom:
        comment = None

        if ('chat' in comment_dom):
            comment = comment_dom['chat']
        elif ('mail' in comment_dom):
            comment = comment_dom
        else:
            continue

        try:
            c = comment['content']

            pos = 0
            color = 0xffffff
            size = fontsize
            for mailstyle in comment['mail'].split():
                if mailstyle == 'ue':
                    pos = 1
                elif mailstyle == 'shita':
                    pos = 2
                elif mailstyle == 'big':
                    size = fontsize * 1.44
                elif mailstyle == 'small':
                    size = fontsize * 0.64
                elif mailstyle in NiconicoColorMap:
                    color = NiconicoColorMap[mailstyle]
            
            yield (max(comment['vpos'], 0) * 0.01, comment['date'], comment.get('no', 0), c, pos, color, size, (c.count('\n') + 1) * size, CalculateLength(c) * size)
        except (AssertionError, AttributeError, IndexError, TypeError, ValueError, KeyError):
            # logging.warning(_('Invalid comment: %s') % json.dumps(comment))
            continue


def ReadCommentsBilibili(f, fontsize):
    dom = xml.dom.minidom.parse(f)
    comment_element = dom.getElementsByTagName('d')
    for i, comment in enumerate(comment_element):
        try:
            p = str(comment.getAttribute('p')).split(',')
            assert len(p) >= 5
            assert p[1] in ('1', '4', '5', '6', '7', '8')
            if comment.childNodes.length > 0:
                if p[1] in ('1', '4', '5', '6'):
                    c = str(comment.childNodes[0].wholeText).replace('/n', '\n')
                    size = int(p[2]) * fontsize / 25.0
                    yield (float(p[0]), int(p[4]), i, c, {'1': 0, '4': 2, '5': 1, '6': 3}[p[1]], int(p[3]), size, (c.count('\n') + 1) * size, CalculateLength(c) * size)
                elif p[1] == '7':  # positioned comment
                    c = str(comment.childNodes[0].wholeText)
                    yield (float(p[0]), int(p[4]), i, c, 'bilipos', int(p[3]), int(p[2]), 0, 0)
                elif p[1] == '8':
                    pass  # ignore scripted comment
        except (AssertionError, AttributeError, IndexError, TypeError, ValueError):
            # logging.warning(_('Invalid comment: %s') % comment.toxml())
            continue

CommentFormatMap = {'Niconico': ReadCommentsNiconico, 'NiconicoJson': ReadCommentsNiconicoJson, 'Bilibili': ReadCommentsBilibili}

def WriteCommentBilibiliPositioned(f, c, width, height, styleid):
    # BiliPlayerSize = (512, 384)  # Bilibili player version 2010
    # BiliPlayerSize = (540, 384)  # Bilibili player version 2012
    BiliPlayerSize = (672, 438)  # Bilibili player version 2014
    ZoomFactor = GetZoomFactor(BiliPlayerSize, (width, height))

    def GetPosition(InputPos, isHeight):
        isHeight = int(isHeight)  # True -> 1
        if isinstance(InputPos, int):
            return ZoomFactor[0] * InputPos + ZoomFactor[isHeight + 1]
        elif isinstance(InputPos, float):
            if InputPos > 1:
                return ZoomFactor[0] * InputPos + ZoomFactor[isHeight + 1]
            else:
                return BiliPlayerSize[isHeight] * ZoomFactor[0] * InputPos + ZoomFactor[isHeight + 1]
        else:
            try:
                InputPos = int(InputPos)
            except ValueError:
                InputPos = float(InputPos)
            return GetPosition(InputPos, isHeight)

    try:
        comment_args = safe_list(json.loads(c[3]))
        text = ASSEscape(str(comment_args[4]).replace('/n', '\n'))
        from_x = comment_args.get(0, 0)
        from_y = comment_args.get(1, 0)
        to_x = comment_args.get(7, from_x)
        to_y = comment_args.get(8, from_y)
        from_x = GetPosition(from_x, False)
        from_y = GetPosition(from_y, True)
        to_x = GetPosition(to_x, False)
        to_y = GetPosition(to_y, True)
        alpha = safe_list(str(comment_args.get(2, '1')).split('-'))
        from_alpha = float(alpha.get(0, 1))
        to_alpha = float(alpha.get(1, from_alpha))
        from_alpha = 255 - round(from_alpha * 255)
        to_alpha = 255 - round(to_alpha * 255)
        rotate_z = int(comment_args.get(5, 0))
        rotate_y = int(comment_args.get(6, 0))
        lifetime = float(comment_args.get(3, 4500))
        duration = int(comment_args.get(9, lifetime * 1000))
        delay = int(comment_args.get(10, 0))
        fontface = comment_args.get(12)
        isborder = comment_args.get(11, 'true')
        from_rotarg = ConvertFlashRotation(rotate_y, rotate_z, from_x, from_y, width, height)
        to_rotarg = ConvertFlashRotation(rotate_y, rotate_z, to_x, to_y, width, height)
        styles = ['\\org(%d, %d)' % (width / 2, height / 2)]
        if from_rotarg[0:2] == to_rotarg[0:2]:
            styles.append('\\pos(%.0f, %.0f)' % (from_rotarg[0:2]))
        else:
            styles.append('\\move(%.0f, %.0f, %.0f, %.0f, %.0f, %.0f)' % (from_rotarg[0:2] + to_rotarg[0:2] + (delay, delay + duration)))
        styles.append('\\frx%.0f\\fry%.0f\\frz%.0f\\fscx%.0f\\fscy%.0f' % (from_rotarg[2:7]))
        if (from_x, from_y) != (to_x, to_y):
            styles.append('\\t(%d, %d, ' % (delay, delay + duration))
            styles.append('\\frx%.0f\\fry%.0f\\frz%.0f\\fscx%.0f\\fscy%.0f' % (to_rotarg[2:7]))
            styles.append(')')
        if fontface:
            styles.append('\\fn%s' % ASSEscape(fontface))
        styles.append('\\fs%.0f' % (c[6] * ZoomFactor[0]))
        if c[5] != 0xffffff:
            styles.append('\\c&H%s&' % ConvertColor(c[5]))
            if c[5] == 0x000000:
                styles.append('\\3c&HFFFFFF&')
        if from_alpha == to_alpha:
            styles.append('\\alpha&H%02X' % from_alpha)
        elif (from_alpha, to_alpha) == (255, 0):
            styles.append('\\fad(%.0f,0)' % (lifetime * 1000))
        elif (from_alpha, to_alpha) == (0, 255):
            styles.append('\\fad(0, %.0f)' % (lifetime * 1000))
        else:
            styles.append('\\fade(%(from_alpha)d, %(to_alpha)d, %(to_alpha)d, 0, %(end_time).0f, %(end_time).0f, %(end_time).0f)' % {'from_alpha': from_alpha, 'to_alpha': to_alpha, 'end_time': lifetime * 1000})
        if isborder == 'false':
            styles.append('\\bord0')
        f.write('Dialogue: -1,%(start)s,%(end)s,%(styleid)s,,0,0,0,,{%(styles)s}%(text)s\n' % {'start': ConvertTimestamp(c[0]), 'end': ConvertTimestamp(c[0] + lifetime), 'styles': ''.join(styles), 'text': text, 'styleid': styleid})
    except (IndexError, ValueError) as e:
        pass
        # try:
            # logging.warning(_('Invalid comment: %r') % c[3])
        # except IndexError:
            # logging.warning(_('Invalid comment: %r') % c)

# Result: (f, dx, dy)
# To convert: NewX = f*x+dx, NewY = f*y+dy
def GetZoomFactor(SourceSize, TargetSize):
    try:
        if (SourceSize, TargetSize) == GetZoomFactor.Cached_Size:
            return GetZoomFactor.Cached_Result
    except AttributeError:
        pass
    GetZoomFactor.Cached_Size = (SourceSize, TargetSize)
    try:
        SourceAspect = SourceSize[0] / SourceSize[1]
        TargetAspect = TargetSize[0] / TargetSize[1]
        if TargetAspect < SourceAspect:  # narrower
            ScaleFactor = TargetSize[0] / SourceSize[0]
            GetZoomFactor.Cached_Result = (ScaleFactor, 0, (TargetSize[1] - TargetSize[0] / SourceAspect) / 2)
        elif TargetAspect > SourceAspect:  # wider
            ScaleFactor = TargetSize[1] / SourceSize[1]
            GetZoomFactor.Cached_Result = (ScaleFactor, (TargetSize[0] - TargetSize[1] * SourceAspect) / 2, 0)
        else:
            GetZoomFactor.Cached_Result = (TargetSize[0] / SourceSize[0], 0, 0)
        return GetZoomFactor.Cached_Result
    except ZeroDivisionError:
        GetZoomFactor.Cached_Result = (1, 0, 0)
        return GetZoomFactor.Cached_Result


# Calculation is based on https://github.com/jabbany/CommentCoreLibrary/issues/5#issuecomment-40087282
#                     and https://github.com/m13253/danmaku2ass/issues/7#issuecomment-41489422
# ASS FOV = width*4/3.0
# But Flash FOV = width/math.tan(100*math.pi/360.0)/2 will be used instead
# Result: (transX, transY, rotX, rotY, rotZ, scaleX, scaleY)
def ConvertFlashRotation(rotY, rotZ, X, Y, width, height):
    def WrapAngle(deg):
        return 180 - ((180 - deg) % 360)
    rotY = WrapAngle(rotY)
    rotZ = WrapAngle(rotZ)
    if rotY in (90, -90):
        rotY -= 1
    if rotY == 0 or rotZ == 0:
        outX = 0
        outY = -rotY  # Positive value means clockwise in Flash
        outZ = -rotZ
        rotY *= math.pi / 180.0
        rotZ *= math.pi / 180.0
    else:
        rotY *= math.pi / 180.0
        rotZ *= math.pi / 180.0
        outY = math.atan2(-math.sin(rotY) * math.cos(rotZ), math.cos(rotY)) * 180 / math.pi
        outZ = math.atan2(-math.cos(rotY) * math.sin(rotZ), math.cos(rotZ)) * 180 / math.pi
        outX = math.asin(math.sin(rotY) * math.sin(rotZ)) * 180 / math.pi
    trX = (X * math.cos(rotZ) + Y * math.sin(rotZ)) / math.cos(rotY) + (1 - math.cos(rotZ) / math.cos(rotY)) * width / 2 - math.sin(rotZ) / math.cos(rotY) * height / 2
    trY = Y * math.cos(rotZ) - X * math.sin(rotZ) + math.sin(rotZ) * width / 2 + (1 - math.cos(rotZ)) * height / 2
    trZ = (trX - width / 2) * math.sin(rotY)
    FOV = width * math.tan(2 * math.pi / 9.0) / 2
    try:
        scaleXY = FOV / (FOV + trZ)
    except ZeroDivisionError:
        logging.error('Rotation makes object behind the camera: trZ == %.0f' % trZ)
        scaleXY = 1
    trX = (trX - width / 2) * scaleXY + width / 2
    trY = (trY - height / 2) * scaleXY + height / 2
    if scaleXY < 0:
        scaleXY = -scaleXY
        outX += 180
        outY += 180
        logging.error('Rotation makes object behind the camera: trZ == %.0f < %.0f' % (trZ, FOV))
    return (trX, trY, WrapAngle(outX), WrapAngle(outY), WrapAngle(outZ), scaleXY * 100, scaleXY * 100)


def ProcessComments(comments, f, width, height, bottomReserved, fontface, fontsize, alpha, duration_marquee, duration_still, filter_regex, reduced, progress_callback):
    styleid = 'Danmaku2ASS_%04x' % random.randint(0, 0xffff)
    WriteASSHead(f, width, height, fontface, fontsize, alpha, styleid)
    rows = [[None] * (height - bottomReserved + 1) for i in range(4)]
    for idx, i in enumerate(comments):
        if progress_callback and idx % 1000 == 0:
            progress_callback(idx, len(comments))
        if isinstance(i[4], int):
            if filter_regex and filter_regex.search(i[3]):
                continue
            row = 0
            rowmax = height - bottomReserved - i[7]
            while row <= rowmax:
                freerows = TestFreeRows(rows, i, row, width, height, bottomReserved, duration_marquee, duration_still)
                if freerows >= i[7]:
                    MarkCommentRow(rows, i, row)
                    WriteComment(f, i, row, width, height, bottomReserved, fontsize, duration_marquee, duration_still, styleid)
                    break
                else:
                    row += freerows or 1
            else:
                if not reduced:
                    row = FindAlternativeRow(rows, i, height, bottomReserved)
                    MarkCommentRow(rows, i, row)
                    WriteComment(f, i, row, width, height, bottomReserved, fontsize, duration_marquee, duration_still, styleid)
        elif i[4] == 'bilipos':
            WriteCommentBilibiliPositioned(f, i, width, height, styleid)
        else:
            pass
            # logging.warning(_('Invalid comment: %r') % i[3])
    if progress_callback:
        progress_callback(len(comments), len(comments))


def TestFreeRows(rows, c, row, width, height, bottomReserved, duration_marquee, duration_still):
    res = 0
    rowmax = height - bottomReserved
    targetRow = None
    if c[4] in (1, 2):
        while row < rowmax and res < c[7]:
            if targetRow != rows[c[4]][row]:
                targetRow = rows[c[4]][row]
                if targetRow and targetRow[0] + duration_still > c[0]:
                    break
            row += 1
            res += 1
    else:
        try:
            thresholdTime = c[0] - duration_marquee * (1 - width / (c[8] + width))
        except ZeroDivisionError:
            thresholdTime = c[0] - duration_marquee
        while row < rowmax and res < c[7]:
            if targetRow != rows[c[4]][row]:
                targetRow = rows[c[4]][row]
                try:
                    if targetRow and (targetRow[0] > thresholdTime or targetRow[0] + targetRow[8] * duration_marquee / (targetRow[8] + width) > c[0]):
                        break
                except ZeroDivisionError:
                    pass
            row += 1
            res += 1
    return res


def FindAlternativeRow(rows, c, height, bottomReserved):
    res = 0
    for row in range(height - bottomReserved - math.ceil(c[7])):
        if not rows[c[4]][row]:
            return row
        elif rows[c[4]][row][0] < rows[c[4]][res][0]:
            res = row
    return res


def MarkCommentRow(rows, c, row):
    try:
        for i in range(row, row + math.ceil(c[7])):
            rows[c[4]][i] = c
    except IndexError:
        pass


def WriteASSHead(f, width, height, fontface, fontsize, alpha, styleid):
    f.write(
        '''[Script Info]
; Script generated by Danmaku2ASS
; https://github.com/m13253/danmaku2ass
Script Updated By: Danmaku2ASS (https://github.com/m13253/danmaku2ass)
ScriptType: v4.00+
PlayResX: %(width)d
PlayResY: %(height)d
Aspect Ratio: %(width)d:%(height)d
Collisions: Normal
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: %(styleid)s, %(fontface)s, %(fontsize).0f, &H%(alpha)02XFFFFFF, &H%(alpha)02XFFFFFF, &H%(alpha)02X000000, &H%(alpha)02X000000, 0, 0, 0, 0, 100, 100, 0.00, 0.00, 1, %(outline).0f, 0, 7, 0, 0, 0, 0

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
''' % {'width': width, 'height': height, 'fontface': fontface, 'fontsize': fontsize, 'alpha': 255 - round(alpha * 255), 'outline': max(fontsize / 25.0, 1), 'styleid': styleid}
    )


def WriteComment(f, c, row, width, height, bottomReserved, fontsize, duration_marquee, duration_still, styleid):
    text = ASSEscape(c[3])
    styles = []
    if c[4] == 1:
        styles.append('\\an8\\pos(%(halfwidth)d, %(row)d)' % {'halfwidth': width / 2, 'row': row})
        duration = duration_still
    elif c[4] == 2:
        styles.append('\\an2\\pos(%(halfwidth)d, %(row)d)' % {'halfwidth': width / 2, 'row': ConvertType2(row, height, bottomReserved)})
        duration = duration_still
    elif c[4] == 3:
        styles.append('\\move(%(neglen)d, %(row)d, %(width)d, %(row)d)' % {'width': width, 'row': row, 'neglen': -math.ceil(c[8])})
        duration = duration_marquee
    else:
        styles.append('\\move(%(width)d, %(row)d, %(neglen)d, %(row)d)' % {'width': width, 'row': row, 'neglen': -math.ceil(c[8])})
        duration = duration_marquee
    if not (-1 < c[6] - fontsize < 1):
        styles.append('\\fs%.0f' % c[6])
    if c[5] != 0xffffff:
        styles.append('\\c&H%s&' % ConvertColor(c[5]))
        if c[5] == 0x000000:
            styles.append('\\3c&HFFFFFF&')
    f.write('Dialogue: 2,%(start)s,%(end)s,%(styleid)s,,0000,0000,0000,,{%(styles)s}%(text)s\n' % {'start': ConvertTimestamp(c[0]), 'end': ConvertTimestamp(c[0] + duration), 'styles': ''.join(styles), 'text': text, 'styleid': styleid})


def ASSEscape(s):
    def ReplaceLeadingSpace(s):
        sstrip = s.strip(' ')
        slen = len(s)
        if slen == len(sstrip):
            return s
        else:
            llen = slen - len(s.lstrip(' '))
            rlen = slen - len(s.rstrip(' '))
            return ''.join(('\u2007' * llen, sstrip, '\u2007' * rlen))
    return '\\N'.join((ReplaceLeadingSpace(i) or ' ' for i in str(s).replace('\\', '\\\\').replace('{', '\\{').replace('}', '\\}').split('\n')))


def CalculateLength(s):
    return max(map(len, s.split('\n')))  # May not be accurate


def ConvertTimestamp(timestamp):
    timestamp = round(timestamp * 100.0)
    hour, minute = divmod(timestamp, 360000)
    minute, second = divmod(minute, 6000)
    second, centsecond = divmod(second, 100)
    return '%d:%02d:%02d.%02d' % (int(hour), int(minute), int(second), int(centsecond))


def ConvertColor(RGB, width=1280, height=576):
    if RGB == 0x000000:
        return '000000'
    elif RGB == 0xffffff:
        return 'FFFFFF'
    R = (RGB >> 16) & 0xff
    G = (RGB >> 8) & 0xff
    B = RGB & 0xff
    if width < 1280 and height < 576:
        return '%02X%02X%02X' % (B, G, R)
    else:  # VobSub always uses BT.601 colorspace, convert to BT.709
        ClipByte = lambda x: 255 if x > 255 else 0 if x < 0 else round(x)
        return '%02X%02X%02X' % (
            ClipByte(R * 0.00956384088080656 + G * 0.03217254540203729 + B * 0.95826361371715607),
            ClipByte(R * -0.10493933142075390 + G * 1.17231478191855154 + B * -0.06737545049779757),
            ClipByte(R * 0.91348912373987645 + G * 0.07858536372532510 + B * 0.00792551253479842)
        )


def ConvertType2(row, height, bottomReserved):
    return height - bottomReserved - row


def ConvertToFile(filename_or_file, *args, **kwargs):
    if isinstance(filename_or_file, bytes):
        filename_or_file = str(bytes(filename_or_file).decode('utf-8', 'replace'))
    if isinstance(filename_or_file, str):
        return open(filename_or_file, *args, **kwargs)
    else:
        return filename_or_file


def FilterBadChars(f):
    s = f.read()
    s = re.sub('[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f]', '\ufffd', s)
    return io.StringIO(s)


class safe_list(list):

    def get(self, index, default=None):
        try:
            return self[index]
        except IndexError:
            return default


def export(func):
    global __all__
    try:
        __all__.append(func.__name__)
    except NameError:
        __all__ = [func.__name__]
    return func

def Danmaku2ASS(input_files, input_format, output_file, stage_width, stage_height, reserve_blank=0, font_face=_('(FONT) sans-serif')[7:], font_size=25.0, text_opacity=1.0, duration_marquee=5.0, duration_still=5.0, comment_filter=None, is_reduce_comments=False, progress_callback=None):
    try:
        if comment_filter:
            filter_regex = re.compile(comment_filter)
        else:
            filter_regex = None
    except:
        raise ValueError(_('Invalid regular expression: %s') % comment_filter)
    fo = None
    comments = ReadComments(input_files, input_format, font_size)
    try:
        if output_file:
            fo = ConvertToFile(output_file, 'w', encoding='utf-8-sig', errors='replace', newline='\r\n')
        else:
            fo = sys.stdout
        ProcessComments(comments, fo, stage_width, stage_height, reserve_blank, font_face, font_size, text_opacity, duration_marquee, duration_still, filter_regex, is_reduce_comments, progress_callback)
    finally:
        if output_file and fo != output_file:
            fo.close()

def ReadComments(input_files, input_format, font_size=25.0, progress_callback=None):
    if isinstance(input_files, bytes):
        input_files = str(bytes(input_files).decode('utf-8', 'replace'))
    if isinstance(input_files, str):
        input_files = [input_files]
    else:
        input_files = list(input_files)
    comments = []
    for idx, i in enumerate(input_files):
        if progress_callback:
            progress_callback(idx, len(input_files))
        with ConvertToFile(i, 'r', encoding='utf-8', errors='replace') as f:
            s = f.read()
            str_io = io.StringIO(s)
            CommentProcessor = CommentFormatMap.get(input_format)
            if not CommentProcessor:
                raise ValueError(
                    _('Unknown comment file format: %s') % input_format
                )
            comments.extend(CommentProcessor(FilterBadChars(str_io), font_size))
    if progress_callback:
        progress_callback(len(input_files), len(input_files))
    comments.sort()
    return comments
