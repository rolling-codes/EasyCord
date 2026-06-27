# Conversation Memory & Token Budgets

EasyCord's AI orchestration engine maintains conversation memory to provide context for follow-up prompts. However, conversation memory directly scales your token usage and operational costs.

## Provider Constraints

Token limitations vary depending on the underlying AI provider and model selected:

### Anthropic (Claude Family)
* **Claude 3 Opus**: 200,000 token context window.
* **Claude 3 Sonnet**: 200,000 token context window.
* **Claude 3 Haiku**: 200,000 token context window.

### OpenAI (GPT Family)
* **GPT-4o / GPT-4 Turbo**: 128,000 token context window.
* **GPT-3.5 Turbo**: 16,384 token context window.

## Eviction Mechanics

To prevent context windows from overflowing and to manage costs, EasyCord uses an eviction strategy.
`ConversationMemory.evict_old_messages()` operates on a **FIFO (First-In, First-Out)** basis with a configurable maximum message cap. When the message count exceeds `max_messages`, the oldest user-assistant message pairs are evicted from the memory buffer. The system prompt is always preserved.

## Financial Scenarios

Maintaining large conversation histories can become expensive. Consider the following cost illustration:

> **Scenario**: A 20-message conversation utilizing **Claude 3 Opus** (assuming $15 / 1M input tokens).
> If the average conversation context per turn is 1,000 tokens, the cumulative cost of processing the 20th message includes all previous messages.
> Approximate cost for this single long conversation path: **~$0.003**. 
> While small for one user, this scales linearly with active users.

## Guardrails & Best Practices

> [!WARNING]
> For low-budget projects or public, high-traffic bots, it is strongly recommended to set `enable_conversation_memory=False` in your bot configuration, or to set a very strict `max_messages` limit (e.g., 4 or 6).

Always monitor your usage limits on the provider's dashboard. API pricing and token limits are subject to change; please refer to the official [Anthropic Pricing](https://www.anthropic.com/pricing) and [OpenAI Pricing](https://openai.com/pricing) pages for the most up-to-date figures.
