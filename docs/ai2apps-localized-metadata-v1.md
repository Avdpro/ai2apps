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

## Resolution and fallback

Consumers use the system UI language and resolve metadata in this order:

1. exact locale, such as `zh-CN`;
2. script/region compatibility fallback (`zh-HK`, `zh-MO`, and `zh-Hant` try
   `zh-TW`);
3. language-only locale, such as `zh`;
4. required base Manifest metadata.

The Shell catalog is the authoritative source for App Launcher, Dock, Mobile,
and host context. Discover resolves the same metadata from Package catalogs and
installed Package state. API clients may pass `locale` to `/apps` and
`/packages/installed` when they need an explicitly localized response.
