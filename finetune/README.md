# Fine-tuning the detection agent

The detection agent is the most prompt-sensitive part of the pipeline, so it is the one we
fine-tune. The workflow is:

1. Run SV-LLM on your designs with `--json-out` and have an engineer review the validator
   verdicts in the reports.
2. `python finetune/prepare_data.py reports/*.json` turns confirmed findings into a
   chat-format JSONL dataset (system prompt, design context, expected JSON output).
3. `python finetune/train_lora.py --base <model> --train ... --out finetune/adapters/<name>`
   trains a LoRA adapter with PEFT. Only the assistant turn contributes to the loss.
4. `python finetune/eval_finetuned.py` reports finding-level precision / recall / F1 against
   the held-out split, either loading the adapter locally or hitting a vLLM / OpenAI-compatible
   endpoint that serves it.

To use a fine-tuned model inside the graph, serve it behind an OpenAI-compatible endpoint and
point the CLI at it:

```bash
export OPENAI_BASE_URL=http://localhost:8000/v1
export OPENAI_API_KEY=unused
export SV_LLM_MODEL=detect-lora
sv-llm run designs/aes_key_wrapper
```

Install the extra dependencies with `pip install -e .[finetune]`. The training script runs
on CPU for smoke tests but is only practical on a GPU.
