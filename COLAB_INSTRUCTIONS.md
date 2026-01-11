# 🇬🇭 Ghana Legal AI: Fine-Tuning LFM2 Guide

## Step 1: Install Dependencies (Fresh Runtime)

**Action**: Runtime → Disconnect and Delete Runtime, then run:

```python
# Step 1: Reinstall Triton
!pip uninstall triton -y
!pip install triton

# Step 2: Install Unsloth
!pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"

# Step 3: LFM2 specific
!pip install --no-deps transformers==4.55.0
!pip install --no-deps causal-conv1d==1.5.0.post8

# Step 4: FORCE tokenizers LAST
!pip install --force-reinstall "tokenizers==0.21.0"

print("✅ Done! Now RESTART the runtime.")
```

**Then**: Runtime → Restart session

---

## Step 2: Load LFM2 Model

```python
from unsloth import FastModel

model, tokenizer = FastModel.from_pretrained(
    model_name = "unsloth/LFM2-1.2B",
    dtype = None,
    max_seq_length = 2048,
    load_in_4bit = True,
    full_finetuning = False,
)
```

---

## Step 3: Configure LoRA/PEFT

```python
model = FastModel.get_peft_model(
    model,
    finetune_vision_layers     = False,
    finetune_language_layers   = True,
    finetune_attention_modules = True,
    finetune_mlp_modules       = True,
    r = 16,
    lora_alpha = 16,
    lora_dropout = 0,
    bias = "none",
    random_state = 3407,
)
```

---

## Step 4: Load Ghana Legal Dataset from HuggingFace

```python
from datasets import load_dataset

# Load from HuggingFace Hub (524 examples)
dataset = load_dataset("gahsilas/ghana-legal-qa", split="train")

def formatting_prompts_func(examples):
    convos = examples["conversations"]
    texts = []
    for convo in convos:
        messages = [{"role": "user" if c["from"] == "human" else "assistant", "content": c["value"]} for c in convo]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        texts.append(text.removeprefix(tokenizer.bos_token))
    return {"text": texts}

dataset = dataset.map(formatting_prompts_func, batched=True)
print(f"✅ Loaded {len(dataset)} examples from HuggingFace")
```

---

## Step 5: Train with SFTTrainer

```python
from trl import SFTTrainer
from transformers import TrainingArguments
from unsloth import is_bfloat16_supported

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = dataset,
    dataset_text_field = "text",
    max_seq_length = 2048,
    args = TrainingArguments(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        warmup_steps = 5,
        max_steps = 60,  # Use num_train_epochs=1 for full training
        learning_rate = 2e-4,
        fp16 = not is_bfloat16_supported(),
        bf16 = is_bfloat16_supported(),
        logging_steps = 1,
        optim = "adamw_8bit",
        output_dir = "outputs",
    ),
)

trainer.train()
```

---

## Step 6: Test Inference

```python
FastModel.for_inference(model)

messages = [{"role": "user", "content": "Is it constitutional to remove the President for misconduct?"}]
inputs = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt").to("cuda")
outputs = model.generate(input_ids=inputs, max_new_tokens=128, use_cache=True)
print(tokenizer.batch_decode(outputs, skip_special_tokens=True)[0])
```

---

## Step 7: Save GGUF

```python
model.save_pretrained_gguf("ghana_legal_lfm2", tokenizer, quantization_method="q4_k_m")
```

Download the `.gguf` file from Files sidebar.

---

## Step 8: Deploy Locally with Ollama

After downloading the GGUF file, create a `Modelfile`:

```
FROM ./LFM2-1.2B.Q4_K_M.gguf

TEMPLATE """<|im_start|>user
{{ .Prompt }}<|im_end|>
<|im_start|>assistant
{{ .Response }}<|im_end|>"""

SYSTEM "You are a legal expert specializing in Ghana's 1992 Constitution."

PARAMETER stop "<|im_end|>"
```

Then run:
```bash
ollama create ghana-legal -f Modelfile
ollama run ghana-legal "Is it constitutional to remove the President?"
```

<!-- from datasets import load_dataset

# Load from HuggingFace Hub (524 examples)
dataset = load_dataset("gahsilas/ghana-legal-qa", split="train")

# Format using tokenizer's built-in chat template
def formatting_prompts_func(examples):
    convos = examples["conversations"]
    texts = []
    for convo in convos:
        # Convert ShareGPT format to standard messages format
        messages = [{"role": "user" if c["from"] == "human" else "assistant", "content": c["value"]} for c in convo]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        # Remove BOS token to avoid double BOS
        texts.append(text.removeprefix(tokenizer.bos_token))
    return {"text": texts}

# Process dataset
dataset = dataset.map(formatting_prompts_func, batched=True)

print(f"✅ Loaded {len(dataset)} examples from HuggingFace")
print(f"Sample: {dataset[0]['text'][:200]}...") -->