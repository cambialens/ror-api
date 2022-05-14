import requests
import zipfile

from zenodo_client import Zenodo

from django.core.management.base import BaseCommand
from .deleteindex import Command as DeleteIndexCommand
from .createindex import Command as CreateIndexCommand
from .indexrordump import Command as IndexRorDumpCommand


def get_ror_filename(ror_zenodo_id: str):
    zenodo = Zenodo()
    latest_record_id = zenodo.get_latest_record(ror_zenodo_id)
    zenodo_json = zenodo.get_record(latest_record_id).json()
    return zenodo_json['files'][0]['key']


class Command(BaseCommand):
    help = 'Setup ROR API'

    def add_arguments(self, parser):
        parser.add_argument('zenodo_id', type=str, help='Zenodo ROR ID - `curl -s \'https://zenodo.org/api/records/?communities=ror-data&sort=mostrecent\' | jq -r \'.hits.hits[0].conceptrecid\'`')

    def handle(self, *args, **options):
        # make sure ROR dump file exists
        ror_zenodo_id = options['zenodo_id']
        filename_zip = get_ror_filename(ror_zenodo_id)  # v1.0-2022-03-17-ror-data.json.zip

        if filename_zip:
            DeleteIndexCommand().handle(*args, **options)
            CreateIndexCommand().handle(*args, **options)
            IndexRorDumpCommand().handle(*args, **options)

        else:
            self.stdout.write('ROR dataset for version {} not found. '.
                              format(filename_zip) +
                              'Please generate the data dump first.')
            return

