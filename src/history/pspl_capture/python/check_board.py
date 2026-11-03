"""Run this in a new notebook on the PYNQ-Z2: %run check_board.py"""
from __future__ import print_function
import platform
import socket
import sys

print('Machine:', platform.machine())
print('Hostname:', socket.gethostname())
print('Python:', sys.version)
try:
    import pynq
except ImportError:
    raise RuntimeError('PYNQ is unavailable in this Python environment. Open the board Jupyter service.')
print('PYNQ:', getattr(pynq, '__version__', 'unknown'))
if not platform.machine().lower().startswith(('arm', 'aarch64')):
    raise RuntimeError('This is not an ARM board environment. Check which Jupyter kernel you opened.')
print('BOARD PYTHON ENVIRONMENT CHECK PASSED')
print('This checks the board Python environment; it does not test the custom PL design yet.')
