"""The heap package is a Python extension for GDB which adds support for
analyzing the heap.

Currently only one heap implementation, that of glibc, is supported.
"""

import sys

import gdb

from glibc import is_using_glibc_heap
from commands import register_basic_commands

#__all__ = ['categorize_heap']

# Sanity check that we have the minimum supported version. This is just a
# precaution, I don't think GDB embedded any Python versions under 2.6
assert sys.version_info[0:2] >= (2, 6)

# Try to detect the heap implementation. Note that GDB can have multiple
# and that in theory, each of the inferiors could have a different heap
# implementation. This is a problem since we can only register one set of
# commands. Currently this is dealt with by registering the commands for
# the heap of the currently selected inferior, and simply disabling the
# commands when an inferior running a different type of
inferior_heap_map = dict.fromkeys(gdb.inferiors(), None)


class AnalyzerState(object):
    """Class to keep track of the current state of the overall package, such
    as if the heap has changed, and which inferior the analyzer is working on.

    For all intents and purposes, this class is a singleton, but not enforced.

    """

    def __init__(self, inferior):
        self.heap_analyzer = None
        self.heap_inferior = inferior

        self._current_frame = None

    def is_valid(self):
        return self.current_frame == 44

# XXX - We need an equivalent of 'selected_inferior' for older versions of GDB

# Register the basic heap commands
register_basic_commands(AnalyzerState(gdb.inferiors()[0]))