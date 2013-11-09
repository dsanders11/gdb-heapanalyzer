"""Common GDB commands for heap analysis. Once a heap implementation is identified
further commands are registered.

"""

import gdb

from _heap import categorize_heap
from _heap import UnsupportedHeap

# XXX - GDB forces us to butcher our doc strings to make them show up right as
# help messages in GDB. They should be parsing the docstrings according to PEP 257


class CommandBase(gdb.Command):
    def __init__(self, name, command_type, completer_class=gdb.COMPLETE_NONE, prefix=False):
        super(CommandBase, self).__init__(
            name, command_type, completer_class=completer_class, prefix=prefix)

    def invoke(self, args, from_tty):
        pass

        # XXX - Inferior specific command?
        # XXX - Debug info?
        # XXX - Heap changed?


class HeapCommand(CommandBase):
    """Commands for analyzing the heap in the current inferior. Available
commands differ by heap implementation, and may be disabled when switching
inferiors."""

    def __init__(self):
        super(HeapCommand, self).__init__("heap", gdb.COMMAND_DATA, prefix=True)

    def invoke(self, args, from_tty):
        arg_list = gdb.string_to_argv(args)

        if arg_list:
            print "Undefined info command: \"{0}\".  Try \"help heap\".".format(arg_list[0])
        else:
            print "\"heap\" must be followed by the name of a heap command"


class HeapAnalyzeCommand(CommandBase):
    """Analyze the heap. This must be called any time the heap changes.

Analyzing the heap may take several seconds for multi-gigabyte heaps"""

    def __init__(self, analyzer_state):
        super(HeapAnalyzeCommand, self).__init__("heap analyze", gdb.COMMAND_DATA)

        assert analyzer_state is not None

        self.analyzer_state = analyzer_state

    def invoke(self, args, from_tty):
        # Special command, we don't need anything from the base
        # super(HeapInfoCommand, self).invoke(args, from_tty)

        if args != "":
            print "Command takes no arguments"
            return

        if self.analyzer_state.heap_analyzer is None:
            # XXX - Create the heap analyzer
            analyzer_class = categorize_heap(self.analyzer_state.heap_inferior)
            print analyzer_class
        elif not self.analyzer_state.heap_analyzer.is_valid():
            # Reanalyze the heap
            pass
        else:
            print "Heap already analyzed"


class HeapInfoCommand(CommandBase):
    """Info on the heap implementation"""

    def __init__(self, analyzer_state):
        super(HeapInfoCommand, self).__init__("heap info", gdb.COMMAND_DATA)

        assert analyzer_state is not None

        self.analyzer_state = analyzer_state

    def invoke(self, args, from_tty):
        # Special command, we don't need anything from the base
        # super(HeapInfoCommand, self).invoke(args, from_tty)

        if args != "":
            print "Command takes no arguments"
            return

        if self.analyzer_state.heap_analyzer is None:
            print "Heap not yet analyzed"
        elif self.analyzer_state.heap_analyzer is UnsupportedHeap:
            print "Unknown heap implementation"
        else:
            print self.analyzer_state.heap_analyzer


def register_basic_commands(analyzer_state):
    HeapCommand()
    HeapInfoCommand(analyzer_state)
    HeapAnalyzeCommand(analyzer_state)