"""Bot and Chat share the same trusted ACPF model catalog."""
from ai2apps.provisioning.profiles import CapabilityProfileRegistry


def test_bot_and_chat_share_identical_conversation_install_profiles():
    registry = CapabilityProfileRegistry()
    chat = registry.capability('ai2apps.general-chat', 'text.chat.local')
    bot = registry.capability('ai2apps.messager', 'text.chat.local')
    assert chat and bot
    assert chat['profiles'] == bot['profiles']
    assert chat['selection_mode'] == bot['selection_mode'] == 'multiple'
    assert bot['requirements']['operations'] == ['conversation']
    assert registry.capability('ai2apps.messager', 'audio.speech_generation')
    assert registry.capability('ai2apps.general-chat', 'audio.speech_recognition')
