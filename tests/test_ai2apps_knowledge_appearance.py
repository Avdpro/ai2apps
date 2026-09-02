from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_knowledge_brand_defaults_to_black_and_is_theme_independent() -> None:
    theme = (ROOT / "ai2apps/web/static/css/knowledge_theme.css").read_text()

    assert "--kn-accent: #171717" in theme
    assert "--kn-on-accent: #fff" in theme
    assert '[data-theme="dark"] .knowledge-brand > span' in theme
    assert "inset 0 0 0 1px" in theme


def test_knowledge_accent_is_per_user_and_shared_with_mini_entry() -> None:
    script = (ROOT / "ai2apps/web/static/js/knowledge.js").read_text()
    full = (ROOT / "ai2apps/web/templates/system_apps/knowledge.html").read_text()
    mini = (ROOT / "ai2apps/web/templates/system_apps/knowledge_mini.html").read_text()

    assert "ai2apps.knowledge.accent.v1:${this.actorUserId" in script
    assert "accentForeground(color)" in script
    assert "localStorage.setItem(this.accentStorageKey(), color)" in script
    assert "knowledge_theme.css" in full
    assert "knowledge_theme.css" in mini
    assert "knowledge-appearance-popover" in full
