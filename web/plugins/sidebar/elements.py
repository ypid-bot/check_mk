#!/usr/bin/python
# -*- encoding: utf-8; py-indent-offset: 4 -*-
# +------------------------------------------------------------------+
# |             ____ _               _        __  __ _  __           |
# |            / ___| |__   ___  ___| | __   |  \/  | |/ /           |
# |           | |   | '_ \ / _ \/ __| |/ /   | |\/| | ' /            |
# |           | |___| | | |  __/ (__|   <    | |  | | . \            |
# |            \____|_| |_|\___|\___|_|\_\___|_|  |_|_|\_\           |
# |                                                                  |
# | Copyright Mathias Kettner 2014             mk@mathias-kettner.de |
# +------------------------------------------------------------------+
#
# This file is part of Check_MK.
# The official homepage is at http://mathias-kettner.de/check_mk.
#
# check_mk is free software;  you can redistribute it and/or modify it
# under the  terms of the  GNU General Public License  as published by
# the Free Software Foundation in version 2.  check_mk is  distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;  with-
# out even the implied warranty of  MERCHANTABILITY  or  FITNESS FOR A
# PARTICULAR PURPOSE. See the  GNU General Public License for more de-
# ails.  You should have  received  a copy of the  GNU  General Public
# License along with GNU Make; see the file  COPYING.  If  not,  write
# to the Free Software Foundation, Inc., 51 Franklin St,  Fifth Floor,
# Boston, MA 02110-1301 USA.


#   .--Pages---------------------------------------------------------------.
#   |                     ____                                             |
#   |                    |  _ \ __ _  __ _  ___  ___                       |
#   |                    | |_) / _` |/ _` |/ _ \/ __|                      |
#   |                    |  __/ (_| | (_| |  __/\__ \                      |
#   |                    |_|   \__,_|\__, |\___||___/                      |
#   |                                |___/                                 |
#   +----------------------------------------------------------------------+
#   | Access to all global pages (table views, dashboards, graph collec-   |
#   | tions, etc.                                                          |
#   '----------------------------------------------------------------------'

def render_pages():
    for topic, links in elements.PageRenderer.global_page_links_by_topic():
        html.begin_foldable_container("pages", topic, False, topic, indent=True)
        for title, url in links:
            bulletlink(title, url, onclick = "return wato_views_clicked(this)")
        html.end_foldable_container()

sidebar_snapins["pages"] = {
    "title"       : _("Pages"),
    "description" : _("Links to global pages like views, dashboards, graph collection, etc."),
    "render"      : render_pages,
    "allowed"     : [ "user", "admin", "guest" ],
}
