import io
import os
from pickle import PickleError

from sflkitlib.events import event

from sflkit.events.mapping import EventMapping

GZIP_MAGIC = b"\x1f\x8b"
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"


def open_event_stream(path: os.PathLike) -> io.BufferedReader:
    """
    Open an event file for reading, transparently decompressing it.

    The runtime tracer may write the event stream through gzip or zstd, so the
    codec is detected from the leading magic bytes rather than the file name.
    The returned object always supports ``peek``, which the event reader relies
    on to detect the end of the stream.

    :param path: Path of the event file.
    :returns: A buffered binary reader over the decoded event stream.
    """
    raw = open(path, "rb")
    try:
        header = raw.read(4)
        raw.seek(0)
    except OSError:
        return raw

    if header.startswith(GZIP_MAGIC):
        import gzip

        return io.BufferedReader(gzip.GzipFile(fileobj=raw, mode="rb"))
    if header.startswith(ZSTD_MAGIC):
        try:
            import zstandard
        except ImportError as e:
            raw.close()
            raise ImportError(
                f"{path} is zstd-compressed but the 'zstandard' package is not "
                "installed. Run: pip install zstandard"
            ) from e
        return io.BufferedReader(zstandard.ZstdDecompressor().stream_reader(raw))
    return raw


class EventFile(object):
    def __init__(
        self,
        path: os.PathLike,
        run_id: int,
        mapping: EventMapping,
        failing: bool = False,
        thread_support: bool = False,
    ):
        self.path = path
        self.run_id = run_id
        self.mapping = mapping
        self.failing = failing
        self.thread_support = thread_support
        self._csv_reader = None
        self._file_pointer = None
        # Event files are the key of every per-run dict in the analysis layer,
        # so this is hashed millions of times per run. The run id never
        # changes, so the hash is computed once.
        self._hash = hash(run_id)

    def __getstate__(self) -> dict:
        # Event files key the analysis layer's per-run state, so they travel
        # with any result that crosses a process boundary. An open (or closed)
        # file handle is not picklable and means nothing in another process,
        # so it is dropped; reopening is what the context manager is for.
        state = dict(self.__dict__)
        state["_file_pointer"] = None
        state["_csv_reader"] = None
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        if not isinstance(other, EventFile):
            return False
        return self.run_id == other.run_id

    def __enter__(self):
        self._file_pointer = open_event_stream(self.path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._file_pointer.close()

    def __repr__(self):
        return f'{self.path}:{self.run_id}:{"FAIL" if self.failing else "PASS"}'

    def __str__(self):
        return repr(self)

    def load(self):
        # A trace can end mid-stream: the run may have been killed by a timeout
        # or have exhausted its trace budget. Every decoding error therefore
        # ends the stream cleanly instead of failing the analysis; events read
        # up to that point stay valid because events are written whole.
        while True:
            try:
                if not self._file_pointer.peek(1):
                    break
                e = event.load_next_event(
                    self._file_pointer,
                    self.mapping.mapping,
                    with_thread_id=self.thread_support,
                )
            except (IndexError, ValueError, PickleError, KeyError, EOFError, OSError):
                break
            if self.mapping.is_valid(e):
                yield e
