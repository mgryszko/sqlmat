import csv
import io
import json
from pathlib import Path

from approvaltests import Options, verify
from fsspec import open_files


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
        normalized_received = json.dumps(received, indent=2)

        verify(normalized_received, options=Options().for_file.with_extension("json"))

    def approve_csv(
        self,
        header: bool = False,
        sort_columns: list[str] | None = None,
        fieldnames: list[str] | None = None,
        delimiter: str = ",",
    ) -> None:
        if header:
            received = self._read_csv_with_header(sort_columns, delimiter)
        else:
            received = self._read_csv_by_fieldnames(fieldnames, sort_columns, delimiter)
        verify(received, options=Options().for_file.with_extension("csv"))

    def _read_csv_with_header(self, sort_columns: list[str] | None, delimiter: str = ",") -> str:
        rows = []
        fieldnames = None
        for of in open_files(str(self.path), "r", compression="infer"):
            with of as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                if fieldnames is None:
                    fieldnames = reader.fieldnames
                rows.extend(reader)
        if sort_columns:
            rows.sort(key=lambda row: tuple(row[col] for col in sort_columns))
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n", delimiter=delimiter)
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    def _read_csv_by_fieldnames(self, fieldnames: list[str] | None, sort_columns: list[str] | None, delimiter: str) -> str:
        rows = []
        for of in open_files(str(self.path), "r", compression="infer"):
            with of as f:
                rows.extend(csv.DictReader(f, fieldnames=fieldnames, delimiter=delimiter))
        if sort_columns:
            rows.sort(key=lambda row: tuple(row[col] for col in sort_columns))
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames or list(rows[0].keys()), lineterminator="\n", delimiter=delimiter)
        writer.writerows(rows)
        return output.getvalue()

    def _read_lines(self) -> list[str]:
        lines = []
        for of in open_files(str(self.path), "r", compression="infer"):
            with of as f:
                lines += f.readlines()
        return lines
