from distutils.core import setup

VERSION = '0.3.1'

setup(
    name='vdisk',
    version=VERSION,
    description="Helper tool to build debian based virtual disks.",
    author='John-John Tedro',
    author_email='udoprog@spotify.com',
    license='Apache License 2.0',
    packages=[
        'vdisk',
        'vdisk.actions',
        'vdisk.preset',
    ],
    scripts=[
        "bin/vdisk"
    ],
    data_files=[
        ("", ["LICENSE.txt"]),
    ],
)
