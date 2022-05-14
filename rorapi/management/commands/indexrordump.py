import json
import os
import re
import requests
import zipfile
import base64
from io import BytesIO
from rorapi.settings import ES, ES_VARS, ROR_DUMP, DATA

from django.core.management.base import BaseCommand
from elasticsearch import TransportError
from zenodo_client import Zenodo


def get_nested_names(org):
    yield org['name']
    for label in org['labels']:
        yield label['label']
    for alias in org['aliases']:
        yield alias
    for acronym in org['acronyms']:
        yield acronym

def get_nested_ids(org):
    yield org['id']
    yield re.sub('https://', '', org['id'])
    yield re.sub('https://ror.org/', '', org['id'])
    for ext_name, ext_id in org['external_ids'].items():
        if ext_name == 'GRID':
            yield ext_id['all']
        else:
            for eid in ext_id['all']:
                yield eid


def get_ror_filename(ror_zenodo_id: str):
    zenodo = Zenodo()
    latest_record_id = zenodo.get_latest_record(ror_zenodo_id)
    zenodo_json = zenodo.get_record(latest_record_id).json()
    return zenodo_json['files'][0]['key']


def get_ror_dump_zip(ror_zenodo_id: str):
    filename_zip = get_ror_filename(ror_zenodo_id)
    if filename_zip:
        zenodo = Zenodo()
        latest_record_id = zenodo.get_latest_record(ror_zenodo_id)
        download_path = zenodo.download(latest_record_id, filename_zip)
        return download_path


class Command(BaseCommand):
    help = 'Indexes ROR dataset from a full dump file in ror-data repo'

    def handle(self, *args, **options):
        json_file = ''
        ror_zenodo_id = options['zenodo_id']

        filename_zip = get_ror_filename(ror_zenodo_id)
        filename = filename_zip.replace('.json.zip', '')
        ror_dump_zip = get_ror_dump_zip(ror_zenodo_id)
        if ror_dump_zip:
            if not os.path.exists(DATA['WORKING_DIR']):
                os.makedirs(DATA['WORKING_DIR'])
            with zipfile.ZipFile(ror_dump_zip, 'r') as zip_ref:
                zip_ref.extractall(DATA['WORKING_DIR'] + filename)
            unzipped_files = os.listdir(DATA['WORKING_DIR'] + filename)
            for file in unzipped_files:
                if file.endswith(".json"):
                    json_file = file
            json_path = os.path.join(DATA['WORKING_DIR'], filename, '') + json_file
            with open(json_path, 'r') as it:
                dataset = json.load(it)

            self.stdout.write('Indexing ROR dataset ' + filename)

            index = ES_VARS['INDEX']
            backup_index = '{}-tmp'.format(index)
            ES.reindex(body={
                'source': {
                    'index': index
                },
                'dest': {
                    'index': backup_index
                }
            })

            try:
                for i in range(0, len(dataset), ES_VARS['BULK_SIZE']):
                    body = []
                    for org in dataset[i:i + ES_VARS['BULK_SIZE']]:
                        body.append({
                            'index': {
                                '_index': index,
                                '_type': 'org',
                                '_id': org['id']
                            }
                        })
                        org['names_ids'] = [{
                            'name': n
                        } for n in get_nested_names(org)]
                        org['names_ids'] += [{
                            'id': n
                        } for n in get_nested_ids(org)]
                        body.append(org)
                    ES.bulk(body)
            except TransportError:
                self.stdout.write(TransportError)
                self.stdout.write('Reverting to backup index')
                ES.reindex(body={
                    'source': {
                        'index': backup_index
                    },
                    'dest': {
                        'index': index
                    }
                })

            if ES.indices.exists(backup_index):
                ES.indices.delete(backup_index)
            self.stdout.write('ROR dataset ' + filename + ' indexed')
        else:
            print("ROR data dump zip file does not exist")
