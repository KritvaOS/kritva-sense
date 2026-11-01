"""Console script entry points (KOS-SENSE-007). Each calls the unchanged main of an existing module with the
process arguments, so an installed command behaves exactly like `python3 -m kritva_sense.<module>`."""
import sys

from . import __main__ as _validate_main
from . import conformance as _conformance
from . import frame_graph as _frame_graph
from . import generator as _generator
from . import stream as _stream


def validate():
    return _validate_main.main(sys.argv)


def frame_graph():
    return _frame_graph.main(sys.argv)


def generator():
    return _generator.main()


def stream():
    return _stream.main(sys.argv)


def conformance():
    return _conformance.main(sys.argv)
