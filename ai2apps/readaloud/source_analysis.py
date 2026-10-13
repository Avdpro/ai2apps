"""Reviewable source-text planning; analysis never changes a project."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator

Role = Literal['auto','narrator','female_lead','male_lead','default_male','default_female']

class ProposedActor(BaseModel):
    model_config = ConfigDict(extra='forbid')
    key: str = Field(pattern=r'^new_[a-zA-Z0-9_]+$', max_length=80)
    name: str = Field(min_length=1, max_length=120)
    role: Role = 'auto'
    notes: str = Field(default='', max_length=2000)
    voice_profile_id: str | None = None

    @field_validator('voice_profile_id', mode='before')
    @classmethod
    def empty_voice(cls, value):
        return value or None


class ProposedLine(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(min_length=1, max_length=10000)
    speaker_id: str | None = None
    @field_validator('speaker_id', mode='before')
    @classmethod
    def empty_speaker(cls, value):
        return value or None

    emotion: Literal['neutral','happy','sad','angry','calm','excited','whisper'] = 'neutral'
    speed: float = Field(default=1, ge=0.5, le=2)
    pause_after_ms: int = Field(default=300, ge=0, le=10000)

class SourceProposal(BaseModel):
    model_config = ConfigDict(extra='forbid')
    actors: list[ProposedActor] = Field(default_factory=list, max_length=30)
    lines: list[ProposedLine] = Field(min_length=1, max_length=400)

class SourceApplyRequest(SourceProposal):
    batch_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    revision: int
    after_id: str | None = None


def validate_proposal(proposal, project):
    existing = {actor['id'] for actor in project['characters']}
    keys = [actor.key for actor in proposal.actors]
    names = [actor.name.strip() for actor in proposal.actors]
    if len(set(keys)) != len(keys) or len(set(names)) != len(names) or any(not name for name in names):
        raise ValueError('New actors must have unique keys and non-empty unique names.')
    if set(names) & {actor['name'] for actor in project['characters']}:
        raise ValueError('Reuse existing actors instead of creating duplicate names.')
    for line in proposal.lines:
        if not line.text.strip() or (line.speaker_id and line.speaker_id not in existing | set(keys)):
            raise ValueError('Every line needs text and a valid actor selection.')
