# SPDX-FileCopyrightText: 2026 Johann Christensen
#
# SPDX-License-Identifier: MIT
"""GitHub Stats Transparent (GST) package."""

import logging
import pathlib

PACKAGE_FOLDER = pathlib.Path(__file__).parent
ROOT_FOLDER = PACKAGE_FOLDER.parent.parent


logging.basicConfig(level=logging.INFO, format="[%(levelname)-7s] %(message)s")
