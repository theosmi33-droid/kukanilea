import os

application = "KUKANILEA"
app_path = os.path.join("dist", f"{application}.app")

volume_name = application
format = "UDZO"
size = "300M"
files = [app_path]
icon_locations = {
    f"{application}.app": (140, 120),
}
background = None
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False
sidebar_width = 180
window_rect = ((100, 100), (480, 320))
