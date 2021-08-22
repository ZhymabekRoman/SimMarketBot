import tarfile
from aioify import aioify


def make_tarfile(output_filename, source_dir):
    tarfile_name = f"{output_filename}.tar.gz"

    with tarfile.open(tarfile_name, "w:gz") as tar:
        tar.add(source_dir)

    return tarfile_name


aiomake_tarfile = aioify(make_tarfile)
