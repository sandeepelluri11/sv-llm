# SV-LLM — agentic SoC security verification with LLMs

SV-LLM is a multi-agent system that reviews the RTL of a system-on-chip block against its
security specification. A supervisor coordinates three specialist agents built on
[LangGraph](https://github.com/langchain-ai/langgraph) and
[LangChain](https://github.com/langchain-ai/langchain):

| Agent | Input | Output |
|---|---|---|
| **Threat modeling** | spec chunks retrieved for the design's assets | typed `Threat` list (asset, entry point, STRIDE-style category, spec references) |
| **Vulnerability detection** | threat model + RTL chunks (+ validator notes on later passes) | typed `Finding` list (module, location, severity, hardware CWE, fix) |
| **Validation** | spec, RTL, findings | per-finding verdicts, SystemVerilog assertions, and a `needs_revision` flag |

Agents communicate only through a shared typed state (`sv_llm/state.py`, `sv_llm/schemas.py`).
The supervisor is deterministic: it routes on that state and stops the
detect → validate loop at a configurable iteration budget, so a model cannot talk its way past
the stop condition.

```
START ─► supervisor ─► threat_model ─► supervisor ─► vuln_detect ─► supervisor ─► validate ─► supervisor ─► END
                                                         ▲                                       │
                                                         └──────── needs_revision && budget ──────┘
```

## How the agents are grounded

- **Retrieval-augmented generation.** `sv-llm run` chunks the spec by Markdown heading and the
  RTL by module, embeds them into an in-memory vector store, and each agent retrieves the
  chunks relevant to its query. Retrieved chunks carry their provenance (`[spec spec.md
  section=Security requirements]`, `[rtl top.v module=bus_arbiter]`) so findings can cite them.
- **In-context learning.** `examples/few_shot/*.yaml` holds worked examples of hardware
  weaknesses (debug-port exposure, non-sticky lock bits, privileged read paths). Each agent
  selects the examples whose tags match the current design and splices them into its prompt.
- **Fine-tuning.** `finetune/` contains scripts that turn reviewed verification reports into a
  chat-format dataset, train a LoRA adapter with PEFT, and score it on finding-level
  precision/recall. See [finetune/README.md](finetune/README.md).
- **Structured output.** Every agent reply is validated with Pydantic. A malformed reply is fed
  back to the model once with the validation error so it can repair its output.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export OPENAI_API_KEY=sk-...

sv-llm inspect designs/aes_key_wrapper      # see how the design is chunked, no tokens spent
sv-llm run designs/aes_key_wrapper --out report.md --json-out report.json
```

Settings are environment variables prefixed `SV_LLM_` (`SV_LLM_MODEL`, `SV_LLM_EMBEDDING_MODEL`,
`SV_LLM_MAX_ITERATIONS`, `SV_LLM_RETRIEVER_K`, ...). Any OpenAI-compatible endpoint works by
setting `OPENAI_BASE_URL`, which is how a fine-tuned adapter served through vLLM is plugged in.

## Example designs

`designs/` contains three small, original Verilog blocks, each paired with a security spec
that the implementation intentionally violates in a few places:

| Design | Assets | Planted gaps |
|---|---|---|
| `aes_key_wrapper` | AES key registers, `debug_lock` bit | key readable by privileged bus reads, debug port ignores `debug_lock`, `debug_lock` not sticky |
| `boot_rom_ctrl` | `boot_done` lock, patch RAM | `boot_done` not write-once, cleared by warm reset |
| `bus_arbiter` | secure-core bus availability, lock privilege | no lock timeout (starvation), `secure_only_lock` not enforced |

They compile with Icarus Verilog (`iverilog -g2012 -t null designs/<name>/*.v`) and are the
fixtures for the test suite.

## Development

```bash
pytest            # unit + graph tests with a scripted fake model; no network needed
ruff check .
```

The tests drive the full LangGraph with a fake chat model that answers per agent, covering
the single-pass path, the revision loop, and the iteration budget.

## Project layout

```
sv_llm/
  agents/        base (structured output + repair), supervisor, threat_model, vuln_detect, validate
  retrieval/     loader (spec/RTL chunking), store (vector store), examples (few-shot selection)
  graph.py       LangGraph assembly
  report.py      Markdown report
  cli.py         typer CLI
designs/         example RTL + specs
examples/        few-shot examples
finetune/        dataset preparation, LoRA training, evaluation
tests/
```

## License

MIT
