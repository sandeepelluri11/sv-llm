"""LoRA fine-tune an open-weight chat model on reviewed detection outputs.

Requires the ``finetune`` extra: ``pip install -e .[finetune]``.

Usage:
    python finetune/train_lora.py --base Qwen/Qwen2.5-Coder-1.5B-Instruct \
        --train finetune/data/train.jsonl --val finetune/data/val.jsonl \
        --out finetune/adapters/detect-lora
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="Hugging Face model id or local path.")
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--val", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--epochs", type=float, default=3)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--rank", type=int, default=16)
    parser.add_argument("--alpha", type=int, default=32)
    parser.add_argument("--max-len", type=int, default=4096)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    args = parser.parse_args()

    import torch
    from datasets import load_dataset
    from peft import LoraConfig, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForSeq2Seq,
        Trainer,
        TrainingArguments,
    )

    tokenizer = AutoTokenizer.from_pretrained(args.base)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    model = AutoModelForCausalLM.from_pretrained(args.base, torch_dtype=dtype)
    model = get_peft_model(
        model,
        LoraConfig(
            r=args.rank,
            lora_alpha=args.alpha,
            lora_dropout=0.05,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            task_type="CAUSAL_LM",
        ),
    )
    model.print_trainable_parameters()

    def tokenize(example: dict) -> dict:
        # Only the assistant turn contributes to the loss.
        prompt_ids = tokenizer.apply_chat_template(
            example["messages"][:-1], add_generation_prompt=True, tokenize=True
        )
        full_ids = tokenizer.apply_chat_template(example["messages"], tokenize=True)
        full_ids = full_ids[: args.max_len]
        labels = [-100] * min(len(prompt_ids), len(full_ids)) + full_ids[len(prompt_ids) :]
        return {"input_ids": full_ids, "attention_mask": [1] * len(full_ids), "labels": labels}

    files = {"train": str(args.train)}
    if args.val:
        files["validation"] = str(args.val)
    dataset = load_dataset("json", data_files=files)
    tokenized = dataset.map(tokenize, remove_columns=dataset["train"].column_names)

    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(args.out / "checkpoints"),
            num_train_epochs=args.epochs,
            learning_rate=args.lr,
            per_device_train_batch_size=args.batch_size,
            gradient_accumulation_steps=args.grad_accum,
            logging_steps=5,
            save_strategy="epoch",
            eval_strategy="epoch" if args.val else "no",
            bf16=torch.cuda.is_available(),
            report_to=[],
        ),
        train_dataset=tokenized["train"],
        eval_dataset=tokenized.get("validation"),
        data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True),
    )
    trainer.train()
    model.save_pretrained(str(args.out))
    tokenizer.save_pretrained(str(args.out))
    print(f"adapter saved to {args.out}")


if __name__ == "__main__":
    main()
