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

#   .--imports-------------------------------------------------------------.
#   |                _                            _                        |
#   |               (_)_ __ ___  _ __   ___  _ __| |_ ___                  |
#   |               | | '_ ` _ \| '_ \ / _ \| '__| __/ __|                 |
#   |               | | | | | | | |_) | (_) | |  | |_\__ \                 |
#   |               |_|_| |_| |_| .__/ \___/|_|   \__|___/                 |
#   |                           |_|                                        |
#   '----------------------------------------------------------------------'

import os, pprint, inspect
import config, table, forms
from lib import *
from valuespec import *

try:
    import simplejson as json
except ImportError:
    import json

#.
#   .--globals-------------------------------------------------------------.
#   |                         _       _           _                        |
#   |                    __ _| | ___ | |__   __ _| |___                    |
#   |                   / _` | |/ _ \| '_ \ / _` | / __|                   |
#   |                  | (_| | | (_) | |_) | (_| | \__ \                   |
#   |                   \__, |_|\___/|_.__/ \__,_|_|___/                   |
#   |                   |___/                                              |
#   +----------------------------------------------------------------------+
#   |  Global methods for the integration of Elements into Multisite       |
#   '----------------------------------------------------------------------'

# Global dict of all page types, e.g. subclasses of Element
element_types = {}

def register_element_type(element_type):
    element_types[element_type.type_name()] = element_type
    element_type.declare_permissions()

def element_type(element_type_name):
    return element_types[element_type_name]

def has_element_type(element_type_name):
    return element_type_name in element_types

def get_element_by_type_and_name(element_type_name, element_name):
    et = element_type(element_type_name)
    return et.get_element_by_name(element_name)

def all_element_types_implementing(some_class):
    for element_type in element_types.values():
        if issubclass(element_type, some_class):
            yield element_type


# Global module functions for the integration into the rest of the code

# index.py uses the following function in order to complete its
# page handler table
def page_handlers():
    page_handlers = {}
    for element_type in element_types.values():
        if (issubclass(element_type, PageRenderer)):
            page_handlers.update(element_type.page_handlers())

    # Ajax handler for adding elements to a container
    # TODO: Shouldn't we move that declaration into the class? Yes!
    page_handlers["ajax_add_element_to_container"] = lambda: Container.ajax_add_element_to_container()
    return page_handlers


def render_addto_popup():
    for element_type in element_types.values():
        # TODO: Wie sorgen wir dafür, dass nur geeignete Elemente zum hinzufügen
        # angeboten werden? Eine View in eine GraphCollection macht keinen Sinn...
        if issubclass(element_type, Container):
            element_type.render_addto_popup()


#.
#   .--Element-------------------------------------------------------------.
#   |                _____ _                           _                   |
#   |               | ____| | ___ _ __ ___   ___ _ __ | |_                 |
#   |               |  _| | |/ _ \ '_ ` _ \ / _ \ '_ \| __|                |
#   |               | |___| |  __/ | | | | |  __/ | | | |_                 |
#   |               |_____|_|\___|_| |_| |_|\___|_| |_|\__|                |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   |  Base class of all things that are UserOverridable, ElementContainer |
#   |  or PageRenderer.                                                    |
#   '----------------------------------------------------------------------'

class Element(object):
    def __init__(self, d):
        object.__init__(self)
        # The dictionary with the name _ holds all information about
        # the page in question - as a dictionary that can be loaded
        # and saved to files using repr().
        self._ = d

        # Now give all subclasses that chance to add mandatory keys in that
        # dictionary in case they are missing.
        # TODO: Check, if this can be done with super() instead of inspect.
        for clazz in inspect.getmro(self.__class__)[::-1]:
            if "sanitize" in clazz.__dict__:
                clazz.sanitize(d)

    @mandatory
    @classmethod
    def type_name(self):
        pass

    @classmethod
    def type_icon(self):
        return self.type_name()

    def internal_representation(self):
        return self._

    # TODO: remove this hack
    def __repr__(self):
        return repr(self._)

    # TODO: remove this hack
    def __getitem__(self, key):
        return self._[key]

    # TODO: remove this hack
    def __contains__(self, key):
        return key in self._

    # TODO: remove this hack
    # def pformat(self):
    #     return self.type_name() + ": " + pprint.pformat(self._)

    # You always must override the following method. Not all phrases
    # might be neccessary depending on the type of you page.
    # Possible phrases:
    # "title"        : Title of one instance
    # "title_plural" : Title in plural
    # "add_to"       : Text like "Add to foo bar..."
    # TODO: Look at GraphCollection for the complete list of phrases to
    # be defined for each page type and explain that here.
    @classmethod
    def phrase(self, phrase):
        return "%s: %s" % (phrase, self.type_name())

    # You can override this if you class needs any permissions to
    # be declared. Note: currently only *one* of the classes in the
    # inheritance tree can override this method. If we need to change
    # this we can do this like in __init__ with sanitize...
    @classmethod
    def declare_permissions(self):
        pass

    # Implement this function in a subclass in order to add parameters
    # to be editable by the user when editing the details of such page
    # type. Note: This method does *not* use overriding, but all methods
    # of this name will be called in all inherited classes and concatenated.
    # Note:
    # - self is the original class, e.g. PageRenderer
    # - clazz is the derived class, e.g. GraphCollection
    # Returns a list of entries.
    # Each entry is a pair of a topic and a list of elements.
    # Each element is a triple of order, key and valuespec
    # TODO: Add topic here
    @classmethod
    def parameters(self, clazz):
        return [ ( _("General Properties"), [
            ( 1.1, 'name', ID(
                title = _('Unique ID'),
                help = _("The ID will be used do identify this page in URLs. If this page has the "
                         "same ID as a builtin page of the type <i>%s</i> then it will shadow the builtin one.") % self.phrase("title"),
            )),
            ( 1.2, 'title', TextUnicode(
                title = _('Title') + '<sup>*</sup>',
                size = 50,
                allow_empty = False,
            )),
            ( 1.3, 'description', TextAreaUnicode(
                title = _('Description') + '<sup>*</sup>',
                help = _("The description is optional and can be used for explainations or documentation"),
                rows = 4,
                cols = 50,
            )),
        ])]

    # Do *not* override this. It collects all editable parameters of our
    # page type by calling parameters() for each class
    @classmethod
    def collect_parameters(self):
        topics = {}
        for clazz in inspect.getmro(self)[::-1]:
            if "parameters" in clazz.__dict__:
                for topic, elements in clazz.parameters(self):
                    el = topics.setdefault(topic, [])
                    el += elements

        # Sort topics and elements in the topics
        for topic in topics.values():
            topic.sort()

        sorted_topics = topics.items()
        sorted_topics.sort(cmp = lambda t1, t2: cmp(t1[1][0], t2[1][0]))

        # Now remove order numbers. Also drop the topic completely
        # for the while
        # TODO: Reenable topic as soon as we have the first page type
        # with more than one topic
        parameters = []
        for topic, elements in sorted_topics:
            for order, key, vs in elements:
                parameters.append((key, vs))

        return parameters


    # Object methods that *can* be overridden - for cases where
    # that pages in question of a dictionary format that is not
    # compatible.
    def name(self):
        return self._["name"]

    def topic(self):
        if "topic" in self._:
            return self._["topic"]
        else:
            return self.default_topic()

    def title(self):
        return self._["title"]

    def description(self):
        return self._.get("description", "")

    @classmethod
    def default_topic(self):
        return _("Other")

    # Store for all instances of this element type. The key into
    # this dictionary????
    # TODO: Brauchen wir hier überhaupt ein dict??
    __instances = {}

    # Beware: __instances is *not* created in each subclass, but
    # exists just once for all element types. For that reason we
    # need a two-tier-dict.
    @classmethod
    def instances_dict(self):
        return self.__instances.setdefault(self.type_name, {})

    @classmethod
    def instances(self):
        return self.instances_dict().values()

    @classmethod
    def clear_instances(self):
        self.instances_dict().clear()

    @classmethod
    def add_instance(self, key, instance):
        self.instances_dict()[key] = instance

    @classmethod
    def remove_instance(self, key):
        del self.instances_dict()[key]

    @classmethod
    def has_instance(self, key):
        return key in self.instances_dict()

    @classmethod
    def instance(self, key):
        return self.instances_dict()[key]

    # Return a list of pairs if instance key and instance, which
    # is sorted by the title of the instance
    @classmethod
    def instances_sorted(self):
        instances = self.instances_dict().values()
        instances.sort(cmp = lambda a,b: cmp(a.title(), b.title()))
        return instances

#.
#   .--Overridable---------------------------------------------------------.
#   |         ___                      _     _       _     _               |
#   |        / _ \__   _____ _ __ _ __(_) __| | __ _| |__ | | ___          |
#   |       | | | \ \ / / _ \ '__| '__| |/ _` |/ _` | '_ \| |/ _ \         |
#   |       | |_| |\ V /  __/ |  | |  | | (_| | (_| | |_) | |  __/         |
#   |        \___/  \_/ \___|_|  |_|  |_|\__,_|\__,_|_.__/|_|\___|         |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   |  Base class for things that the user can override by cloning and     |
#   |  editing and where the user might also create complete new types.    |
#   |  Examples: views, dashboards, graphs collections                     |
#   '----------------------------------------------------------------------'

class Overridable:
    @classmethod
    def parameters(self, clazz):
        if clazz.has_overriding_permission("publish"):
            return [( _("General Properties"), [
                ( 2.2, 'public', Checkbox(
                    title = _("Visibility"),
                    label = _('Make available for all users')
                )),
            ])]
        else:
            return []

    def page_header(self):
        header = self.phrase("title") + " - " + self.title()
        if not self.is_mine():
            header += " (%s)" % self.owner()
        return header

    # Checks wether a page is publicly visible. This does not only need a flag
    # in the page itself, but also the permission from its owner to publish it.
    def is_public(self):
        return self._["public"] and (
            not self.owner() or config.user_may(self.owner(), "general.publish_" + self.type_name()))

    # Same, but checks if the owner has the permission to override builtin views
    def is_public_forced(self):
        return self.is_public() and \
          config.user_may(self.owner(), "general.force_" + self.type_name())

    def is_hidden(self):
        return self._.get("hidden", False)

    # Derived method for conveniance
    def is_builtin(self):
        return not self.owner()

    def is_mine(self):
        return self.owner() == config.user_id

    def owner(self):
        return self._["owner"]

    # Checks if the current user is allowed to see a certain page
    # TODO: Wie is die Semantik hier genau? Umsetzung vervollständigen!
    def may_see(self):
        perm_name = "%s.%s" % (self.type_name(), self.name())
        if config.permission_exists(perm_name) and not config.may(perm_name):
            return False

        # if self.owner() == "" and not config.may(perm_name):
        #    return False

        return True
        #    continue # not allowed to see this view

        # TODO: Permissions
        ### visual = visuals[(owner, visual_name)]
        ### if owner == config.user_id or \
        ###    (visual["public"] and owner != '' and config.user_may(owner, "general.publish_" + what)):
        ###     custom.append((owner, visual_name, visual))
        ### elif visual["public"] and owner == "":
        ###     builtin.append((owner, visual_name, visual))

    def may_delete(self):
        if self.is_builtin():
            return False
        elif self.is_mine():
            return True
        else:
            return config.may('general.delete_foreign_%s' % self.type_name())

    def edit_url(self):
        return "edit_%s.py?load_name=%s" % (self.type_name(), self.name())

    def clone_url(self):
        backurl = html.urlencode(html.makeuri([]))
        return "edit_%s.py?load_user=%s&load_name=%s&mode=clone&back=%s" \
                    % (self.type_name(), self.owner(), self.name(), backurl)

    def delete_url(self):
        add_vars = [('_delete', self.name())]
        if not self.is_mine():
            add_vars.append(('_owner', self.owner()))
        return html.makeactionuri(add_vars)

    # Default value for the creation dialog can be overridden by the
    # sub class.
    @classmethod
    def default_name(self):
        stem = self.type_name()
        nr = 1
        while True:
            name = "%s_%d" % (stem, nr)
            conflict = False
            for instance in self.instances():
                if instance.name() == name:
                    conflict = True
                    break
            if not conflict:
                return name
            else:
                nr += 1

    @classmethod
    def create_url(self):
        return "edit_%s.py?mode=create" % self.type_name()

    @classmethod
    def list_url(self):
        return "%ss.py" % self.type_name()

    @classmethod
    def render_list_button(self):
        html.context_button(self.phrase("title_plural"), self.list_url(), self.type_icon())

    def render_edit_button(self):
        # TODO: Who checks the permissions??
        html.context_button(_("Edit"), self.edit_url(), "edit")

    def render_edit_buttons(self):
        # TODO: Who checks the permissions??
        self.render_list_button()
        self.render_edit_button()

    def render_header_buttons(self):
        if self.is_mine():
            self.header_button(self.phrase("edit"), self.edit_url(), "edit")
        else:
            self.header_button(self.phrase("clone"), self.clone_url(), "clone")


    @classmethod
    def declare_permissions(self):
        config.declare_permission("general.edit_" + self.type_name(),
             _("Customize %s and use them") % self.phrase("title_plural"),
             _("Allows to create own %s, customize builtin %s and use them.") % (self.phrase("title_plural"), self.phrase("title_plural")),
             [ "admin", "user" ])

        config.declare_permission("general.publish_" + self.type_name(),
             _("Publish %s") % self.phrase("title_plural"),
             _("Make %s visible and usable for other users.") % self.phrase("title_plural"),
             [ "admin", "user" ])

        config.declare_permission("general.see_user_" + self.type_name(),
             _("See user %s") % self.phrase("title_plural"),
             _("Is needed for seeing %s that other users have created.") % self.phrase("title_plural"),
             [ "admin", "user", "guest" ])

        config.declare_permission("general.force_" + self.type_name(),
             _("Modify builtin %s") % self.phrase("title_plural"),
             _("Make own published %s override builtin %s for all users.") % (self.phrase("title_plural"), self.phrase("title_plural")),
             [ "admin" ])

        config.declare_permission("general.delete_foreign_" + self.type_name(),
             _("Delete foreign %s") % self.phrase("title_plural"),
             _("Allows to delete %s created by other users.") % self.phrase("title_plural"),
             [ "admin" ])


    @classmethod
    def has_overriding_permission(self, how):
        return config.may("general.%s_%s" % (how, self.type_name()))

    @classmethod
    def need_overriding_permission(self, how):
        if not self.has_overriding_permission(how):
            raise MKAuthException(_("Sorry, you lack the permission. Operation: %s, table: %s") % (
                                    how, self.phrase("title_plural")))

    # Return all pages visible to the user, implements shadowing etc.
    @classmethod
    def pages(self):
        self.load()
        pages = {}

        # Builtin pages
        for page in self.instances():
            if page.is_public() and page.may_see() and page.is_builtin():
                pages[page.name()] = page

        # Public pages by normal other users
        for page in self.instances():
            if page.is_public() and page.may_see():
                pages[page.name()] = page

        # Public pages by admin users, forcing their versions over others
        for page in self.instances():
            if page.is_public() and page.may_see() and page.is_public_forced():
                pages[page.name()] = page

        # My own pages
        for page in self.instances():
            if page.is_mine() and config.may("general.edit_" + self.type_name()):
                pages[page.name()] = page

        return sorted(pages.values(), cmp = lambda a, b: cmp(a.title(), b.title()))


    # Find a page by name, implements shadowing and
    # publishing und overriding by admins
    @classmethod
    def get_element_by_name(self, name):
        self.load()

        mine = None
        forced = None
        builtin = None
        foreign = None

        for page in self.instances():
            if page.name() != name:
                continue

            if page.is_mine() and config.may("general.edit_" + self.type_name()):
                mine = page

            elif page.is_public() and page.may_see():
                if page.is_public_forced():
                    forced = page
                elif page.is_builtin():
                    builtin = page
                else:
                    foreign = page

        if mine:
            return mine
        elif forced:
            return forced
        elif builtin:
            return builtin
        elif foreign:
            return foreign
        else:
            return None

    @classmethod
    def find_my_page(self, name):
        for page in self.instances():
            if page.is_mine() and page.name() == name:
                return page


    # Lädt alle Dinge vom aktuellen User-Homeverzeichnis und
    # mergt diese mit den übergebenen eingebauten
    @classmethod
    def load(self):
        self.clear_instances()

        # First load builtin pages. Set username to ''
        for name, page_dict in self.builtin_pages().items():
            page_dict["owner"]  = '' # might have been forgotten on copy action
            page_dict["public"] = True
            page_dict["name"]   = name
            new_page = self(page_dict)
            self.add_instance(("", name), new_page)

        # Now scan users subdirs for files "user_$type_name.mk"
        subdirs = os.listdir(config.config_dir)
        for user in subdirs:
            try:
                path = "%s/%s/user_%ss.mk" % (config.config_dir, user, self.type_name())
                if not os.path.exists(path):
                    continue

                user_pages = eval(file(path).read())
                for name, page_dict in user_pages.items():
                    page_dict["owner"] = user
                    page_dict["name"] = name
                    self.add_instance((user, name), self(page_dict))

            except SyntaxError, e:
                raise MKGeneralException(_("Cannot load %s from %s: %s") % (what, path, e))

        # Declare permissions - one for each of the pages, if it is public
        config.declare_permission_section(self.type_name(), self.phrase("title_plural"), do_sort = True)

        for instance in self.instances():
            if instance.is_public():
                self.declare_permission(instance)

    @classmethod
    def save_user_instances(self, owner=None):
        if not owner:
            owner = config.user_id

        save_dict = {}
        for page in self.instances():
            if page.owner() == owner:
                save_dict[page.name()] = page.internal_representation()

        config.save_user_file('user_%ss' % self.type_name(), save_dict, user=owner)

    @classmethod
    def add_page(self, new_page):
        self.add_instance((new_page.owner(), new_page.name()), new_page)

    def clone(self):
        page_dict = {}
        page_dict.update(self._)
        page_dict["owner"] = config.user_id
        new_page = self.__class__(page_dict)
        self.add_page(new_page)
        return new_page

    @classmethod
    def declare_permission(self, page):
        permname = "%s.%s" % (self.type_name(), page.name())
        if page.is_public() and not config.permission_exists(permname):
            config.declare_permission(permname, page.title(),
                             page.description(), ['admin','user','guest'])


    @classmethod
    def page_list(self):
        self.load()

        # custom_columns = []
        # render_custom_buttons = None
        # render_custom_columns = None
        # render_custom_context_buttons = None
        # check_deletable_handler = None

        self.need_overriding_permission("edit")

        html.header(self.phrase("title_plural"), stylesheets=["pages", "views", "status"])
        html.begin_context_buttons()
        html.context_button(_('New'), self.create_url(), "new_" + self.type_name())

        # TODO: Remove this legacy code as soon as views, dashboards and reports have been
        # moved to pagetypes.py
        html.context_button(_("Views"), "edit_views.py", "view")
        html.context_button(_("Dashboards"), "edit_dashboards.py", "dashboard")
        html.context_button(_("Reports"), "edit_reports.py", "report")

        ### if render_custom_context_buttons:
        ###     render_custom_context_buttons()
        ### for other_what, info in visual_types.items():
        ###     if what != other_what:
        ###         html.context_button(info["plural_title"].title(), 'edit_%s.py' % other_what, other_what[:-1])
        ### html.end_context_buttons()
        html.end_context_buttons()

        # Deletion
        delname  = html.var("_delete")
        if delname and html.transaction_valid():
            owner = html.var('_owner', config.user_id)
            if owner != config.user_id:
                self.need_overriding_permission("delete_foreign")

            instance = self.instance((owner, delname))

            try:
                if owner != config.user_id:
                    owned_by = _(" (owned by %s)") % owner
                else:
                    owned_by = ""
                c = html.confirm(_("Please confirm the deletion of \"%s\"%s.") % (
                  instance.title(), owned_by))
                if c:
                    self.remove_instance((owner, delname))
                    self.save_user_instances(owner)
                    html.reload_sidebar()
                elif c == False:
                    html.footer()
                    return
            except MKUserError, e:
                html.write("<div class=error>%s</div>\n" % e.message)
                html.add_user_error(e.varname, e.message)


        my_instances  = []
        foreign_instances  = []
        builtin_instances = []
        for instance in self.instances_sorted():
            if instance.may_see():
                if instance.is_builtin():
                    builtin_instances.append(instance)
                elif instance.is_mine():
                    my_instances.append(instance)
                else:
                    foreign_instances.append(instance)

        for title, instances in [
            (_('Customized'),           my_instances),
            (_('Owned by other users'), foreign_instances),
            (_('Builtin'),              builtin_instances),
        ]:
            if not instances:
                continue

            html.write('<h3>' + title + '</h3>')

            table.begin(limit = None)
            for instance in instances:
                table.row()

                # Actions
                table.cell(_('Actions'), css = 'buttons visuals')

                # Clone / Customize
                buttontext = _("Create a customized copy of this")
                html.icon_button(instance.clone_url(), buttontext, "new_" + self.type_name())

                # Delete
                if instance.may_delete():
                    html.icon_button(instance.delete_url(), _("Delete!"), "delete")

                # Edit
                # TODO: Reihenfolge der Aktionen. Ist nicht delete immer nach edit? Sollte
                # nicht clone und edit am gleichen Platz sein?
                if instance.is_mine():
                    html.icon_button(instance.edit_url(), _("Edit"), "edit")

                ### # Custom buttons - visual specific
                ### if render_custom_buttons:
                ###     render_custom_buttons(visual_name, visual)

                # Internal ID of instance (we call that 'name')
                table.cell(_('ID'), instance.name())

                # Title
                table.cell(_('Title'))
                title = _u(instance.title())
                if not instance.is_hidden():
                    html.write("<a href=\"%s.py?%s=%s\">%s</a>" %
                        (self.type_name(), self.ident_attr(), instance.name(), html.attrencode(instance.title())))
                else:
                    html.write(html.attrencode(instance.title()))
                html.help(html.attrencode(_u(instance.description())))

                # Custom columns specific to that page type
                instance.render_extra_columns()

                ### for title, renderer in custom_columns:
                ###     table.cell(title, renderer(visual))

                # Owner
                if instance.is_builtin():
                    ownertxt = "<i>" + _("builtin") + "</i>"
                else:
                    ownertxt = instance.owner()
                table.cell(_('Owner'), ownertxt)
                table.cell(_('Public'), instance.is_public() and _("yes") or _("no"))
                table.cell(_('Hidden'), instance.is_hidden() and _("yes") or _("no"))

                # TODO: Haeeh? Another custom columns
                ### if render_custom_columns:
                ###     render_custom_columns(visual_name, visual)
            table.end()

        html.footer()
        return

    # Override this in order to display additional columns of an instance
    # in the table of all instances.
    def render_extra_columns(self):
        pass

    # Page for editing an existing page, or creating a new one
    @classmethod
    def page_edit(self):
        back_url = html.var("back", self.list_url())

        self.load()
        self.need_overriding_permission("edit")

        # Three possible modes:
        # "create" -> create completely new page
        # "clone"  -> like new, but prefill form with values from existing page
        # "edit"   -> edit existing page
        mode = html.var('mode', 'edit')
        if mode == "create":
            title = self.phrase("create")
            page_dict = {
                "name"  : self.default_name(),
                "topic" : self.default_topic(),
            }
        else:
            # Load existing page. visual from disk - and create a copy if 'load_user' is set
            page_name = html.var("load_name")
            if mode == "edit":
                title = self.phrase("edit")
                page = self.find_my_page(page_name)
                self.remove_instance((config.user_id, page_name)) # will be added later again
            else: # clone
                title = self.phrase("clone")
                load_user = html.var("load_user")
                page = self.instance((load_user, page_name))
            page_dict = page.internal_representation()


        html.header(title) ### TODO: extra stylesheets for BI. Move bi.css into views.css , stylesheets=["pages", "views", "status", "bi"])
        html.begin_context_buttons()
        html.context_button(_("Back"), back_url, "back")
        html.end_context_buttons()

        # TODO: Implement multiple topics
        vs = Dictionary(
            title = _("General Properties"),
            render = 'form',
            optional_keys = None,
            elements = self.collect_parameters(),
        )

        def validate(page_dict):
            if self.find_my_page(page_dict["name"]):
                raise MKUserError("_p_name", _("You already have an with the ID <b>%s</b>") % page_dict["name"])

        new_page_dict = forms.edit_valuespec(vs, page_dict, validate=validate)
        if new_page_dict != None:
            new_page_dict["owner"] = config.user_id
            new_page = self(new_page_dict)

            if mode in ("edit", "clone"):
                # Take over non-editable keys from previous version
                for key in page_dict:
                    if key not in new_page_dict:
                        new_page_dict[key] = page_dict[key]

            self.add_page(new_page)
            self.save_user_instances()
            html.immediate_browser_redirect(1, back_url)
            html.message(_('Your changes haven been saved.'))
            # Reload sidebar. TODO: This code logically belongs to PageRenderer. How
            # can we simply move it there?
            if new_page_dict.get("hidden") == False or new_page_dict.get("hidden") != page_dict.get("hidden"):
                html.reload_sidebar()

        else:
            html.show_localization_hint()

        html.footer()
        return

#.
#   .--ContextAware--------------------------------------------------------.
#   |    ____            _            _      _                             |
#   |   / ___|___  _ __ | |_ _____  _| |_   / \__      ____ _ _ __ ___     |
#   |  | |   / _ \| '_ \| __/ _ \ \/ / __| / _ \ \ /\ / / _` | '__/ _ \    |
#   |  | |__| (_) | | | | ||  __/>  <| |_ / ___ \ V  V / (_| | | |  __/    |
#   |   \____\___/|_| |_|\__\___/_/\_\\__/_/   \_\_/\_/ \__,_|_|  \___|    |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   |  Any subclass of this is aware of contexts. That means that for      |
#   |  rendering it or otherwise bringing it into action we always need    |
#   |  a context (i.e. bunch of Selectors). ContextAware elements have a   |
#   |  list of "single infos". Example: a view that shows exactly one host |
#   |  has the single info "host".                                         |
#   |  ContextAwares also can have an intrinsic context. In that case the  |
#   |  key "context" must be present in the elements dict.                 |
#   '----------------------------------------------------------------------'


class ContextAware(Element):
    # Return a list of infos that this element is about. For views this comes
    # from the datasource
    @mandatory
    def infos(self):
        pass

    # Return the list of single infos of this element (i.e. to what information
    # it is specific. In most cases this is [], [ "host" ], or [ "host", "service"].
    # single_infos() is of course a subset of infos()
    @mandatory
    def single_infos(self):
        pass

    # Return the intrinsic context of a ContextAware. This is taken from
    # the dict variable "context" if that is present. An empty context
    # is being returned if that is missing.
    def get_intrinsic_context(self):
        return Context(self.infos(), self.single_infos(), self._.get("context", {}))

    def unsatisfied_single_infos(self):
        return self.get_intrinsic_context().unsatisfied_single_infos()

    # Construct a context from current URL variables. This takes infos and
    # single infos into account.
    # TODO: Should this be moved to ContextProvider?
    def get_context_from_url(self):
        context_dict = {}
        for selector in Selector.instances():
            if selector.info() in self.infos() and \
               selector.is_active():
               context_dict[selector.name()] = selector.get_selector_context_from_url()
        return Context(self.infos(), self.single_infos(), context_dict)

    # Construct a context from one row of the results of a datasource query
    def get_context_from_row(self, row):
        context_dict = {}
        for info_name in self.single_infos():
            info = Info.instance(info_name)
            context_dict.update(info.context_from_row(row))
        return Context(self.infos(), self.single_infos(), context_dict)


    def validate_single_infos(self, context):
        for info_name in self.single_infos():
            if info_name not in context:
                raise MKGeneralException(_("This %s cannot be rendered. It is missing "
                                           "the specification of \"<b>%s</b>\"." %
                                           (self.phrase("title"), Info.instance(info_name).title())))

    # Combine the intrinsic context (aka hard coded selectors in the view)
    # and the context from the outside (e.g. from URL or from report
    # or from dashboard). Both context types share the same infos and
    # single infos. The context from the URL has precedence.
    def build_inner_context(self, external_context):
        context = self.get_intrinsic_context()
        context.update(external_context)
        self.validate_single_infos(context)
        return context


#.
#   .--PageRenderer--------------------------------------------------------.
#   |   ____                  ____                _                        |
#   |  |  _ \ __ _  __ _  ___|  _ \ ___ _ __   __| | ___ _ __ ___ _ __     |
#   |  | |_) / _` |/ _` |/ _ \ |_) / _ \ '_ \ / _` |/ _ \ '__/ _ \ '__|    |
#   |  |  __/ (_| | (_| |  __/  _ <  __/ | | | (_| |  __/ | |  __/ |       |
#   |  |_|   \__,_|\__, |\___|_| \_\___|_| |_|\__,_|\___|_|  \___|_|       |
#   |              |___/                                                   |
#   +----------------------------------------------------------------------+
#   |  Base class for all things that have an URL and can be rendered as   |
#   |  an HTML page. And that can be added to the sidebar snapin of all    |
#   |  pages.
#   '----------------------------------------------------------------------'

class PageRenderer:
    # Stuff to be overridden by the implementation of actual page types

    # TODO: Das von graphs.py rauspfluecken. Also alles, was man
    # überladen muss oder kann.

    # Attribute for identifying that page when building an URL to
    # the page. This is always "name", but
    # in the views it's for historic reasons "view_name". We might
    # change this in near future.
    # TODO: Change that. In views.py we could simply accept *both*.
    # First look for "name" and then for "view_name" if "name" is
    # missing.
    @classmethod
    def ident_attr(self):
        return "name"

    def topic(self):
        return self._.get("topic", _("Other"))

    # Helper functions for page handlers and render function
    def page_header(self):
        return self.phrase("title") + " - " + self.title()

    def page_url(self, add_vars=[]):
        return html.makeuri_contextless([(self.ident_attr(), self.name())] + add_vars, filename = "%s.py" % self.type_name())

    @classmethod
    def global_page_links_by_topic(self):
        by_topic = {}
        for element_type in all_element_types_implementing(PageRenderer):
            for topic, title, url in  element_type.global_page_links():
                by_topic.setdefault(topic, []).append((title, url))

        return self.sort_by_topic(by_topic.items())

    @classmethod
    def sort_by_topic(self, topic_items):
        topic_order = [
            _("Overview"),
            _("Hosts"),
            _("Host Groups"),
            _("Services"),
            _("Service Groups"),
            _("Metrics"),
            _("Business Intelligence"),
            _("Problems"),
            _("Other"),
        ]

        topic_to_nr = dict( [(topic, nr) for nr, topic in enumerate(topic_order)] )

        def cmp_topic(a, b):
            return cmp(topic_to_nr.get(a[0], 999), topic_to_nr.get(b[0], 999))

        return sorted(topic_items, cmp = cmp_topic)

    # Parameters special for pgge renderers. These can be added to the sidebar,
    # so we need a topic and a checkbox for the visibility
    @classmethod
    def parameters(self, clazz):
        return [(_("General Properties"), [
            ( 1.4, 'topic', TextUnicode(
                title = _('Topic') + '<sup>*</sup>',
                size = 50,
                allow_empty = False,
            )),
            ( 2.0, 'hidden', Checkbox(
                title = _("Sidebar integration"),
                label = _('Do not add a link to this page in sidebar'),
            )),
        ])]


    # Define page handlers for the neccessary pages like listing all pages, editing
    # one and so on. This is being called (indirectly) in index.py. That way we do
    # not need to hard code page handlers for all types of PageTypes in plugins/pages.
    # It is simply sufficient to register a PageType and all page handlers will exist :-)
    # TODO: Anscheinend werden alle Views schon geladen,
    # bevor überhaupt ein Request läuft. Da ist eine load()-Funktion,
    # die stört. Brauchen wir die hier schon?
    # TODO: Das edit_ und list ist doch eine Sache von Overridable. Das gehört
    # hier doch garnicht hin!
    @classmethod
    def page_handlers(self):
        return {
            "%ss" % self.type_name()     : lambda: self.page_list(),
            "edit_%s" % self.type_name() : lambda: self.page_edit(),
            self.type_name()             : lambda: self.page_show(),
        }

    @classmethod
    def global_page_links(self):
        for page in self.pages():
            if not page.is_hidden():
                yield page.topic(), page.title(), page.page_url()


    @classmethod
    def find_page_by_name(self, name):
        for instance in self.instances():
            if instance.name() == name:
                return instance


    # Most important: page for showing the page ;-)
    @classmethod
    def page_show(self):
        name = html.var(self.ident_attr())
        if name == None:
            raise MKGeneralException(_("You need to specify the name of the %s "
                       "you want to show in the URL variable \"<tt>%s</tt>\".") % (self.phrase("title"), self.ident_attr()))
        page = self.get_element_by_name(name)
        if not page:
            raise MKGeneralException(_("Cannot find %s with the name %s") % (
                        self.phrase("title"), name))
        page.render()


    def begin_header_buttons(self):
        html.write("<div class=headerbuttons>\n")

    def end_header_buttons(self):
        html.write("</div>\n")

    def header_button(self, title, url, icon, target=""):
        html.icon_button(url, title, icon, target=target)

    def header_toggle_button(self, title, div_id, icon, is_open):
        if is_open:
            cssclass = "down"
        else:
            cssclass = "up"
        html.write('<div id="%s_on" class="togglebutton %s %s" title="%s" '
                   'onclick="view_toggle_form(this, \'%s\');"></div>' % (
                   div_id, cssclass, icon, title, div_id))

    def render_header_buttons(self):
        self.header_button(_("Open this page without the sidebar"),
                html.makeuri([]), "frameurl", target="_top")
        self.header_button(_("Show this page with the sidebar"),
                html.makeuri([("start_url", html.makeuri([]))], filename="index.py"), "pageurl", target="_top")


#.
#   .--ContextAwarePageRenderer--------------------------------------------.
#   |                       ____    _    ____  ____                        |
#   |                      / ___|  / \  |  _ \|  _ \                       |
#   |                     | |     / _ \ | |_) | |_) |                      |
#   |                     | |___ / ___ \|  __/|  _ <                       |
#   |                      \____/_/   \_\_|   |_| \_\                      |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   |  Elements that are context aware and page renderer at the same time  |
#   |  are relevant targets for being linked to in situations where con-   |
#   |  texts are present.                                                  |
#   '----------------------------------------------------------------------'

class ContextAwarePageRenderer(ContextAware, PageRenderer):
    pass

    @classmethod
    def get_url_to_page_for_row(self, element_type_name, element_name, row):
        target_element = get_element_by_type_and_name(element_type_name, element_name)
        context = target_element.get_context_from_row(row)
        return target_element.get_url_for_context(context)

    def get_url_for_context(self, context):
        return self.page_url(context.as_url_variables())

    def context_page_links_by_topic(self, context):
        by_topic = {}
        for element_type in all_element_types_implementing(ContextAwarePageRenderer):
            for topic, title, url in element_type.context_page_links(context):
                if url != self.page_url():
                    by_topic.setdefault(topic, []).append((title, url))
        return self.sort_by_topic(by_topic.items())

    def has_page_links(self, context):
        # This is just a guess
        return context.single_infos() != []

    @classmethod
    def context_page_links(self, context):
        single_info_context = context.get_single_info_context()
        links = []
        for page in self.pages():
            if page.relevant_for_context(single_info_context):
                links.append((page.topic(), page.title(), page.get_url_for_context(single_info_context)))
        return links

    def render_page_links(self, context, render_options, is_open):
        by_topic = self.context_page_links_by_topic(context)
        if by_topic:
            html.write('<div class="view_form" id="page_links" %s>' %
                    (not is_open and 'style="display: none"' or '') )
            for topic, links in by_topic:
                self.render_page_link_topic(topic, links)
            html.write('</div>')

    def render_page_link_topic(self, topic, links):
        html.write("<h3>%s</h3>" % topic)
        html.write("<ul>")
        # TODO: Icon for each URL
        for title, url in links:
            html.write('<li><a href="%s">%s</a></li>' % (url, title))
        html.write("</ul>")

    def relevant_for_context(self, context):
        if self.do_not_context_link():
            return False

        unsatisfied = self.unsatisfied_single_infos()
        if not unsatisfied:
            return False # global page has no context

        for info_name in unsatisfied:
            if info_name not in context.single_infos():
                return False # wrong context siganture
            if info_name not in context:
                return False # object name not provided

        return True

    def do_not_context_link(self):
        return bool(self._.get("hidebutton"))

    def render_header_buttons(self, context):
        self.render_selectors_button()
        self.render_page_links_button(context)

    def render_selectors_button(self):
        # TODO: is_open bei Search-Views immer True
        self.header_toggle_button(
            title = _("Refine the contents of this table by defining selectors (filters)"),
            div_id = "selectors",
            icon = "selectors",
            is_open = False)

    def render_selectors_form(self, context, render_options, is_open):
        html.begin_form("filter")
        html.write('<div class="view_form" id="selectors" %s>' %
                (not is_open and 'style="display: none"' or '') )
        by_topic = self.sort_by_topic(Selector.selectors_by_topic(context).items())
        for topic, selectors in by_topic:
            self.render_selector_topic(context, topic, selectors)

        html.button("search", _("Search"), "submit")
        html.hidden_fields()
        html.end_form()
        html.write('</div>')


    def render_selector_topic(self, context, topic, selectors):
        html.write("<div class=selector_topic>")
        html.write("<div class=topic>%s</div>" % topic)
        html.write("<div class=selector_container>")
        for selector in selectors:
            selector_context = context.get_selector_context(selector.name(), {})
            selector.render(selector_context)
        html.write("</div>")
        html.write("</div><br>")


    def render_page_links_button(self, context):
        if self.has_page_links(context):
            self.header_toggle_button(
                title = _("Useful links to other pages about the same object"),
                div_id = "page_links",
                icon = "page_links",
                is_open = False)




#.
#   .--Container-----------------------------------------------------------.
#   |              ____            _        _                              |
#   |             / ___|___  _ __ | |_ __ _(_)_ __   ___ _ __              |
#   |            | |   / _ \| '_ \| __/ _` | | '_ \ / _ \ '__|             |
#   |            | |__| (_) | | | | || (_| | | | | |  __/ |                |
#   |             \____\___/|_| |_|\__\__,_|_|_| |_|\___|_|                |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   |  Base class for element containers - things that contain elements.   |
#   |  Examples: dashboards contain dashlets, graph collections contain    |
#   |  graphs.                                                             |
#   '----------------------------------------------------------------------'

class Container:
    @classmethod
    def sanitize(self, d):
        d.setdefault("elements", [])

    def elements(self):
        return self._["elements"]

    def add_element(self, element):
        self._["elements"].append(element)

    def move_element(self, nr, whither):
        el = self._["elements"][nr]
        del self._["elements"][nr]
        self._["elements"][whither:whither] = [ el ]

    def is_empty(self):
        return not self.elements()

    # The popup for "Add to ...", e.g. for adding a graph to a report
    # or dashboard. This is needed for page types with the aspect "ElementContainer".
    @classmethod
    def render_addto_popup(self):
        pages = self.pages()
        if pages:
            html.write('<li><span>%s:</span></li>' % self.phrase("add_to"))
            for page in pages:
                html.write('<li><a href="javascript:void(0)" '
                           'onclick="add_element_to_container(\'%s\', \'%s\'); reload_sidebar();"><img src="images/icon_%s.png"> %s</a></li>' %
                           (self.type_name(), page.name(), self.type_name(), page.title()))


    # Callback for the Javascript function pagetype_add_to_container(). The
    # create_info will contain a dictionary that is known to the underlying
    # element. Note: this is being called with the base class object Container,
    # not with any actual subclass like GraphCollection. We need to find that
    # class by the URL variable element.
    @classmethod
    def ajax_add_element_to_container(self):
        container_type_name = html.var("container_type")
        container_name      = html.var("container_name")
        element_type_name   = html.var("element_type")
        create_info         = json.loads(html.var("create_info"))

        container_type = element_types[container_type_name]

        target_page_url, need_sidebar_reload = container_type.add_element_to_container(container_name, element_type_name, create_info)
        if target_page_url:
            html.write(target_page.page_url())
        html.write("\n%s" % (need_sidebar_reload and "true" or "false"))


    # Default implementation for generic containers - used e.g. by GraphCollection
    @classmethod
    def add_element_to_container(self, container_name, element_type_name, create_info):
        self.need_overriding_permission("edit")
        need_sidebar_reload = False
        container = self.get_element_by_name(container_name)
        if not container.is_mine():
            container = container.clone()
            if isinstance(container, PageRenderer) and not container.is_hidden():
                need_sidebar_reload = True

        container.add_element(create_info) # can be overridden
        self.save_user_instances()
        return None, need_sidebar_reload
        # With a redirect directly to the page afterwards do it like this:
        # return page, need_sidebar_reload


#.
#   .--Infos---------------------------------------------------------------.
#   |                       ___        __                                  |
#   |                      |_ _|_ __  / _| ___  ___                        |
#   |                       | || '_ \| |_ / _ \/ __|                       |
#   |                       | || | | |  _| (_) \__ \                       |
#   |                      |___|_| |_|_|  \___/|___/                       |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   |  An info is something like a database table. Examples are "host" or  |
#   |  "service". The Livestatus table "service" provides the infos "host" |
#   |  and "service", though! A Livestatus "table" is like a database view |
#   |  that joins possible several tables.                                 |
#   '----------------------------------------------------------------------'

class Info(Element):
    # Mandatory arguments are:
    # name         : unique name, like "host"
    # title        : l18n'ed title for the user
    # title_plural : the same but in plural
    # selector     : the name of a selector for identifying one object of this ifno
    def __init__(self, **kwargs):
        Element.__init__(self, kwargs)

    @classmethod
    def type_name(self):
        return "info"

    @classmethod
    def phrase(self, what):
        return {
            "title"          : _("Info"),
            "title_plural"   : _("Infos"), # TODO: Present the user a better name for this
        }.get(what, Element.phrase(what))

    def key_columns(self):
        return self._.get("key_columns", [])

    def context_from_row(self, row):
        return self._["context_from_row"](row)

    def page_heading_prefix_for(self, selector_context):
        selector = Selector.instance(self.name())
        return selector.heading_info(selector_context)




register_element_type(Info)

def register_info(info):
    Info.add_instance(info.name(), info)

#.
#   .--Selectors-----------------------------------------------------------.
#   |              ____       _           _                                |
#   |             / ___|  ___| | ___  ___| |_ ___  _ __ ___                |
#   |             \___ \ / _ \ |/ _ \/ __| __/ _ \| '__/ __|               |
#   |              ___) |  __/ |  __/ (__| || (_) | |  \__ \               |
#   |             |____/ \___|_|\___|\___|\__\___/|_|  |___/               |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   |  In the old implemention its name was Filter.                        |
#   '----------------------------------------------------------------------'

# Begriffe:
#
# Kontext -> Eine Sammlung von Filtervariablen, bereits bestimmten Filtern
# zugeordnet. Die Variablen können in eine URL gesetzt werden.
#
# Filter -> ähnlich wie ein Valuespec, aber ohne Varprefix und mit Zusatzfunktionen
#
# male_dich(kontext) -> None   Malt Eingabefelder anhand von Kontext
# gib_kontext() -> kontext     Hole HTML-Variablen und füllt Kontext
# livestatus_headers(kontext)  Erzeugt Header für Anfrage
# filter_table(rows, kontext)  Filtert eine bereits geholte Table nachträglich
#
# Info -> Entspricht einer Datenbanktabelle
#
# Aktuell: Filter holen Dinge aus den HTML-Vars.
# Neu: Filter bekommen beim Aufruf immer einen Kontext. Das holen der HTML-Vars
# machen sie isoliert in einer eigenen Funktion.

# context -> Ein globaler Context
# selector_context -> Daraus nur die Variablen für einen bestimmten Selektor

# Ein Selektor muss sagen können, welche Spalten er benötigt, um die
# nachgelagerte Filterung mit filter_table() machen zu können. Diese werden
# nur dann geholt, wenn der Filter aktiv ist. Beispiel ist das host_inventory.

class Selector(Element):
    # This is called by the subclass-__init__ functions. The arguments are
    # name:        the unique name of the selector
    # title:       a title
    # description: A description (help text). Should this be optional?
    # variables:   A list of URL variable names owned by this selector
    # info:        The info (e.g. "service") this selector deals with
    def __init__(self, **kwargs):
        Element.__init__(self, kwargs)

    @classmethod
    def type_name(self):
        return "selector"

    @classmethod
    def phrase(self, what):
        return {
            "title"          : _("Selector"),
            "title_plural"   : _("Selectors"),
        }.get(what, Element.phrase(what))

    def info(self):
        return self._["info"]

    # Return the URL variables that this selector owns
    def variables(self):
        return self._["variables"]

    # Pick out the URL variables that make up this selector. The selector
    # needs to decide wether it is active in the first place. If not it
    # must return None and not a list of empty URL variables.
    def get_selector_context_from_url(self):
        if self.is_active():
            return dict([(varname, html.var(varname, "")) for varname in self.variables()])

    # STUFF TO BE OVERRIDDEN STARTS HERE

    # Checks, if the URL variables are set in a way that the
    # selector actual selects something.
    @mandatory
    def is_active(self):
        pass

    # Some selectors can be unavailable due to the configuration (e.g.
    # the WATO Folder selector is only available if WATO is enabled.
    def available(self):
        return True

    # More complex selector need more height in the HTML layout
    def double_height(self):
        return False

    # Render HTML Code for user. selector_context is a dict of
    # URL variables
    @mandatory
    def display(self, selector_context):
        pass

    # Formerly called filter(). Create Livestatus headers for
    # query, e.g. the selector does its actual job. The selector
    # may assume that it is active.
    def livestatus_headers(self, selector_context):
        return ""

    # Post-Processing: this is for selectors that cannot work via
    # Livestatus. Formerly called filter_table(). The selector
    # may assume that it is active.
    def select_rows(self, rows, selector_context):
        return rows

    # Only needed for selectors of single infos. Vanilla implementation for
    # the case that the selector context has just one entry
    def heading_info(self, selector_context):
        return selector_context.values()[0]

    @classmethod
    def selectors_by_topic(self, context):
        by_topic = {}
        for selector in self.instances():
            if selector.info() not in context.infos():
                continue # not relevant for current context
            if selector.info() in context.single_infos() and \
                selector.name() != selector.info():
                continue # not *the* single info selector for this info
            topic = selector.topic()
            by_topic.setdefault(topic, []).append(selector)
        return by_topic

    def render(self, selector_context):
        html.write('<div class="selector %s">' % (self.double_height() and "double" or "single"))
        html.write('<div class=legend>%s</div>' % self.title())
        html.write('<div class=content>')
        self.render_input(selector_context)
        html.write("</div>")
        html.write("</div>")

register_element_type(Selector)

def register_selector(selector):
    Selector.add_instance(selector.name(), selector)

#.
#   .--Contexts------------------------------------------------------------.
#   |                 ____            _            _                       |
#   |                / ___|___  _ __ | |_ _____  _| |_ ___                 |
#   |               | |   / _ \| '_ \| __/ _ \ \/ / __/ __|                |
#   |               | |__| (_) | | | | ||  __/>  <| |_\__ \                |
#   |                \____\___/|_| |_|\__\___/_/\_\\__|___/                |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   |  A Context is a bunch of Selectors plus specification for single     |
#   |  infos. For example a service context might be the specification of  |
#   |  a host name plus selectors that select only problem services of     |
#   |  this host.
#   '----------------------------------------------------------------------'

class Context(Element):
    # TODO: Müsste es hier nicht info_names und single_info_names heißen?
    # Oder arbeitet man gleich mit den Referenzen auf die Info-Objekte?
    def __init__(self, infos, single_infos, context_dict):
        self._single_infos = single_infos
        self._infos = infos
        self._ = self.sanitize_context_dict(context_dict)

    # Bring visuals-style contexts with non-dict values for
    # single infos into new elements-style context, where single
    # infos are no longer special.
    def sanitize_context_dict(self, context_dict):
        sanitized = {}
        for key, value in context_dict.items():
            if type(value) == dict:
                sanitized[key] = value
            else:
                sanitized[key] = { key: value }

        # TODO: Problem ist, dass das umwandeln nicht immer stimmt, da früher
        # bei single-Kontexten einzelne URL-Variablen als Keys verwendet wurden
        # und heute ganz normale Selektor-Namen.
        return sanitized

    def infos(self):
        return self._infos

    def single_infos(self):
        return self._single_infos

    def unsatisfied_single_infos(self):
        return [
            info_name
            for info_name in self._single_infos
            if info_name not in self._
        ]

    def get_single_info_context(self):
        new_dict = {}
        for info_name in self._single_infos:
            if info_name in self._:
                new_dict[info_name] = self._[info_name]
        return Context(self.infos(), self.single_infos(), new_dict)

    def get_selector_context(self, selector_name, default_value=None):
        return self._.get(selector_name, default_value)


    # Much like a dict update, but we make sure that the original
    # dict (which we might have borrowed from somewhere) is not
    # changed.
    def update(self, other):
        new_dict = {}
        new_dict.update(self._)
        new_dict.update(other._)
        self._ = new_dict

    def livestatus_filters(self):
        # TODO: single infos
        headers = ""
        for selector_name, selector_context in self._.items():
            if not Selector.has_instance(selector_name):
                # TODO: If we have migrated all selectors then this
                # must not happen
                pass
            else:
                selector = Selector.instance(selector_name)
                headers += selector.livestatus_headers(selector_context)
        return headers

    # Non-Livestatus filtering (e.g. for BI tables)
    def select_rows(self, rows, context):
        for selector_name, selector_context in self._.items():
            if not Selector.has_instance(selector_name):
                pass
            else:
                selector = Selector.instance(selector_name)
                rows = selector.select_rows(rows, selector_context)
        return rows

    def as_url_variables(self):
        url_vars = []
        for selector_context in self._.values():
            url_vars += selector_context.items()
        return url_vars

    def page_heading_prefix(self):
        components = [
            Info.instance(i).page_heading_prefix_for(self._[i])
            for i in self.single_infos()
        ]
        return " / ".join(components)



