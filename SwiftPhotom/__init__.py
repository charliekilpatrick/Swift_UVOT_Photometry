#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) Giacomo Terreran (2021)
#
# This file is part of Swift_host_subtraction
#
# Swift_host_subtraction is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Swift_host_subtraction is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Swift_host_subtraction.  If not, see <http://www.gnu.org/licenses/>

"""Swift_host_subtraction: Swift UVOT aperture and template-subtracted photometry.

This package provides a Python wrapper around HEASoft commands for aperture
and image-subtracted photometry on Swift UVOT data, following the methods
of Brown et al. (2009, 2014).

Submodules
----------
commands : Run HEASoft shell commands (uvotimsum, uvotmaghist, fcopy, fappend).
help : CLI help strings for the bin scripts.
uvot : UVOT-specific logic (filter sorting, aspect correction, product creation).
"""

try:
    from ._version import __version__
except ImportError:
    __version__ = "0+unknown"

__author__ = 'Giacomo Terreran <gterreran@lco.global>'
__credits__ = ['Peter Brown <grbpeter@yahoo.com>']
__all__ = ['commands', 'help', 'uvot']
