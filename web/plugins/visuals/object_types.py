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


ObjectType(
    name                 = "host",
    title                = _("Host"),
    title_plural         = _("Hosts"),
    description          = _("A monitored host"),
    get_selector_context = lambda row: { "host" : row["host_name"] },
    key_columns          = [ "host_name" ],
).register()


ObjectType(
    name                 = "service",
    title                = _("Service"),
    title_plural         = _("Services"),
    description          = _("A monitored service"),
    get_selector_context = lambda row: { "service" : row["service_description"] },
    key_columns          = [ "service_description" ],
).register()


ObjectType(
    name                 = "log",
    title                = _("Monitoring Log Entry"),
    title_plural         = _("Monitoring Log Entries"),
    description          = _("An entry in the history of monitoring events"),
).register()
