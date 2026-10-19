"""Export the notebook's verified data and Python modules for local inspection."""
from pathlib import Path
import argparse
import ast
import base64
import hashlib
import io
import json
import zipfile


def extract_bundle(notebook, destination):
    destination = Path(destination).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Choose a new or empty output directory; existing files are preserved.')
    document = json.loads(Path(notebook).read_text(encoding='utf-8'))
    payload = {}
    for cell in document['cells']:
        if 'embedded-inputs' not in cell.get('metadata', {}).get('tags', []):
            continue
        for statement in ast.parse(''.join(cell['source'])).body:
            if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
                target = statement.targets[0]
                if isinstance(target, ast.Name) and target.id in ('PAYLOAD_BASE64', 'PAYLOAD_SHA256'):
                    payload[target.id] = ast.literal_eval(statement.value)
    packed = base64.b64decode(payload['PAYLOAD_BASE64'], validate=True)
    if hashlib.sha256(packed).hexdigest() != payload['PAYLOAD_SHA256']:
        raise ValueError('Notebook payload checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(packed)) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        for name, record in manifest.items():
            output = (destination / name).resolve()
            if not output.is_relative_to(destination):
                raise ValueError('Archive path leaves output directory')
            data = archive.read(name)
            if hashlib.sha256(data).hexdigest() != record['sha256']:
                raise ValueError('File checksum mismatch: ' + name)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
        (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return len(manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('notebook', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    count = extract_bundle(args.notebook, args.destination)
    print(f'Exported {count} verified files to {args.destination.resolve()}')
