"""Commands specific to the glibc implementation of the heap"""

import gdb

from ..commands import CommandBase


class HeapArenas(CommandBase):
    """Show information about the arenas"""

    def __init__(self, analyzer):
        super(HeapArenas, self).__init__("heap arenas", gdb.COMMAND_DATA)

        assert analyzer is not None

        self.analyzer = analyzer

    def invoke(self, args, from_tty):
        # Special command, we don't need anything from the base
        # super(HeapInfoCommand, self).invoke(args, from_tty)

        if args != "":
            print "Command takes no arguments"
            return