"""Owned Studio forms backed by a pinned, installed Skill."""
import json
import math
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .library import is_text_reference

IMAGINE = "ai2apps.imagine-studio"
OPTIONS = (
    (IMAGINE, "Imagine Studio", "图像工作室"),
    ("ai2apps.doc-studio", "Doc Studio", "文档工作室"),
    ("ai2apps.readaloud", "Voice Studio", "语音工作室"),
    ("ai2apps.video-studio", "Video Studio", "视频工作室"),
)
Scalar = str | float | bool
Choice = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class Parameter(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    label: str = Field(min_length=1, max_length=80)
    type: Literal["text", "multiline", "number", "boolean", "choice", "image"]
    required: bool = False
    default: Scalar | None = None
    choices: list[Choice] = Field(default_factory=list, max_length=20)

    def clean(self, value):
        if value is None or value == "":
            if self.required:
                raise ValueError(f"{self.label} is required")
            return None
        valid = False
        if self.type in ("text", "multiline"):
            limit = 300 if self.type == "text" else 4000
            valid = isinstance(value, str) and bool(value.strip()) and len(value) <= limit
        elif self.type == "choice":
            valid = value in self.choices
        elif self.type == "number":
            valid = type(value) in (int, float) and math.isfinite(value)
        elif self.type == "boolean":
            valid = type(value) is bool
        elif self.type == "image":
            valid = isinstance(value, str) and 1 <= len(value) <= 128
        if not valid:
            raise ValueError(f"Invalid value for {self.label}")
        return value

    @model_validator(mode="after")
    def validate_definition(self):
        self.label = self.label.strip()
        if not self.label:
            raise ValueError("Parameter label is required")
        if self.type == "choice":
            if not self.choices or len(set(self.choices)) != len(self.choices):
                raise ValueError("Choice parameters need distinct options")
        elif self.choices:
            raise ValueError("Options apply to choice parameters")
        if self.default is not None:
            if self.type == "image" or self.default == "":
                raise ValueError("Image parameters and empty values cannot be saved as defaults")
            self.clean(self.default)
        return self


class MiniAppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str = Field(min_length=1, max_length=80)
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    studio: str
    parameters: list[Parameter] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def validate_form(self):
        self.title = self.title.strip()
        keys = {field.key for field in self.parameters}
        if not self.title or len(keys) != len(self.parameters):
            raise ValueError("Enter a title and use unique parameter keys")
        if self.studio != IMAGINE:
            raise ValueError("This Studio does not support the Skill's image workflow")
        if sum(field.type == "image" for field in self.parameters) > 4:
            raise ValueError("Use at most four reference image parameters")
        return self


class RunInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    values: dict[str, Scalar | None] = Field(max_length=12)
    key: str = Field(pattern=r"^[0-9a-f-]{36}$")
    model: str = Field(min_length=1, max_length=255)
    size: str = Field(pattern=r"^[0-9]{2,5}x[0-9]{2,5}$")


def resolve_values(config, supplied):
    parameters = [Parameter.model_validate(field) for field in config["parameters"]]
    if supplied.keys() - {field.key for field in parameters}:
        raise ValueError("Unexpected parameter")
    values, images = {}, {}
    for field in parameters:
        value = field.clean(supplied.get(field.key, field.default))
        if value is not None:
            (images if field.type == "image" else values)[field.key] = value
    return values, images


class SkillMiniApps:
    def __init__(self, library):
        self.library = library

    def create(self, owner, skill_id, config):
        with self.library.connect() as db, db:
            db.execute("BEGIN IMMEDIATE")
            skill = self.library.summary(self.library._installed(db, owner, skill_id))
            if skill["revision"] != config.revision:
                raise ValueError("Skill changed. Reopen its details before creating the Mini-App")
            if skill["unsupported"] or not skill["user_invocable"]:
                raise ValueError("This Skill cannot be used in a hosted Mini-App")
            identifier = "ai2apps.skill." + uuid4().hex
            form = config.model_dump() | {
                "skill_name": skill["name"], "description": skill["description"],
                "references": [path for path in skill["files"] if is_text_reference(path)],
            }
            db.execute("INSERT INTO skill_mini_apps VALUES (?,?,?,?,?,?)", (
                owner, identifier, skill_id, config.revision, config.studio, json.dumps(form),
            ))
        return {"id": identifier, **form}

    def list(self, owner, studio):
        with self.library.connect() as db:
            rows = db.execute("SELECT id,config FROM skill_mini_apps WHERE owner=? AND studio=? ORDER BY rowid",
                              (owner, studio)).fetchall()
        return [{"id": row["id"], **json.loads(row["config"])} for row in rows]

    def get(self, owner, identifier, studio, *, read=False):
        archive_column = "r.archive" if read else "NULL AS archive"
        with self.library.connect() as db:
            row = db.execute(f"""SELECT m.config, {archive_column} FROM skill_mini_apps m
                                JOIN skill_revisions r USING(owner,revision)
                                WHERE m.owner=? AND m.id=? AND m.studio=?""",
                             (owner, identifier, studio)).fetchone()
        if row is None:
            raise LookupError("Skill Mini-App is unavailable")
        return json.loads(row["config"]), row["archive"]
