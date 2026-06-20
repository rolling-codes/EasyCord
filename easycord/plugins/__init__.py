"""Optional first-party plugins."""
from ._config_manager import PluginConfigManager
from ._ai_providers import (
    AIProvider,
    AnthropicProvider,
    GeminiProvider,
    GroqProvider,
    HuggingFaceProvider,
    LiteLLMProvider,
    MistralProvider,
    OllamaProvider,
    OpenAIProvider,
    TogetherAIProvider,
)
from .ai_moderator import AIModeratorPlugin
from .auto_responder import AutoResponderPlugin
from .economy import EconomyPlugin
from .invite_tracker import InviteTrackerPlugin
from .levels import LevelsPlugin
from .member_logging import MemberLoggingPlugin
from .moderation import ModerationPlugin
from .openclaude import AIPlugin, OpenClaudePlugin
from .openclaw import OpenClawPlugin
from .polls import PollsPlugin
from .reaction_roles import ReactionRolesPlugin
from .role_persistence import RolePersistencePlugin
from .starboard import StarboardPlugin
from .suggestions import SuggestionsPlugin
from .tags import TagsPlugin
from .translate import TranslatePlugin
from .auto_role import AutoRolePlugin
from .birthday import BirthdayPlugin
from .giveaway import GiveawayPlugin
from .reminder import ReminderPlugin
from .reputation import ReputationPlugin
from .scheduled_announcements import ScheduledAnnouncementsPlugin
from .server_stats import ServerStatsPlugin
from .tickets import TicketsPlugin
from .verification import VerificationPlugin
from .welcome import WelcomePlugin
from .word_filter import WordFilterPlugin
from .security_lab import SecurityLabPlugin

__all__ = [
    "AIModeratorPlugin",
    "AutoRolePlugin",
    "BirthdayPlugin",
    "GiveawayPlugin",
    "ReminderPlugin",
    "ReputationPlugin",
    "ScheduledAnnouncementsPlugin",
    "SecurityLabPlugin",
    "ServerStatsPlugin",
    "TicketsPlugin",
    "VerificationPlugin",
    "WordFilterPlugin",
    "PluginConfigManager",
    "AIPlugin",
    "AIProvider",
    "AnthropicProvider",
    "AutoResponderPlugin",
    "EconomyPlugin",
    "GeminiProvider",
    "GroqProvider",
    "HuggingFaceProvider",
    "InviteTrackerPlugin",
    "LevelsPlugin",
    "LiteLLMProvider",
    "MemberLoggingPlugin",
    "MistralProvider",
    "ModerationPlugin",
    "OllamaProvider",
    "OpenAIProvider",
    "OpenClaudePlugin",
    "OpenClawPlugin",
    "PollsPlugin",
    "ReactionRolesPlugin",
    "RolePersistencePlugin",
    "StarboardPlugin",
    "SuggestionsPlugin",
    "TagsPlugin",
    "TranslatePlugin",
    "TogetherAIProvider",
    "WelcomePlugin",
]
