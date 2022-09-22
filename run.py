import argparse
import os
import uuid
from pathlib import Path

from odl import prepare, pipeline


'''
/////////////////////////////////////////////
//  Entry point
/////////////////////////////////////////////
'''

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "input_file", help="File path to raw source events (in CSV format)")

    args = parser.parse_args()

    input_file = args.input_file

    uid = uuid.uuid4().hex

    # Ensure AVRO workdir exists
    avro_output_path = '/tmp/odl/'
    Path(avro_output_path).mkdir(parents=True, exist_ok=True)

    basename, ext = os.path.splitext(input_file)
    fmt = ext.split('.').pop()

    avro_file = '{}{}.avro'.format(avro_output_path, uid)
    prepare.run(input_file, avro_file, fmt)

    # Ensure output dir exists
    output_path = '{}{}'.format('/var/lib/odl/', uid);
    Path(output_path).mkdir(parents=True, exist_ok=True)

    pipeline.run(avro_file, output_path)
