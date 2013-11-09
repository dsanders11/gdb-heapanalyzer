"""Collection of GDB helpers, mainly compatibility shims"""

__all__ = ['selected_inferior']

# Older versions of the GDB Python API don't have
# selected_inferior, so we have ot fake the support
try:
    from gdb import selected_inferior
except ImportError:
    import gdb

    def selected_inferior():
        inferiors = gdb.inferiors()
        inferior_output = gdb.execute("info inferiors", to_string=True)
        header, inferior_lines = inferior_output.split('\n')[0], inferior_output.split('\n')[1:]

        assert header.split() == ["Num", "Description", "Executable"]

        for inferior_line in inferior_lines:
            # The selected inferior has a star in front:
            if inferior_line.lstrip().startswith('*'):
                inferior_id = inferior_line.split()[1]

                for inferior in inferiors:
                    if int(inferior.num) == int(inferior_id):
                        return inferior

        assert False, "Selected inferior not found"
