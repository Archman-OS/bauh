# Generates a .desktop file based on the current python version. Used for AUR installation
import os
import sys


desktop_file = """
[Desktop Entry]
Type = Application
Name = bauh ( tray )
Name[pt] = bauh ( bandeja )
Name[es] = bauh ( bandeja )
Categories = System;
Comment=Manage your Flatpak / Snap / AppImage / AUR applications
Comment[pt]=Gerencie seus aplicativos Flatpak / Snap / AppImage / AUR
Comment[es]=Administre sus aplicaciones Flatpak / Snap / AppImage / AUR
Exec = {path}
Icon = {lib_path}/python{version}/site-packages/bauh/view/resources/img/logo.svg
"""

py_version = "{}.{}".format(sys.version_info.major, sys.version_info.minor)

app_cmd = os.getenv('BAUH_PATH', '/usr/bin/bauh') + ' --tray=1'

with open('bauh_tray.desktop', 'w+') as f:
    f.write(desktop_file.format(lib_path=os.getenv('BAUH_LIB_PATH', '/usr/lib'),
                                version=py_version,
                                path=app_cmd))


with open('bauh-tray', 'w') as f:
    f.write(app_cmd)
