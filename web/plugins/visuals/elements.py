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

# NOTE: This file will eventually move into plugins/elements/selectors.py
# This will be when visuals.py has finally died.

from elements import Selector, register_selector

# Filters for substring search, displaying a text input field
class TextSelector(Selector):
    def __init__(self, **kwargs):
        Selector.__init__(self, **kwargs)

    def is_active(self):
        return bool(html.var(self.variables()[0]))


class LivestatusTextSelector(TextSelector):
    def __init__(self, **kwargs):
        TextSelector.__init__(self, **kwargs)

    def livestatus_headers(self, selector_context):
        return "Filter: %s %s %s\n" % (
            self._["column"], self._["expression"], selector_context[self.variables()[0]])


register_selector(
    LivestatusTextSelector(
        name       = "host",
        title      = _("Host"),
        info       = "host",
        variables  = [ "host" ],
        expression = "=",
        column     = "host_name",
))

register_selector(
    LivestatusTextSelector(
        name       = "host_regex",
        title      = _("Hostname (regular expression)"),
        info       = "host",
        variables  = [ "host_regex" ],
        expression = "~~",
        column     = "host_name",
))

register_selector(
    LivestatusTextSelector(
        name       = "service",
        title      = _("Service"),
        info       = "service",
        variables  = [ "service" ],
        expression = "=",
        column     = "service_description",
))

register_selector(
    LivestatusTextSelector(
        name       = "service_regex",
        title      = _("Service (regular expression)"),
        info       = "service",
        variables  = [ "service_regex" ],
        expression = "~~",
        column     = "service_description",
))

class GOOBAR_FilterText(Filter):
    def __init__(self, name, title, info, column, htmlvar, op, negateable=False):
        htmlvars = [htmlvar]
        if negateable:
            htmlvars.append("neg_" + htmlvar)
        Filter.__init__(self, name, title, info, htmlvars, [column])
        self.op = op
        self.column = column
        self.negateable = negateable

    def _current_value(self):
        htmlvar = self.htmlvars[0]
        return html.var(htmlvar, "")

    def display(self):
        current_value = self._current_value()
        html.text_input(self.htmlvars[0], current_value, self.negateable and 'neg' or '')
        if self.negateable:
            html.write(" <nobr>")
            html.checkbox(self.htmlvars[1], label=_("negate"))
            html.write("</nobr>")

    def filter(self, infoname):
        current_value = self._current_value()

        if self.negateable and html.get_checkbox(self.htmlvars[1]):
            negate = "!"
        else:
            negate = ""

        if current_value:
            return "Filter: %s %s%s %s\n" % (self.column, negate, self.op, lqencode(current_value))
        else:
            return ""

    def variable_settings(self, row):
        return [ (self.htmlvars[0], row[self.column]) ]

    def heading_info(self):
        return self._current_value()


