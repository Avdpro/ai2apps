# AI2Apps localized metadata v1

AI2Apps keeps stable identifiers and one required base language in every signed
manifest. Optional translations live beside that base metadata under
`localizations`; they never change App IDs, Package IDs, permissions, entrypoints,
or signatures.

## App and Agent manifests

```yaml
schema: ai2apps.app/v1
id: example.notes
name: Notes
description: Keep short notes
navigation:
  category: Productivity
localizations:
  zh-CN:
    name: 笔记
    description: 记录简短笔记
    navigation:
      category: 效率
```

Each locale entry requires `name`. `description` and
`navigation.category` are optional. Locale tags use a BCP-47-like form such as
`zh`, `zh-CN`, `zh-TW`, `ja`, or `en-GB`.

## Distributable Package manifests

```json
{
  "package": {
    "id": "example/notes",
    "type": "app",
    "version": "1.0.0",
    "displayName": "Notes",
    "description": "Keep short notes",
    "localizations": {
      "zh-CN": {
        "displayName": "笔记",
        "description": "记录简短笔记"
      }
    }
  }
}
```

Package translations are covered by the Package manifest and signature. During
installation, `displayName` is converted to the runtime Manifest field `name`.
An App's own localized `navigation.category` is retained.

## Studio Mini-App metadata

An App Package can contribute several Studio Mini-Apps. Package-level and App-level
translations do not rename those child components: each `mini_apps[]` declaration
owns its own bounded `localizations` map.

```yaml
mini_apps:
  - schema: ai2apps.mini-app/v1
    id: example.media.video-subtitles
    name: Video Subtitles and Translation
    description: Create, translate, export, or burn subtitles into a video.
    localizations:
      zh-CN:
        name: 视频字幕与翻译
        description: 生成和翻译字幕，可导出字幕文件或直接添加到视频。
      zh-TW:
        name: 影片字幕與翻譯
        description: 產生和翻譯字幕，可匯出字幕檔或直接加入影片。
```

`name` is required in every Mini-App locale entry; `description` is optional.
The base `name` and `description` remain the English fallback. Studio hosts resolve
the declaration before rendering the Mini-App list, active header, and details.
The same Host locale is passed to the mounted Entry, which localizes its document
title, visible controls, dynamic state, errors, placeholders, and accessible names.
User-authored content and canonical identifiers are never translated.

For an authoring checklist and App-Dev verification procedure, see
[AI2Apps App 开发指南：Package Mini-App 名称与界面本地化](ai2apps-app-development-guide.md#package-mini-app-名称与界面本地化必选)。

## Resolution and fallback

Consumers use the system UI language and resolve metadata in this order:

1. exact locale, such as `zh-CN`;
2. script/region compatibility fallback (`zh-HK`, `zh-MO`, and `zh-Hant` try
   `zh-TW`);
3. language-only locale, such as `zh`;
4. the product language default when only a region-specific resource exists
   (`zh` tries `zh-CN`);
5. required base Manifest metadata.

The Shell catalog is the authoritative source for App Launcher, Dock, Mobile,
and host context. Discover resolves the same metadata from Package catalogs and
installed Package state. API clients may pass `locale` to `/apps` and
`/packages/installed` when they need an explicitly localized response.
