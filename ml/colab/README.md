# Fine-Tuning Guide: Google Colab (QLoRA + Unsloth)

This guide walks you through fine-tuning **Qwen2.5-7B-Instruct** (or fallback 3B) using the generated Phase 4 dataset on a free or standard Google Colab T4/A100 GPU instance.

---

## 1. Prerequisites & Files to Prepare

From your local project repository, you will upload the following dataset files to Google Drive (or directly into Colab):
- `ml/dataset/data/train.jsonl` (~978 KB)
- `ml/dataset/data/val.jsonl` (~110 KB)
- `ml/dataset/data/test.jsonl` (~382 KB)

Recommended Google Drive folder structure:
```
Google Drive/
└── finreq/
    ├── data/
    │   ├── train.jsonl
    │   ├── val.jsonl
    │   └── test.jsonl
    └── checkpoints/
```

---

## 2. Launching Google Colab

1. Open [Google Colab](https://colab.research.google.com).
2. Go to **Runtime** > **Change runtime type**.
3. Select **T4 GPU** (or **A100 / L4** if you have Colab Pro).
4. Upload `ml/colab/finetune.ipynb` or follow the code cells below.

---

## 3. Step-by-Step Execution Overview

1. **Mount Google Drive** to ensure checkpoints and models persist if the session disconnects.
2. **Install Unsloth & Dependencies** for 2x faster, memory-efficient 4-bit QLoRA training.
3. **Load Base Model in 4-bit**: `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` (or `Qwen2.5-3B-Instruct-bnb-4bit` if low on VRAM).
4. **Configure LoRA Adapters**: Rank $r=16$, $\alpha=32$, targeting `q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj`.
5. **Format Dataset**: Convert messages list into Qwen chat template (`<|im_start|>user...<|im_end|><|im_start|>assistant...<|im_end|>`).
6. **Train with SFTTrainer**: 2-3 epochs, cosine learning rate scheduler ($2 \times 10^{-4}$), batch size 2, gradient accumulation 8. Train on assistant tokens only.
7. **Export LoRA & GGUF**:
   - Save adapter to Drive.
   - Export to **GGUF Q4_K_M** (quantized for local CPU inference).
8. **Download GGUF to Local Laptop**:
   - Save into `ml/models/qwen2.5-7b-req-engineer-q4_k_m.gguf`.
9. **Register in Ollama**:
   ```bash
   cd ml/models
   ollama create req-engineer-ft -f Modelfile
   ```
10. **Verify with Local Inference**:
   ```bash
   ollama run req-engineer-ft "Extract requirements from: Customer wants instant UPI onboarding with Aadhaar OTP."
   ```
