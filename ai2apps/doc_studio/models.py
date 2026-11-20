from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Id = Annotated[str, StringConstraints(pattern=r'^[a-zA-Z0-9_-]{1,80}$')]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
MAX_DRAFT_CHARS = 24_000
X_POST_LIMIT = 280
X_LONG_POST_LIMIT = 25_000
# Inline evidence markers are removed before export.
MAX_LONG_DRAFT_CHARS = X_LONG_POST_LIMIT + 1_000
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_LONG_DRAFT_CHARS)]
Target = Literal['x-post', 'x-long-post', 'html']
Style = Literal['summary', 'analysis', 'commentary', 'news']
Language = Literal['zh', 'zh-TW', 'en', 'ja', 'ko', 'fr', 'de', 'es', 'pt-BR', 'ru']

APP_ID = 'ai2apps.doc-studio'
MINI_ID = 'ai2apps.doc-studio.write-article'


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class PackSelection(Input):
    article_ids: list[Id] = Field(min_length=1, max_length=20)


class Import(Input):
    pack_id: Id
    project_id: Id | None = None
    title: Title | None = None
    request_id: Id


class ProjectTitle(Input):
    title: Title


class CreateProject(ProjectTitle):
    request_id: Id


class WritingOptions(Input):
    style: Style
    target: Target
    language: Language
    guidance: str = Field(default='', max_length=4000)
    base_version_id: Id | None = None


class Generate(WritingOptions):
    request_id: Id


class Edit(Input):
    request_id: Id
    title: Title
    content: Text | None = None
    blocks: list['DraftBlock'] | None = Field(default=None, max_length=1200)


class TextBlock(Input):
    type: Literal['paragraph', 'heading', 'quote', 'list']
    text: Text


class DraftImage(Input):
    asset_id: Id
    alt: str = Field(default='', max_length=1000)


class ImageRow(Input):
    type: Literal['image_row']
    images: list[DraftImage] = Field(min_length=1, max_length=20)


DraftBlock = Annotated[TextBlock | ImageRow, Field(discriminator='type')]


class GalleryImage(Input):
    asset_id: Id


class RewriteBlock(Input):
    request_id: Id
    version_id: Id
    block: TextBlock
    instruction: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class Export(Input):
    request_id: Id
    version_id: Id
