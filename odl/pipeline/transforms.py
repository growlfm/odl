"""
The beam transforms.

Many of these could just be functions, but we make them transforms so they can
be easily imported into other pipelines if needed.
"""
import re
import hashlib
import udatetime

import apache_beam as beam
import apache_beam.transforms.window as window
import apache_beam.transforms.trigger as trigger

from odl import players

# User Agents that don't tell us about the app.
useless_ua_re = re.compile('okhttp|AppleCoreMedia')

MILLIS_PER_SEC = 1000


def to_unix_timestamp(timestamp):
    # Convert ISO8601 string to Unix numeric timestamp (unit = seconds)
    return int(udatetime.from_string(timestamp).timestamp())


def remove_denied_ua(item):
    if not item['player']['bot']:
        yield item


class RemoveByUADenyList(beam.PTransform):
    """
    Using opawg's bot list, remove known bots.
    """

    def expand(self, downloads):
        return (downloads
                | 'RemoveByUADenyList' >> beam.FlatMap(remove_denied_ua))


def add_player(item):
    item['player'] = players.get_player(item['user_agent'])
    return item


class AddPodcastPlayer(beam.PTransform):
    """
    Augments the download stream to include player information.
    """

    def expand(self, downloads):
        return (downloads | 'AddPodcastPlayer' >> beam.Map(add_player))


def timestamp_and_key(item):
    """
    In order to use beam's windowing functions, each row needs to have a timestamp

    We also give each row a key based on ip, user agent, and episode url.

    Together, the timestamp and key make sure we don't count a download pair more
    than once per 24 hour period
    """

    # get the unix timestamp for the row
    timestamp = to_unix_timestamp(item['timestamp'])

    # build the download pair key for this enclosure url
    key = '^'.join(
        [item['encoded_ip'], item['user_agent'], item['episode_id']])
    key = hashlib.md5(key.encode('utf-8')).hexdigest()

    # create rows that beam's window functions can work with
    yield beam.window.TimestampedValue((key, item), timestamp)


class IsGoodDownload(beam.DoFn):
    """
    Determines if a download is "good"
    """

    def process(self, element):
        key = element[0]
        events = element[1]

        # First thing is to filter out all the http_method that aren't a get.
        gets = [evt for evt in events if evt['http_method'].lower() == 'get']

        if len(gets) == 0:
            yield beam.pvalue.TaggedOutput('bad', element)
        else:
            # Next determine if we got any full GET requests (i.e. not a partial (range) request).
            full_reqs = [evt for evt in gets if not evt['byte_range_start'] and not evt['byte_range_end']]

            if len(full_reqs):
                yield element
            else:
                # There are only range requests for this element

                # Determine if any range requests are unbounded - if so, count them as good download
                start_only_reqs = [evt for evt in gets if not evt['byte_range_end']]
                if len(start_only_reqs):
                    yield element
                else:
                    # Throw out all the 2 byte requests and sum the rest.
                    byte_count = sum(
                        map(lambda evt: abs(evt['byte_range_end'] - evt['byte_range_start']),
                            filter(lambda evt: evt['byte_range_end'] != 1,
                                   gets)))

                    if byte_count > 0:
                        yield element
                    else:
                        yield beam.pvalue.TaggedOutput('bad', element)


class CountByAttribute(beam.PTransform):
    def __init__(self, attribute, label=None):
        super(CountByAttribute, self).__init__(label=label)
        self.attribute = attribute

    def expand(self, downloads):

        return (downloads | 'Get{}'.format(self.attribute.capitalize()) >>
                beam.Map(lambda dl: dl[self.attribute])
                | 'CountBy{}'.format(self.attribute.capitalize()) >>
                beam.combiners.Count.PerElement())


class CountByApp(beam.PTransform):
    def expand(self, downloads):
        return (downloads
                | 'AppGlobalWindow' >> beam.WindowInto(window.GlobalWindows())
                | CountByAttribute(attribute="app"))


class CountByEpisode(beam.PTransform):
    def expand(self, downloads):
        return (
            downloads
            | 'EpisodeGlobalWindow' >> beam.WindowInto(window.GlobalWindows())
            | CountByAttribute(attribute="episode_id"))


class CountByHour(beam.PTransform):
    def expand(self, downloads):
        return (downloads | 'GetHour' >> beam.Map(lambda dl: udatetime.from_string(dl['timestamp']).replace(
            minute=0, second=0, microsecond=0).isoformat())
                | 'CountByHour' >> beam.combiners.Count.PerElement())


class CountDownloads(beam.PTransform):
    def expand(self, downloads):
        return (
            downloads
            |
            'DownloadsGlobalWindow' >> beam.WindowInto(window.GlobalWindows())
            | beam.CombineGlobally(
                beam.combiners.CountCombineFn()).without_defaults())


class ExtractDownloads(beam.PTransform):
    def expand(self, downloads):
        return (downloads | 'ExtractDownloads' >> beam.Map(get_odl_download_values))


def partition_fn(dl, num_partitions):
    return int(udatetime.from_string(dl['timestamp']).hour)


class ExtractDownloadsByHour(beam.PTransform):
    def expand(self, downloads):
        hours = []
        downloads_by_hour = downloads | 'PartitionByHour' >> beam.Partition(partition_fn, 24)
        for i, hour in enumerate(downloads_by_hour):
            hours.append((i, hour | 'ExtractHour{}Downloads'.format(i) >> beam.Map(get_odl_download_values)))
        return hours


def add_ip_user_agents(element):
    """
    Add the alternative user_agents. "AppleCoreMedia" can be any number of
    different apps. We want to look for a better app that made a request to the
    episodes before CoreMedia did it's thing.
    """
    events = element[1]

    # We need the ua
    user_agents = sorted(
        [(evt['user_agent'], to_unix_timestamp(evt['timestamp']))
         for evt in events if not useless_ua_re.search(evt['user_agent'])],
        key=lambda ua: ua[1],
        reverse=True)

    for evt in events:
        timestamp = to_unix_timestamp(evt['timestamp'])

        # It's 5 minutes, but in generally happens under 10 seconds.
        lookback = timestamp - 5 * 60

        evt['ip_user_agents'] = [
            ua for ua in user_agents if ua[0] != evt['user_agent']
            and timestamp > ua[1] and lookback < ua[1]
        ]
        yield evt


class ODLGroupUserAgents(beam.PTransform):
    """
    :experimental:

    `AppleCoreMedia` can belong to a few apps. Apple Podcasts, Stitcher and
    Spotify for example.

    The ideal way of handling this is looking back at the IP and seeing which
    app made the request with an better user agent right before the stream
    started.

    It can produce false positives at a large scale.
    """

    def expand(self, events):
        return (events | 'ToIpMap' >> beam.Map(lambda e: (e['encoded_ip'], e))
                | 'GroupByIP' >> beam.GroupByKey()
                | 'AddIpUserAgents' >> beam.FlatMap(add_ip_user_agents))


def get_odl_download_values(element):

    key = '^'.join([element['encoded_ip'], element['user_agent']])
    listener_id = hashlib.md5(key.encode('utf-8')).hexdigest()

    # Want Unix timestamp to be in milliseconds, not seconds
    ts_in_ms = element['unix'] * MILLIS_PER_SEC

    if 'ip' in element:
        output = {
            'timestamp': ts_in_ms,
            'ip': element['ip'],
            'user_agent': element['user_agent'],
            'listener_id': listener_id,
            'episode_id': element['episode_id'],
            'app': element['app'],
            'device': element['device'],
            'os': element['os']
        }
    else:
        output = {
            'timestamp': ts_in_ms,
            'encoded_ip': element['encoded_ip'],
            'user_agent': element['user_agent'],
            'listener_id': listener_id,
            'episode_id': element['episode_id'],
            'app': element['app'],
            'device': element['device'],
            'os': element['os']
        }

    return list(output.values())


def to_odl_download(element):
    """
    Sort out the final output
    """
    key = element[0]
    events = element[1]

    # sort the events by timestamp and use the first one.
    for evt in events:
        evt['unix'] = to_unix_timestamp(evt['timestamp'])

    events = sorted(events, key=lambda e: e['unix'])
    evt = events[0]

    # put together an 'app'
    player = evt['player']

    app = player.get('app')
    device = player.get('device')
    os = player.get('os')

    if app == 'Unknown':
        # Use the rest of the data.
        print("Unknown app! user_agent = {}".format(player.get('user_agent')))
        app = '{}.{}'.format(device, os)

    output = {
        'id': key,  # id of the download, for dedupe if needed.
        'timestamp': evt['timestamp'],
        'unix': evt['unix'],
        'encoded_ip': evt['encoded_ip'],
        'user_agent': evt['user_agent'],
        'episode_id': evt['episode_id'],
        'app': app,
        'device': device,
        'os': os
    }

    if evt['ip']:
        output['ip'] = evt['ip']

    return output


def pair_ua(element):
    events = element[1]

    # We need the ua
    user_agents = [evt['user_agent'] for evt in events]

    for evt in events:
        for ua in [ua for ua in user_agents if ua != evt['user_agent']]:
            yield '{}||{}'.format(evt['user_agent'], ua)


class CommonPairs(beam.PTransform):
    """
    Helper function to determine popular user_agent pairs at the same ip.
    """

    def expand(self, events):
        return (events | 'ToIpMap' >> beam.Map(lambda e: (e['encoded_ip'], e))
                | 'GroupByIP' >> beam.GroupByKey()
                | 'PairToUa' >> beam.FlatMap(pair_ua)
                | beam.combiners.Count.PerElement())


class ODLDownloads(beam.PTransform):
    """
    Window events into a 24 hour window.
    """

    def __init__(self, window_offset, label=None):
        super(ODLDownloads, self).__init__(label=label)
        self.window_offset = window_offset

    def expand(self, events):
        window_trigger = trigger.DefaultTrigger()
        offset = self.window_offset and self.window_offset or 0

        good, bad = (
            events
            | 'AddPodcastPlayer' >> AddPodcastPlayer()
            | 'RemoveByUADenyList' >> RemoveByUADenyList()
            | 'TimestampKey' >> beam.ParDo(timestamp_and_key)
            # window into 24 hour windows
            | 'Window' >> beam.WindowInto(
                window.FixedWindows(60 * 60 * 24, offset=offset),
                trigger=window_trigger,
                accumulation_mode=trigger.AccumulationMode.ACCUMULATING)

            # since we've set a beam window in the last step, GroupByKey
            # will group by key and window. This covers the window and
            # download pair requirements for the ODL spec.
            | 'GroupOverWindow' >> beam.GroupByKey()
            | 'IsGoodDownload' >> beam.ParDo(IsGoodDownload()).with_outputs(
                'bad', main='good'))

        return (good | 'ODLDownload' >> beam.Map(to_odl_download))
