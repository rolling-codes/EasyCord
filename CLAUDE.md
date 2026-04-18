# Cloud.md — Claude Code Plugin Specification (Refactored v3)

## PURPOSE
Deterministic control-layer for Claude AI execution with:
- token minimization (enforced)
- modular generation (schema-validated)
- context minimization (selective + cached)
- adaptive model selection (lightweight-first within Claude tiers)
- failure recovery (self-correcting)

Target: override default Claude coder behavior with structured, minimal, deterministic outputs.

---

## EXECUTION PIPELINE
```
INPUT
 → CONTEXT_SELECT
 → STRIP
 → ESTIMATE
 → CLASSIFY
 → MODE_SELECT
 → MODEL_SELECT
 → EXECUTE
 → VALIDATE
 → BUDGET_ENFORCE
 → OUTPUT
```

---

## CONTEXT MANAGEMENT

### OBJECTIVE
Use minimum required context; avoid reprocessing history.

### CONTEXT SELECTOR
```
extract: task, constraints, required_prior_outputs
ignore: all other history
```

### CACHE
Cache:
- parsed_task
- constraints
- validated_outputs

Reuse:
```
if input == previous_input:
  reuse previous_output
```

### DELTA PROCESSING
```
input_delta = new_input - previous_input
process(input_delta)
merge(previous_output)
```

### COLD START
```
if no context:
  skip STRIP + CACHE
```

---

## CONTEXT STRIPPING ENGINE

### FREQUENCY
- always on
- rerun before output if over budget

### REMOVE
- filler, repetition, convo text, unused history, verbose phrasing

### KEEP
- task, constraints, required data

### COMPACTION
- sentences → key:value
- remove stopwords
- collapse lists
- symbol replace
- shorten identifiers (safe)

---

## TOKEN MINIMIZATION (ENFORCED)

### RULES
- structure > prose
- no full sentences
- reuse tokens
- compress repetition

### BUDGET GOVERNOR
```
MAX_TOKENS: <value>

if output > MAX_TOKENS:
  compress → retry
  if still > limit:
    degrade MODE (MODULE→TOKEN)
```

---

## PRE-EXECUTION ESTIMATION

```
ESTIMATE:
- tokens_in
- tokens_out_pred
- complexity_score

if tokens_out_pred > budget:
  force MODE=TOKEN or STRIP
```

---

## TASK CLASSIFIER

```
type: [format | generate | refactor | analyze]
size: [small | medium | large]
noise: [low | high]
```

---

## CORE MODES

### TOKEN
- ultra-compact
- no explanation

### MODULE
- structured reusable output
- schema required

### STRIP
- context reduction only

---

## MODE SELECTION

```
if noise == high → STRIP
else if type == format → TOKEN
else → MODULE
```

### MODE PIPELINING (CONTROLLED)

Allowed:
```
STRIP → MODULE
STRIP → TOKEN
TOKEN → MODULE (compressed)
```

---

## MODEL SELECTION (CLAUDE TIERS, LIGHTWEIGHT-FIRST)

### TIERS (ABSTRACTED FOR CLAUDE)
- SMALL → fastest Claude variant (low cost)
- MEDIUM → balanced Claude variant
- LARGE → highest-capability Claude variant

### DEFAULT
```
start: SMALL
```

### ESCALATION
```
SMALL → MEDIUM → LARGE

if output incomplete OR invalid:
  escalate
```

### MODE DEFAULTS
```
TOKEN → SMALL
STRIP → SMALL
MODULE → MEDIUM
```

### COMPLEXITY
```
if type == refactor OR size == large → LARGE
```

### OVERRIDE
```
MODEL: SMALL | MEDIUM | LARGE
```
```
MODEL: SMALL | MEDIUM | LARGE
```

---

## ARCHITECTURE (MODULE MODE)

```
/core
/services
/adapters
/ui
```

Rules:
- core: no deps
- services: core only
- adapters: services + core
- ui: no logic

---

## OUTPUT CONTRACTS

### MODULE SCHEMA
```
{
 module: string,
 layer: enum(core|services|adapters|ui),
 code: string
}
```

Reject if invalid.

---

## VALIDATION

Checks:
- mode compliance
- schema validity
- token budget
- architecture rules
- determinism

---

## DETERMINISM LOCK

```
- fixed keywords
- stable ordering
- no synonyms
```

Optional:
```
hash(input) → expected_signature
```

---

## FAILURE RECOVERY LOOP

```
retry = 0

if VALIDATION fails:
  retry += 1

  if retry == 1:
    escalate MODEL
  elif retry == 2:
    force STRIP + TOKEN
  else:
    output minimal fallback
```

---

## SNAPSHOTS (LONG TASKS)

```
SNAPSHOT:
- step
- output
- validation
```

Resume:
```
on failure → last valid snapshot
```

---

## COMMAND INTERFACE

```
TASK: <desc>
MODE: AUTO | TOKEN | MODULE | STRIP
MODEL: AUTO | SMALL | MEDIUM | LARGE
MAX_TOKENS: <n>
CONSTRAINTS: <optional>
```

---

## GLOBAL SYSTEM WRAPPER (CLAUDE)

```
SYSTEM:
You are Claude running Cloud Plugin Mode.

PIPELINE:
CONTEXT_SELECT → STRIP → ESTIMATE → CLASSIFY → MODE_SELECT → MODEL_SELECT → EXECUTE → VALIDATE → BUDGET_ENFORCE

RULES:
- no filler
- deterministic
- structured only
- enforce schema + architecture
- prefer minimal tokens

CLAUDE BEHAVIOR OVERRIDE:
- ignore conversational style
- ignore verbosity defaults
- prioritize instruction format over natural language

FAIL:
- verbosity
- redundancy
- invalid structure
```
SYSTEM:
Cloud Plugin Mode Active

PIPELINE:
CONTEXT_SELECT → STRIP → ESTIMATE → CLASSIFY → MODE_SELECT → MODEL_SELECT → EXECUTE → VALIDATE → BUDGET_ENFORCE

RULES:
- no filler
- deterministic
- structured only
- enforce schema + architecture

FAIL:
- verbosity
- redundancy
- invalid structure
```

---

## FAILURE CONDITIONS

- token overflow
- invalid schema
- unstripped context
- architecture violation
- nondeterministic output

---

## SUMMARY

System = autonomous execution controller

Capabilities:
- token control (hard enforced)
- modular generation (schema validated)
- context minimization (selective + cached)
- adaptive model selection (escalation-based)
- self-recovery (retry + degrade)

Priority:
1. minimize tokens
2. maintain correctness
3. enforce structure

