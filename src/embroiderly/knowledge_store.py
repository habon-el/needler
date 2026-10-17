"""Read-only knowledge loader. Advisors receive values, never filesystem handles."""
import hashlib
import json
from pathlib import Path

TABLES = ('placements.json','lettering.json','backing.json','defaults.json','sewout.json','threads/generic.json','legacy.json','knockout.json','generation.json')


def load_knowledge():
    directory = Path(__file__).with_name('knowledge')
    result = {}
    for name in TABLES:
        raw = (directory/name).read_bytes()
        table = json.loads(raw)
        if type(table.get('version')) is not int or table['version'] < 1 or type(table.get('seed_data')) is not bool or not isinstance(table.get('rows'),list):
            raise ValueError(f'Invalid knowledge table: {name}')
        ids = set()
        for row in table['rows']:
            if not isinstance(row.get('id'),str) or row['id'] in ids or not isinstance(row.get('source_note'),str) or not row['source_note'].strip() or type(row.get('verified_by_user')) is not bool:
                raise ValueError(f'Invalid knowledge row: {name}')
            ids.add(row['id'])
        result[name] = {**table,'sha256':hashlib.sha256(raw).hexdigest()}
    return result
