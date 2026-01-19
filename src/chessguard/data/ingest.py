"""Utilities for downloading and validating chess game data.

The ingestion helpers centralise knowledge about *trusted* upstream sources so
that experiments and production pipelines both rely on the same validation
rules.  The functions operate purely on the Python standard library to keep the
module lightweight; optional dependencies such as :mod:`pyarrow` are imported
lazily when materialising Arrow/Parquet tables.
"""
from __future__ import annotations

import datetime as _dt
import gzip
import json
import logging
import bz2
import lzma
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

PGN_TAG_PATTERN = re.compile(r"^\[(?P<key>[A-Za-z0-9_]+)\s+\"(?P<value>.*)\"\]")


@dataclass(frozen=True)
class FieldSpec:
    """Definition of a required field within an incoming record.

    Attributes
    ----------
    path:
        Dot-separated location inside the mapping.  Nested keys such as
        ``"players.white.rating"`` are supported.
    types:
        Tuple of accepted Python types for the field.  The first entry is used
        when attempting to coerce values represented as strings.
    required:
        Whether the field must be present.  Optional fields are skipped when
        missing but still validated when provided.
    description:
        Optional human readable explanation of the field.
    """

    path: str
    types: Tuple[type, ...] = (str,)
    required: bool = True
    description: Optional[str] = None

    def __post_init__(self) -> None:  # pragma: no cover - defensive programming
        if not self.types:
            raise ValueError("FieldSpec.types must contain at least one type")


@dataclass(frozen=True)
class TrustedSource:
    """Metadata describing a known-good upstream dataset."""

    name: str
    url: str
    format: str
    schema: Sequence[FieldSpec] = field(default_factory=tuple)
    description: str = ""
    compression: Optional[str] = None
    default_output_name: Optional[str] = None

    def resolve_compression(self) -> Optional[str]:
        """Return the configured compression or infer it from the URL."""

        if self.compression:
            return self.compression
        return infer_compression_from_path(self.url)


TRUSTED_SOURCES: Dict[str, TrustedSource] = {}
"""Registry of known ingestion endpoints keyed by ``TrustedSource.name``."""


def register_trusted_source(source: TrustedSource) -> None:
    """Register a :class:`TrustedSource` for reuse.

    Existing entries with the same ``name`` will be replaced.
    """

    TRUSTED_SOURCES[source.name] = source
    logger.debug("Registered trusted source '%s' -> %s", source.name, source.url)


def get_trusted_source(name: str) -> TrustedSource:
    """Retrieve a :class:`TrustedSource` by name."""

    try:
        return TRUSTED_SOURCES[name]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise KeyError(f"Unknown trusted source: {name!r}") from exc


# Pre-populate the registry with a couple of commonly used sources.
register_trusted_source(
    TrustedSource(
        name="lichess_master_games",
        url="https://database.lichess.org/masters/lichess_db_master_rated_2023-01.pgn.bz2",
        format="pgn",
        schema=(
            FieldSpec("Event"),
            FieldSpec("Site"),
            FieldSpec("Date"),
            FieldSpec("White"),
            FieldSpec("Black"),
            FieldSpec("Result"),
            FieldSpec("Moves"),
        ),
        description="Monthly Lichess masters database (compressed PGN).",
        compression="bz2",
    )
)
register_trusted_source(
    TrustedSource(
        name="lichess_json_sample",
        url="https://lichess.org/api/games/user/Hikaru?max=100&pgnInJson=true",
        format="json",
        schema=(
            FieldSpec("id"),
            FieldSpec("status"),
            FieldSpec("pgn"),
            FieldSpec("players.white.rating", (int, float)),
            FieldSpec("players.black.rating", (int, float)),
        ),
        description="Sample JSON payload from the Lichess games API.",
    )
)


def infer_compression_from_path(path: str) -> Optional[str]:
    """Infer the compression type based on a filename or URL."""

    lowered = path.lower()
    for suffix, comp in {
        ".gz": "gzip",
        ".gzip": "gzip",
        ".bz2": "bz2",
        ".xz": "xz",
        ".lzma": "xz",
        ".zst": "zstd",
    }.items():
        if lowered.endswith(suffix):
            return comp
    return None


def fetch_remote_bytes(source: TrustedSource, timeout: int = 120) -> bytes:
    """Download a remote resource and return its raw bytes."""

    logger.info("Fetching %s from %s", source.name, source.url)
    request = urllib.request.Request(
        source.url,
        headers={"User-Agent": "ChessGuard/ingest (+https://github.com/)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to download data from {source.url!r}: {exc}") from exc

    logger.debug("Fetched %d bytes from %s", len(data), source.url)
    return data


def decompress_bytes(data: bytes, compression: Optional[str]) -> bytes:
    """Decompress ``data`` according to ``compression`` if provided."""

    if not compression:
        return data
    compression = compression.lower()
    if compression in {"gzip", "gz"}:
        return gzip.decompress(data)
    if compression == "bz2":
        return bz2.decompress(data)
    if compression in {"xz", "lzma"}:
        return lzma.decompress(data)
    if compression == "zstd":  # pragma: no cover - optional dependency
        try:
            import zstandard as zstd
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "zstandard support requires the 'zstandard' package to be installed"
            ) from exc
        dctx = zstd.ZstdDecompressor()
        return dctx.decompress(data)
    raise ValueError(f"Unsupported compression format: {compression}")


def parse_pgn_records(pgn_text: str) -> List[Dict[str, Any]]:
    """Parse PGN formatted text into a list of dictionaries.

    The parser focuses on metadata extraction.  Move text is concatenated into a
    single string stored under the ``"Moves"`` key.
    """

    records: List[Dict[str, Any]] = []
    headers: Dict[str, Any] = {}
    moves: List[str] = []

    def flush_game() -> None:
        if not headers:
            return
        record = dict(headers)
        record["Moves"] = " ".join(moves).strip()
        records.append(record)
        headers.clear()
        moves.clear()

    for line in pgn_text.splitlines():
        stripped = line.strip()
        if not stripped:
            flush_game()
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            match = PGN_TAG_PATTERN.match(stripped)
            if match:
                headers[match.group("key")] = match.group("value")
            continue
        moves.append(stripped)

    flush_game()
    logger.debug("Parsed %d PGN games", len(records))
    return records


def parse_json_records(json_text: str) -> List[Dict[str, Any]]:
    """Parse JSON or JSON Lines game payloads into dictionaries."""

    text = json_text.strip()
    if not text:
        return []

    # JSON Lines support: treat each non-empty line as an individual JSON object.
    if text[0] != "{" and text[0] != "[":
        records: List[Dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, list):
                records.extend(obj)
            else:
                records.append(obj)
        logger.debug("Parsed %d JSONL games", len(records))
        return records

    loaded = json.loads(text)
    if isinstance(loaded, list):
        records = [item for item in loaded if isinstance(item, Mapping)]
    elif isinstance(loaded, Mapping):
        # Some APIs wrap payloads in an outer dictionary containing a ``games``
        # array.  Fall back to the values if possible.
        if "games" in loaded and isinstance(loaded["games"], list):
            records = [item for item in loaded["games"] if isinstance(item, Mapping)]
        else:
            records = [dict(loaded)]
    else:
        raise ValueError("Unsupported JSON payload structure")

    logger.debug("Parsed %d JSON games", len(records))
    return [dict(record) for record in records]


def _walk_path(record: Mapping[str, Any], path: str) -> Tuple[Any, bool]:
    """Traverse ``record`` using a dotted path.

    Returns a tuple ``(value, present)`` where ``present`` indicates whether the
    full path existed.
    """

    current: Any = record
    for segment in path.split("."):
        if isinstance(current, Mapping) and segment in current:
            current = current[segment]
        else:
            return None, False
    return current, True


def _validate_record(record: MutableMapping[str, Any], schema: Sequence[FieldSpec], *, index: int) -> None:
    """Validate and optionally coerce ``record`` according to ``schema``."""

    for field in schema:
        value, present = _walk_path(record, field.path)
        if not present:
            if field.required:
                raise ValueError(f"Missing required field '{field.path}' in record {index}")
            continue
        if value is None:
            continue
        if not isinstance(value, field.types):
            primary_type = field.types[0]
            try:
                coerced = primary_type(value)
            except Exception as exc:  # pragma: no cover - defensive guard
                raise TypeError(
                    f"Field '{field.path}' in record {index} has type {type(value).__name__}, "
                    f"expected {','.join(t.__name__ for t in field.types)}"
                ) from exc
            _assign_path(record, field.path, coerced)


def _assign_path(record: MutableMapping[str, Any], path: str, value: Any) -> None:
    """Assign ``value`` to a nested ``path`` inside ``record``."""

    parts = path.split(".")
    target: MutableMapping[str, Any] = record
    for part in parts[:-1]:
        next_value = target.get(part)
        if not isinstance(next_value, MutableMapping):
            next_value = {}
            target[part] = next_value
        target = next_value  # type: ignore[assignment]
    target[parts[-1]] = value


def validate_records(records: Sequence[MutableMapping[str, Any]], schema: Sequence[FieldSpec]) -> None:
    """Validate a sequence of records in-place."""

    for index, record in enumerate(records):
        _validate_record(record, schema, index=index)


def records_to_arrow(records: Sequence[Mapping[str, Any]]):
    """Convert ``records`` into a :class:`pyarrow.Table`.

    The dependency on :mod:`pyarrow` is optional and only imported when this
    function is executed.
    """

    try:
        import pyarrow as pa  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "pyarrow is required to materialise Arrow tables. Install it via 'pip install pyarrow'."
        ) from exc

    table = pa.Table.from_pylist(list(records))
    logger.debug("Converted %d records into an Arrow table with schema: %s", table.num_rows, table.schema)
    return table


def write_arrow_table(table, path: Path, format: str = "parquet") -> Path:
    """Persist an Arrow table as ``parquet``/``feather``/``arrow``."""

    format_normalised = format.lower()
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import pyarrow as pa  # noqa: F401 - imported for side effects
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "pyarrow is required to write Arrow or Parquet files. Install it via 'pip install pyarrow'."
        ) from exc

    if format_normalised == "parquet":
        from pyarrow import parquet as pq  # type: ignore

        pq.write_table(table, path)
    elif format_normalised in {"feather", "arrow", "ipc"}:
        import pyarrow.feather as feather  # type: ignore

        # Feather v2 stores data using the Arrow IPC format and is widely
        # supported, so we reuse it for ``.arrow`` as well.
        feather.write_feather(table, path)
    else:
        raise ValueError(f"Unsupported output format: {format}")

    logger.info("Wrote %d rows to %s", table.num_rows, path)
    return path


def ingest_trusted_source(
    source: str | TrustedSource,
    output_dir: Path,
    output_format: str = "parquet",
    *,
    raw_output_dir: Optional[Path] = None,
    limit: Optional[int] = None,
    timestamp: Optional[str] = None,
) -> Path:
    """Fetch, validate, and persist a dataset from a trusted source.

    Parameters
    ----------
    source:
        Either the name of a registered :class:`TrustedSource` or the object
        itself.
    output_dir:
        Directory where the materialised table will be written.
    output_format:
        One of ``"parquet"`` (default), ``"feather"``, or ``"arrow"``.
    raw_output_dir:
        Optional directory in which the raw payload is stored for auditing.
    limit:
        If provided, truncate the dataset to at most ``limit`` records.  Useful
        during local development.
    timestamp:
        Optional timestamp string used when generating the output filename.  By
        default the current UTC timestamp is used.
    """

    if isinstance(source, str):
        source_obj = get_trusted_source(source)
    else:
        source_obj = source

    raw_bytes = fetch_remote_bytes(source_obj)
    if raw_output_dir is not None:
        raw_output_dir.mkdir(parents=True, exist_ok=True)
        raw_name = source_obj.default_output_name or f"{source_obj.name}.raw"
        raw_path = raw_output_dir / raw_name
        raw_path.write_bytes(raw_bytes)
        logger.info("Stored raw snapshot at %s", raw_path)

    compression = source_obj.resolve_compression()
    decompressed = decompress_bytes(raw_bytes, compression)
    text = decompressed.decode("utf-8", errors="replace")

    if source_obj.format.lower() == "pgn":
        records = parse_pgn_records(text)
    elif source_obj.format.lower() == "json":
        records = parse_json_records(text)
    else:
        raise ValueError(f"Unsupported source format: {source_obj.format}")

    if limit is not None:
        records = list(records)[:limit]

    mutable_records: List[MutableMapping[str, Any]] = [dict(record) for record in records]
    if source_obj.schema:
        validate_records(mutable_records, source_obj.schema)

    table = records_to_arrow(mutable_records)

    timestamp_str = timestamp or _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    suffix = {
        "parquet": "parquet",
        "feather": "feather",
        "arrow": "arrow",
        "ipc": "arrow",
    }.get(output_format.lower())
    if suffix is None:
        raise ValueError(f"Unsupported output format: {output_format}")

    file_stem = source_obj.default_output_name or source_obj.name
    output_path = Path(output_dir) / f"{file_stem}-{timestamp_str}.{suffix}"
    write_arrow_table(table, output_path, format=output_format)
    return output_path


__all__ = [
    "FieldSpec",
    "TrustedSource",
    "TRUSTED_SOURCES",
    "register_trusted_source",
    "get_trusted_source",
    "infer_compression_from_path",
    "fetch_remote_bytes",
    "decompress_bytes",
    "parse_pgn_records",
    "parse_json_records",
    "validate_records",
    "records_to_arrow",
    "write_arrow_table",
    "ingest_trusted_source",
]
