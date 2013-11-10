""""Support for the glibc implementation of the heap"""

import commands

from .. import _gdb as gdb
from .._heap import HeapDetectionError, WrongHeapVersionError, BaseHeapAnalyzer


class BaseGlibcHeapAnalyzer(BaseHeapAnalyzer):
    """Base class for version specific GlibcHeapAnalyzer classes

    This class implements the common functionality across all versions of the
    glibc heap implementation. The subpackages in this package should extend
    this class to implement functionality specific to a glibc version.

    The main reason that this is important is that earlier versions of the
    glibc heap didn't have arenas. This is a fundamental design difference
    and not something we can or should easily gloss over with lots of
    conditional code, so we use separate code bases instead

    """

    def activate_commands(self):
        commands.HeapArenasCommand(self)
        commands.HeapDetailsCommand(self)


def detect_glibc_heap(inferior):
    """Detects if the glibc implementation of the heap is in use

    Returns a heap analyzer for the glibc heap if detection was successful,
    otherwise it raises HeapDetectionError if no glibc heap is found or
    WrongHeapVersion if it is found but is an unsupported version.

    """

    glibc_version = detect_glibc_version()

    if glibc_version is None:
        raise HeapDetectionError("glibc heap not found")

    # TBD - Is it safe to assume that if glibc is linked, and no malloc hooks are
    # found that we must be using the glibc heap implementation?
    # But what about harmless uses of malloc hooks such as mtrace()?
    # We need to determine the best way to find if malloc is truly going to glibc or
    # is being intercepted by something like tcmalloc
    # AND we can't depend on anything that must execute, since we need to work with
    # core dumps as well as active processes

    try:
        module_name = '_' + glibc_version.replace('.', '_')
        package_name = "heap.glibc.{0}".format(module_name)
        analyzer = __import__(package_name, fromlist=["GlibcHeapAnalyzer"]).GlibcHeapAnalyzer
    except ImportError:
        raise WrongHeapVersionError("glibc version {0} not supported".format(glibc_version))

    return analyzer(inferior)

def detect_glibc_version():
    """Detects the glibc version in the currently selected inferior and returns
    the version number as a string, e.g. "2.12"

    """

    # XXX - This code doesn't work because apparently gnu_get_libc_release() returns
    #       a bad pointer value when called in GDB, so for now just stick to objfiles
    #       even though they're less than ideal since they require the version number
    #       to be in the file name, which we might not always get lucky with
    #
    # running_status = gdb.execute("info program", to_string=True)
    #
    # if running_status.strip() == "The program being debugged is not being run.":
    #     pass
    # else:
    #     glibc_version_output = gdb.parse_and_eval("(char*)gnu_get_libc_release()")

    libc_objfiles = [obj.filename for obj in gdb.objfiles() if obj.filename.find('libc-') > 0]

    if len(libc_objfiles) != 1:
        return None
    else:
        return libc_objfiles[0].split('-')[1].split('.so')[0]