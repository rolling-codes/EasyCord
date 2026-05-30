"""Public package export smoke tests."""
from __future__ import annotations


def test_public_exports_import_from_easycord() -> None:
    import easycord
    from easycord import (
        BotConfig,
        PluginCheck,
        PluginCheckReport,
        PluginManifest,
        PluginScaffoldOptions,
        PluginScaffoldResult,
        audit_tool_registry,
        check_plugin_project,
        command_error,
        cooldown,
        create_in_project_plugin,
        create_package_plugin,
        create_plugin_scaffold,
        describe,
        discover_plugins,
        format_doctor_report,
        format_interaction_inventory,
        format_sync_plan,
        format_tool_audit,
        install_type,
        load_entrypoint_plugins,
        load_plugin_manifest,
        premium_required,
        require_permissions,
        validate_plugin_manifest,
    )

    for name in (
        "BotConfig",
        "PluginCheck",
        "PluginCheckReport",
        "PluginManifest",
        "PluginScaffoldOptions",
        "PluginScaffoldResult",
        "audit_tool_registry",
        "check_plugin_project",
        "command_error",
        "cooldown",
        "create_in_project_plugin",
        "create_package_plugin",
        "create_plugin_scaffold",
        "describe",
        "discover_plugins",
        "format_doctor_report",
        "format_interaction_inventory",
        "format_sync_plan",
        "format_tool_audit",
        "install_type",
        "load_entrypoint_plugins",
        "load_plugin_manifest",
        "premium_required",
        "require_permissions",
        "validate_plugin_manifest",
    ):
        assert name in easycord.__all__

    assert BotConfig is easycord.BotConfig
    assert PluginCheck is easycord.PluginCheck
    assert PluginCheckReport is easycord.PluginCheckReport
    assert PluginManifest is easycord.PluginManifest
    assert PluginScaffoldOptions is easycord.PluginScaffoldOptions
    assert PluginScaffoldResult is easycord.PluginScaffoldResult
    assert callable(audit_tool_registry)
    assert callable(check_plugin_project)
    assert callable(command_error)
    assert callable(cooldown)
    assert callable(create_in_project_plugin)
    assert callable(create_package_plugin)
    assert callable(create_plugin_scaffold)
    assert callable(describe)
    assert callable(discover_plugins)
    assert callable(format_doctor_report)
    assert callable(format_interaction_inventory)
    assert callable(format_sync_plan)
    assert callable(format_tool_audit)
    assert callable(install_type)
    assert callable(load_entrypoint_plugins)
    assert callable(load_plugin_manifest)
    assert callable(premium_required)
    assert callable(require_permissions)
    assert callable(validate_plugin_manifest)


def test_no_private_modules_in_public_api() -> None:
    import easycord

    private_names = [
        name
        for name in easycord.__all__
        if name.startswith("_") and not (name.startswith("__") and name.endswith("__"))
    ]
    assert private_names == []
