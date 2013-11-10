""""glibc 2.12 specific heap implementation"""

from .. import BaseGlibcHeapAnalyzer


class GlibcHeapAnalyzer(BaseGlibcHeapAnalyzer):
    def get_heap_description(self):
        return "GNU libc 2.12 Heap Implementation"