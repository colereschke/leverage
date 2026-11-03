"""Immutable source data and lineup records for a slate."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

Position = Literal["QB", "RB", "WR", "TE", "DST"]
ContestType = Literal["cash", "gpp"]
NonEmptyStr = Annotated[str, Field(min_length=1)]
FieldSize = Annotated[int, Field(gt=0)]
OwnershipPercent = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]


class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class Slot(DomainModel):
    name: NonEmptyStr
    eligible_positions: frozenset[Position] = Field(min_length=1)

    def accepts(self, position: Position) -> bool:
        return position in self.eligible_positions


class RosterFormat(DomainModel):
    name: NonEmptyStr
    slots: tuple[Slot, ...] = Field(min_length=1)
    salary_cap: int = Field(gt=0)

    @model_validator(mode="after")
    def unique_slots(self) -> "RosterFormat":
        names = [slot.name for slot in self.slots]
        if len(names) != len(set(names)):
            raise ValueError("slot names must be unique")
        return self


DK_CLASSIC = RosterFormat(
    name="DraftKings NFL Classic",
    slots=(
        Slot(name="QB", eligible_positions=frozenset({"QB"})),
        Slot(name="RB1", eligible_positions=frozenset({"RB"})),
        Slot(name="RB2", eligible_positions=frozenset({"RB"})),
        Slot(name="WR1", eligible_positions=frozenset({"WR"})),
        Slot(name="WR2", eligible_positions=frozenset({"WR"})),
        Slot(name="WR3", eligible_positions=frozenset({"WR"})),
        Slot(name="TE", eligible_positions=frozenset({"TE"})),
        Slot(name="FLEX", eligible_positions=frozenset({"RB", "WR", "TE"})),
        Slot(name="DST", eligible_positions=frozenset({"DST"})),
    ),
    salary_cap=50_000,
)


class Game(DomainModel):
    id: NonEmptyStr
    away_team: NonEmptyStr
    home_team: NonEmptyStr
    kickoff: AwareDatetime

    @field_validator("kickoff")
    @classmethod
    def utc_kickoff(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class Slate(DomainModel):
    id: NonEmptyStr
    site: NonEmptyStr
    roster_format: RosterFormat
    week: int = Field(gt=0)
    games: tuple[Game, ...] = Field(min_length=1)
    source_files: tuple[NonEmptyStr, ...] = ()


class Player(DomainModel):
    dk_id: NonEmptyStr
    name: NonEmptyStr
    positions: frozenset[Position] = Field(min_length=1)
    team: NonEmptyStr
    opponent: NonEmptyStr
    game_id: NonEmptyStr
    salary: int = Field(gt=0)


class Projection(DomainModel):
    player_id: NonEmptyStr
    source: NonEmptyStr
    proj: float = Field(ge=0, allow_inf_nan=False)
    floor: float = Field(ge=0, allow_inf_nan=False)
    ceiling: float = Field(ge=0, allow_inf_nan=False)
    imported_at: AwareDatetime
    ownership_by_field_size: tuple[tuple[FieldSize, OwnershipPercent], ...] = ()


class LineupSlot(DomainModel):
    slot: NonEmptyStr
    player_id: NonEmptyStr


class Lineup(DomainModel):
    build_id: NonEmptyStr
    slots: tuple[LineupSlot, ...] = Field(min_length=1)
    salary: int = Field(gt=0)
    proj: float = Field(ge=0, allow_inf_nan=False)
    ceiling: float = Field(ge=0, allow_inf_nan=False)
    ownership: float = Field(ge=0, allow_inf_nan=False)
    tags: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode="after")
    def unique_assignments(self) -> "Lineup":
        names = [entry.slot for entry in self.slots]
        players = [entry.player_id for entry in self.slots]
        if len(names) != len(set(names)) or len(players) != len(set(players)):
            raise ValueError("lineup slots and players must be unique")
        return self


class Portfolio(DomainModel):
    name: NonEmptyStr
    contest_type: ContestType
    lineups: tuple[Lineup, ...]
    target_size: int = Field(gt=0)
