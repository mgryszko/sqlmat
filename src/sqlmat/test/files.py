import csv
import io
import json
from pathlib import Path

from approvaltests import Namer, get_default_namer, verify
from approvaltests.namer import NamerFactory
from fsspec import open_files


class ExtensionNamer(Namer):
    def __init__(self, base_namer: Namer, extension: str):
        self.base_namer = base_namer
        self.extension = extension

    def get_approved_filename(self, base_name: str | None = None) -> str:
        return self.base_namer.get_approved_filename(base_name).replace(".approved.txt", f".approved.{self.extension}")

    def get_received_filename(self, base_name: str | None = None) -> str:
        return self.base_namer.get_received_filename(base_name).replace(".received.txt", f".received.{self.extension}")


class Files:
    def __init__(self, path: Path | str):
        self.path = path

    def approve_parquet(self, scrub_columns: list[str] | None = None, sort_columns: list[str] | None = None) -> None:
        import polars as pl

        pl.Config.set_tbl_width_chars(1000)
        df = pl.read_parquet(str(self.path))
        if sort_columns:
            df = df.sort(sort_columns)
        for column in scrub_columns or []:
            col_type = df.schema[column]
            if col_type == pl.Date:
                df = df.with_columns(pl.lit("YYYY-MM-DD").alias(column))
            elif col_type.base_type() == pl.Datetime:
                df = df.with_columns(pl.lit("YYYY-MM-DD HH:MM:SS").alias(column))
            else:
                df = df.with_columns(pl.lit("SCRUBBED").alias(column))
        verify(str(df))

    def approve_jsonl(self, sort_columns: list[str] | None = None) -> None:
        received = [json.loads(line) for line in (self._read_lines())]
        if sort_columns:
            received.sort(key=lambda row: tuple(row[col] for col in sort_columns))
        normalized_received = json.dumps(received, indent=2, sort_keys=True)

        namer = ExtensionNamer(get_default_namer(), "json")
        verify(normalized_received, options=NamerFactory.with_parameters().with_namer(namer))

    def approve_csv(self, header: bool = False, sort_columns: list[str] | None = None) -> None:
        if header:
            received = self._read_csv_with_header(sort_columns)
        else:
            received = self._read()

        namer = ExtensionNamer(get_default_namer(), "csv")
        verify(received, options=NamerFactory.with_parameters().with_namer(namer))

    def _read_csv_with_header(self, sort_columns: list[str] | None = None) -> str:
        rows = []
        fieldnames = None
        for of in open_files(str(self.path), "r", compression="infer"):
            with of as f:
                reader = csv.DictReader(f)
                if fieldnames is None:
                    fieldnames = reader.fieldnames
                rows.extend(reader)
        if sort_columns:
            rows.sort(key=lambda row: tuple(row[col] for col in sort_columns))
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    def _read(self) -> str:
        contents = []
        for of in open_files(str(self.path), "r", compression="infer"):
            with of as f:
                contents.append(f.read())
        return "".join(contents)

    def _read_lines(self) -> list[str]:
        lines = []
        for of in open_files(str(self.path), "r", compression="infer"):
            with of as f:
                lines += f.readlines()
        return lines
