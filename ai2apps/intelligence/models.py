from __future__ import annotations

import ipaddress
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator


def public_url(value: str) -> str:
    value = value.strip()
    parts = urlsplit(value)
    host = (parts.hostname or '').lower()
    if parts.scheme not in ('http', 'https') or not host or parts.username or parts.password:
        raise ValueError('请填写公开的 HTTP(S) 网页地址')
    if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')) or '.' not in host:
        raise ValueError('信息源必须是公开网站')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError('信息源不能使用本地或私有地址')
    if parts.port not in (None, 80, 443):
        raise ValueError('信息源仅支持标准 HTTP(S) 端口')
    # Canonical IDs discard only known tracking parameters, retaining topic/search parameters.
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                       if not k.lower().startswith('utm_') and k.lower() not in ('fbclid', 'gclid')])
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or '/', query, ''))


class EditableSection(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9_-]+$')
    name: str = Field(min_length=1, max_length=24)
    description: str = Field(min_length=1, max_length=240)

    @field_validator('name', 'description')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('栏目内容不能为空')
        return value.strip()


class ChannelInput(BaseModel):
    output_language: Literal['zh','zh-TW','en','ja','ko','fr','de','es','pt-BR','ru'] | None = None

    sections: list[EditableSection] | None = Field(default=None, max_length=32)
    expected_sections: list[EditableSection] | None = Field(default=None, max_length=32)

    @field_validator('sections')
    @classmethod
    def unique_sections(cls, value):
        if value is not None and (len({s.id for s in value}) != len(value) or len({s.name.casefold() for s in value}) != len(value)):
            raise ValueError('栏目 ID 和名称不能重复')
        return value

    post_filter_level: Literal['loose', 'standard', 'strict'] = 'standard'
    post_filter_guidance: str = Field(default='', max_length=1000)
    name: str = Field(min_length=1, max_length=80)
    interests: str = Field(min_length=1, max_length=3000)
    excluded: str = Field(default='', max_length=1000)
    interval_hours: Literal[0, 1, 6, 12, 24] = 0
    knowledge_bucket_ids: list[str] | None = Field(default=None, max_length=20)

    @field_validator('knowledge_bucket_ids')
    @classmethod
    def unique_buckets(cls, value):
        if value is None:
            return None
        if any(not x or len(x)>128 for x in value):
            raise ValueError('无效的知识库 ID')
        return list(dict.fromkeys(value))

    @field_validator('name', 'interests')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('内容不能为空')
        return value.strip()


class SectionDraft(BaseModel):
    name: str = Field(min_length=1, max_length=24)
    description: str = Field(min_length=1, max_length=240)

    @field_validator('name', 'description')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('栏目内容不能为空')
        return value.strip()


class SectionPlan(BaseModel):
    sections: list[SectionDraft] = Field(min_length=4, max_length=8)

    @field_validator('sections')
    @classmethod
    def unique_names(cls, values):
        if len({v.name.casefold() for v in values}) != len(values):
            raise ValueError('栏目名称不能重复')
        return values


class ArticleSection(BaseModel):
    article_id: str
    section_id: str


class SectionAssignments(BaseModel):
    assignments: list[ArticleSection] = Field(max_length=30)


class SourceInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    url: str = Field(max_length=2048)
    kind: Literal['website', 'social'] = 'website'
    profile_key: str = Field(default='default', pattern=r'^(default|[0-9a-f]{32})$')
    list_agent_generation_id: str = Field(default="", max_length=128)
    article_agent_generation_id: str = Field(default="", max_length=128)
    enabled: bool = True
    social_interval_hours: Literal[1, 3, 6, 12, 24] = 6

    @model_validator(mode='after')
    def social_source(self):
        from .social import youtube_url, weibo_url
        target=youtube_url(self.url) or weibo_url(self.url)
        if target:
            self.url=target
            self.kind='social'
        return self

    _url = field_validator('url')(public_url)


def cover_url(value: str) -> str:
    if not value:
        return ''
    # Validate without stripping signed CDN query parameters or rewriting escapes.
    try:
        public_url(value)
    except (ValueError, TypeError):
        return ''
    return value.strip()


class PageImage(BaseModel):
    url: str = Field(max_length=4096)
    alt: str = Field(default='', max_length=300)
    _url = field_validator('url')(cover_url)


class ArticleImages(BaseModel):
    source_url: str = Field(max_length=2048)
    images: list[PageImage] = Field(default_factory=list, max_length=24)
    image_url: str = Field(default='', max_length=4096)
    _source = field_validator('source_url')(public_url)
    _image = field_validator('image_url')(cover_url)


class ArticleCover(BaseModel):
    source_url: str = Field(max_length=2048)
    image_url: str = Field(default='', max_length=4096)
    _source = field_validator('source_url')(public_url)
    _image = field_validator('image_url')(cover_url)


class Page(BaseModel):
    content_type: Literal['', 'webpage', 'post', 'video', 'audio', 'image', 'document'] = ''
    duration_seconds: int | None = Field(default=None, ge=1, le=604800)
    page_count: int | None = Field(default=None, ge=1, le=100000)
    platform: str = Field(default='', max_length=40)
    post_id: str = Field(default='', max_length=100)
    author: str = Field(default='', max_length=200)
    published_at: str = Field(default='', max_length=100)
    coverage: Literal['', 'description', 'transcript'] = ''
    images: list[PageImage] = Field(default_factory=list, max_length=24)
    image_url: str = Field(default='', max_length=4096)
    _image = field_validator('image_url')(cover_url)
    requested_url: str = Field(default='', max_length=2048)

    @field_validator('requested_url')
    @classmethod
    def canonical_requested_url(cls, value):
        return public_url(value) if value else ''

    source_id: str = Field(max_length=64)
    url: str = Field(max_length=2048)
    title: str = Field(default='', max_length=500)
    text: str = Field(min_length=1, max_length=20000)
    _url = field_validator('url')(public_url)


class Candidate(BaseModel):
    url: str = Field(max_length=2048)
    title: str = Field(default='', max_length=500)
    text: str = Field(default='', max_length=1500)
    _url = field_validator('url')(public_url)


class ArticleDraft(BaseModel):
    section_id: str | None = None
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=800)
    body: str = Field(min_length=1, max_length=12000)
    evidence_ids: list[int] = Field(min_length=1, max_length=20)
    update_article_id: str | None = None


class Digest(BaseModel):
    articles: list[ArticleDraft] = Field(max_length=12)


class Recommendation(BaseModel):
    url: str
    name: str = Field(max_length=160)
    reason: str = Field(max_length=500)
    kind: Literal['website', 'social'] = 'website'


class Recommendations(BaseModel):
    sources: list[Recommendation] = Field(max_length=8)


class ChannelQuestion(BaseModel):
    request_id: str = Field(min_length=16, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')
    question: str = Field(min_length=1, max_length=3000)
    article_id: str | None = Field(default=None, max_length=80)

    @field_validator('question')
    @classmethod
    def question_not_blank(cls, value):
        if not value.strip():
            raise ValueError('请输入问题')
        return value.strip()


class ChannelAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=16000)
    evidence_ids: list[int] = Field(default_factory=list, max_length=20)
