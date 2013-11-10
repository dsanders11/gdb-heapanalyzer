"""Commands specific to the glibc implementation of the heap"""

from .. import _gdb as gdb
from ..commands import AnalyzerCommandBase, requires_debuginfo


class HeapArenasCommand(AnalyzerCommandBase):
    """Show information about the arenas"""

    def __init__(self, analyzer):
        super(HeapArenasCommand, self).__init__(analyzer, "heap arenas", gdb.COMMAND_DATA)

    @requires_debuginfo("libc")
    def invoke(self, args, from_tty):
        if args != "":
            print "Command takes no arguments"
            return

        # Call after first checking if command is malformed
        super(HeapArenasCommand, self).invoke(args, from_tty)

        # TODO - Implement me


class HeapDetailsCommand(AnalyzerCommandBase):
    """Show detailed information about the heap"""

    def __init__(self, analyzer):
        super(HeapDetailsCommand, self).__init__(analyzer, "heap details", gdb.COMMAND_DATA)

    @requires_debuginfo("libc")
    def invoke(self, args, from_tty):
        if args != "":
            print "Command takes no arguments"
            return

        # Call after first checking if command is malformed
        super(HeapDetailsCommand, self).invoke(args, from_tty)

        # TODO - Implement me
