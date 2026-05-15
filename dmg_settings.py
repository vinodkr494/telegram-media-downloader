import os

# DMG Volume Name
volume_name = 'TG Media Downloader'

# DMG Format
format = 'UDZO'

# File path to the .app bundle (this will be relative to where dmgbuild is run)
app_name = os.environ.get('APP_NAME', 'TGDownloader.app')
app_path = os.path.join('src', 'dist', app_name)

# Contents of the DMG
files = [app_path]

# Symlinks in the DMG
symlinks = { 'Applications': '/Applications' }

# Icon positions
icon_locations = {
    app_name: (140, 120),
    'Applications': (380, 120)
}

# Window configuration
window_rect = ((100, 100), (520, 320))
default_view = 'icon-view'
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_sidebar = False
sidebar_width = 180

# Icon size
icon_size = 128

# Text size
text_size = 12
