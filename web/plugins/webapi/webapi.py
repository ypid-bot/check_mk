#!/usr/bin/python
# -*- encoding: utf-8; py-indent-offset: 4 -*-
# +------------------------------------------------------------------+
# |             ____ _               _        __  __ _  __           |
# |            / ___| |__   ___  ___| | __   |  \/  | |/ /           |
# |           | |   | "_ \ / _ \/ __| |/ /   | |\/| | " /            |
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

###############

def action_add_host(request):
    if html.var("create_folders"):
        create_folders = bool(html.var("create_folders"))
    else:
        create_folders = True

    if not request:
        request = { "attributes": {
                         "tag_criticality": "prod",
                         "tag_agent": "cmk-agent",
                         "alias": "olalala",
                         "ipaddress": "127.0.0.1",
                         "site": "localsite"
                       },
                       "folder": "subfolder/ding/dong",
                       "hostname": "dingdong3"
                     }

    hostname   = request.get("hostname")
    folder     = request.get("folder")
    attributes = request.get("attributes")

    return g_api.add_host(hostname, folder, attributes, create_folders = create_folders)

api_actions["add_host"] = {
    "handler"     : action_add_host,
    "title"       : _("Add a host to WATO"),
    "description" : _("Add a host to WATO"),
    "locking"     : True,
}

###############

def action_edit_host(request):
    if not request:
        request = { "attributes": {
                     "tag_agent": "snmp-only",
                     "site": "slave"
                   },
                   "hostname": "dingdong3"
                }

    hostname   = request.get("hostname")
    attributes = request.get("attributes")

    return g_api.edit_host(hostname, attributes)

api_actions["edit_host"] = {
    "handler"     : action_edit_host,
    "title"       : _("Edit a host within WATO"),
    "description" : _("Edit a host within WATO"),
    "locking"     : True,
}

###############

def action_get_host(request):
    if html.var("effective_attributes"):
        effective_attributes = bool(html.var("effective_attributes"))
    else:
        effective_attributes = True

    if not request:
        request = {
                    "hostname": "dingdong3"
                }

    hostname = request.get("hostname")
    return g_api.get_host(hostname, effective_attributes)

api_actions["get_host"] = {
    "handler"     : action_get_host,
    "title"       : _("Get host data from WATO"),
    "description" : _("Get host data from WATO"),
    "locking"     : True,
}

###############

def action_delete_host(request):
    if not request:
        request = {
                    "hostname": "dingdong3"
                    }

    hostname = request.get("hostname")
    return g_api.delete_host(hostname)

api_actions["delete_host"] = {
    "handler"     : action_delete_host,
    "title"       : _("Delete host in WATO"),
    "description" : _("Delete host in WATO"),
    "locking"     : True,
}

###############

def action_discover_services(request):
    mode = html.var("var") and html.var("mode") or "new"

    if not request:
        request = {
                    "hostname": "dingdong3"
                    }

    hostname = request.get("hostname")
    return g_api.discover_services(hostname, mode)

api_actions["discover_services"] = {
    "handler"     : action_discover_services,
    "title"       : _("Host service discovery"),
    "description" : _("Host service discovery"),
    "locking"     : True,
}

###############

def action_activate_changes(request):
    mode = html.var("mode") and html.var("mode") or "dirty"

    if not request:
        request = {
                "sites": ["slave", "localsite"]
                }

    sites = request.get("sites")
    return g_api.activate_changes(sites, mode)

api_actions["activate_changes"] = {
    "handler"     : action_activate_changes,
    "title"       : _("Activate changes"),
    "description" : _("Activate changes"),
    "locking"     : True,
}

