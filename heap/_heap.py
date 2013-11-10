"""Common heap classes and functions are grouped into this module"""

import _gdb as gdb

#from _gdb.events import cont as ContinueEvent
from _helpers import create_singleton
from abc import ABCMeta, abstractmethod

# Special singleton to identify unsupported heaps
UnsupportedHeap = create_singleton("UnsupportedHeap")


class HeapDetectionError(Exception):
    """Exception for a failed heap detection"""


class WrongHeapVersionError(Exception):
    """Exception for heap successfully detected, but wrong version"""


class BaseHeapAnalyzer(object):
    """Abstract base class for heap analyzers

    This class outlines the methods all heap analyzers must support, and
    provides a little bit of common functionality, such as detecting when
    the heap has changed out from underneath of us and must be reanalyzed.

    """

    __metaclass__ = ABCMeta

    def __init__(self, inferior):
        self.inferior = inferior
        self._is_valid = True

        gdb.events.cont.connect(self._on_continue)

    def _on_continue(self, event):
        self._is_valid = False

    def analyze(self):
        """Analyze the heap and store the information"""

        self._is_valid = True

    def is_valid(self):
        """Check if this analyzer is still valid

        The analyzer will be invalid when the heap has moved since the last
        time it was analyzed. At that point it must be reanalzyed before many
        of the heap analysis commands will work again.

        """

        return self._is_valid and self.inferior.is_valid()

    @abstractmethod
    def activate_commands(self):
        """Activate the commands specific to this heap analyzer"""
        pass

    @abstractmethod
    def get_heap_description(self):
        """Return a string describing this heap implementation"""
        pass