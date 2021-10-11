from zipfile import ZipFile
from aioify import aioify
from pathlib import Path


def make_zip_file(output_file_name, source_dir):
    zip_file_name = f"{output_file_name}.zip"

    dir = Path(source_dir)

    with ZipFile(zip_file_name, 'w') as zip_file:
        for entry_file in dir.rglob("*"):
            zip_file.write(entry_file, entry_file.relative_to(dir))

    return zip_file_name


aio_make_zip_file = aioify(make_zip_file)

