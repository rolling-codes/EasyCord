"""Optional first-party plugins."""
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
from .welcome import WelcomePlugin

__all__ = [
    "AIModeratorPlugin",
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
    "TogetherAIProvider",
    "WelcomePlugin",
]
