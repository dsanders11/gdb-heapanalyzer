"""The heap package is a Python extension for GDB which adds support for
analyzing the heap.

Currently only one heap implementation, that of glibc, is supported.
"""

import _gdb as gdb
import sys
import threading

from _heap import HeapDetectionError, WrongHeapVersionError, UnsupportedHeap
from glibc import detect_glibc_heap
from commands import activate_basic_commands

# Always import any non-standard GDB helpers from _gdb
from _gdb import watch_active_inferior

_heap_detectors = [detect_glibc_heap]

# Sanity check that we have the minimum supported version. This is just a
# precaution, I don't think GDB embedded any Python versions under 2.6
assert sys.version_info[0:2] >= (2, 6)

# GDB can have multiple inferiors and in theory each of these inferiors
# might have a different heap implementation. As such, we have to keep a
# different analyzer for each inferior, and try to be smart about swapping
# between inferiors. This includes activating commands on a per-inferior
# basis, which can be accomplished by simply registering the commands again
# in the correct order.


class AnalyzerState(object):
    """Class to keep track of the current state of the overall extension, such
    as which inferior the analyzer is working on.

    For all intents and purposes, this class is a singleton, but not enforced.
    This class also has basic thread-safety by coarse level, recursive locking.

    """

    def __init__(self):
        self._lock = threading.RLock()
        self.inferior_to_analyzer_map = dict.fromkeys(gdb.inferiors(), None)

        # Use a background thread to monitor if the user switches inferiors
        background_function = lambda: watch_active_inferior(self.on_inferior_change,
                                                            gdb.selected_inferior())
        inferior_watcher = threading.Thread(target=background_function)
        inferior_watcher.daemon = True
        inferior_watcher.start()

    def get_current_analyzer(self):
        with self._lock:
            inferior = gdb.selected_inferior()

            # Use setdefault in case this is a new inferior we haven't seen
            return self.inferior_to_analyzer_map.setdefault(inferior, None)

    def detect_heap(self):
        with self._lock:
            inferior = gdb.selected_inferior()

            # Assert that this inferior has not already been detected
            assert self.inferior_to_analyzer_map[inferior] is None

            heap_analyzer = UnsupportedHeap

            for detector in _heap_detectors:
                try:
                    heap_analyzer = detector(inferior)
                    break
                except HeapDetectionError:
                    pass  # Expected error
                except WrongHeapVersionError, e:
                    print "INFO: Unsupported heap version detected: {0}".format(e)
                    break

            self.inferior_to_analyzer_map[inferior] = heap_analyzer

            return heap_analyzer

    def on_inferior_change(self, new_inferior):
        with self._lock:
            # First wipe the active commands back to basics
            activate_basic_commands(self)

            # Check to see if an analyzer exists yet for this inferior
            analyzer = self.inferior_to_analyzer_map.setdefault(new_inferior, None)

            # If one does, activate the commands for it
            if analyzer is not UnsupportedHeap and analyzer is not None:
                analyzer.activate_commands()


# Register the basic heap commands
activate_basic_commands(AnalyzerState())