#!/usr/bin/python3

# system76-driver: Universal driver for System76 computers
# Copyright (C) 2005-2016 System76, Inc.
#
# This file is part of `system76-driver`.
#
# `system76-driver` is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# `system76-driver` is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with `system76-driver`; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import os
from os import path
from subprocess import PIPE, Popen, check_output
import logging


logging.basicConfig(
    level=logging.DEBUG,
    format='system76-fix-swap %(levelname)s %(message)s',
)
log = logging.getLogger()


NO_AUTO = '63'


def iter_swap_uuids(filename='/etc/crypttab'):
    try:
        fp = open(filename, 'r')
    except FileNotFoundError:
        return
    for line in fp.readlines():
        # Skip commented out lines:
        if line.startswith('#'):
            continue

        # Split line into (mdev, dev, key, options):
        parts = line.split()

        # Skip mallformed lines:
        if len(parts) != 4:
            continue

        (mdev, dev, key, options) = parts

        # Skip lines that don't have key source of /dev/urandom:
        if key != '/dev/urandom':
            continue

        # Skip lines that don't have 'swap' in options:
        if 'swap' not in options.split(','):
            continue

        # Skip lines that doen't have dev specified by UUID=:
        if not dev.startswith('UUID='):
            continue

        yield dev[5:]


def get_partition_from_uuid(uuid):
    d = '/dev/disk/by-uuid'
    f = path.join(d, uuid)
    link = os.readlink(f)
    return path.abspath(path.join(d, link))


def get_scheme(partition):
    cmd = ['blkid', '-p', '-s', 'PART_ENTRY_SCHEME', '-o', 'value', partition]
    return check_output(cmd, timeout=5).decode().rstrip()


def call_fdisk(drive, *args):
    indata = ('\n'.join(args) + '\n').encode()
    p = Popen(['fdisk', drive], stdin=PIPE, stdout=PIPE)
    try:
        (outdata, outerr) = p.communicate(indata, timeout=5)
        return outdata.decode()
    finally:
        p.kill()


def has_no_auto(drive, partion):
    for line in call_fdisk(drive, 'x', 'p').splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == partition:
            log.info('fdisk line: %r', parts)
            if parts[-1].startswith('GUID:'):
                return NO_AUTO in parts[-1][5:].split(',')
            return False
    raise ValueError(
        '{!r} not found in fdisk output for {!r}'.format(partition, drive)
    )


def toggle_no_auto(drive, pnum):
    log.info('toggling no-auto bit on partition %r of %r', pnum, drive)
    call_fdisk(drive, 'x', 'S', pnum, NO_AUTO, 'r', 'w')


for uuid in iter_swap_uuids():
    partition = get_partition_from_uuid(uuid)

    # Skip non-NVMe drives:
    if not partition.startswith('/dev/nvme'):
        continue

    # Skip if partition scheme isn't  GPT:
    if get_scheme(partition) != 'gpt':
        continue

    # Get drive dev and partition number:
    (drive, pnum) = partition.split('p')

    #call_fdisk(drive, 'x', 'S', pnum, NO_AUTO, 'r', 'w')

    # Only set no-auto flag if not aready set:
    if not has_no_auto(drive, partition):
        toggle_no_auto(drive, pnum)

