#!/usr/bin/env python
# -*- coding: utf-8 -*-

# imports: standard
from __future__ import unicode_literals
from __future__ import print_function
import sys
from time import sleep
import os
import subprocess

# imports: third party
from gooey import Gooey, GooeyParser

# contants
trackers = {
    "red",
    "ops",
    "nwcd",
    "dic",
}

def remove_suffix(text, suffix):
    if text is not None and suffix is not None:
        return text[:-len(suffix)] if text.endswith(suffix) else text
    else:
        return text

# determine if application is a script file or frozen exe
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(os.path.realpath(sys.executable))
    if sys.platform == "darwin":
        application_path = remove_suffix(application_path, "/{0}.app/Contents/MacOS".format(os.path.basename(sys.executable)))
elif __file__:
    application_path = os.path.dirname(os.path.realpath(__file__))

@Gooey(optional_cols=2,
       default_size=(610, 740),
       show_success_modal=False,
       show_failure_modal=False,
       program_name="GazelleSync GUI")
def parse_args():
    settings_msg = 'Bring torrents from one Gazelle instance to another'
    parser = GooeyParser(description=settings_msg)

    # --from <>
    parser.add_argument(
        '--from',
        choices=trackers,
        required=True,
        help="torrents from which Gazelle instance"
    )

    # -to <>
    parser.add_argument(
        "--to",
        choices=trackers,
        required=True,
        help="sync to which Gazelle instance"
    )

    # --album <> / --folder <>
    group = parser.add_mutually_exclusive_group(
        required=True,
        gooey_options={
            'initial_selection': 0
        }
    )
    group.add_argument(
        "--album",
        help="the folder of the album",
        widget="DirChooser"
    )
    group.add_argument(
        "--folder",
        help="the folder that contauins all albums. The album folder will be extracted from the site metadata",
        widget="DirChooser"
    )

    # --tid <> / --link <> / --tpath <> / --tfolder <>
    group = parser.add_mutually_exclusive_group(required=True,
                                                gooey_options={
                                                    'initial_selection': 0
                                                })
    group.add_argument(
        "--link",
        help="the whole permalinlk. The tool os smart enough to extract it"
    )
    group.add_argument(
        "--tid",
        help="the torrent ID"
    )
    group.add_argument(
        "--tpath",
        help="the path that points towards the .torrent file. The infohash will be computed",
        widget="FileChooser"
    )
    group.add_argument(
        "--tfolder",
        help="the folder containing all the .torrent files",
        widget="DirChooser"
    )

    parser.add_argument(
        '-c', '--config',
        metavar='FILE',
        default=os.path.join(application_path, 'config.cfg'),
        help='config file with login details (default: config.cfg)',
        widget="FileChooser"
    )

    return parser.parse_args()

def main():
    args = parse_args()

    # get original command line arguments
    argv = []
    for arg in vars(args):
        value = getattr(args, arg)
        if value:
            argv.append("--" + arg)
            argv.append(value)

    # execute real command with the same arguments
    real_command_code = os.path.join(application_path, "gs-cli.py")
    real_command_exe = os.path.join(application_path, "gs-cli")
    real_command_exe_win = os.path.join(application_path, "gs-cli.exe")
    real_command_exe_unix = real_command_exe
    if os.path.isfile(real_command_exe_win) or os.path.isfile(real_command_exe_unix):
        argv.insert(0, real_command_exe)
    else:
        argv.insert(0, real_command_code)
        argv.insert(0, "python")

    print(argv)
    return subprocess.call(argv)

if __name__ == "__main__":
    sys.exit(main())
