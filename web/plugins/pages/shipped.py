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

# Import modules that contain the page functions

import config
import main
import logwatch
import views
import prediction
import sidebar
import actions
import weblib
import dashboard
import login
import help
import bi
import userdb
import notify
import webapi
import visuals
import crashed_check
import metrics

# map URLs to page rendering functions

pagehandlers.update({
   "add_bookmark"                : sidebar.ajax_add_bookmark,
   "ajax_add_visual"             : visuals.ajax_add_visual,
   "ajax_dashlet_pos"            : dashboard.ajax_dashlet_pos,
   "ajax_inv_render_tree"        : views.ajax_inv_render_tree,
   "ajax_inv_render_tree"        : views.ajax_inv_render_tree,
   "ajax_popup_action_menu"      : views.ajax_popup_action_menu,
   "ajax_popup_add_visual"       : visuals.ajax_popup_add,
   "ajax_popup_icon_selector"    : views.ajax_popup_icon_selector,
   "ajax_search"                 : sidebar.ajax_search,
   "ajax_set_rowselection"       : weblib.ajax_set_rowselection,
   "ajax_set_viewoption"         : views.ajax_set_viewoption,
   "ajax_switch_help"            : help.ajax_switch_help,
   "ajax_userdb_sync"            : userdb.ajax_sync,
   "count_context_button"        : views.ajax_count_button,
   "crashed_check"               : crashed_check.page_crashed_check,
   "create_dashboard"            : dashboard.page_create_dashboard,
   "create_view"                 : views.page_create_view,
   "create_view_dashlet"         : dashboard.page_create_view_dashlet,
   "create_view_dashlet_infos"   : dashboard.page_create_view_dashlet_infos,
   "create_view_infos"           : views.page_create_view_infos,
   "dashboard"                   : dashboard.page_dashboard,
   "dashboard_dashlet"           : dashboard.ajax_dashlet,
   "del_bookmark"                : sidebar.ajax_del_bookmark,
   "delete_dashlet"              : dashboard.page_delete_dashlet,
   "edit_bookmark"               : sidebar.page_edit_bookmark,
   "edit_dashboard"              : dashboard.page_edit_dashboard,
   "edit_dashboards"             : dashboard.page_edit_dashboards,
   "edit_dashlet"                : dashboard.page_edit_dashlet,
   "edit_view"                   : views.page_edit_view,
   "edit_views"                  : views.page_edit_views,
   "export_views"                : views.ajax_export,
   "index"                       : main.page_index,
   "login"                       : login.page_login,
   "logout"                      : login.page_logout,
   "logwatch"                    : logwatch.page_show,
   "nagios_action"               : actions.ajax_action,
   "notify"                      : notify.page_notify,
   "prediction_graph"            : prediction.page_graph,
   "search_open"                 : sidebar.search_open,
   "show_graph"                  : metrics.page_show_graph,
   "side"                        : sidebar.page_side,
   "sidebar_add_snapin"          : sidebar.page_add_snapin,
   "sidebar_ajax_speedometer"    : sidebar.ajax_speedometer,
   "sidebar_ajax_tag_tree"       : sidebar.ajax_tag_tree,
   "sidebar_ajax_tag_tree_enter" : sidebar.ajax_tag_tree_enter,
   "sidebar_fold"                : sidebar.ajax_fold,
   "sidebar_get_messages"        : sidebar.ajax_get_messages,
   "sidebar_message_read"        : sidebar.ajax_message_read,
   "sidebar_move_snapin"         : sidebar.move_snapin,
   "sidebar_openclose"           : sidebar.ajax_openclose,
   "sidebar_snapin"              : sidebar.ajax_snapin,
   "switch_master_state"         : sidebar.ajax_switch_masterstate,
   "switch_site"                 : main.ajax_switch_site,
   "tree_openclose"              : weblib.ajax_tree_openclose,
   "view"                        : views.page_view,
   "webapi"                      : webapi.page_api,

   # Experimental:
   "view_new"                    : views.page_view_new,
})

