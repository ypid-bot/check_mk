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

infos['host'] = {
    'title'       : _('Host'),
    'title_plural': _('Hosts'),
    'single_spec' : [
        ('host', TextUnicode(
            title = _('Hostname'),
        )),
    ],
}

# single_spec is being dropped in the new implementation
# Instead there is the rule, that for each info there must
# be one selector that has the name of that info. Therefore
# nothing more needs to be specified here.
# TODO: Was hier noch fehlt, ist der Weg von einer row zu
# dem gültigen Selektorkontext. Bauen wir das in den Selektor
# ein oder lieber in das Info? Würde sagen, in das Info.

register_info(
    Info(
        name             = "host",
        title            = _("Host"),
        title_plural     = _("Hosts"),
        # TODO: umbenennen, weil es ja kein Context() liefert, sondern
        # nur ein partielles dict.
        context_from_row = lambda row: { "host" : row["host_name"] },
        key_columns      = [ "host_name" ],
))

register_info(
    Info(
        name             = "service",
        title            = _("Service"),
        title_plural     = _("Services"),
        context_from_row = lambda row: { "service" : row["service_description"] },
        key_columns      = [ "service_description" ],
))

register_info(
    Info(
        name             = "log",
        title            = _("Monitoring Log Entry"),
        title_plural     = _("Monitoring Log Entries"),
))

infos['log'] = {
    'title'       : _('Log Entry'),
    'title_plural': _('Log Entries'),
    # TODO: Es könnte doch einen geben: nämlich die Kombi aus Zeitstempel und
    # Dateizeile. Dafür können wir einen hübschen Filter bauen, den man sowieso
    # nicht händisch braucht, aber nur so kann man einen single-Kontext herstellen!
    'single_spec' : None,
}


infos['service'] = {
    'title'       : _('Service'),
    'title_plural': _('Services'),
    'single_spec' : [
        ('service', TextUnicode(
            title = _('Service Description'),
        )),
    ],
}

infos['hostgroup'] = {
    'title'       : _('Host Group'),
    'title_plural': _('Host Groups'),
    'single_site' : False, # spread over multiple sites
    'single_spec' : [
        ('hostgroup', TextUnicode(
            title = _('Host Group Name'),
        )),
    ],
}

infos['servicegroup'] = {
    'title'       : _('Service Group'),
    'title_plural': _('Service Groups'),
    'single_site' : False, # spread over multiple sites
    'single_spec' : [
        ('servicegroup', TextUnicode(
            title = _('Service Group Name'),
        )),
    ],
}

infos['log'] = {
    'title'       : _('Log Entry'),
    'title_plural': _('Log Entries'),
    # TODO: Es könnte doch einen geben: nämlich die Kombi aus Zeitstempel und
    # Dateizeile. Dafür können wir einen hübschen Filter bauen, den man sowieso
    # nicht händisch braucht, aber nur so kann man einen single-Kontext herstellen!
    'single_spec' : None,
}

infos['comment'] = {
    'title'       : _('Comment'),
    'title_plural': _('Comments'),
    'single_spec' : [
        ('comment_id', Integer(
            title = _('Comment ID'),
        )),
    ]
}

infos['downtime'] = {
    'title'       : _('Downtime'),
    'title_plural': _('Downtimes'),
    'single_spec' : [
        ('downtime_id', Integer(
            title = _('Downtime ID'),
        )),
    ]
}

infos['contact'] = {
    'title'       : _('Contact'),
    'title_plural': _('Contacts'),
    'single_spec' : [
        ('log_contact_name', TextUnicode(
            title = _('Contact Name'),
        )),
    ]
}

infos['command'] = {
    'title'       : _('Command'),
    'title_plural': _('Commands'),
    'single_spec' : [
        ('command_name', TextUnicode(
            title = _('Command Name'),
        )),
    ]
}

infos['aggr'] = {
    'title'       : _('BI Aggregation'),
    'title_plural': _('BI Aggregations'),
    'single_spec' : [
        ('aggr_name', TextAscii(
            title = _('Aggregation Name'),
        )),
    ],
}

