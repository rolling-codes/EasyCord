# Starter workflow validation

<!-- Last verified: 2026-11-06 -->

The starter checks exercise user actions and state transitions, not only generated
strings or the number of registered commands. Shared behavior runs across all
five templates; template-specific behavior gets targeted scenarios.

| Scenario | Observable behavior | Test file |
|---|---|---|
| First offline command | Documented command returns the expected reply without credentials | `tests/test_cli_scaffold.py` |
| Awkward project names | Keyword, space, digit, and pytest-style names still produce invokable commands | `tests/test_starter_scenarios.py` |
| Copied next step | Printed `cd` command enters a directory containing spaces | `tests/test_starter_scenarios.py` |
| User adds a command | Both offline and configured instances execute the added handler | `tests/test_starter_scenarios.py` |
| Installed package | Each starter wheel executes outside its source directory | `tests/test_starter_scenarios.py` |
| Installed console command | Framework and starter wheels provide a working `easycord` executable | `tests/test_starter_scenarios.py` |
| Invalid configuration | Invalid server IDs and unusable storage fail before login with actionable errors | `tests/test_starter_config_scenarios.py` |
| Inherited production shell | Invalid live settings cannot force an offline command to use production storage | `tests/test_starter_config_scenarios.py` |
| Disabled publication | Actual startup never calls Discord sync when explicitly disabled | `tests/test_starter_config_scenarios.py` |
| Restart and server isolation | SQLite notes survive restart without leaking between servers or fresh memory bots | `tests/test_starter_config_scenarios.py` |
| Actual startup | Real setup hooks publish complete command schemas only to the selected guild | `tests/test_starter_lifecycle_scenarios.py` |
| Failed publication | Sync failures propagate and the bot can still be closed | `tests/test_starter_lifecycle_scenarios.py` |
| Plugin file isolation | Fresh test fixtures and offline/live/custom instances cannot read one another's tags | `tests/test_starter_lifecycle_scenarios.py` |
| Cleanup | Startup tasks are gone after the bot closes | `tests/test_starter_lifecycle_scenarios.py` |
| Documentation moves | APIs remain in their current task guides and beginner links resolve | `tests/test_release_readiness.py` |

## Regressions uncovered during review

Scenario review exposed a community startup crash caused by missing base
initialization in `LevelsPlugin`; JSON-backed plugin data shared between tests;
ignored launch configuration; invalid integer server IDs reaching login;
unhandled storage-path errors; invalid keyword imports; and broken printed
instructions for paths containing spaces.

The previous launch test also passed when its `run()` call was removed because
all assertions were inside an uncalled fake. Launch tests now assert exactly one
call independently of their callback assertions.

Six intentional mutations were checked in scratch generated projects. Removing
launch from the original, configuration, and community scenarios; removing the
main guild target; dropping factory guild forwarding; and ignoring disabled sync
were all detected. This is evidence for those regressions, not a comprehensive
mutation score for the framework.

## Removing repeated code

Version history provides useful precedents: the v5.60 DRY pass
([397755b](https://github.com/rolling-codes/EasyCord/commit/397755b)) consolidated
plugin locking, while the community scaffold and Composer parity work
([#134](https://github.com/rolling-codes/EasyCord/pull/134),
[#135](https://github.com/rolling-codes/EasyCord/pull/135)) introduced additional
setup paths. The current refactor keeps their public entrypoints compatible and
gives each shared policy one implementation.

Compared with the preceding revision of this PR:

| Generated bot | Before | After |
|---|---:|---:|
| Minimal | 60 lines | 26 lines |
| Plugin | 58 lines | 24 lines |
| Community | 76 lines | 43 lines |
| AI | 58 lines | 24 lines |
| Database | 58 lines | 24 lines |

`run_bot(create_bot)` replaces copied launch code and reuses BotConfig's mapping.
The CLI shares project assembly, plugin headers, and test headers instead of
maintaining five copies. FrameworkManager delegates its preset policy to the
existing Composer implementation. These changes remove 40 framework Python lines
net, including the new startup helper; the generated files together lose 169
lines. These are separate measures, not additive repository savings.

The four starter scenario files and their shared process helper shrink from 722
to 664 lines. Expected replies remain independent of production metadata, and
documented-command checks now require the expected response as well as exit zero.
Additional focused checks exercise factory overrides and enabled/disabled manager
presets; overall repository test code grows by 12 lines while framework code
shrinks. Line counts accompany behavioral checks rather than substituting for them.

After extraction, four mutations were rerun against scratch package snapshots:
omitting the shared launch call, removing BotConfig's guild mapping, overriding
disabled sync, and dropping factory guild forwarding. All four were detected by
the adapted launch and real-startup scenarios.

## Limits and extending the matrix

Discord network publication is faked at the command-tree boundary. These checks
do not prove Developer Portal settings, gateway behavior, real permissions,
Discord availability, or command visibility in the client. Credentialed live
validation remains separate.

Wheel tests use already installed third-party dependencies and disable network
dependency resolution. They verify packaged files, imports, and entrypoints;
they do not simulate every Python package-index state.

Local validation uses Linux and Python 3.12; CI also runs the suite on Python
3.10 and 3.11. PowerShell instructions have not been executed locally. The copied
POSIX `cd` scenario explicitly exercises a POSIX shell.

These are correctness scenarios, not throughput benchmarks. They establish no
capacity claim for a particular number of guilds or concurrent commands. When a
new template or persistence mechanism is introduced, add it to the shared matrix
and add targeted restart, isolation, and failure cases for its distinct behavior.
