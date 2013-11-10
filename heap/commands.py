"""Common GDB commands for heap analysis. Once a heap implementation is identified
further commands are registered.

"""

import _gdb as gdb
import functools

from _heap import UnsupportedHeap

# Always import any non-standard GDB helpers from _gdb
from _gdb import is_debuginfo_loaded, is_inferior_running, is_inferior_coredump

# XXX - GDB forces us to butcher our doc strings to make them show up right as
# help messages in GDB. They should be parsing the docstrings according to PEP 257


def requires_debuginfo(debuginfo):
    """Decorator for commands which require certain debug info to function

    This decorator was inspired by the original one in gdb-heap, but improved
    to add more versatility and functionality.
    """

    assert not callable(debuginfo), \
        "Programming error, you're probably using this decorator wrong, it requires an argument"

    debuginfo_cache = {}

    def decorator(func):
        @functools.wraps(func)
        def new_func(*args, **kwargs):
            debuginfo_found = debuginfo_cache.setdefault(debuginfo, is_debuginfo_loaded(debuginfo))

            if not debuginfo_found:
                print "Missing debuginfo for {0}".format(debuginfo)
                print "Suggested fix:"
                print "    debuginfo-install {0}".format(debuginfo)
            else:
                func(*args, **kwargs)

        return new_func

    return decorator


def requires_running_or_core(msg="Inferior must be a running process or core dump"):
    """Decorator for commands which need a running program, or a core dump"""

    assert not callable(msg), \
        "Programming error, you're probably using this decorator wrong, it requires an argument"

    def decorator(func):
        @functools.wraps(func)
        def new_func(*args, **kwargs):
            inferior = gdb.selected_inferior()

            if not is_inferior_running(inferior) and not is_inferior_coredump(inferior):
                print msg
            else:
                func(*args, **kwargs)

        return new_func

    return decorator


class CommandBase(gdb.Command):
    """Base class for GDB commands

    Provides some basic functionality such as saving the command name and
    other arguments. More functionality may be added later, so it's a good idea
    to derive any new commands from this base class or one of it's subclasses.

    """

    _prefix_cache = []

    def __init__(self, name, command_type, **kwargs):
        completer_class = kwargs.pop("completer_class", gdb.COMPLETE_NONE)
        prefix = kwargs.pop("prefix", False)
        existing_prefix = kwargs.pop("existing_prefix", False)

        if len(kwargs) > 0:
            error_msg = "__init__() got an unexpected keyword argument '{0}'"
            raise TypeError(error_msg.format(kwargs.keys()[0]))

        super(CommandBase, self).__init__(
            name, command_type, completer_class=completer_class, prefix=prefix)

        name_chunks = name.rsplit()
        command_prefix = ""

        if len(name_chunks) > 1:
            command_prefix = ''.join(name_chunks[:-1])

            if not CommandBase._prefix_cache.count(command_prefix) and not existing_prefix:
                # Not an existing prefix (such as a built in command), and not in our
                # cache, so this is more than likely a programming error
                #
                # XXX - The reason we throw a fit here is because GDB seems to silently
                # ignore the middle words and turn things like "heap extra command" into
                # "heap command", which is not what anyone intended. To make things worse,
                # the help for the prefix will list "heap command", but running the command
                # "help heap command" will try to list subcommands of "heap extra command"
                # if "heap extra command" was created as a prefix command itself. So, we're
                # trying to prevent confusion cause by this weird GDB behavior
                msg = ("Programming error: Trying to create a command with an unknown prefix, "
                       "see note above this assertion")
                assert False, msg

        if prefix:
            # If we got to here, it's a new prefix, so add it to our cache
            CommandBase._prefix_cache.append(name)

        self.is_prefix = prefix
        self.command_name = name
        self.command_prefix = command_prefix
        self.command_type = command_type
        self.completer_class = completer_class


class PrefixCommandBase(CommandBase):
    """Base class for a prefix command

    This class's __init__ simply passes all arguments through to CommandBase,
    except for prefix, so argument order and kwargs can be found on that class.

    Supplies a basic invoke for prefix commands which really just complains
    if it is called, since the prefix command shouldn't be invokable by itself.
    If this behavior is not desirable, supply your own invoke method.

    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("prefix", True)
        kwargs["prefix"] = True

        super(PrefixCommandBase, self).__init__(*args, **kwargs)

    def invoke(self, args, from_tty):
        # If invoke gets called for a prefix command then the user
        # must have added an unknown sub command at the end

        # TBD - How does GDB handle nested prefix commands? Does each
        # prefix command get invoked, or only the last one? For now
        # we'll just assume the latter until proven otherwise

        arg_list = gdb.string_to_argv(args)

        if arg_list:
            message_template = "Undefined {0} command: \"{1}\". Try \"help {0}\"."
        else:
            message_template = "\"{0}\" must be followed by the name of a {0} command"

        # You're allowed to pass more arguments then there are slots to format
        print message_template.format(self.command_name, *arg_list)


class AnalyzerCommandBase(CommandBase):
    """Base class for a command which uses a heap analyzer

    This class's __init__ simply passes all arguments except the first through
    to CommandBase, so argument order and kwargs can be found on that class.

    One of the benefits of this base class is it checks for a valid analyzer
    when invoking the command, and complains if it's not valid. If that isn't
    desirable behavior then don't call super(...).invoke(...) in your invoke.

    """

    def __init__(self, analyzer, *args, **kwargs):
        super(AnalyzerCommandBase, self).__init__(*args, **kwargs)

        assert analyzer is not None

        self.analyzer = analyzer

    def invoke(self, args, from_tty):
        if not self.analyzer.is_valid():
            print "Heap information is out of date, re-run \"heap analyze\""
            return


class HeapCommand(PrefixCommandBase):
    """Commands for analyzing the heap of the current inferior. Available commands
differ by heap implementation, and may become unavailable when switching inferiors."""

    def __init__(self):
        super(HeapCommand, self).__init__("heap", gdb.COMMAND_DATA)


class HeapAnalyzeCommand(CommandBase):
    """Analyze the heap. This must be called any time the heap changes.

Analyzing the heap may take several seconds for multi-gigabyte heaps"""

    def __init__(self, analyzer_state):
        super(HeapAnalyzeCommand, self).__init__("heap analyze", gdb.COMMAND_DATA)

        assert analyzer_state is not None

        self.analyzer_state = analyzer_state

    @requires_running_or_core("Can only analyze heap for a running process or core dump")
    def invoke(self, args, from_tty):
        self.dont_repeat()

        if args != "":
            print "Command takes no arguments"
            return

        a_state = self.analyzer_state

        current_analyzer = a_state.get_current_analyzer()

        if current_analyzer is None:
            # Detect the heap
            current_analyzer = a_state.detect_heap()

            # Activate the commands for it
            if current_analyzer is not UnsupportedHeap:
                current_analyzer.activate_commands()

            # Perform the analyze
            current_analyzer.analyze()
        elif not current_analyzer.is_valid():
            # Reanalyze the heap
            current_analyzer.analyze()
        else:
            response = raw_input(("Heap already analyzed and appears valid. "
                                  "Are you sure you want to reanalyze? [y/n] "))

            if response == "Y" or response == "y":
                # Reanalyze the heap
                current_analyzer.analyze()


class HeapInfoCommand(CommandBase):
    """Info on the heap implementation"""

    def __init__(self, analyzer_state):
        super(HeapInfoCommand, self).__init__("heap info", gdb.COMMAND_DATA)

        assert analyzer_state is not None

        self.analyzer_state = analyzer_state

    def invoke(self, args, from_tty):
        if args != "":
            print "Command takes no arguments"
            return

        current_analyzer = self.analyzer_state.get_current_analyzer()

        if current_analyzer is None:
            print "Heap not yet analyzed"
        elif current_analyzer is UnsupportedHeap:
            print "Unknown heap implementation"
        else:
            print current_analyzer.get_heap_description()


def activate_basic_commands(analyzer_state):
    HeapCommand()
    HeapInfoCommand(analyzer_state)
    HeapAnalyzeCommand(analyzer_state)