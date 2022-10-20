import csv
import os
from io import StringIO

import apache_beam as beam


def to_csv(item):
    """
    Uses the csv lib to escape everything correctly.
    """
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(list(item))
    return buf.getvalue().rstrip(csv.excel.lineterminator)


class WriteCSV(beam.PTransform):
    """
    Writes a CSV.
    """

    def __init__(self, file_path, name, label=None):
        super(WriteCSV, self).__init__(label=label)
        self.file_path = file_path
        self.name = name

    def expand(self, items):
        path = os.path.join(self.file_path, self.name)
        return (items | 'ToCSV' >> beam.Map(to_csv)
                | 'WriteCSV' >> beam.io.WriteToText(
                    path, file_name_suffix='.csv', shard_name_template=''))


class Write(beam.PTransform):
    """
    Just write.
    """

    def __init__(self, file_path, name, label=None):
        super(Write, self).__init__(label=label)
        self.file_path = file_path
        self.name = name

    def expand(self, items):
        path = os.path.join(self.file_path, self.name)
        return (items
                | 'WriteCSV' >> beam.io.WriteToText(
                    path, file_name_suffix='.txt', shard_name_template=''))
