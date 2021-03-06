#!/usr/bin/env python
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
# tails. You should have  received  a copy of the  GNU  General Public
# License along with GNU Make; see the file  COPYING.  If  not,  write
# to the Free Software Foundation, Inc., 51 Franklin St,  Fifth Floor,
# Boston, MA 02110-1301 USA.

# TODO:
#
# Notes for future rewrite:
#
# - Make clear which functions return values and which write out values
#   render_*, add_*, write_* (e.g. icon() -> outputs directly,
#                                  render_icon() -> returns icon
#
# - Order of arguments:
#   e.g. icon(help, icon) -> change and make help otional?
#
# - Fix names of message() show_error() show_warning()
#
# - change naming of html.attrencode() to html.render()
#
# - General rules:
# 1. values of type str that are passed as arguments or
#    return values or are stored in datastructures must not contain
#    non-Ascii characters! UTF-8 encoding must just be used in
#    the last few CPU cycles before outputting. Conversion from
#    input to str or unicode must happen as early as possible,
#    directly when reading from file or URL.
#
# - indentify internal helper methods and prefix them with "_"
#
# - Split HTML handling (page generating) code and generic request
#   handling (vars, cookies, ...) up into separate classes to make
#   the different tasks clearer. For example a RequestHandler()
#   and a HTMLGenerator() or similar.

import time
import os
import urllib
import random
import re
import __builtin__
import signal

from collections import deque

try:
    import simplejson as json
except ImportError:
    import json

from cmk.exceptions import MKGeneralException, MKException
from lib import MKUserError


# TODO: REMOVE (JUST FOR TESTING)
#__builtin__._ = lambda x: x



# Information about uri
class InvalidUserInput(Exception):
    def __init__(self, varname, text):
        self.varname = varname
        self.text = text


class RequestTimeout(MKException):
    pass


#.
#   .--HTML----------------------------------------------------------------.
#   |                      _   _ _____ __  __ _                            |
#   |                     | | | |_   _|  \/  | |                           |
#   |                     | |_| | | | | |\/| | |                           |
#   |                     |  _  | | | | |  | | |___                        |
#   |                     |_| |_| |_| |_|  |_|_____|                       |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   | This is a simple class which wraps a string provided by the caller   |
#   | to make html.attrencode() know that this string should not be        |
#   | encoded, html.attrencode() will then return the unmodified value.    |
#   |                                                                      |
#   | This way we can implement encodings while still allowing HTML code   |
#   | processing for some special cases. This is useful when one needs     |
#   | to print out HTML tables in messages or help texts.                  |
#   |                                                                      |
#   | The class now implements all relevant string comparison methods.     |
#   | The HTMLGenerator render_tag() function returns a HTML object.       |
#   '----------------------------------------------------------------------'
class HTML(object):


    def __init__(self, value):
        super(HTML, self).__init__()
        if isinstance(value, HTML):
            self.value = value.value
        else:
            self.value = value


    def __str__(self):
        return self.value


    def __add__(self, other):
        if isinstance(other, HTML):
            return self.value + other.value
        else:
            return self.value + other


    def __radd__(self, other):
        if isinstance(other, HTML):
            return other.value + self.value
        else:
            return other + self.value


    def __iadd__(self, other):
        self.value = self.__add__(other)
        return self


    def __lt__(self, other):
        if isinstance(other, HTML):
            return self.value < other.value
        else:
            return self.value < other


    def ___le__(self, other):
        if isinstance(other, HTML):
            return self.value <= other.value
        else:
            return self.value <= other


    def __eq__(self, other):
        if isinstance(other, HTML):
            return self.value == other.value
        else:
            return self.value == other


    def __ne__(self, other):
        if isinstance(other, HTML):
            return self.value != other.value
        else:
            return self.value != other


    def __gt__(self, other):
        if isinstance(other, HTML):
            return self.value > other.value
        else:
            return self.value > other


    def __ge__(self, other):
        if isinstance(other, HTML):
            return self.value >= other.value
        else:
            return self.value >= other


    def __len__(self):
        return len(self.value)



__builtin__.HTML = HTML


#   .--OutputFunnel--------------------------------------------------------.
#   |     ___        _               _   _____                       _     |
#   |    / _ \ _   _| |_ _ __  _   _| |_|  ___|   _ _ __  _ __   ___| |    |
#   |   | | | | | | | __| '_ \| | | | __| |_ | | | | '_ \| '_ \ / _ \ |    |
#   |   | |_| | |_| | |_| |_) | |_| | |_|  _|| |_| | | | | | | |  __/ |    |
#   |    \___/ \__,_|\__| .__/ \__,_|\__|_|   \__,_|_| |_|_| |_|\___|_|    |
#   |                   |_|                                                |
#   +----------------------------------------------------------------------+
#   | Provides the write functionality. The method lowlevel_write needs to |
#   | to be overwritten in the specific subclass!                          |
#   '----------------------------------------------------------------------'


class OutputFunnel(object):


    def __init__(self):
        self.plugged = False
        self.plugged_text = ""


    # Accepts str and unicode objects only!
    # The plugged functionality can be used for debugging.
    def write(self, text):

        if isinstance(text, HTML):
            text = text.value

        if type(text) not in [str, unicode]: # also possible: type Exception!
            raise MKGeneralException(_('Write accepts str and unicode objects only!'))

        if self.plugged:
            self.plugged_text += text
        else:
            # encode when really writing out the data. Not when writing plugged,
            # because the plugged code will be handled somehow by our code. We
            # only encode when leaving the pythonic world.
            if type(text) == unicode:
                text = text.encode("utf-8")
            self.lowlevel_write(text)


    def lowlevel_write(self, text):
        raise NotImplementedError()


    # Put in a plug which stops the text stream and redirects it to a sink.
    def plug(self):
        self.plugged = True
        self.plugged_text = ''


    def is_plugged(self):
        return self.plugged


    # Pull the plug for a moment to allow the sink content to pass through.
    def flush(self):
        if self.plugged:
            text = self.plugged_text

            # encode when really writing out the data. Not when writing plugged,
            # because the plugged code will be handled somehow by our code. We
            # only encode when leaving the pythonic world.
            if type(text) == unicode:
                text = text.encode("utf-8")

            self.lowlevel_write(text)
            self.plugged_text = ''


    # Get the sink content in order to do something with it.
    def drain(self):
        if self.plugged:
            text = self.plugged_text
            self.plugged_text = ''
            return text
        else:
            return ''


    def unplug(self):
        self.flush()
        self.plugged = False


#.
#   .--HTML Generator------------------------------------------------------.
#   |                      _   _ _____ __  __ _                            |
#   |                     | | | |_   _|  \/  | |                           |
#   |                     | |_| | | | | |\/| | |                           |
#   |                     |  _  | | | | |  | | |___                        |
#   |                     |_| |_| |_| |_|  |_|_____|                       |
#   |                                                                      |
#   |             ____                           _                         |
#   |            / ___| ___ _ __   ___ _ __ __ _| |_ ___  _ __             |
#   |           | |  _ / _ \ '_ \ / _ \ '__/ _` | __/ _ \| '__|            |
#   |           | |_| |  __/ | | |  __/ | | (_| | || (_) | |               |
#   |            \____|\___|_| |_|\___|_|  \__,_|\__\___/|_|               |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   |  Generator which provides top level HTML writing functionality.      |
#   '----------------------------------------------------------------------'


class HTMLGenerator(OutputFunnel):

    """ Usage Notes:

          - Tags can be opened using the open_[tag]() call where [tag] is one of the possible tag names.
            All attributes can be passed as function arguments, such as open_div(class_="example").
            However, python specific key words need to be escaped using a trailing underscore.
            One can also provide a dictionary as attributes: open_div(**{"class": "example"}).

          - All tags can be closed again using the close_[tag]() syntax.

          - For tags which shall only contain plain text (i.e. no tags other than highlighting tags)
            you can a the direct call using the tag name only as function name,
            self.div("Text content", **attrs). Tags featuring this functionality are listed in
            the "featured shortcuts" list.

          - Some tags require mandatory arguments. Those are defined explicitly below.
            For example an a tag needs the href attribute everytime.

          - If you want to provide plain HTML to a tag, please use the tag_content function or
            facillitate the HTML class.

        HOWTO HTML Attributes:

          - Python specific attributes have to be escaped using a trailing underscore

          - All attributes can be python objects. However, some attributes can also be lists of attrs:

                'class' attributes will be concatenated using one whitespace
                'style' attributes will be concatenated using the semicolon and one whitespace
                Behaviorial attributes such as 'onclick', 'onmouseover' will bec concatenated using
                a semicolon and one whitespace.

          - All attributes will be escaped, i.e. the characters '&', '<', '>', '"' will be replaced by
            non HtML relevant signs '&amp;', '&lt;', '&gt;' and '&quot;'. """


    # these tags can be called by their tag names, e.g. 'self.title(content)'
    _shortcut_tags = set(['title', 'h1', 'h2', 'h3', 'th', 'tr', 'td', 'center',\
                              'div', 'p', 'span', 'canvas', 'strong', 'sub', 'tt', 'u'])

    # these tags can be called by open_name(), close_name() and render_name(), e.g. 'self.open_html()'
    _tag_names = set(['html', 'head', 'body', 'header', 'footer', 'a', 'b',\
                              'script', 'form', 'button', 'p', 'select', 'pre',\
                              'table', 'row', 'ul', 'li', 'br', 'nobr', 'input',\
                              'tt'])

    # Of course all shortcut tags can be used as well.
    _tag_names.update(_shortcut_tags)


    def __init__(self):
        super(HTMLGenerator, self).__init__()

        self.indent_level = 0
        self.indent = 2



    #
    # Escaping functions
    #


    # Encode HTML attributes. Replace HTML syntax with HTML text.
    # For example: replace '"' with '&quot;', '<' with '&lt;'.
    # This code is slow. Works on str and unicode without changing
    # the type. Also works on things that can be converted with '%s'.
    def _escape_attribute(self, value):
        attr_type = type(value)
        if value is None:
            return ''
        elif attr_type == int:
            return str(value)
        elif isinstance(value, HTML):
            return value.value # This is HTML code which must not be escaped
        elif attr_type not in [str, unicode]: # also possible: type Exception!
            value = "%s" % value # Note: this allows Unicode. value might not have type str now
        return value.replace("&", "&amp;")\
                    .replace('"', "&quot;")\
                    .replace("<", "&lt;")\
                    .replace(">", "&gt;")


    # render HTML text.
    # We only strip od some tags and allow some simple tags
    # such as <h1>, <b> or <i> to be part of the string.
    # This is useful for messages where we want to keep formatting
    # options. (Formerly known as 'permissive_attrencode') """
    # for the escaping functions

    _unescaper_text = re.compile(r'&lt;(/?)(h2|b|tt|i|br(?: /)?|pre|a|sup|p|li|ul|ol)&gt;')
    _unescaper_href = re.compile(r'&lt;a href=&quot;(.*?)&quot;&gt;')

    def _escape_text(self, text):

        if isinstance(text, HTML):
            return text.value # This is HTML code which must not be escaped

        text = self._escape_attribute(text)
        text = self._unescaper_text.sub(r'<\1\2>', text)
        # Also repair link definitions
        text = self._unescaper_href.sub(r'<a href="\1">', text)
        return text


    #
    # Rendering
    #


    def _render_attributes(self, **attrs):
        # TODO: REMOVE AFTER REFACTORING IS DONE!!
        for key in attrs:
            assert key.rstrip('_') in ['class', 'id', 'src', 'type', 'name',\
                'onclick', 'onsubmit', 'onmouseover', 'onmouseout', 'onfocus', 'value', \
                'content',  'href', 'http-equiv', 'rel', 'for', 'title', 'target',\
                'align', 'valign', 'style', 'width', 'height', 'colspan', 'data-role',\
                'cellspacing', 'cellpadding', 'border'], key

        for k, v in attrs.iteritems():
            if v is None: continue

            if not isinstance(v, list):
                yield ' %s=\"%s\"' % (k.rstrip('_'), self._escape_attribute(v))
            elif k in ["class", "class_"]:
                yield ' %s=\"%s\"' % (k.rstrip('_'),  ' '.join(a for a in (self._escape_attribute(vi) for vi in v) if a))
            elif k == "style" or k.startswith('on'):
                yield ' %s=\"%s;\"' % (k.rstrip('_'), re.sub(';+', ';', '; '.join(a for a in (self._escape_attribute(vi) for vi in v) if a)))
            else:
                yield ' %s=\"%s\"' % (k.rstrip('_'),   '_'.join(a for a in (self._escape_attribute(vi) for vi in v) if a))


    # applies attribute encoding to prevent code injections.
    def _render_opening_tag(self, tag_name, close_tag=False, **attrs):
        """ You have to replace attributes which are also python elements such as
            'class', 'id', 'for' or 'type' using a trailing underscore (e.g. 'class_' or 'id_'). """
        #self.indent_level += self.indent
        if not attrs:
            return "%s<%s%s>" % (' ' * (self.indent_level - self.indent),\
                                   tag_name,\
                                   ' /' if close_tag else '')
        else:
            return "%s<%s%s%s>" % (' ' * (self.indent_level - self.indent),\
                                     tag_name, ''.join(self._render_attributes(**attrs)),\
                                     ' /' if close_tag else '')


    def _render_closing_tag(self, tag_name):
        #self.indent_level -= self.indent if self.indent_level < 0 else 0
        return  "%s</%s>" % (' ' * self.indent_level, tag_name)


    def _render_content_tag(self, tag_name, tag_content, **attrs):
        return "%s%s%s%s" % (self._render_opening_tag(tag_name, **attrs),\
                               ' ' * self.indent_level,\
                               self._escape_text(tag_content),\
                               self._render_closing_tag(tag_name))


    # does not escape the script content
    def _render_javascript(self, code):
        return "<script language=\"javascript\">\n%s\n</script>\n" % code


    # Write functionlity
#    def write(self, text):
#        raise NotImplementedError()


    # This is used to create all the render_tag() and close_tag() functions
    def __getattr__(self, name):
        """ All closing tags can be called like this: 
            self.close_html(), self.close_tr(), etc. """

        parts = name.split('_')

        # generating the shortcut tag calls
        if len(parts) == 1 and name in self._shortcut_tags:
            return lambda content, **attrs: self.write(self._render_content_tag(name, content, **attrs))

        # generating the open, close and render calls
        elif len(parts) == 2:
            what, tag_name = parts[0], parts[1]

            if what == "open" and tag_name in self._tag_names:
                return lambda **attrs: self.write(self._render_opening_tag(tag_name, **attrs))

            elif what == "close" and tag_name in self._tag_names:
                return lambda : self.write(self._render_closing_tag(tag_name))

            elif what == "idle" and tag_name in self._tag_names:
                return lambda **attrs: self.write(self._render_content_tag(tag_name, '', **attrs))

            elif what == "render" and tag_name in self._tag_names:
                return lambda content, **attrs: HTML(self._render_content_tag(tag_name, content, **attrs))

        else:
            return object.__getattribute__(self, name)

    #
    # HTML element methods
    # If an argument is mandatory, it is used as default and it will overwrite an
    # implicit argument (e.g. id_ will overwrite attrs["id"]).
    #


    #
    # basic elements
    #

    def write_text(self, text):
        """ Write text. Highlighting tags such as h2|b|tt|i|br|pre|a|sup|p|li|ul|ol are not escaped. """
        self.write(self._escape_text(text))


    def write_html(self, content):
        """ Write HTML code directly, without escaping. """
        self.write(content + "\n")


    def comment(self, comment_text):
        self.write("<!--%s-->" % self.encode_attribute(comment_text))


    def meta(self, httpequiv=None, **attrs):
        if httpequiv:
            attrs['http-equiv'] = httpequiv
        self.write(self._render_opening_tag('meta', close_tag=True, **attrs))


    def base(self, target):
        self.write(self._render_opening_tag('base', close_tag=True, target=target))


    def open_a(self, href, **attrs):
        attrs['href'] = href
        self.write(self._render_opening_tag('a', **attrs))


    def a(self, content, href, **attrs):
        attrs['href'] = href
        self.write(self._render_content_tag('a', content, **attrs))


    def stylesheet(self, href):
        self.write(self._render_opening_tag('link', rel="stylesheet", type_="text/css", href=href, close_tag=True))


    #
    # Helper functions to be used by snapins
    #


    def url_prefix(self):
        raise NotImplementedError()


    def render_link(self, text, url, target="main", onclick = None):
        # Convert relative links into absolute links. We have three kinds
        # of possible links and we change only [3]
        # [1] protocol://hostname/url/link.py
        # [2] /absolute/link.py
        # [3] relative.py
        if not (":" in url[:10]) and not url.startswith("javascript") and url[0] != '/':
            url = self.url_prefix() + "check_mk/" + url
        return self.render_a(text, class_="link", target=target or '', href=url,\
                             onfocus = "if (this.blur) this.blur();",\
                             onclick = onclick or None)


    def link(self, text, url, target="main", onclick = None):
        self.write(self.render_link(text, url, target=target, onclick=onclick))


    def simplelink(self, text, url, target="main"):
        self.link(text, url, target)
        self.br()


    def bulletlink(self, text, url, target="main", onclick = None):
        self.open_li(class_="sidebar")
        self.link(text, url, target, onclick)
        self.close_li()


    def iconlink(self, text, url, icon):
        self.open_a(class_=["iconlink", "link"], target="main", href=url)
        self.icon(icon=icon, help=None, cssclass="inline")
        self.write_text(text)
        self.close_a()
        self.br()


    def nagioscgilink(self, text, target):
        self.open_li(class_="sidebar")
        self.a(text, class_="link", target="main", href="%snagios/cgi-bin/%s" % (self.url_prefix(), target))
        self.close_li()


    #
    # Scriptingi
    #


    def javascript(self, code):
        self.write(self._render_javascript(code))


    def javascript_file(self, name):
        """ <script type="text/javascript" src="js/%(name)s.js"/>\n """
        self.write(self._render_content_tag('script', '', type_="text/javascript", src='js/%s.js' % name))


    def img(self, src, **attrs):
        attrs['src'] = src
        self.write(self._render_opening_tag('img', close_tag=True, **attrs))


    def open_button(self, type_, **attrs):
        attrs['type'] = type_
        self.write(self._render_opening_tag('button', close_tag=True, **attrs))


    def play_sound(self, url):
        self.write(self._render_opening_tag('audio autoplay', src_=url))


    #
    # form elements
    #


    def label(self, content, for_, **attrs):
        attrs['for'] = for_
        self.write(self._render_content_tag('label', content, **attrs))


    def input(self, name, type_, **attrs):
        attrs['type_'] = type_
        attrs['name'] = name
        self.write(self._render_opening_tag('input', close_tag=True, **attrs))


    #
    # table elements
    #


    def td(self, content, **attrs):
        """ Only for text content. You can't put HTML structure here. """
        self.write(self._render_content_tag('td', content, **attrs))


    #
    # list elements
    #


    def li(self, content, **attrs):
        """ Only for text content. You can't put HTML structure here. """
        self.write(self._render_content_tag('li', content, **attrs))


    #
    # structural text elements
    #


    def heading(self, content):
        """ <h2>%(content)</h2> """
        self.write(self._render_content_tag('h2', content))


    def br(self):
        self.write('<br/>')


    def hr(self, **attrs):
        self.write(self._render_opening_tag('hr', close_tag=True, **attrs))


    def rule(self):
        self.hr()


#.
#   .--HTML Check_MK-------------------------------------------------------.
#   |                      _   _ _____ __  __ _                            |
#   |                     | | | |_   _|  \/  | |                           |
#   |                     | |_| | | | | |\/| | |                           |
#   |                     |  _  | | | | |  | | |___                        |
#   |                     |_| |_| |_| |_|  |_|_____|                       |
#   |                                                                      |
#   |              ____ _               _        __  __ _  __              |
#   |             / ___| |__   ___  ___| | __   |  \/  | |/ /              |
#   |            | |   | '_ \ / _ \/ __| |/ /   | |\/| | ' /               |
#   |            | |___| | | |  __/ (__|   <    | |  | | . \               |
#   |             \____|_| |_|\___|\___|_|\_\___|_|  |_|_|\_\              |
#   |                                      |_____|                         |
#   +----------------------------------------------------------------------+
#   | A HTML generating class which introduces some logic of the Check_MK  |
#   | web application.                                                     |
#   | It also contains various settings for how the page should be built.  |
#   '----------------------------------------------------------------------'


class HTMLCheck_MK(HTMLGenerator):


    def __init__(self):
        super(HTMLCheck_MK, self).__init__()

        # rendering state
        self.html_is_open = False
        self.header_sent = False

        # style options
        self.body_classes = ['main']
        self._default_stylesheets = [ "check_mk", "graphs" ]
        self._default_javascripts = [ "checkmk", "graphs" ]

        # behaviour options
        self.render_headfoot = True
        self.enable_debug = False
        self.screenshotmode = False
        self.help_visible = False

        # browser options
        self.output_format = "html"
        self.browser_reload = 0
        self.browser_redirect = ''
        self.link_target = None

    def default_html_headers(self):
        self.meta(httpequiv="Content-Type", content="text/html; charset=utf-8")
        self.meta(httpequiv="X-UA-Compatible", content="IE=edge")
        self.write(self._render_opening_tag('link', rel="shortcut icon", href="images/favicon.ico", type_="image/ico", close_tag=True))


    def _head(self, title, javascripts=None, stylesheets=None):

        javascripts = javascripts if javascripts else []
        stylesheets = stylesheets if stylesheets else ["pages"]

        self.open_head()

        self.default_html_headers()
        self.title(title)

        # If the variable _link_target is set, then all links in this page
        # should be targetted to the HTML frame named by _link_target. This
        # is e.g. useful in the dash-board
        if self.link_target:
            self.base(target=self.link_target)

        # Load all specified style sheets and all user style sheets in htdocs/css
        for css in self._default_stylesheets + stylesheets:
            fname = self.css_filename_for_browser(css)
            if fname is not None:
                self.stylesheet(fname)

        # write css for internet explorer
        fname = self.css_filename_for_browser("ie")
        if fname is not None:
            self.write("<!--[if IE]>\n")
            self.stylesheet(fname)
            self.write("<![endif]-->\n")

        self.add_custom_style_sheet()

        # Load all scripts
        for js in self._default_javascripts + javascripts:
            filename_for_browser = self.javascript_filename_for_browser(js)
            if filename_for_browser:
                self.javascript_file(filename_for_browser)

        if self.browser_reload != 0:
            if self.browser_redirect != '':
                self.javascript('set_reload(%s, \'%s\')' % (self.browser_reload, self.browser_redirect))
            else:
                self.javascript('set_reload(%s)' % (self.browser_reload))

        self.close_head()


    def html_head(self, title, javascripts=None, stylesheets=None, force=False):

        force_new_document = force # for backward stability and better readability

        #TODO: html_is_open?

        if force_new_document:
            self.header_sent = False

        if not self.header_sent:
            self.write('<!DOCTYPE HTML>\n')
            self.open_html()
            self._head(title, javascripts, stylesheets)
            self.header_sent = True



    def header(self, title='', javascripts=None, stylesheets=None, force=False):
        if self.output_format == "html":
            if not self.header_sent:
                self.body_start(title, javascripts=javascripts, stylesheets=stylesheets, force=force)
                self.header_sent = True
                if self.render_headfoot:
                    self.top_heading(title)


    def body_start(self, title='', javascripts=None, stylesheets=None, force=False):
        self.html_head(title, javascripts, stylesheets, force)
        self.open_body(class_=self._get_body_css_classes())


    def _get_body_css_classes(self):
        if self.screenshotmode:
            return self.body_classes + ["screenshotmode"]
        else:
            return self.body_classes


    def add_custom_style_sheet(self):
        raise NotImplementedError()


    def css_filename_for_browser(self, css):
        raise NotImplementedError()


    def javascript_filename_for_browser(self, jsname):
        raise NotImplementedError()


    def html_foot(self):
        self.close_html()


    def top_heading(self, title):
        raise NotImplementedError()


    def top_heading_left(self, title):
        self.open_table(class_="header")
        self.open_tr()
        self.open_td(width="*", class_="heading")
        self.a(title, href="#", onfocus="if (this.blur) this.blur();", 
               onclick="this.innerHTML=\'%s\'; document.location.reload();" % _("Reloading..."))
        self.close_td()


    def top_heading_right(self):
        cssclass = "active" if self.help_visible else "passive"

        self.icon_button(None, _("Toggle context help texts"), "help", id="helpbutton",
                         onclick="toggle_help()", style="display:none", ty="icon", cssclass=cssclass)
        self.open_a(href=_("http://mathias-kettner.de"), class_="head_logo")
        self.img(src="images/logo_cmk_small.png")
        self.close_a()
        self.close_td()
        self.close_tr()
        self.close_table()
        self.hr(class_="header")

        if self.enable_debug:
            self._dump_get_vars()


    #
    # HTML form rendering
    #


    def detect_icon_path(self, icon_name):
        raise NotImplementedError()


    def icon(self, help, icon, **kwargs):

        #TODO: Refactor
        title = help

        self.write(self.render_icon(icon_name=icon, help=title, **kwargs))


    def empty_icon(self):
        self.write(self.render_icon("images/trans.png"))


    def render_icon(self, icon_name, help=None, middle=True, id=None, cssclass=None):

        # TODO: Refactor
        title    = help
        id_      = id

        attributes = {'title'   : title,
                      'id'      : id_,
                      'class'   : ["icon", cssclass],
                      'align'   : 'absmiddle' if middle else None,
                      'src'     : icon_name if "/" in icon_name else self.detect_icon_path(icon_name)}

        return self._render_opening_tag('img', close_tag=True, **attributes)


    def render_icon_button(self, url, help, icon, id=None, onclick=None,
                           style=None, target=None, cssclass=None, ty="button"):

        # TODO: Refactor
        title    = help
        id_      = id

        # TODO: Can we clean this up and move all button_*.png to internal_icons/*.png?
        if ty == "button":
            icon = "images/button_" + icon + ".png"

        icon = HTML(self.render_icon(icon, cssclass="iconbutton"))

        return self.render_a(icon, **{'title'   : title,
                                      'id'      : id_,
                                      'class'   : cssclass,
                                      'style'   : style,
                                      'target'  : target if target else '',
                                      'href'    : url if not onclick else "javascript:void(0)",
                                      'onfocus' : "if (this.blur) this.blur();",
                                      'onclick' : onclick })


    def icon_button(self, *args, **kwargs):
        self.write(self.render_icon_button(*args, **kwargs))


#.


class DeprecationWrapper(HTMLCheck_MK):
    # Only strip off some tags. We allow some simple tags like
    # <b>, <tt>, <i> to be part of the string. This is useful
    # for messages where we still want to have formating options.
    def permissive_attrencode(self, obj):
        return self._escape_text(obj)


    # Encode HTML attributes: replace " with &quot;, also replace
    # < and >. This code is slow. Works on str and unicode without
    # changing the type. Also works on things that can be converted
    # with %s.
    def attrencode(self, value):
        return self._escape_attribute(value)


#.
#   .--html----------------------------------------------------------------.
#   |                        _     _             _                         |
#   |                       | |__ | |_ _ __ ___ | |                        |
#   |                       | '_ \| __| '_ ` _ \| |                        |
#   |                       | | | | |_| | | | | | |                        |
#   |                       |_| |_|\__|_| |_| |_|_|                        |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   | Caution! The class needs to be derived from Outputfunnel first!      |
#   '----------------------------------------------------------------------'


class html(DeprecationWrapper):


    def __init__(self):
        super(html, self).__init__()

        self.myfile = None
        self.cookies = {}
        self._user_id = None
        self.user_errors = {}
        self.focus_object = None
        self.events = set([]) # currently used only for sounds
        self.status_icons = {}
        self.final_javascript_code = ""
        self.auto_id = 0
        self.caches = {}
        self.treestates = None
        self.new_transids = []
        self.ignore_transids = False
        self.current_transid = None
        self.page_context = {}
        self._request_timeout = 110 # seconds

        # Settings
        self.have_help = False
        self.io_error = False
        self.mobile = False
        self.buffering = True
        self.keybindings_enabled = True
        self.keybindings = []
        self.context_buttons_open = False

        # Forms
        self.form_name = None
        self.form_vars = []

        # Variable management
        self.vars      = {}
        self.listvars  = {} # for variables with more than one occurrance
        self.uploads   = {}
        self.var_stash = []

        # Time measurement
        self.times            = {}
        self.start_time       = time.time()
        self.last_measurement = self.start_time


    RETURN    = 13
    SHIFT     = 16
    CTRL      = 17
    ALT       = 18
    BACKSPACE = 8
    F1        = 112


    def set_user_id(self, user_id):
        self._user_id = user_id


    def is_mobile(self):
        return self.mobile


    def is_api_call(self):
        return self.output_format != "html"


    def get_user_agent(self):
        raise NotImplementedError()


    def get_referer(self):
        raise NotImplementedError()


    # The system web servers configured request timeout. This is the time
    # before the request is terminated from the view of the client.
    def client_request_timeout(self):
        raise NotImplementedError()


    def is_ssl_request(self):
        raise NotImplementedError()


    def request_method(self):
        raise NotImplementedError()


    def set_page_context(self, c):
        self.page_context = c


    def set_buffering(self, b):
        self.buffering = b


    # TODO: Can this please be dropped?
    def some_id(self):
        self.auto_id += 1
        return "id_%d" % self.auto_id


    def set_output_format(self, f):
        self.output_format = f
        if f == "json":
            content_type = "application/json; charset=UTF-8"

        elif f == "jsonp":
            content_type = "application/javascript; charset=UTF-8"

        elif f in ("csv", "csv_export"): # Cleanup: drop one of these
            content_type = "text/csv; charset=UTF-8"

        elif f == "python":
            content_type = "text/plain; charset=UTF-8"

        elif f == "text":
            content_type = "text/plain; charset=UTF-8"

        elif f == "html":
            content_type = "text/html; charset=UTF-8"

        elif f == "xml":
            content_type = "text/xml; charset=UTF-8"

        elif f == "pdf":
            content_type = "application/pdf"

        else:
            raise MKGeneralException(_("Unsupported context type '%s'") % f)
        self.set_content_type(content_type)


    def set_content_type(self, ty):
        raise NotImplementedError()


    def set_link_target(self, framename):
        self.link_target = framename


    def set_focus(self, varname):
        self.focus_object = (self.form_name, varname)


    def set_render_headfoot(self, render):
        self.render_headfoot = render


    def set_browser_reload(self, secs):
        self.browser_reload = secs


    def set_browser_redirect(self, secs, url):
        self.browser_reload   = secs
        self.browser_redirect = url


    def immediate_browser_redirect(self, secs, url):
        self.javascript("set_reload(%s, '%s');" % (secs, url))


    def add_body_css_class(self, cls):
        self.body_classes.append(cls)


    def add_status_icon(self, img, tooltip, url = None):
        if url:
            self.status_icons[img] = tooltip, url
        else:
            self.status_icons[img] = tooltip


    def final_javascript(self, code):
        self.final_javascript_code += code + "\n"


    def reload_sidebar(self):
        if not self.has_var("_ajaxid"):
            self.javascript("reload_sidebar()")


    def http_redirect(self, url):
        raise MKGeneralException("http_redirect not implemented")


    #
    # Request processing
    #

    def get_unicode_input(self, varname, deflt = None):
        try:
            return self.var_utf8(varname, deflt)
        except UnicodeDecodeError:
            raise MKUserError(varname, _("The given text is wrong encoded. "
                                         "You need to provide a UTF-8 encoded text."))


    def var(self, varname, deflt = None):
        return self.vars.get(varname, deflt)


    def has_var(self, varname):
        return varname in self.vars


    # Checks if a variable with a given prefix is present
    def has_var_prefix(self, prefix):
        for varname in self.vars:
            if varname.startswith(prefix):
                return True
        return False


    def var_utf8(self, varname, deflt = None):
        val = self.vars.get(varname, deflt)
        if val != None and type(val) != unicode:
            return val.decode("utf-8")
        else:
            return val


    def all_vars(self):
        return self.vars


    def all_varnames_with_prefix(self, prefix):
        for varname in self.vars.keys():
            if varname.startswith(prefix):
                yield varname


    # Return all values of a variable that possible occurs more
    # than once in the URL. note: self.listvars does contain those
    # variable only, if the really occur more than once.
    def list_var(self, varname):
        if varname in self.listvars:
            return self.listvars[varname]
        elif varname in self.vars:
            return [self.vars[varname]]
        else:
            return []


    # Adds a variable to listvars and also set it
    def add_var(self, varname, value):
        self.listvars.setdefault(varname, [])
        self.listvars[varname].append(value)
        self.vars[varname] = value


    def set_var(self, varname, value):
        if value == None:
            self.del_var(varname)
        else:
            self.vars[varname] = value


    def del_var(self, varname):
        if varname in self.vars:
            del self.vars[varname]
        if varname in self.listvars:
            del self.listvars[varname]


    def del_all_vars(self, prefix = None):
        if not prefix:
            self.vars = {}
            self.listvars = {}
        else:
            self.vars = dict([(k,v) for (k,v) in self.vars.iteritems()
                                            if not k.startswith(prefix)])
            self.listvars = dict([(k,v) for (k,v) in self.listvars.iteritems()
                                            if not k.startswith(prefix)])


    def stash_vars(self):
        self.var_stash.append(self.vars.copy())


    def unstash_vars(self):
        self.vars = self.var_stash.pop()


    def uploaded_file(self, varname, default = None):
        return self.uploads.get(varname, default)


    # Returns a dictionary containing all parameters the user handed over to this request.
    # The concept is that the user can either provide the data in a single "request" variable,
    # which contains the request data encoded as JSON, or provide multiple GET/POST vars which
    # are then used as top level entries in the request object.
    def get_request(self, exclude_vars=None):
        if exclude_vars == None:
            exclude_vars = []

        request = json.loads(self.var("request", "{}"))

        for key, val in self.all_vars().items():
            if key not in [ "request", "output_format" ] + exclude_vars:
                request[key] = val

        return request


    def parse_field_storage(self, fields, handle_uploads_as_file_obj = False):
        self.vars     = {}
        self.listvars = {} # for variables with more than one occurrance
        self.uploads  = {}

        # TODO: Fix this regex. +-\ selects all from + to \, not +, - and \!
        varname_regex = re.compile('^[\w\d_.%+-\\\*]+$')

        for field in fields.list:
            varname = field.name

            # To prevent variours injections, we only allow a defined set
            # of characters to be used in variables
            if not varname_regex.match(varname):
                continue

            # put uploaded file infos into separate storage
            if field.filename is not None:
                if handle_uploads_as_file_obj:
                    value = field.file
                else:
                    value = field.value
                self.uploads[varname] = (field.filename, field.type, value)

            else: # normal variable
                # Multiple occurrance of a variable? Store in extra list dict
                if varname in self.vars:
                    if varname in self.listvars:
                        self.listvars[varname].append(field.value)
                    else:
                        self.listvars[varname] = [ self.vars[varname], field.value ]
                # In the single-value-store the last occurrance of a variable
                # has precedence. That makes appending variables to the current
                # URL simpler.
                self.vars[varname] = field.value



    #
    # Cookie handling
    #

    def has_cookie(self, varname):
        return varname in self.cookies


    def get_cookie_names(self):
        return self.cookies.keys()


    def cookie(self, varname, deflt):
        try:
            return self.cookies[varname].value
        except:
            return deflt


    #
    # URL building
    #

    # [('varname1', value1), ('varname2', value2) ]
    def makeuri(self, addvars, remove_prefix=None, filename=None, delvars=None):
        new_vars = [ nv[0] for nv in addvars ]
        vars = [ (v, self.var(v))
                 for v in self.vars
                 if v[0] != "_" and v not in new_vars and (not delvars or v not in delvars) ]
        if remove_prefix != None:
            vars = [ i for i in vars if not i[0].startswith(remove_prefix) ]
        vars = vars + addvars
        if filename == None:
            filename = self.urlencode(self.myfile) + ".py"
        if vars:
            return filename + "?" + self.urlencode_vars(vars)
        else:
            return filename


    def makeuri_contextless(self, vars, filename=None):
        if not filename:
            filename = self.myfile + ".py"
        if vars:
            return filename + "?" + self.urlencode_vars(vars)
        else:
            return filename


    def makeactionuri(self, addvars, filename=None):
        return self.makeuri(addvars + [("_transid", self.get_transid())], filename=filename)


    def makeactionuri_contextless(self, addvars, filename=None):
        return self.makeuri_contextless(addvars + [("_transid", self.get_transid())], filename=filename)


    #
    # Encoding and escaping
    #

    # This function returns a str object, never unicode!
    # Beware: this code is crucial for the performance of Multisite!
    # Changing from the self coded urlencode to urllib.quote
    # is saving more then 90% of the total HTML generating time
    # on more complex pages!
    def urlencode_vars(self, vars):
        output = []
        for varname, value in sorted(vars):
            if type(value) == int:
                value = str(value)
            elif type(value) == unicode:
                value = value.encode("utf-8")

            try:
                # urllib is not able to encode non-Ascii characters. Yurks
                output.append(varname + '=' + urllib.quote(value))
            except:
                output.append(varname + '=' + self.urlencode(value)) # slow but working

        return '&'.join(output)


    def urlencode(self, value):
        if type(value) == unicode:
            value = value.encode("utf-8")
        elif value == None:
            return ""
        ret = ""
        for c in value:
            if c == " ":
                c = "+"
            elif ord(c) <= 32 or ord(c) > 127 or c in [ '#', '+', '"', "'", "=", "&", ":", "%" ]:
                c = "%%%02x" % ord(c)
            ret += c
        return ret


    # Escape a variable name so that it only uses allowed charachters for URL variables
    def varencode(self, varname):
        if varname == None:
            return "None"
        if type(varname) == int:
            return varname

        ret = ""
        for c in varname:
            if not c.isdigit() and not c.isalnum() and c != "_":
                ret += "%%%02x" % ord(c)
            else:
                ret += c
        return ret


    def u8(self, c):
        if ord(c) > 127:
            return "&#%d;" % ord(c)
        else:
            return c


    def utf8_to_entities(self, text):
        if type(text) != unicode:
            return text
        else:
            return text.encode("utf-8")


    # remove all HTML-tags
    def strip_tags(self, ht):
        if type(ht) not in [str, unicode]:
            return ht
        while True:
            x = ht.find('<')
            if x == -1:
                break
            y = ht.find('>', x)
            if y == -1:
                break
            ht = ht[0:x] + ht[y+1:]
        return ht.replace("&nbsp;", " ")


    def strip_scripts(self, ht):
        while True:
            x = ht.find('<script')
            if x == -1:
                break
            y = ht.find('</script>')
            if y == -1:
                break
            ht = ht[0:x] + ht[y+9:]
        return ht


    #
    # Debugging, diagnose and logging
    #

    def debug(self, *x):
        import pprint
        for element in x:
            try:
                formatted = pprint.pformat(element)
            except UnicodeDecodeError:
                formatted = repr(element)
            self.lowlevel_write("<pre>%s</pre>\n" % self.attrencode(formatted))


    def log(self, *args):
        raise NotImplementedError()




    #
    # HTML form rendering
    #

    def begin_form(self, name, action = None, method = "GET",
                   onsubmit = None, add_transid = True):
        self.form_vars = []
        if action == None:
            action = self.myfile + ".py"
        self.current_form = name
        if method.lower() == "post":
            enctype = ' enctype="multipart/form-data"'
        else:
            enctype = ''
        if onsubmit:
            onsubmit = ' onsubmit="%s"' % self.attrencode(onsubmit)
        else:
            onsubmit = ''
        enc_name = self.attrencode(name)
        self.write('<form id="form_%s" name="%s" class="%s" action="%s" method="%s"%s%s>\n' %
                   (enc_name, enc_name, enc_name, self.attrencode(action), self.attrencode(method),
                    enctype, onsubmit))
        self.hidden_field("filled_in", name, add_var=True)
        if add_transid:
            self.hidden_field("_transid", str(self.get_transid()))
        self.form_name = name


    def end_form(self):
        self.write("</form>\n")
        self.form_name = None


    def in_form(self):
        return self.form_name != None


    def prevent_password_auto_completion(self):
        # These fields are not really used by the form. They are used to prevent the browsers
        # from filling the default password and previous input fields in the form
        # with password which are eventually saved in the browsers password store.
        self.write("<input type=\"text\" style=\"display:none;\">")
        self.write("<input style=\"display:none\" type=\"password\">")


    # Needed if input elements are put into forms without the helper
    # functions of us. TODO: Should really be removed and cleaned up!
    def add_form_var(self, varname):
        self.form_vars.append(varname)


    # Beware: call this method just before end_form(). It will
    # add all current non-underscored HTML variables as hiddedn
    # field to the form - *if* they are not used in any input
    # field. (this is the reason why you must not add any further
    # input fields after this method has been called).
    def hidden_fields(self, varlist = None, **args):
        add_action_vars = args.get("add_action_vars", False)
        if varlist != None:
            for var in varlist:
                value = self.vars.get(var, "")
                self.hidden_field(var, value)
        else: # add *all* get variables, that are not set by any input!
            for var, value in self.vars.items():
                if var not in self.form_vars and \
                    (var[0] != "_" or add_action_vars): # and var != "filled_in":
                    self.hidden_field(var, value)


    def hidden_field(self, *args, **kwargs):
        self.write(self.render_hidden_field(*args, **kwargs))


    def render_hidden_field(self, var, value, id=None, add_var=False):
        if value == None:
            return ""

        if add_var:
            self.add_form_var(var)

        id = id and ' id="%s"' % self.attrencode(id) or ''
        return "<input type=\"hidden\" name=\"%s\" value=\"%s\"%s />" % \
                            (self.attrencode(var), self.attrencode(value), id)


    def image_button(self, varname, title, cssclass = '', style=None):
        if not self.mobile:
            self.write('<label for="%s" class="image_button"%s>' %
               (self.attrencode(varname), style and (" style=\"%s\"" % style) or ""))
        self.raw_button(varname, title, cssclass)
        if not self.mobile:
            self.write('</label>')


    def button(self, *args, **kwargs):
        self.image_button(*args, **kwargs)


    def raw_button(self, varname, title, cssclass=""):
        self.write("<input onfocus=\"if (this.blur) this.blur();\" "
                   "type=\"submit\" name=\"%s\" id=\"%s\" value=\"%s\" "
                   "class=\"%s\" />\n" % \
                   (varname, varname, title, cssclass))
        self.add_form_var(varname)


    def buttonlink(self, href, text, add_transid=False, obj_id='', style='', title='', disabled=''):
        if add_transid:
            href += "&_transid=%s" % self.get_transid()
        if not obj_id:
            obj_id = self.some_id()
        obj_id = ' id=%s' % obj_id
        if style:
            style = ' style="%s"' % style
        if title:
            title = ' title="%s"' % title
        if disabled:
            title = ' disabled="%s"' % disabled

        if not self.mobile:
            self.write('<label for="%s" class="image_button">' % obj_id)
        self.write('<input%s%s%s%s value="%s" class="buttonlink" type="button" onclick="location.href=\'%s\'" />\n' % \
                (obj_id, style, title, disabled, text, href))
        if not self.mobile:
            self.write('</label>')



    def empty_icon_button(self):
        self.write(self.render_icon("images/trans.png", cssclass="iconbutton trans"))


    def disabled_icon_button(self, icon):
        self.write(self.render_icon(icon, cssclass="iconbutton"))


    def jsbutton(self, varname, text, onclick, style=''):
        if style:
            style = ' style="%s"' % style
        self.write("<input type=button name=%s id=%s onclick=\"%s\" "
                   "class=button%s value=\"%s\" />" % (varname, varname, onclick, style, text))


    def number_input(self, varname, deflt = "", size=8, style="", submit=None):
        if deflt != None:
            deflt = str(deflt)
        self.text_input(varname, deflt, "number", size=size, style=style, submit=submit)


    def text_input(self, varname, default_value = "", cssclass = "text", label = None, id = None,
                   submit = None, attrs = {}, **args):
        if default_value == None:
            default_value = ""
        addprops = ""
        add_style = ""
        if "size" in args and args["size"]:
            if args["size"] == "max":
                add_style = "width: 100%; "
            else:
                addprops += " size=\"%d\"" % (args["size"] + 1)
                if not args.get('omit_css_width', False) and "width:" not in args.get("style", "") and not self.mobile:
                    add_style = "width: %d.8ex; " % args["size"]

        if "type" in args:
            mytype = args["type"]
        else:
            mytype = "text"
        if "autocomplete" in args:
            addprops += " autocomplete=\"%s\"" % args["autocomplete"]
        if args.get("style"):
            addprops += " style=\"%s%s\"" % (add_style, args["style"])
        elif add_style:
            addprops += " style=\"%s\"" % add_style
        if args.get("read_only"):
            addprops += " readonly"

        if submit != None:
            if not id:
                id = "ti_%s" % varname
            self.final_javascript('document.getElementById("%s").onkeydown = '
                             'function(e) { if (!e) e = window.event; textinput_enter_submit(e, "%s"); };'
                             % (id, submit))

        value = self.vars.get(varname, default_value)
        error = self.user_errors.get(varname)
        html = ""
        if error:
            html = "<x class=\"inputerror\">"
        if label:
            if not id:
                id = "ti_%s" % varname
            html += '<label for="%s">%s</label>' % (id, label)

        if id:
            addprops += ' id="%s"' % id

        attributes = ' ' + ' '.join([ '%s="%s"' % (k, self.attrencode(v)) for k, v in attrs.iteritems() ])
        html += "<input type=\"%s\" class=\"%s\" value=\"%s\" name=\"%s\"%s%s />\n" % \
                     (mytype, cssclass, self.attrencode(value), varname, addprops, attributes)
        if error:
            html += "</x>"
            self.set_focus(varname)
        self.write(html)
        self.form_vars.append(varname)


    def password_input(self, varname, default_value = "", size=12, **args):
        self.text_input(varname, default_value, type="password", size = size, **args)


    def text_area(self, varname, deflt="", rows=4, cols=30, attrs = {}):
        value = self.var(varname, deflt)
        error = self.user_errors.get(varname)
        if error:
            self.write("<x class=inputerror>")

        attributes = ' ' + ' '.join([ '%s="%s"' % (k, v) for k, v in attrs.iteritems() ])
        self.write("<textarea style=\"width: %d.8ex\" rows=%d cols=%d name=\"%s\"%s>%s</textarea>\n" % (
            cols, rows, cols, varname, attributes, self.attrencode(value)))
        if error:
            self.write("</x>")
            self.set_focus(varname)
        self.form_vars.append(varname)


    def sorted_select(self, varname, choices, deflt="", onchange=None, attrs = {}):
        # Sort according to display texts, not keys
        sorted = choices[:]
        sorted.sort(lambda a,b: cmp(a[1].lower(), b[1].lower()))
        self.select(varname, sorted, deflt, onchange, attrs)


    # Choices is a list pairs of (key, title). They keys of the choices
    # and the default value must be of type None, str or unicode.
    def select(self, varname, choices, deflt="", onchange=None, attrs = {}):
        current = self.get_unicode_input(varname, deflt)
        onchange_code = onchange and " onchange=\"%s\"" % (onchange) or ""
        attrs.setdefault('size', 1)
        attributes = ' ' + ' '.join([ '%s="%s"' % (k, v) for k, v in attrs.iteritems() ])

        error = self.user_errors.get(varname)
        if error:
            self.write("<x class=\"inputerror\">")
        self.write("<select%s name=\"%s\" id=\"%s\"%s>\n" %
                             (onchange_code, varname, varname, attributes))
        for value, text in choices:
            if value == None:
                value = ""
            sel = value == current and " selected" or ""
            self.write("<option value=\"%s\"%s>%s</option>\n" %
                (self.attrencode(value), sel, self.attrencode(text)))
        self.write("</select>\n")
        if error:
            self.write("<x class=\"inputerror\">")
        if varname:
            self.form_vars.append(varname)


    def icon_select(self, varname, options, deflt=""):
        current = self.var(varname, deflt)
        self.write("<select class=icon name=\"%s\" id=\"%s\" size=\"1\">\n" %
                    (varname, varname))
        for value, text, icon in options:
            if value == None: value = ""
            sel = value == current and " selected" or ""
            self.write('<option style="background-image:url(images/icon_%s.png);" '
                       'value=\"%s\"%s>%s</option>\n' %
                        (icon, self.attrencode(value), sel, self.attrencode(text)))
        self.write("</select>\n")
        if varname:
            self.form_vars.append(varname)


    def begin_radio_group(self, horizontal=False):
        if self.mobile:
            if horizontal:
                add = 'data-type="horizontal" '
            else:
                add = ''
            self.write('<fieldset %s data-role="controlgroup">' % add)


    def end_radio_group(self):
        if self.mobile:
            self.write('</fieldset>')


    def radiobutton(self, varname, value, checked, label):
        if self.has_var(varname):
            checked = self.var(varname) == value
        checked_text = checked and " checked" or ""
        if label:
            id = "rb_%s_%s" % (varname, self.attrencode(value))
            idtxt = ' id="%s"' % id
        else:
            idtxt = ""
        self.write("<input type=radio name=%s value=\"%s\"%s%s>\n" %
                      (varname, self.attrencode(value), checked_text, idtxt))
        if label:
            self.write('<label for="%s">%s</label>\n' % (id, label))
        self.form_vars.append(varname)


    def begin_checkbox_group(self, horizonal=False):
        self.begin_radio_group(horizonal)


    def end_checkbox_group(self):
        self.end_radio_group()


    def checkbox(self, *args, **kwargs):
        self.write(self.render_checkbox(*args, **kwargs))


    def render_checkbox(self, varname, deflt=False, cssclass = '', onclick = None, label=None,
                        id=None, add_attr = None):
        if add_attr == None:
            add_attr = [] # do not use [] as default element, it will be a global variable!
        code = ""
        error = self.user_errors.get(varname)
        if error:
            code += "<x class=inputerror>"

        code += "<span class=checkbox>"
        # Problem with checkboxes: The browser will add the variable
        # only to the URL if the box is checked. So in order to detect
        # wether we should add the default value, we need to detect
        # if the form is printed for the first time. This is the
        # case if "filled_in" is not set.
        value = self.get_checkbox(varname)
        if value == None: # form not yet filled in
             value = deflt

        checked = value and " CHECKED " or ""
        if cssclass:
            cssclass = ' class="%s"' % cssclass
        onclick_code = onclick and " onclick=\"%s\"" % (onclick) or ""
        if label and not id:
            id = "cb_" + varname
        if id:
            add_attr.append('id="%s"' % id)
        add_attr_code = ''
        if add_attr:
            add_attr_code = ' ' + ' '.join(add_attr)
        code += "<input type=checkbox name=\"%s\"%s%s%s%s>\n" % \
                        (varname, checked, cssclass, onclick_code, add_attr_code)
        self.form_vars.append(varname)
        if label:
            code += '<label for="%s">%s</label>\n' % (id, label)
        code += "</span>"
        if error:
            code += "</x>"

        return code


    def upload_file(self, varname):
        error = self.user_errors.get(varname)
        if error:
            self.write("<x class=inputerror>")
        self.write('<input type="file" name="%s">' % varname)
        if error:
            self.write("</x>")
        self.form_vars.append(varname)


    def show_user_errors(self):
        if self.has_user_errors():
            self.write('<div class=error>\n')
            self.write('<br>'.join(self.user_errors.values()))
            self.write('</div>\n')


    # The confirm dialog is normally not a dialog which need to be protected
    # by a transid itselfs. It is only a intermediate step to the real action
    # But there are use cases where the confirm dialog is used during rendering
    # a normal page, for example when deleting a dashlet from a dashboard. In
    # such cases, the transid must be added by the confirm dialog.
    # add_header: A title can be given to make the confirm method render the HTML
    #             header when showing the confirm message.
    def confirm(self, msg, method="POST", action=None, add_transid=False, add_header=False):
        if self.var("_do_actions") == _("No"):
            # User has pressed "No", now invalidate the unused transid
            self.check_transaction()
            return # None --> "No"

        if not self.has_var("_do_confirm"):
            if add_header != False:
                self.header(add_header)

            if self.mobile:
                self.write('<center>')
            self.write("<div class=really>%s" % self.permissive_attrencode(msg))
            # FIXME: When this confirms another form, use the form name from self.vars()
            self.begin_form("confirm", method=method, action=action, add_transid=add_transid)
            self.hidden_fields(add_action_vars = True)
            self.button("_do_confirm", _("Yes!"), "really")
            self.button("_do_actions", _("No"), "")
            self.end_form()
            self.write("</div>")
            if self.mobile:
                self.write('</center>')

            return False # False --> "Dialog shown, no answer yet"
        else:
            # Now check the transaction
            return self.check_transaction() and True or None # True: "Yes", None --> Browser reload of "yes" page

    #
    # Form submission and variable handling
    #

    # Check if the current form is currently filled in (i.e. we display
    # the form a second time while showing value typed in at the first
    # time and complaining about invalid user input)
    def form_filled_in(self, form_name = None):
        if form_name == None:
            form_name = self.form_name

        return self.has_var("filled_in") and (
            form_name == None or \
            form_name in self.list_var("filled_in"))


    def do_actions(self):
        return self.var("_do_actions") not in [ "", None, _("No") ]


    def form_submitted(self, form_name=None):
        if form_name:
            return self.var("filled_in") == form_name
        else:
            return self.has_var("filled_in")


    def add_user_error(self, varname, msg_or_exc):
        if isinstance(msg_or_exc, Exception):
            message = "%s" % msg_or_exc
        else:
            message = msg_or_exc

        if type(varname) == list:
            for v in varname:
                self.add_user_error(v, message)
        else:
            self.user_errors[varname] = message


    def has_user_errors(self):
        return len(self.user_errors) > 0


    # Get value of checkbox. Return True, False or None. None means
    # that no form has been submitted. The problem here is the distintion
    # between False and None. The browser does not set the variables for
    # Checkboxes that are not checked :-(
    def get_checkbox(self, varname, form_name = None):
        if self.has_var(varname):
            return not not self.var(varname)
        elif not self.form_filled_in(form_name):
            return None
        else:
            # Form filled in but variable missing -> Checkbox not checked
            return False


    # TODO: Remove this specific legacy function. Change code using this to valuespecs
    def datetime_input(self, varname, default_value, submit=None):
        try:
            t = self.get_datetime_input(varname)
        except:
            t = default_value

        if varname in self.user_errors:
            self.add_user_error(varname + "_date", self.user_errors[varname])
            self.add_user_error(varname + "_time", self.user_errors[varname])
            self.set_focus(varname + "_date")

        br = time.localtime(t)
        self.date_input(varname + "_date", br.tm_year, br.tm_mon, br.tm_mday, submit=submit)
        self.write(" ")
        self.time_input(varname + "_time", br.tm_hour, br.tm_min, submit=submit)
        self.form_vars.append(varname + "_date")
        self.form_vars.append(varname + "_time")


    # TODO: Remove this specific legacy function. Change code using this to valuespecs
    def time_input(self, varname, hours, mins, submit=None):
        self.text_input(varname, "%02d:%02d" % (hours, mins), cssclass="time", size=5,
                        submit=submit, omit_css_width = True)


    # TODO: Remove this specific legacy function. Change code using this to valuespecs
    def date_input(self, varname, year, month, day, submit=None):
        self.text_input(varname, "%04d-%02d-%02d" % (year, month, day),
                        cssclass="date", size=10, submit=submit, omit_css_width = True)


    # TODO: Remove this specific legacy function. Change code using this to valuespecs
    def get_datetime_input(self, varname):
        t = self.var(varname + "_time")
        d = self.var(varname + "_date")
        if not t or not d:
            raise MKUserError([varname + "_date", varname + "_time"],
                              _("Please specify a date and time."))

        try:
            br = time.strptime(d + " " + t, "%Y-%m-%d %H:%M")
        except:
            raise MKUserError([varname + "_date", varname + "_time"],
                              _("Please enter the date/time in the format YYYY-MM-DD HH:MM."))
        return int(time.mktime(br))


    # TODO: Remove this specific legacy function. Change code using this to valuespecs
    def get_time_input(self, varname, what):
        t = self.var(varname)
        if not t:
            raise MKUserError(varname, _("Please specify %s.") % what)

        try:
            h, m = t.split(":")
            m = int(m)
            h = int(h)
            if m < 0 or m > 59 or h < 0:
                raise Exception()
        except:
            raise MKUserError(varname, _("Please enter the time in the format HH:MM."))
        return m * 60 + h * 3600


    #
    # HTML - All the common and more complex HTML rendering methods
    #

    def show_info(self, msg):
        self.message(msg, 'message')


    def show_error(self, msg):
        self.message(msg, 'error')


    def show_warning(self, msg):
        self.message(msg, 'warning')


    # obj might be either a string (str or unicode) or an exception object
    def message(self, obj, what='message'):
        if what == 'message':
            cls    = 'success'
            prefix = _('MESSAGE')
        elif what == 'warning':
            cls    = 'warning'
            prefix = _('WARNING')
        else:
            cls    = 'error'
            prefix = _('ERROR')

        msg = self.permissive_attrencode(obj)

        if self.output_format == "html":
            if self.mobile:
                self.write('<center>')
            self.write("<div class=%s>%s</div>\n" % (cls, msg))
            if self.mobile:
                self.write('</center>')
        else:
            self.write('%s: %s\n' % (prefix, self.strip_tags(msg)))

        #self.guitest_record_output("message", (what, msg))


    def show_localization_hint(self):
        url = "wato.py?mode=edit_configvar&varname=user_localizations"
        self.message(HTML("<sup>*</sup>" +
            _("These texts may be localized depending on the users' "
              "language. You can configure the localizations "
              "<a href=\"%s\">in the global settings</a>.") % url))


    # Embed help box, whose visibility is controlled by a global
    # button in the page.
    def help(self, text):
        if text and text.strip():
            self.have_help = True
            self.write('<div class=help style="display: %s">' % (
                        not self.help_visible and "none" or "block"))
            self.write(text.strip())
            self.write('</div>')

    def _dump_get_vars(self):
        self.begin_foldable_container("html", "debug_vars", True, _("GET/POST variables of this page"))
        self.debug_vars(hide_with_mouse = False)
        self.end_foldable_container()


    def footer(self):
        if self.output_format == "html":
            self.bottom_footer()
            self.body_end()


    def bottom_footer(self):
        if self.header_sent:
            self.bottom_focuscode()
            if self.render_headfoot:
                self.write("<table class=footer><tr>")

                self.write("<td class=left>")
                self._write_status_icons()
                self.write("</td>")

                self.write("<td class=middle></td>"
                           "<td class=right>")
                self.write("<div style=\"display:%s\" id=foot_refresh>%s</div>" % (
                        (self.browser_reload and "inline-block" or "none",
                     _("refresh: <div id=foot_refresh_time>%s</div> secs") % self.browser_reload)))
                self.write("</td></tr></table>")


    def bottom_focuscode(self):
        if self.focus_object:
            formname, varname = self.focus_object
            obj = formname + "." + varname
            self.write("<script language=\"javascript\" type=\"text/javascript\">\n"
                           "<!--\n"
                           "if (document.%s) {"
                           "    document.%s.focus();\n"
                           "    document.%s.select();\n"
                           "}\n"
                           "// -->\n"
                           "</script>\n" % (obj, obj, obj))


    def body_end(self):
        if self.have_help:
            self.javascript("enable_help();")
        if self.keybindings_enabled and self.keybindings:
            self.javascript("var keybindings = %s;\n"
                            "document.body.onkeydown = keybindings_keydown;\n"
                            "document.body.onkeyup = keybindings_keyup;\n"
                            "document.body.onfocus = keybindings_focus;\n" %
                                json.dumps(self.keybindings))
        if self.final_javascript_code:
            self.javascript(self.final_javascript_code)
        self.write("</body></html>\n")

        # Hopefully this is the correct place to performe some "finalization" tasks.
        self.store_new_transids()


    def popup_trigger(self, *args, **kwargs):
        self.write(self.render_popup_trigger(*args, **kwargs))


    def render_popup_trigger(self, content, ident, what=None, data=None, url_vars=None,
                             style=None, menu_content=None, cssclass=None, onclose=None):
        style = style and (' style="%s"' % style) or ""
        src = '<div class="popup_trigger%s" id="popup_trigger_%s"%s>\n' % (cssclass and (" " + cssclass) or "", ident, style)
        onclick = 'toggle_popup(event, this, \'%s\', %s, %s, %s, %s, %s)' % \
                    (ident, what and  "'"+what+"'" or 'null',
                     data and self.attrencode(json.dumps(data)) or 'null',
                     url_vars and "'"+self.urlencode_vars(url_vars)+"'" or 'null',
                     menu_content and "'"+self.attrencode(menu_content)+"'" or 'null',
                     onclose and "'%s'" % onclose.replace("'", "\\'") or 'null')
        src += '<a class="popup_trigger" href="javascript:void(0)" onclick="%s">\n' % onclick
        src += content
        src += '</a>'
        src += '</div>\n'
        return src


    def _write_status_icons(self):
        self.icon_button(self.makeuri([]), _("URL to this frame"),
                         "frameurl", target="_top", cssclass="inline")
        self.icon_button("index.py?" + self.urlencode_vars([("start_url", self.makeuri([]))]),
                         _("URL to this page including sidebar"),
                         "pageurl", target="_top", cssclass="inline")

        # TODO: Move this away from here. Make a context button. The view should handle this
        if self.myfile == "view" and self.var('mode') != 'availability':
            self.icon_button(self.makeuri([("output_format", "csv_export")]),
                             _("Export as CSV"),
                             "download_csv", target="_top", cssclass="inline")

        if self.myfile == "view":
            mode_name = self.var('mode') == "availability" and "availability" or "view"

            encoded_vars = {}
            for k, v in self.page_context.items():
                if v == None:
                    v = ''
                elif type(v) == unicode:
                    v = v.encode('utf-8')
                encoded_vars[k] = v

            self.popup_trigger(
                self.render_icon("menu", _("Add this view to..."), cssclass="iconbutton inline"),
                'add_visual', 'add_visual', data=[mode_name, encoded_vars, {'name': self.var('view_name')}],
                url_vars=[("add_type", "view")])

        for img, tooltip in self.status_icons.items():
            if type(tooltip) == tuple:
                tooltip, url = tooltip
                self.icon_button(url, tooltip, img, cssclass="inline")
            else:
                self.icon(tooltip, img, cssclass="inline")

        if self.times:
            self.measure_time('body')
            self.write('<div class=execution_times>')
            entries = self.times.items()
            entries.sort()
            for name, duration in entries:
                self.write("<div>%s: %.1fms</div>" % (name, duration * 1000))
            self.write('</div>')


    def debug_vars(self, prefix=None, hide_with_mouse=True, vars=None):
        if not vars:
            vars = self.vars

        if hide_with_mouse:
            hover = ' onmouseover="this.style.display=\'none\';"'
        else:
            hover = ""

        self.write('<table %s class=debug_vars>' % hover)
        self.write("<tr><th colspan=2>"+_("POST / GET Variables")+"</th></tr>")
        for name, value in sorted(vars.items()):
            if name in [ "_password", "password" ]:
                value = "***"
            if not prefix or name.startswith(prefix):
                self.write("<tr><td class=left>%s</td><td class=right>%s</td></tr>\n" %
                    (self.attrencode(name), self.attrencode(value)))
        self.write("</table>")


    def begin_context_buttons(self):
        if not self.context_buttons_open:
            self.context_button_hidden = False
            self.write("<table class=contextlinks><tr><td>\n")
            self.context_buttons_open = True


    def end_context_buttons(self):
        if self.context_buttons_open:
            if self.context_button_hidden:
                self.write('<div title="%s" id=toggle class="contextlink short" '
                      % _("Show all buttons"))
                self._context_button_hover_code("_short")
                self.write("><a onclick='unhide_context_buttons(this);' href='#'>...</a></div>")
            self.write("</td></tr></table>\n")
        self.context_buttons_open = False


    def context_button(self, title, url, icon=None, hot=False, id=None, bestof=None, hover_title='', fkey=None):
        #self.guitest_record_output("context_button", (title, url, icon))
        title = self.attrencode(title)
        display = "block"
        if bestof:
            counts = self.get_button_counts()
            weights = counts.items()
            weights.sort(cmp = lambda a,b: cmp(a[1],  b[1]))
            best = dict(weights[-bestof:])
            if id not in best:
                display="none"
                self.context_button_hidden = True

        if not self.context_buttons_open:
            self.begin_context_buttons()

        title = "<span>%s</span>" % self.attrencode(title)
        if icon:
            title = '%s%s' % (self.render_icon(icon, cssclass="inline", middle=False), title)

        if id:
            idtext = " id='%s'" % self.attrencode(id)
        else:
            idtext = ""
        self.write('<div%s style="display:%s" class="contextlink%s%s" ' %
            (idtext, display, hot and " hot" or "", (fkey and self.keybindings_enabled) and " button" or ""))
        self._context_button_hover_code(hot and "_hot" or "")
        self.write('>')
        self.write('<a href="%s"' % self.attrencode(url))
        if hover_title:
            self.write(' title="%s"' % self.attrencode(hover_title))
        if bestof:
            self.write(' onclick="count_context_button(this); " ')
        if fkey and self.keybindings_enabled:
            title += '<div class=keysym>F%d</div>' % fkey
            self.add_keybinding([html.F1 + (fkey - 1)], "document.location='%s';" % self.attrencode(url))
        self.write('>%s</a></div>\n' % title)


    def get_button_counts(self):
        raise NotImplementedError()


    def _context_button_hover_code(self, what):
        self.write(r'''onmouseover='this.style.backgroundImage="url(\"images/contextlink%s_hi.png\")";' ''' % what)
        self.write(r'''onmouseout='this.style.backgroundImage="url(\"images/contextlink%s.png\")";' ''' % what)


    def begin_foldable_container(self, treename, id, isopen, title, indent=True,
                                 first=False, icon=None, fetch_url=None, title_url=None,
                                 tree_img="tree"):
        self.folding_indent = indent

        if self._user_id:
            isopen = self.foldable_container_is_open(treename, id, isopen)

        onclick = ' onclick="toggle_foldable_container(\'%s\', \'%s\', \'%s\')"' % (
               treename, id, fetch_url and fetch_url or '');

        if indent == "nform":
            self.write('<tr class=heading><td id="nform.%s.%s" %s colspan=2>' % (treename, id, onclick))
            if icon:
                self.write('<img class="treeangle title" src="images/icon_%s.png">' % self.attrencode(icon))
            else:
                self.write('<img align=absbottom class="treeangle nform %s" src="images/%s_closed.png">' %
                                                ("open" if isopen else "closed", tree_img))
            self.write('%s</td></tr>' % self.attrencode(title))
        else:
            if not icon:
                self.write('<img align=absbottom class="treeangle %s" id="treeimg.%s.%s" '
                           'src="images/%s_closed.png" %s>' %
                        ("open" if isopen else "closed", treename, id, tree_img, onclick))
            if isinstance(title, HTML): # custom HTML code
                self.write(self.attrencode(title))
                if indent != "form":
                    self.write("<br>")
            else:
                self.write('<b class="treeangle title" %s>' % (not title_url and onclick or ""))
                if icon:
                    self.write('<img class="treeangle title" src="images/icon_%s.png">' % self.attrencode(icon))
                if title_url:
                    self.write('<a href="%s">%s</a>' % (self.attrencode(title_url), self.attrencode(title)))
                else:
                    self.write(self.attrencode(title))
                self.write('</b><br>')

            indent_style = "padding-left: %dpx; " % (indent == True and 15 or 0)
            if indent == "form":
                self.write("</td></tr></table>")
                indent_style += "margin: 0; "
            self.write('<ul class="treeangle %s" style="%s" id="tree.%s.%s">' %
                 (isopen and "open" or "closed", indent_style,  treename, id))

        # give caller information about current toggling state (needed for nform)
        return isopen


    def end_foldable_container(self):
        if self.folding_indent != "nform":
            self.write("</ul>")


    def foldable_container_is_open(self, treename, id, isopen):
        # try to get persisted state of tree
        tree_state = self.get_tree_states(treename)

        if id in tree_state:
            isopen = tree_state[id] == "on"
        return isopen


    #
    # Tree states
    #

    def get_tree_states(self, tree):
        self.load_tree_states()
        return self.treestates.get(tree, {})


    def set_tree_state(self, tree, key, val):
        self.load_tree_states()

        if tree not in self.treestates:
            self.treestates[tree] = {}

        self.treestates[tree][key] = val


    def set_tree_states(self, tree, val):
        self.load_tree_states()
        self.treestates[tree] = val


    def load_tree_states(self):
        raise NotImplementedError()


    def save_tree_states(self):
        raise NotImplementedError()


    #
    # Transaction IDs
    #

    def set_ignore_transids(self):
        self.ignore_transids = True


    # Compute a (hopefully) unique transaction id. This is generated during rendering
    # of a form or an action link, stored in a user specific file for later validation,
    # sent to the users browser via HTML code, then submitted by the user together
    # with the action (link / form) and then validated if it is a known transid. When
    # it is a known transid, it will be used and invalidated. If the id is not known,
    # the action will not be processed.
    def fresh_transid(self):
        transid = "%d/%d" % (int(time.time()), random.getrandbits(32))
        self.new_transids.append(transid)
        return transid


    def get_transid(self):
        if not self.current_transid:
            self.current_transid = self.fresh_transid()
        return self.current_transid


    # All generated transids are saved per user. They are stored in the transids.mk.
    # Per user only up to 20 transids of the already existing ones are kept. The transids
    # generated on the current page are all kept. IDs older than one day are deleted.
    def store_new_transids(self):
        if self.new_transids:
            valid_ids = self.load_transids(lock = True)
            cleared_ids = []
            now = time.time()
            for valid_id in valid_ids:
                timestamp = valid_id.split("/")[0]
                if now - int(timestamp) < 86400: # one day
                    cleared_ids.append(valid_id)
            self.save_transids((cleared_ids[-20:] + self.new_transids))


    # Remove the used transid from the list of valid ones
    def invalidate_transid(self, used_id):
        valid_ids = self.load_transids(lock = True)
        try:
            valid_ids.remove(used_id)
        except ValueError:
            return
        self.save_transids(valid_ids)


    # Checks, if the current transaction is valid, i.e. in case of
    # browser reload a browser reload, the form submit should not
    # be handled  a second time.. The HTML variable _transid must be present.
    #
    # In case of automation users (authed by _secret in URL): If it is empty
    # or -1, then it's always valid (this is used for webservice calls).
    # This was also possible for normal users, but has been removed to preven
    # security related issues.
    def transaction_valid(self):
        if not self.has_var("_transid"):
            return False

        id = self.var("_transid")
        if self.ignore_transids and (not id or id == '-1'):
            return True # automation

        if '/' not in id:
            return False

        # Normal user/password auth user handling
        timestamp = id.split("/", 1)[0]

        # If age is too old (one week), it is always
        # invalid:
        now = time.time()
        if now - int(timestamp) >= 604800: # 7 * 24 hours
            return False

        # Now check, if this id is a valid one
        if id in self.load_transids():
            #self.guitest_set_transid_valid()
            return True
        else:
            return False

    # Checks, if the current page is a transation, i.e. something
    # that is secured by a transid (such as a submitted form)
    def is_transaction(self):
        return self.has_var("_transid")


    # called by page functions in order to check, if this was
    # a reload or the original form submission. Increases the
    # transid of the user, if the latter was the case.
    # There are three return codes:
    # True:  -> positive confirmation by the user
    # False: -> not yet confirmed, question is being shown
    # None:  -> a browser reload or a negative confirmation
    def check_transaction(self):
        if self.transaction_valid():
            id = self.var("_transid")
            if id and id != "-1":
                self.invalidate_transid(id)
            return True
        else:
            return False


    def load_transids(self, lock=False):
        raise NotImplementedError()


    def save_transids(self, used_ids):
        raise NotImplementedError()


    #
    # Keyboard control
    # TODO: Can we move this specific feature to AQ?
    #

    def add_keybinding(self, keylist, jscode):
        self.keybindings.append([keylist, jscode])


    def add_keybindings(self, bindings):
        self.keybindings += bindings


    def disable_keybindings(self):
        self.keybindings_enabled = False


    #
    # Per request caching
    #

    def set_cache(self, name, value):
        self.caches[name] = value
        return value


    def set_cache_default(self, name, value):
        if self.is_cached(name):
            return self.get_cached(name)
        else:
            return self.set_cache(name, value)


    def is_cached(self, name):
        return name in self.caches


    def get_cached(self, name):
        return self.caches.get(name)


    def del_cache(self, name):
        if name in self.caches:
            del self.caches[name]


    def measure_time(self, name):
        self.times.setdefault(name, 0.0)
        now = time.time()
        elapsed = now - self.last_measurement
        self.times[name] += elapsed
        self.last_measurement = now


    #
    # Request timeout handling
    #
    # The system apache process will end the communication with the client after
    # the timeout configured for the proxy connection from system apache to site
    # apache. This is done in /omd/sites/[site]/etc/apache/proxy-port.conf file
    # in the "timeout=x" parameter of the ProxyPass statement.
    #
    # The regular request timeout configured here should always be lower to make
    # it possible to abort the page processing and send a helpful answer to the
    # client.
    #
    # It is possible to disable the applications request timeout (temoporarily)
    # or totally for specific calls, but the timeout to the client will always
    # be applied by the system webserver. So the client will always get a error
    # page while the site apache continues processing the request (until the
    # first try to write anything to the client) which will result in an
    # exception.
    #

    # The timeout of the Check_MK GUI request processing. When the timeout handling
    # has been enabled with enable_request_timeout(), after this time an alarm signal
    # will be raised to give the application the option to end the processing in a
    # gentle way.
    def request_timeout(self):
        return self._request_timeout


    def enable_request_timeout(self):
        signal.signal(signal.SIGALRM, self.handle_request_timeout)
        signal.alarm(self.request_timeout())


    def disable_request_timeout(self):
        signal.alarm(0)


    def handle_request_timeout(self, signum, frame):
        raise RequestTimeout(_("Your request timed out after %d seconds. This issue may be "
                               "related to a local configuration problem or a request which works "
                               "with a too large number of objects. But if you think this "
                               "issue is a bug, please send a crash report.") %
                                                            self.request_timeout())
