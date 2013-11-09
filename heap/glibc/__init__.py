""""Support for the glibc implementation of the heap"""

import gdb
from .._gdb import selected_inferior

def is_using_glibc_heap(inferior):
    # XXX - How to properly detect if we're using the glibc heap? How does the use
    # of malloc hooks affect this?

    #print detect_glibc_version((selected_inferior()))
    return True

def detect_glibc_version():
    """Detects the glibc version in the currently selected inferior and returns
    the version number as a string, e.g. "2.12"

    """

    # XXX - This code doesn't work because apparently gnu_get_libc_release() returns
    #       a bad pointer value when called in GDB, so for now just stick to objfiles
    #
    # running_status = gdb.execute("info program", to_string=True)
    #
    # if running_status.strip() == "The program being debugged is not being run.":
    #     pass
    # else:
    #     glibc_version_output = gdb.parse_and_eval("(char*)gnu_get_libc_release()")

    libc_objfiles = [obj.filename for obj in gdb.objfiles() if obj.filename.find('libc-') > 0]

    if len(libc_objfiles) != 1:
        # XXX - Can't detect version
        pass
    else:
        return libc_objfiles[0].split('-')[1].split('.so')[0]