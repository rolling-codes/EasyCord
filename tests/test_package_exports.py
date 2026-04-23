from easycord import (
    EmbedCard,
    ErrorEmbed,
    InfoEmbed,
    SuccessEmbed,
    WarningEmbed,
    component,
    message_command,
    modal,
    user_command,
)


def test_package_exports_include_beginner_decorators():
    assert component is not None
    assert modal is not None
    assert user_command is not None
    assert message_command is not None


def test_package_exports_include_embed_cards():
    assert EmbedCard is not None
    assert InfoEmbed is not None
    assert SuccessEmbed is not None
    assert WarningEmbed is not None
    assert ErrorEmbed is not None
