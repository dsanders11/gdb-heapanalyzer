"""Collection of GDB helpers, mainly compatibility shims"""

import sys
import os
import time
import tempfile
import functools
import types
import gdb

from types import ModuleType

# Even though it is bad form, import everything from the real GDB
# module so that we can masquerade as him in the rest of the code base
from gdb import *


# Older versions of the GDB Python API don't have
# newest_frame, so we have to implement it ourselves
try:
    from gdb import newest_frame
except ImportError:
    def newest_frame():
        """Returns the newest frame on the currently selected thread"""

        selected_frame = gdb.selected_frame()
        _newest_frame = None

        while selected_frame is not None:
            _newest_frame = selected_frame
            selected_frame = newest_frame.newer()

        return _newest_frame

# Older versions of the GDB Python API don't have Inferior.is_valid,
# so we have to implement it ourselves as a simple check of all inferiors.
# The tricky thing is patching it into the existing framework, so we add
# a new proxy class which we use to wrap
try:
    _is_valid_found = gdb.Inferior.is_valid
except AttributeError:
    def _inferior_is_valid(self):
        """Checks if the inferior is still valid"""

        _inferiors = gdb.inferiors()

        for inferior in _inferiors:
            if inferior == self:
                return True

        return False

    class InferiorProxy(object):
        __slots__ = ("_obj", "is_valid")

        def __init__(self, obj):
            self._obj = obj

            # XXX - The repr for this method is ugly, but it's a fairly minor thing
            object.__setattr__(self, "is_valid", types.MethodType(_inferior_is_valid, obj))

        def __call__(self, *args, **kwargs):
            return self._obj(*args, **kwargs)

        def __getattribute__(self, attr):
            obj = object.__getattribute__(self, "_obj")

            if attr == "_obj":
                return obj
            elif attr == "is_valid":
                return object.__getattribute__(self, "is_valid")
            else:
                return getattr(obj, attr)

        def __setattr__(self, attr, val):
            if attr == "_obj":
                object.__setattr__(self, attr, val)
            else:
                setattr(self._obj, attr, val)

        def __delattr__(self,attr):
            if attr == "_obj":
                object.__delattr__(self, attr)
            else:
                delattr(self._obj, attr)

        def __repr__(self):
            return repr(self._obj)

        def __str__(self):
            return str(self._obj)

        def __hash__(self):
            return hash(self._obj)

        def __lt__(self, obj):
            return self._obj < obj

        def __gt__(self, obj):
            return self._obj > obj

        def __le__(self, obj):
            return self._obj <= obj

        def __ge__(self, obj):
            return self._obj >= obj

        def __eq__(self, obj):
            return self._obj == obj

        def __ne__(self, obj):
            return self._obj != obj

    @functools.wraps(gdb.inferiors)
    def inferiors():
        return [InferiorProxy(i) for i in gdb.inferiors()]

# Older versions of the GDB Python API don't have
# selected_inferior, so we have to fake the support
try:
    from gdb import selected_inferior

    try:
        _is_valid_found = gdb.Inferior.is_valid
    except AttributeError:
        @functools.wraps(gdb.selected_inferior)
        def selected_inferior():
            return InferiorProxy(gdb.selected_inferior())
except ImportError:
    def selected_inferior():
        """Returns the currently selected inferior"""

        _inferiors = inferiors()
        inferior_output = gdb.execute("info inferiors", from_tty=True, to_string=True)
        header, inferior_lines = inferior_output.split('\n')[0], inferior_output.split('\n')[1:]

        assert header.split() == ["Num", "Description", "Executable"]

        for inferior_line in inferior_lines:
            # The selected inferior has a star in front:
            if inferior_line.lstrip().startswith('*'):
                inferior_id = inferior_line.split()[1]

                for inferior in _inferiors:
                    if int(inferior.num) == int(inferior_id):
                        return inferior

        assert False, "Selected inferior not found"

def is_debuginfo_loaded(debuginfo):
    """Checks if debug symbols are loaded for a given library"""

    sharedlibrary_output = gdb.execute("info sharedlibrary", to_string=True)

    if sharedlibrary_output == "No shared libraries loaded at this time.":
        return False

    sharedlibrary_lines = sharedlibrary_output.split('\n')

    # Make sure the columns are what we think they are
    assert [i.strip() for i in sharedlibrary_lines[0].split('  ') if i.strip() != ''] == \
           ["From", "To", "Syms Read", "Shared Object Library"]

    for line in sharedlibrary_lines[1:]:
        line_columns = [column.strip() for column in line.split('  ') if column.strip() != '']

        if not line_columns:
            break

        assert len(line_columns) == 4

        syms_read = line_columns[2]
        sharedlibrary = os.path.basename(line_columns[3])

        if sharedlibrary.startswith(debuginfo):
            if syms_read == "Yes":
                return True
            else:
                return False

    # Name not found in 'info sharedlibrary' output, check objfiles
    # XXX - This is a last ditch effort for cases where a full version name
    # is specified but the sharedlibrary output only gives the name of the
    # symlink which doesn't allow us to know the underlying version
    for objfile in gdb.objfiles():
        objfile_name = os.path.basename(objfile.filename)

        if objfile_name.startswith(debuginfo) and objfile_name.endswith(".debug"):
            return True

    return False


def watch_active_inferior(callback, initial_inferior, stop_event=None):
    """Watch for changes in the currently selected inferior and invoke callback

    This function is meant to be used on a background thread, since it would
    otherwise block the main thread. If no stop_event is provided, the function
    will simply run forever. This would work if you set the thread as a daemon.

    NOTE: More than one callback can be active at a time if rapid inferior
          switching occurs, so keep callbacks as short as possible.

    """

    # A bit hackish, but we use a list here since it
    # is mutable and so it can be passed to the function
    # and still update the original value
    last_inferior = [initial_inferior]
    event_finished = [True]

    def check_for_change():
        event_finished[0] = True

        try:
            current_inferior = selected_inferior()

            if current_inferior != last_inferior[0]:
                callback(current_inferior)
                last_inferior[0] = current_inferior
        except:
            pass

    def should_stop():
        if stop_event is not None:
            return stop_event.is_set()
        else:
            return False

    while not should_stop():
        # Very important to use post_event here. It is not safe
        # to use gdb functions from a thread that isn't the main
        # one, and it *will* lead to segmentation faults
        event_finished[0] = False
        gdb.post_event(check_for_change)

        # Wait for the event to finish before starting
        # another one. This doesn't wait for callbacks
        # to finish though, so there might be several
        # which fire in a row if inferiors are switching
        while not event_finished[0]:
            time.sleep(0.05)

        time.sleep(0.2)


def is_inferior_running(inferior):
    """Check if the inferior is a running process

    For the purposes of this check, running does not necessarily mean currently
    executing, but rather that there is a running process on the system for the
    inferior. If this function is being run in the first place then the inferior
    is more than likely stopped by GDB anyway, unless this function were called
    from a background thread.

    """

    for thread in inferior.threads():
        if thread.is_running():
            return True

    return False


def is_inferior_coredump(inferior):
    """Check if the inferior is a core dump

    This may return True for inferiors which segfault while under GDB control

    """

    is_inferior_running(inferior)

    if not is_inferior_running(inferior):
        # A core dump won't be a running inferior, but it
        # will have threads if it was at one time running
        if inferior.threads():
            return True

    return False


# XXX - Lack of event support in earlier versions of the GDB Python API forced
# me to come up with another way to get notified of when the program is moved
# forward. It's a bit ugly, and hackish but it works.

class _GDBHook(object):
    """A callback system for GDB commands

    Uses the hook ability in GDB (by defining a command named hook-<command>)
    to allow for Python callbacks. Since this removes the user's ability to
    hook commands themselves, there's a new "hook" and "unhook" command.

    Callbacks should accept the command name, and 10 additional arguments, the
    max for a user-defined GDB command. All arguments will be passed as strings

    """

    _hook_registry = {}

    def __init__(self, command):
        assert not _GDBHook._hook_registry.has_key(command)

        self.command = command
        self.callbacks = []

        self._install_hook()

    def add_callback(self, callback):
        assert self.callbacks.count(callback) == 0

        self.callbacks.append(callback)

    def remove_callback(self, callback):
        assert self.callbacks.count(callback) == 1

        self.callbacks.remove(callback)

    def _install_hook(self):
        # Well this is super annoying and ugly
        gdb_hook_command_parts = [
            'define hook-{0}','if $argc == 0', '{1}["{0}"]()', 'end', 'if $argc == 1',
            '{1}["{0}"]("{2}0")', 'end', 'if $argc == 2', '{1}["{0}"]("{2}0","{2}1")', 'end',
            'if $argc == 3', '{1}["{0}"]("{2}0","{2}1","{2}2")', 'end', 'if $argc == 4',
            '{1}["{0}"]("{2}0","{2}1","{2}2","{2}3")', 'end', 'if $argc == 5',
            '{1}["{0}"]("{2}0","{2}1","{2}2","{2}3","{2}4")', 'end', 'if $argc == 6',
            '{1}["{0}"]("{2}0","{2}1","{2}2","{2}3","{2}4","{2}5")', 'end',  'if $argc == 7',
            '{1}["{0}"]("{2}0","{2}1","{2}2","{2}3","{2}4","{2}5",{2}6)', 'end',
            'if $argc == 8', '{1}["{0}"]("{2}0","{2}1","{2}2","{2}3","{2}4","{2}5","{2}6","{2}7")',
            'end', 'if $argc == 9',
            '{1}["{0}"]("{2}0","{2}1","{2}2","{2}3","{2}4","{2}5","{2}6","{2}7","{2}8")', 'end',
            'if $argc == 10',
            '{1}["{0}"]("{2}0","{2}1","{2}2","{2}3","{2}4","{2}5","{2}6","{2}7","{2}8","{2}9")',
            'end'
        ]

        gdb_hook_command = '\n'.join(gdb_hook_command_parts)

        formatted_hook_command = gdb_hook_command.format(self.command, "python gdb._hooks", "$arg")

        # Write the command to file, then source it
        def write_and_source():
            try:
                with tempfile.NamedTemporaryFile(delete=False) as f:
                    f.write(formatted_hook_command)
                    f.close()

                    gdb.execute("source {0}".format(f.name))

                    # XXX - This is a hack. Apparently GDB isn't reading
                    # the file right away on execute, and deleting it right
                    # away causes the command not to be defined
                    time.sleep(0.15)
                    f.delete()
            except:
                pass

        # The use of post_event is important here. Without it,
        # the commands don't seem to actually get defined in GDB
        gdb.post_event(write_and_source)

        try:
            gdb._hooks[self.command] = self._on_call
        except AttributeError:
            gdb._hooks = {}
            gdb._hooks[self.command] = self._on_call

        _GDBHook._hook_registry[self.command] = self

    def _on_call(self, *args):
        for callback in self.callbacks:
            callback(self.command, *args)

    @staticmethod
    def get_hook(command):
        if not _GDBHook._hook_registry.has_key(command):
            _GDBHook._hook_registry[command] = _GDBHook(command)

        return _GDBHook._hook_registry[command]


class HookCommand(gdb.Command):
    """Hook a command with a user-defined hook

Usage: hook [command] [hook]

When hooking a command, the user-defined hook is pushed onto a stack of
commands. The hooks are run in the order they were defined in. You can remove
a user-defined command from this stack of hooks by using unhook."""

    def __init__(self, hook_registry):
        super(HookCommand, self).__init__("hook", gdb.COMMAND_SUPPORT)

        self.user_hooks = hook_registry

    def invoke(self, args, from_tty):
        parsed_args = gdb.string_to_argv(args)

        if len(parsed_args) != 2:
            print "hook takes exactly two arguments, see \"help hook\""
            return

        builtin_func, user_func = parsed_args

        # XXX - Should probably check that the user function is defined

        current_hooks = self.user_hooks.setdefault(builtin_func, None)

        if current_hooks is None:
            _GDBHook.get_hook(builtin_func).add_callback(self.on_command)

            current_hooks = []
            self.user_hooks[builtin_func] = current_hooks

        current_hooks.append(user_func)

    def on_command(self, command):
        """Execute the user-defined hooks"""

        for hook in self.user_hooks[command]:
            gdb.execute(hook)


class UnhookCommand(gdb.Command):
    """Unhook a hooked command

Usage: unhook [command] [hook]

"""

    def __init__(self, hook_registry):
        super(UnhookCommand, self).__init__("unhook", gdb.COMMAND_SUPPORT)

        self.user_hooks = hook_registry

    def invoke(self, args, from_tty):
        parsed_args = gdb.string_to_argv(args)

        if len(parsed_args) != 2:
            print "unhook takes exactly two arguments, see \"help unhook\""
            return

        builtin_func, user_func = parsed_args

        current_hooks = self.user_hooks.get(builtin_func, None)

        if current_hooks is None:
            print "No hooks installed for this command"
            return

        if current_hooks.count(user_func) > 0:
            current_hooks.remove(user_func)
        else:
            print "User-defined function is not a hook for this command"
            return

# Initialize the "hook" and "unhook" commands
_hook_registry = {}
HookCommand(_hook_registry)
UnhookCommand(_hook_registry)

try:
    from gdb import events
except ImportError:
    # Now we're cooking with fire. This is a best approximation
    # of the events API from the documentation. I don't have a GDB
    # version new enough to test it out, but the goal was a drop in
    # replacement to allow for cross-version compatibility

    events = ModuleType("_gdb.events")

    # Simulate this being a sub module
    sys.modules[__name__].events = events
    sys.modules[__name__ + ".events"] = events

    class _ThreadEvent(object):
        def __init__(self):
            self.inferior_thread = None

    class _ContinueEvent(_ThreadEvent):
        pass

    class _EventRegistry(object):
        def connect(self, _callable):
            pass

        def disconnect(self, _callable):
            pass

    class _ContinueEventRegistry(_EventRegistry):
        def __init__(self):
            self._hooks = []
            self._callables_to_callbacks = {}

            continue_events = [
                "advance", "continue", "finish", "jump", "next", "nexti", "reverse-continue",
                "reverse-finish", "reverse-next", "reverse-nexti", "reverse-step", "reverse-stepi",
                "step", "stepi", "until"
            ]

            for command in continue_events:
                self._hooks.append(_GDBHook.get_hook(command))

        def connect(self, _callable):
            assert _callable is not None

            for hook in self._hooks:
                def callback(*args):
                    _ContinueEventRegistry._event_callback(_callable, *args)

                #callback = lambda a1, a2, a3, a4, a5, a6, a7, a8, a9, a10: _callable
                hook.add_callback(callback)
                self._callables_to_callbacks[_callable] = callback

        def disconnect(self, _callable):
            callback = self._callables_to_callbacks.pop(_callable, None)

            assert callback is not None

            for hook in self._hooks:
                hook.remove_callback(callback)

        @staticmethod
        def _event_callback(_callable, *args):
            # We probably don't have enough info to do a real
            # ThreadEvent object, so always return an empty one
            _callable(_ThreadEvent())

    events.ThreadEvent = _ThreadEvent
    events.ContinueEvent = _ContinueEvent
    events.EventRegistry = _EventRegistry
    events.cont = _ContinueEventRegistry()