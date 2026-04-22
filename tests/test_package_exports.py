from easycord import component, message_command, modal, user_command


def test_package_exports_include_beginner_decorators():
    assert component is not None
    assert modal is not None
    assert user_command is not None
    assert message_command is not None
