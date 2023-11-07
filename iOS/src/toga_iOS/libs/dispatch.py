##########################################################################
# Library/Developer/CommandLineTools/SDKs/MacOSX13.1.sdk/usr/include/dispatch
##########################################################################
from ctypes import (
    Structure,
    byref,
    c_char_p,
    c_int64,
    c_uint64,
    c_ulong,
    c_void_p,
    cast,
    cdll,
    util,
)

from rubicon.objc import ObjCInstance, objc_id

######################################################################
libdispatch = cdll.LoadLibrary(util.find_library("libdispatch"))
######################################################################

# libdispatch = load_library("System")


class struct_dispatch_queue_s(Structure):
    pass  # No _fields_, because this is an opaque structure.


_dispatch_main_q = struct_dispatch_queue_s.in_dll(libdispatch, "_dispatch_main_q")


def dispatch_get_main_queue():
    return ObjCInstance(cast(byref(_dispatch_main_q), objc_id))


libdispatch.dispatch_queue_create.restype = objc_id
libdispatch.dispatch_queue_create.argtypes = [c_char_p, objc_id]

libdispatch.dispatch_after.restype = c_void_p
libdispatch.dispatch_after.argtypes = [c_uint64, objc_id, objc_id]
# (dispatch_time_t when, dispatch_queue_t queue, dispatch_block_t block);

libdispatch.dispatch_block_create.restype = objc_id
libdispatch.dispatch_block_create.argtypes = [c_ulong, objc_id]

libdispatch.dispatch_block_cancel.restype = c_void_p
libdispatch.dispatch_block_cancel.argtypes = [objc_id]

libdispatch.dispatch_time.restype = c_uint64
libdispatch.dispatch_time.argtypes = [c_uint64, c_int64]
# (dispatch_block_flags_t flags, dispatch_block_t block);

DISPATCH_TIME_NOW = 0
NSEC_PER_SEC = 1000000000
