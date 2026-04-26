"""CLI integration for roles plugin setup."""
import asyncio
import sys
from pathlib import Path


class RolesCLI:
    """Command-line interface for roles plugin."""

    @staticmethod
    async def setup_interactive() -> dict:
        """Interactive setup wizard.

        Returns config dict for BlueprintSet.
        """
        print("\n" + "=" * 60)
        print("🎭 EasyCord Roles Plugin — Server Setup")
        print("=" * 60)

        print("\nWhat kind of server are you running?")
        print("  1. Community Server (welcome, members, mods, admins)")
        print("  2. Gaming Server (players, VIPs, moderators, admins)")
        print("  3. Developer Server (contributors, maintainers, admins)")
        print("  4. Minimal Setup (just bot + admin)")
        print("  5. Custom (skip, configure manually)")

        choice = input("\nChoice (1-5): ").strip()

        presets = {
            "1": "community",
            "2": "gaming",
            "3": "developer",
            "4": "minimal",
            "5": "custom",
        }

        preset = presets.get(choice, "community")

        if preset == "custom":
            print("\n✅ Skipped. Use `/roles setup` in Discord, or edit `.easycord/server-config/<guild_id>.json` directly.")
            return {}

        print(f"\n✅ Selected: {preset.title()} preset")
        return {
            "preset": preset,
            "install_method": "cli",
        }

    @staticmethod
    def get_preset_config(preset: str) -> dict:
        """Get blueprint config for a preset."""
        presets = {
            "community": {
                "version": "1.0",
                "blueprints": {
                    "member": {
                        "name": "Member",
                        "permissions": ["send_messages", "read_message_history"],
                        "color": 0x0099FF,
                    },
                    "moderator": {
                        "name": "Moderator",
                        "inherits": "member",
                        "permissions": ["kick_members", "manage_messages"],
                        "color": 0xFF6600,
                        "hoist": False,
                    },
                    "admin": {
                        "name": "Admin",
                        "permissions": ["ban_members", "kick_members", "manage_channels", "manage_messages"],
                        "color": 0xFF0000,
                        "hoist": True,
                    },
                },
            },
            "gaming": {
                "version": "1.0",
                "blueprints": {
                    "player": {
                        "name": "Player",
                        "permissions": ["send_messages", "read_message_history"],
                        "color": 0x0099FF,
                    },
                    "vip": {
                        "name": "VIP",
                        "inherits": "player",
                        "permissions": ["priority_speaking"],
                        "color": 0xFFD700,
                        "hoist": True,
                    },
                    "moderator": {
                        "name": "Moderator",
                        "inherits": "player",
                        "permissions": ["kick_members", "manage_messages", "move_members"],
                        "color": 0xFF6600,
                        "hoist": True,
                    },
                    "admin": {
                        "name": "Admin",
                        "permissions": ["administrator"],
                        "color": 0xFF0000,
                        "hoist": True,
                    },
                },
            },
            "developer": {
                "version": "1.0",
                "blueprints": {
                    "contributor": {
                        "name": "Contributor",
                        "permissions": ["send_messages", "read_message_history"],
                        "color": 0x0099FF,
                    },
                    "maintainer": {
                        "name": "Maintainer",
                        "inherits": "contributor",
                        "permissions": ["manage_channels", "manage_messages", "manage_webhooks"],
                        "color": 0x00CC99,
                        "hoist": True,
                    },
                    "admin": {
                        "name": "Admin",
                        "permissions": ["ban_members", "manage_roles", "manage_channels"],
                        "color": 0xFF0000,
                        "hoist": True,
                    },
                },
            },
            "minimal": {
                "version": "1.0",
                "blueprints": {
                    "bot": {
                        "name": "Bot",
                        "permissions": ["send_messages", "manage_roles", "manage_channels"],
                        "hoist": True,
                    },
                    "admin": {
                        "name": "Admin",
                        "permissions": ["ban_members", "kick_members", "manage_messages"],
                        "color": 0xFF0000,
                        "hoist": True,
                    },
                },
            },
        }
        return presets.get(preset, presets["community"])

    @staticmethod
    def print_summary(preset: str) -> None:
        """Print preset summary."""
        config = RolesCLI.get_preset_config(preset)
        blueprints = config.get("blueprints", {})

        print(f"\n📋 {preset.title()} Preset:")
        print("   Roles to be created:")
        for key, bp in blueprints.items():
            perms = ", ".join(bp.get("permissions", [])[:2])
            perms = perms + ("..." if len(bp.get("permissions", [])) > 2 else "")
            print(f"     • {bp['name']:<15} ({perms})")

        print("\n💡 Next steps:")
        print("   1. In Discord, join your server")
        print("   2. Run: /roles setup")
        print("   3. Run: /roles sync")
        print("   4. Check: /roles debug")
