import os
import json
import unittest

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.testing.test_pipeline import TestPipeline

from odl import avro
from odl.pipeline import transforms

DIR_PATH = os.path.dirname(os.path.realpath(__file__))


def print_item(i):
    print(i)
    return i


class TestODLWindow(unittest.TestCase):
    def test_window(self):

        pipeline_options = {
            'runner': 'DirectRunner',
            'project': 'adaptive-growth'
        }

        options = PipelineOptions.from_dictionary(pipeline_options)

        with TestPipeline(options=options) as p:

            # load up the fixture.
            events = (p | beam.Create(
                list(
                    avro.read(
                        os.path.join(DIR_PATH,
                                     '../../fixtures/demo.odl.avro')))))

            # Use 1 hour offset (in seconds) from UTC for the attribution window
            offset = 60 * 60
            downloads = (events | transforms.ODLDownloads(window_offset=offset))

            # Get hourly Downloads.
            hourly = (downloads | 'CountByHour' >> transforms.CountByHour())

            # Downloads by Episode
            episodes = (downloads | 'CountByEpisode' >> transforms.CountByEpisode())

            # Downloads by App.
            apps = (downloads | 'CountByApp' >> transforms.CountByApp())

            # Total number of downloads.
            count = (downloads | 'CountDownloads' >> transforms.CountDownloads()
                            | 'Num Downloads' >> beam.Map(print_item))


if __name__ == '__main__':
    unittest.main()
