"""Attach a projection CSV to a Slate, applying the spec's import policy."""

import csv
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import TypeAdapter

from leverage.domain import DomainModel, FieldSize, Player, Projection, Slate

TEAM_ALIASES = {"LA": "LAR"}  # ETR's Rams code; DK's is LAR.
NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "dst"}


class ColumnMap(DomainModel):
    source: str
    name: str
    position: str
    team: str
    salary: str
    projection: str
    dk_id: str | None = None
    floor: str | None = None
    ceiling: str | None = None
    ownership: tuple[tuple[FieldSize, str], ...] = ()

    @property
    def required(self) -> list[str]:
        optional = (self.dk_id, self.floor, self.ceiling)
        return [
            self.name,
            self.position,
            self.team,
            self.salary,
            self.projection,
            *(column for column in optional if column is not None),
            *(column for _, column in self.ownership),
        ]


ETR_COLUMNS = ColumnMap(
    source="ETR",
    name="Player",
    position="DK Pos",
    team="Team",
    salary="DK Salary",
    projection="DK Proj",
    dk_id="id",
    floor="DK Floor",
    ceiling="DK Ceiling",
    ownership=(("small", "Small Field"), ("large", "Large Field")),
)
GENERIC_COLUMNS = ColumnMap(
    source="generic",
    name="name",
    position="position",
    team="team",
    salary="salary",
    projection="projection",
)


class ReportRow(DomainModel):
    row: int
    name: str
    team: str


class Mismatch(DomainModel):
    dk_id: str
    name: str
    attribute: str
    dk_value: str
    file_value: str


class ImportReport(DomainModel):
    """Every file row is imported, blocked, ambiguous, unmatched or ignored."""

    rows: int
    imported: int
    ambiguous: tuple[ReportRow, ...]
    unmatched: tuple[ReportRow, ...]
    ignored: tuple[ReportRow, ...]
    mismatches: tuple[Mismatch, ...]
    blocked: tuple[str, ...]
    unprojected_count: int
    unprojected_names: tuple[str, ...]

    @property
    def is_clean(self) -> bool:
        return self.imported == self.rows and not self.mismatches and not self.unprojected_count


class ImportResult(DomainModel):
    projections: tuple[Projection, ...]
    report: ImportReport


class ProjectionFileError(ValueError):
    def __init__(self, row: int, reason: str) -> None:
        super().__init__(f"row {row}: {reason}")
        self.row = row
        self.reason = reason


class AmbiguousMatchError(ValueError):
    """Blocks the whole import, so ambiguous rows can't reach a build by being overlooked."""

    def __init__(self, report: ImportReport) -> None:
        rows = ", ".join(f"row {entry.row} ({entry.name})" for entry in report.ambiguous)
        super().__init__(f"ambiguous matches: {rows}")
        self.report = report


@dataclass(frozen=True)
class ParsedRow:
    row: int
    name: str
    team: str
    position: str
    salary: int
    dk_id: str
    projection: Projection

    @property
    def key(self) -> str:
        # Not the row number: ETR re-issues files, and a shifted row must not match a resolution.
        return f"{self.name}|{self.team}|{self.position}|{self.salary}"

    def resolution_key(self, resolved: dict[str, str | None]) -> str | None:
        # The row key is for rows identical in key alone. It embeds the key, so a shifted row
        # that lands on another player's row number misses it and stays blocked.
        row_key = f"{self.key}|row {self.row}"
        return next((key for key in (row_key, self.key) if key in resolved), None)

    @property
    def report_row(self) -> ReportRow:
        return ReportRow(row=self.row, name=self.name, team=self.team)


def normalize_name(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    words = re.sub(r"[^\w\s]", "", ascii_name).lower().split()
    return " ".join(word for word in words if word not in NAME_SUFFIXES)


def number_text(value: str) -> str:
    return value.strip().replace("$", "").replace(",", "").rstrip("%")


def parse_row(
    row: dict[str, str], line: int, columns: ColumnMap, imported_at: datetime
) -> ParsedRow:
    for label, column in (
        ("name", columns.name),
        ("position", columns.position),
        ("team", columns.team),
    ):
        if not row[column].strip():
            raise ValueError(f"blank {label}")

    salary = number_text(row[columns.salary])
    if not salary.isdecimal():
        raise ValueError(f"invalid salary {row[columns.salary]!r}")

    name = row[columns.name].strip()
    team = row[columns.team].strip()
    proj = float(number_text(row[columns.projection]))
    # A file without floor or ceiling has no spread to offer, so both collapse to the projection.
    floor = float(number_text(row[columns.floor])) if columns.floor else proj
    ceiling = float(number_text(row[columns.ceiling])) if columns.ceiling else proj
    return ParsedRow(
        row=line,
        name=name,
        team=TEAM_ALIASES.get(team, team),
        position=row[columns.position].strip().replace("D/ST", "DST"),
        salary=int(salary),
        dk_id=row[columns.dk_id].strip() if columns.dk_id else "",
        # Validated here so a bad value fails with its row, even on a row that won't match;
        # player_id is replaced once the row is matched.
        projection=Projection(
            player_id=name,
            source=columns.source,
            proj=proj,
            floor=floor,
            ceiling=ceiling,
            imported_at=imported_at,
            ownership_by_field_size=tuple(
                (size, float(number_text(row[column]))) for size, column in columns.ownership
            ),
        ),
    )


def read_rows(path: Path, columns: ColumnMap, imported_at: datetime) -> list[ParsedRow]:
    """Row numbers are file lines, header = 1."""
    rows: list[ParsedRow] = []
    # utf-8-sig because ETR files start with a BOM, which would corrupt the first column name.
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        headers = reader.fieldnames or ()
        # DictReader keeps only the last value of a repeated column, losing the others silently.
        duplicates = sorted({header for header in headers if headers.count(header) > 1})
        if duplicates:
            raise ProjectionFileError(1, f"duplicate columns: {', '.join(duplicates)}")
        missing = [column for column in columns.required if column not in headers]
        if missing:
            raise ProjectionFileError(1, f"missing columns: {', '.join(missing)}")

        for row in reader:
            try:
                if None in row or None in row.values():
                    raise ValueError(f"expected {len(headers)} columns")
                rows.append(parse_row(row, reader.line_num, columns, imported_at))
            except ValueError as exc:
                raise ProjectionFileError(reader.line_num, str(exc)) from exc

    if not rows:
        raise ProjectionFileError(1, "empty file: no projection rows")
    return rows


def find_mismatches(row: ParsedRow, player: Player) -> list[Mismatch]:
    values = (
        ("salary", str(player.salary), str(row.salary)),
        ("team", player.team, row.team),
        ("position", "/".join(sorted(player.positions)), row.position),
    )
    return [
        Mismatch(
            dk_id=player.dk_id,
            name=player.name,
            attribute=attribute,
            dk_value=dk_value,
            file_value=file_value,
        )
        for attribute, dk_value, file_value in values
        if dk_value != file_value
    ]


def unprojected_names(players: list[Player], slate: Slate) -> tuple[str, ...]:
    minimums: dict[str, int] = {}
    for player in slate.players.values():
        for position in player.positions:
            minimums[position] = min(player.salary, minimums.get(position, player.salary))
    return tuple(
        player.name
        for player in players
        if not player.injury_status
        and player.salary > min(minimums[position] for position in player.positions)
    )


def import_projections(
    path: Path,
    slate: Slate,
    columns: ColumnMap,
    imported_at: datetime,
    resolutions: Path | None = None,
) -> ImportResult:
    """Match by DK ID, then name + team; raises AmbiguousMatchError until every match is settled.

    The resolutions file is a JSON object of "name|team|position|salary" to a DK ID, or to null to
    ignore the row. Team and position are normalized (LAR, DST) and salary is a plain integer.
    Naming a row also marks its team mismatch as reviewed. DK IDs change per slate, so a
    resolution file belongs to one slate. Rows identical in all four need a row-specific key,
    "name|team|position|salary|row N", with N the file line; it wins over the plain key.
    """
    rows = read_rows(path, columns, imported_at)
    resolved: dict[str, str | None] = {}
    if resolutions is not None:
        resolved = TypeAdapter(dict[str, str | None]).validate_json(resolutions.read_bytes())

    by_name_team: dict[tuple[str, str], list[Player]] = {}
    for player in slate.players.values():
        by_name_team.setdefault((normalize_name(player.name), player.team), []).append(player)

    ambiguous: list[ParsedRow] = []
    unmatched: list[ParsedRow] = []
    ignored: list[ParsedRow] = []
    claims: dict[str, list[ParsedRow]] = {}
    for row in rows:
        key = row.resolution_key(resolved)
        if key is not None:
            target = resolved[key]
            if target is None:
                ignored.append(row)
                continue
            if target not in slate.players:
                raise ProjectionFileError(row.row, f"resolution names unknown DK ID {target}")
            candidates = [slate.players[target]]
        elif row.dk_id in slate.players:
            candidates = [slate.players[row.dk_id]]
        else:
            candidates = by_name_team.get((normalize_name(row.name), row.team), [])

        if not candidates:
            unmatched.append(row)
        elif len(candidates) > 1:
            ambiguous.append(row)
        else:
            claims.setdefault(candidates[0].dk_id, []).append(row)

    projections: list[Projection] = []
    mismatches: list[Mismatch] = []
    blocked: list[str] = []
    for dk_id, claimed in claims.items():
        if len(claimed) > 1:
            ambiguous.extend(claimed)
            continue
        row = claimed[0]
        found = find_mismatches(row, slate.players[dk_id])
        mismatches.extend(found)
        reviewed = row.resolution_key(resolved) is not None
        if any(entry.attribute == "team" for entry in found) and not reviewed:
            blocked.append(dk_id)
        else:
            projections.append(row.projection.model_copy(update={"player_id": dk_id}))

    unprojected = [player for dk_id, player in slate.players.items() if dk_id not in claims]
    report = ImportReport(
        rows=len(rows),
        imported=len(projections),
        ambiguous=tuple(row.report_row for row in sorted(ambiguous, key=lambda row: row.row)),
        unmatched=tuple(row.report_row for row in unmatched),
        ignored=tuple(row.report_row for row in ignored),
        mismatches=tuple(mismatches),
        blocked=tuple(blocked),
        unprojected_count=len(unprojected),
        unprojected_names=unprojected_names(unprojected, slate),
    )
    if ambiguous:
        raise AmbiguousMatchError(report)
    return ImportResult(projections=tuple(projections), report=report)
