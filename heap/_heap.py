"""Common heap classes and functions are grouped into this module"""

#from glibc import is_using_glibc_heap, register_glibc_commands

from abc import ABCMeta, abstractmethod
from glibc import is_using_glibc_heap

UnsupportedHeap = 44

class HeapAnalyzer(object):
    from abc import ABCMeta

    @abstractmethod
    def register_commands(self):
        pass

    @abstractmethod
    def get_heap_description(self):
        pass

def categorize_heap(inferior):
    if is_using_glibc_heap(inferior):
        return "glibc"
#        inferior_heap_map[inferior] = GlibcHeapAnalyzer
#    else:
#        inferior_heap_map[inferior] = UnsupportedHeap