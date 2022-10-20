import os
import glob
import apache_beam as beam

from apache_beam.options.pipeline_options import PipelineOptions

from odl.pipeline import transforms, outputs

base_options = {"save_main_session": False, "runner": "DirectRunner"}


def _to_absolute_path(path):
    if path.startswith('/'):
        return path

    if '://' in path:
        return path

    return os.path.join(os.getcwd(), path)


def run(path, output_path, options=None, offset=None):
    """
    Run the oDL pipeline.

    path: Where we are getting the download data.
    offset: Offset in seconds from UTC for the attribution window.
    """

    print("Running the oDL pipeline from {} to {}".format(path, output_path))

    # if it's a relative path, we need to make it absolue.
    path = _to_absolute_path(path)
    output_path = _to_absolute_path(output_path)

    # create the actual pipeline
    pipeline_options = base_options.copy()
    if options:
        pipeline_options.update(options)

    options = PipelineOptions.from_dictionary(pipeline_options)
    pipeline = beam.Pipeline(options=options)

    # We are going to
    events = (pipeline | beam.io.avroio.ReadFromAvro(path))

    # Does the bulk of the work.
    downloads = (events | transforms.ODLDownloads(window_offset=offset))

    # Get hourly Downloads.
    hourly = (downloads | 'CountByHour' >> transforms.CountByHour())

    # Downloads by Episode
    episodes = (downloads | 'CountByEpisode' >> transforms.CountByEpisode())

    # Downloads by App.
    apps = (downloads | 'CountByApp' >> transforms.CountByApp())

    # Total number of downloads.
    count = (downloads | 'CountDownloads' >> transforms.CountDownloads())

    # All values
    values = (downloads | 'AllValues' >> transforms.ExtractDownloads())

    # All values by hour
    values_by_hour = (downloads | 'AllValuesByHour' >> transforms.ExtractDownloadsByHour())

    # Write everything out.

    # Write hourly (CSV)
    hourly_out = (hourly
                  | 'WriteHourly' >> outputs.WriteCSV(output_path, 'hourly'))

    # Write episodes (CSV)
    episodes_out = (
        episodes
        | 'WriteEpisodes' >> outputs.WriteCSV(output_path, 'episodes'))

    # Write apps (CSV)
    apps_out = (apps | 'WriteApps' >> outputs.WriteCSV(output_path, 'apps'))

    # Write count (TXT)
    count_out = (count | 'WriteCount' >> outputs.Write(output_path, 'count'))

    # Write downloads (CSV)
    downloads_out = (values | 'WriteDownloads' >> outputs.WriteCSV(output_path, 'downloads'))

    # Write downloads by hour (CSV)
    for i, hour in values_by_hour:
        downloads_by_hour_out = (hour
            | 'WriteDownloads{}'.format(i) >> outputs.WriteCSV(output_path, 'downloads-{:02d}'.format(i)))

    # Actually start this thing and wait till it's done.
    resp = pipeline.run()
    resp.wait_until_finish()

    # Delete any empty hourly files
    files = glob.glob('{}/downloads-??.csv'.format(output_path))
    for filename in files:
        if os.path.getsize(filename) == 0:
            os.remove(filename)

    if output_path.startswith('/'):

        with open(os.path.join(output_path, 'count.txt')) as file:
            print("\noDL run complete.\nDownloads: {}".format(
                file.read().strip()))

        print("Output files written to path: {}".format(output_path))
