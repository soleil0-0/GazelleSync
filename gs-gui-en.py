#!/usr/bin/env Python3
import PySimpleGUI as sg
import os
import sys

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def is_exe(fpath):
    return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

move_cmd = "python gs-cli.py"
if is_exe("gs-cli.exe") or is_exe("gs-cli"):
    move_cmd = os.path.join(".", "gs-cli")

sg.ChangeLookAndFeel('DarkBlue')

layout = [
    [sg.Text('GazelleSync 5.0.5 - DIC Variant', size=(30, 1), justification='center', font=("Helvetica", 25), relief=sg.RELIEF_RIDGE)],
    [sg.Text('(Note: You should edit config.cfg first, to include usernames and passwords of all relevant trackers)', font=("Helvetica", 8))],
    [sg.Text('(Note: This .py should be in the same directory as the other .py files)', font=( "Helvetica", 8))],
    [sg.Text('From: ', font=("Helvetica", 15)), sg.InputCombo(('OPS', 'RED', 'NWCD', 'DIC'), key='_from_', default_value='none'), sg.Text('To :', font=("Helvetica", 15)), sg.InputCombo(('OPS', 'RED', 'NWCD', 'DIC'), key='_to_', default_value='none')],
    [sg.Text('1) Fetch the torrent info from source tracker :', font=("Helvetica", 20))],
    [sg.Text('Method A - using Source Tracker permalink', font=("Helvetica", 15))],
    [sg.InputText(key='_permalink_')],
    [sg.Text('The Source Tracker Permalink can be either of these three forms:', font=("Helvetica", 8))],
    [sg.Text('https://source.tracker/torrents.php?torrentid=1', font=("Helvetica", 8))],
    [sg.Text('https://source.tracker/torrents.php?id=1&torrentid=1#torrent1', font=("Helvetica", 8))],
    [sg.Text('https://source.tracker/torrents.php?id=1&torrentid=1', font=("Helvetica", 8))],
    [sg.Text('Method B - using Source Tracker .torrent file', font=("Helvetica", 15))],
    [sg.Text('Choose a .torrent file', size=(15, 1), auto_size_text=False, justification='right'), sg.InputText(key='_torrentFile_'), sg.FileBrowse(file_types=(("ALL Files", ".torrent"),))],
    [sg.Text('Method C - using a folder of torrents', font=("Helvetica", 15))],
    [sg.Text('Choose a folder', size=(15, 1), auto_size_text=False, justification='right'), sg.InputText(key='_torrentFolder_'), sg.FolderBrowse()],
    [sg.Text('2) Select the Music Folder(s)', font=("Helvetica", 20))],
    [sg.InputCombo(('Single Mode', 'Bash Mode'), size=(20, 1), key='_singleOrBash_'), sg.InputText(key='_musicFolder_'), sg.FolderBrowse()],
    [sg.Text('Single Mode : Please browse to the directory that contains the actual music files', font=("Helvetica", 8))],
    [sg.Text('Bash Mode : Please browse to the directory ABOVE your music directory (or directories)!', font=("Helvetica", 8))],
    [sg.Text('_' * 80)],
    [sg.Submit(button_text='Go! Go! Go! (Let\'s rip)', key='_goGo_'), sg.Exit(button_text='Exit')]
]


window = sg.Window('Gazelle -> Gazelle (5.0)', layout, default_element_size=(40, 1), grab_anywhere=False, icon=resource_path("favicon.ico"))
event, values = window.Read()

while True:
    event, values = window.Read()
    callMovePy = ''
    if event == '_goGo_':
        callMovePy = move_cmd + ' --from=' + \
            values['_from_'].lower() + ' --to=' + values['_to_'].lower()
        if len(values['_permalink_']) > 0:
            callMovePy += ' --link="' + values['_permalink_'] + '"'
        elif len(values['_torrentFile_']) > 0:
            callMovePy += ' --tpath="' + values['_torrentFile_'] + '"'
        elif len(values['_torrentFolder_']) > 0:
            callMovePy += ' --tfolder="' + values['_torrentFolder_'] + '"'

        if values['_singleOrBash_'] == 'Single Mode':
            callMovePy += ' --album="' + values['_musicFolder_'] + '"'
        elif values['_singleOrBash_'] == 'Bash Mode':
            callMovePy += ' --folder="' + values['_musicFolder_'] + '"'
        os.system(callMovePy)
    elif event is None or event == 'Exit':
        break
window.Close()
