🚀 EasyCord
A high-level framework for discord.py that actually gets out of your way.

I built EasyCord because I was tired of fighting with boilerplate. It’s a wrapper designed to make bot development faster and a lot less frustrating by automating the repetitive API setup that usually eats up your afternoon.

💡 The Backstory
This project wasn't just a coding exercise—it was a solution to a real problem. I founded and managed the Senior IT Program Discord server for my school.

When you're running a live server for a class full of IT students, you need a bot that can scale now. I found myself spending way too much time on "plumbing"—syncing slash commands, manually handling events, and writing the same permission checks over and over.

The Fix: I decided to stop being just a user and started being an architect. I collaborated with AI tools to design a system that handles the heavy lifting automatically. EasyCord allowed me to move from a "hey, we need this feature" idea to a live, working tool for my school's community without the usual Discord API headaches.

🛠 What it actually does
1. Fast Slash Commands
No more manual syncing. EasyCord uses signature rewriting to look at your function arguments and build the Discord UI for you automatically.

Python
@bot.slash(description="Give someone temporary lab access")
async def grant_access(ctx, user: discord.Member, hours: int = 4):
    # EasyCord handles the 'user' and 'hours' types for you.
    await ctx.respond(f"Access granted to {user.display_name} for {hours}h.")
2. Clean Middleware
Stop repeating yourself. Use the middleware chain to wrap every command in a logic layer—perfect for global logging or blocking commands during maintenance.

Python
@bot.use
async def simple_logger(ctx, next):
    print(f"User {ctx.user} ran /{ctx.command_name}")
    await next() 
3. Stress-Free Config
Skip the complex database setup. The built-in ServerConfigStore lets you save server-specific settings (like role IDs or welcome channels) to simple JSON files.

📖 The Docs
I put together a full docs/ folder to make sure the transition from "cloning the repo" to "running a bot" is as seamless as possible:

getting-started.md: The quick-start guide for your first 5 minutes.

concepts.md: A look under the hood at how the middleware and plugins work.

api.md: The full technical reference for when you need to dig deep.

examples.md: Real-world patterns you can copy and paste.

fork-and-expand.md: A guide on making this project your own.

🤖 Expanding with AI (Even if you don't code)
One of the coolest things about EasyCord is that it’s AI-native. I wanted my entire IT class to be able to contribute, even the people who weren't Python experts.

Inside the repo, there is a file called model.md. It’s a "Single-Source Context Map" designed specifically for AI agents.

If you have an idea but zero coding knowledge, you can still expand this bot:

Feed the AI: Copy the text from README.md, model.md, and the docs/ folder.

The Prompt: "Hey, using the EasyCord framework, write me a new Plugin that adds a [Your Feature Idea] feature."

The framework is so modular that the AI can write a perfect Plugin file. You just drop it into the server_commands/ folder, and the bot is updated. It makes the project a living tool that anyone can help build.

📂 Layout
easycord/: The core engine logic.

docs/: The full roadmap (Getting Started, API, Examples).

server_commands/: The actual plugins I used for the Senior IT server.

model.md: The "Cheat Sheet" for expanding the bot with AI.

.easycord/: Where the bot stores your server-specific settings.
