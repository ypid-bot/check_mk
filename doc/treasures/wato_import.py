#!/usr/bin/env python3
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
#
# Author: Bastian Kuhn bk@mathias-kettner.de
# Rewrite and cleanup Robin Schneider <robin.schneider@hamcos.de>

"""
Read CSV host list and create the hosts in Check_MK WATO.
"""

__version__ = '0.8'

# modules {{{
# std {{{
import os
import logging
import csv
import re
import socket
# }}}
# }}}


class CsvToCheckMkConverter:
    CMK_TAG_SEPARATOR = '|'
    DEFAULT_HOST_TAGS = CMK_TAG_SEPARATOR.join(
        (
            'wato', '/" + FOLDER_PATH + "/'
        )
    )
    KEYS_IN_HOST_ATTRIBUTES = [
        'alias',
        'ipaddress'
    ]

    def __init__(
        self,
        csv_file,
        wato_default_folder=None,
        hostname_suffix='',
        host_tags='',
    ):

        self._csv_file = csv_file
        self._wato_default_folder = wato_default_folder
        self._hostname_suffix = hostname_suffix

        if host_tags:
            self._host_tags = self.CMK_TAG_SEPARATOR.join(
                (
                    host_tags,
                    self.DEFAULT_HOST_TAGS
                )
            )
        else:
            self._host_tags = self.DEFAULT_HOST_TAGS

        self._folders = {}

        self._csv_fh = open(self._csv_file, newline='')

        sample = self._csv_fh.read(1024)
        # if not csv.Sniffer().has_header(sample):
        #     raise Exception("No header line in CSV file found. Example header: hostname;ip;description")
        self._csv_fh.seek(0)  # rewind

        # FIXME might use sniffer for delimiter detection.
        # logger.debug(csv.Sniffer().sniff(sample))
        if sample.find(','):
            self._csv_delimiter = ','
        elif sample.find(';'):
            self._csv_delimiter = ';'
        else:
            raise Exception("Unknown CSV delimiter.")

    def parse(self):
        for self.__row in csv.DictReader(
                filter(lambda row: row[0] != '#', self._csv_fh),
                delimiter=self._csv_delimiter
        ):

            if re.match(r'\s*$', self.__row['hostname']):
                continue

            self._parse_row()

    def _parse_row(self):
        logger.debug("Parsing row: \"{0}\"".format(self.__row))

        wato_foldername = self._wato_default_folder
        if 'wato_foldername' in self.__row and self.__row['wato_foldername']:
            wato_foldername = self.__row['wato_foldername']
        elif not wato_foldername:
            raise Exception(
                "Column wato_foldername not given."
                " Either specify it in the CSV file or use the parameter "
            )

        hostname = re.sub(
            r'[^\w_.-]', '_',
            self.__row['hostname']
        ) + self._hostname_suffix
        self._folders.setdefault(wato_foldername, {})
        host_properties = {
            'hostname':   hostname,
            'alias':      self.__get_host_property('host_alias'),
            'ipaddress':  self.__get_host_property('ipaddress'),
            'host_tags':  self.__get_host_property('host_tags', default=''),
        }

        if self._host_tags:
            if host_properties['host_tags']:
                host_properties['host_tags'] += self.CMK_TAG_SEPARATOR + self._host_tags
            else:
                host_properties['host_tags'] = self._host_tags

        if not host_properties['ipaddress']:
            host_properties['ipaddress'] = self.__get_host_property('ip')

        if not host_properties['ipaddress'] or host_properties['ipaddress'].lower() == "None".lower():
            host_properties['ipaddress'] = False

        self._folders[wato_foldername][hostname] = host_properties

    def __get_host_property(
        self,
        host_property,
        prefix='',
        suffix='',
        default=None
    ):

        if host_property in self.__row:
            return prefix + self.__row[host_property].strip() + suffix
        elif type(default) is str:
            return prefix + default + suffix
        else:
            return default

    def _get_host_attributes_string(self, host_properties, skip_properties=[]):
        host_attributes = []
        for host_property in self.KEYS_IN_HOST_ATTRIBUTES:
            if (host_property not in skip_properties
                    and host_property in host_properties
                    and host_properties[host_property]):

                # host_attributes += "\t'{}': {{'alias' : u'{}', 'ipaddress' : '{}' }},\n".format(
                host_attributes.append("'{}': u'{}'".format(
                    host_property,
                    host_properties[host_property]
                ))
        if 'snmp-only' in host_properties['host_tags']:
            host_attributes.append("'{}': u'{}'".format(
                'tag_agent',
                'snmp-only',
            ))

        if len(host_attributes) > 0:
            return " '{}': {{{}}},\n".format(
                host_properties['hostname'],
                ','.join(host_attributes),
            )
        else:
            return " '{}': {{}}, # needed for WATO\n".format(
                host_properties['hostname'],
            )

    def get_hosts(self):
        output = ""
        for wato_foldername in self._folders:
            output += "\t{}:\n".format(wato_foldername)
            for hostname in sorted(self._folders[wato_foldername]):
                host_properties = self._folders[wato_foldername][hostname]
                ip_address = ""
                if host_properties['ipaddress']:
                    ip_address = " -> {}".format(host_properties['ipaddress'])
                output += "{}{}\n".format(
                    hostname,
                    ip_address,
                )
        return output

    def write_configuration(self, export_dir, include_ip_address=True):
        logger.debug(include_ip_address)
        for wato_foldername in self._folders:
            config_dir = os.path.join(export_dir, wato_foldername)
            try:
                os.makedirs(config_dir)
            except os.error:
                pass
                # logger.debug("Could not create directory for {}: {}".format(wato_foldername, err))
            all_hosts = ""
            host_attributes = ""
            ips = ""
            host_aliases = []
            for hostname in sorted(self._folders[wato_foldername]):
                host_properties = self._folders[wato_foldername][hostname]
                all_hosts += '  "{}{}",\n'.format(
                    hostname,
                    self.CMK_TAG_SEPARATOR + host_properties['host_tags'] if host_properties['host_tags'] else '',
                )
                host_attributes += self._get_host_attributes_string(
                    host_properties,
                    skip_properties=['' if include_ip_address else 'ipaddress'],
                )
                if include_ip_address and host_properties['ipaddress']:
                    ips += "'{}': u'{}',\n".format(
                        hostname,
                        host_properties['ipaddress']
                    )
                if host_properties['alias']:
                    host_aliases.append(" (u'{}', ['{}']),".format(
                        host_properties['alias'],
                        hostname,
                    ))

            config_file = os.path.join(config_dir, 'hosts.mk')
            wato = open(os.path.join(config_dir, '.wato'), 'w')
            wato.write(
                "{'attributes': {}, 'num_hosts': %d, 'title': u'%s'}\n" % (
                    len(self._folders[wato_foldername]),
                    wato_foldername.split(r'/')[-1],
                )
            )
            wato.close()
            logger.info("Writing configuration file: {}".format(config_file))
            target_file = open(config_file, 'w')
            target_file.write('# Written by {}\n'.format(os.path.basename(__file__)))
            target_file.write('# encoding: utf-8\n\n')

            target_file.write('all_hosts += [\n')
            target_file.write(all_hosts)
            target_file.write(']\n\n')

            if len(ips) > 0:
                target_file.write('ipaddresses.update({\n')
                target_file.write(ips)
                target_file.write('})\n\n')

            if len(host_aliases) > 0:
                target_file.write("extra_host_conf.setdefault('alias', []).extend([\n")
                target_file.write('\n'.join(host_aliases))
                target_file.write('\n])\n')

            if host_attributes:
                target_file.write('host_attributes.update({\n')
                target_file.write(host_attributes)
                target_file.write('})\n\n')

            target_file.close()

    def write_dns_record_export(self, filepath, do_not_resolve_hostname):
        with open(filepath, 'w', newline='') as outcsv:
            writer = csv.writer(outcsv)
            writer.writerow(["FQDN", "IP"])

            for wato_foldername in self._folders:
                for hostname in sorted(self._folders[wato_foldername]):
                    host_properties = self._folders[wato_foldername][hostname]

                    dns_record = None
                    if not do_not_resolve_hostname:
                        try:
                            dns_record = socket.gethostbyname(hostname)
                        except socket.gaierror:
                            dns_record = None

                    if dns_record:
                        logger.debug("Hostname {} is already resolvable.".format(hostname))
                    elif host_properties['ipaddress']:
                        logger.debug("Write hostname/FQDN {} to {}".format(
                            hostname,
                            filepath
                        ))
                        writer.writerow([hostname, host_properties['ipaddress']])
                    else:
                        logger.error("Hostname {} is not resolvable and no IP address was given.".format(hostname))


# main {{{
if __name__ == '__main__':
    from argparse import ArgumentParser, RawTextHelpFormatter

    args_parser = ArgumentParser(
        description=__doc__,
        formatter_class=RawTextHelpFormatter,
        epilog="CSV example:\n\t" +
        '\n\t'.join(
            [
                "wato_foldername;hostname;host_alias;ipaddress;host_tags",
                "production;main.domain.tld;main;;own_tag",
            ]
        )
    )
    args_parser.add_argument(
        '-V', '--version',
        action='version',
        version='%(prog)s {version}'.format(version=__version__),
    )
    args_parser.add_argument(
        '-d', '--debug',
        help="Print lots of debugging statements",
        action="store_const", dest="loglevel", const=logging.DEBUG,
        default=logging.WARNING,
    )
    args_parser.add_argument(
        '-v', '--verbose',
        help="Be verbose",
        action="store_const", dest="loglevel", const=logging.INFO,
    )
    args_parser.add_argument(
        'csv_file',
        help="CSV host list file to import.",
    )
    args_parser.add_argument(
        '-e', '--export-dir',
        help="Check_MK WATO directory path where the generated configuration should be written to"
        " (default: %(default)s).",
        default='/etc/check_mk/conf.d',
    )
    args_parser.add_argument(
        '-u', '--unresolvable-hosts-to-file',
        help="Test all hosts if they can be resolved to a network/IP address by the system"
        " and write the hosts that could not be resolved into the given file as CSV."
        " For each host, the FQDN and the IP address is written."
        " If no IP address is given for a host then a error message is going to be printed."
        " This parameter is intended for a list of hosts which contains hosts laking an DNS entry."
        " The exported CSV file can then be used to import the missing records into the DNS."
        " If this option is used, the IP address will not be included into the configuration for Check_MK."
    )
    args_parser.add_argument(
        '-n', '--no-dns-resolve',
        action='store_true',
        default=False,
        help="Do not check if the host is already resolvable via DNS"
        " and write all FQDN/IP pairs to the file specified by --unresolvable-hosts-to-file.",
    )
    args_parser.add_argument(
        '-w', '--wato-default-folder',
        help="Set a WATO default folder if none was specified for a given host.",
    )
    args_parser.add_argument(
        '-s', '--hostname-suffix',
        help="Append this suffix to all hostnames.",
        default='',
    )
    args_parser.add_argument(
        '-t', '--host-tags',
        help="Append these tags to all hostnames."
        " Use a pipe „{}“ as tag separator.".format(
            CsvToCheckMkConverter.CMK_TAG_SEPARATOR
        ),
        default='',
    )
    args_parser.add_argument(
        '-l', '--list',
        action='store_true',
        default=False,
        help="List hosts intended for the bulk import of WATO.",
    )

    args = args_parser.parse_args()
    logger = logging.getLogger(__file__)
    logging.basicConfig(
        format='%(levelname)s: %(message)s',
        level=args.loglevel,
        # level=logging.DEBUG,
        # level=logging.INFO,
    )

    parser = CsvToCheckMkConverter(
        args.csv_file,
        wato_default_folder=args.wato_default_folder,
        hostname_suffix=args.hostname_suffix,
        host_tags=args.host_tags,
    )

    parser.parse()
    if args.list:
        print(parser.get_hosts())
    else:
        parser.write_configuration(
            args.export_dir,
            not args.unresolvable_hosts_to_file
        )

    if args.unresolvable_hosts_to_file:
        parser.write_dns_record_export(
            args.unresolvable_hosts_to_file,
            args.no_dns_resolve
        )

# }}}
