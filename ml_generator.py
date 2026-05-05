"""Horcrux · ML password generator (PassGPT hybrid).

Integrazione di PassGPT (Rando et al., USENIX Security 2024) per:
  1. Generazione condizionale: dato un set di token target (nomi, anni, citta'),
     produce password "umane" plausibili che li contengono/iniziano con essi
  2. Re-ranking: log-likelihood del modello come misura di "umanita'" della pwd

Modello: javirandor/passgpt-10characters (~58M params, GPT-2 base, vocab=99)
Lazy load + cache singleton — il modello sta in RAM una volta sola tra chiamate.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("horcrux.ml")

# Lazy imports (transformers/torch sono pesanti — importa solo se chiamato)
_MODEL = None
_TOKENIZER = None
_MAX_LEN = 12   # max length del modello PassGPT-10 (10 char + <s>/</s>)

DEFAULT_MODEL = os.environ.get("HORCRUX_PASSGPT_MODEL", "javirandor/passgpt-10characters")


def _ensure_loaded():
    """Lazy load del modello + tokenizer. Costo prima call: ~5-10s."""
    global _MODEL, _TOKENIZER
    if _MODEL is not None:
        return _MODEL, _TOKENIZER
    logger.info(f"Caricamento PassGPT: {DEFAULT_MODEL} (cold start ~5-10s)")
    from transformers import AutoModelForCausalLM, AutoTokenizer
    _TOKENIZER = AutoTokenizer.from_pretrained(DEFAULT_MODEL, max_len=_MAX_LEN)
    _MODEL = AutoModelForCausalLM.from_pretrained(DEFAULT_MODEL)
    _MODEL.eval()
    logger.info(f"PassGPT caricato: {sum(p.numel() for p in _MODEL.parameters())/1e6:.1f}M params")
    return _MODEL, _TOKENIZER


def generate_conditional(
    prompts: list[str],
    samples_per_prompt: int = 30,
    max_length: int = _MAX_LEN,
    temperature: float = 1.0,
    top_k: int = 50,
) -> list[str]:
    """Per ogni prompt (es. 'marco', '1996'), genera N password che lo contengono
    o lo prolungano. Restituisce lista deduplicata di candidati ML.

    Args:
        prompts: token target (lowercase, breve). Stringa vuota = prompt libero
        samples_per_prompt: candidati per ogni prompt
        max_length: lunghezza massima password (cap PassGPT-10 = 12 con <s></s>)
        temperature: 1.0 = standard, <1 piu' conservativo, >1 piu' diverso
        top_k: top-k sampling (50 default)
    """
    model, tok = _ensure_loaded()
    import torch

    results: set[str] = set()
    # Aggiungi sempre un prompt libero <s> per generare candidati senza bias
    if not prompts:
        prompts = [""]
    elif "" not in prompts:
        prompts = list(prompts) + [""]

    for prompt in prompts[:15]:  # cap prompts per evitare cost esplosivo
        # PassGPT comincia con <s>; per condizionare, prependiamo il prompt
        text_prompt = "<s>" + prompt
        inputs = tok(text_prompt, return_tensors="pt")
        try:
            with torch.no_grad():
                out = model.generate(
                    **inputs,
                    max_length=max_length,
                    num_return_sequences=samples_per_prompt,
                    do_sample=True,
                    temperature=temperature,
                    top_k=top_k,
                    pad_token_id=tok.eos_token_id,
                )
        except Exception as e:
            logger.warning(f"PassGPT generate fallito su prompt '{prompt}': {e}")
            continue
        for seq in out:
            decoded = tok.decode(seq, skip_special_tokens=True).strip()
            # Cleanup: rimuovi residual special tokens text
            for sp in ("<s>", "</s>", "<pad>"):
                decoded = decoded.replace(sp, "")
            decoded = decoded.strip()
            if 3 <= len(decoded) <= 30:
                results.add(decoded)
    return sorted(results)


def score_passwords(
    passwords: list[str],
    batch_size: int = 64,
) -> dict[str, float]:
    """Calcola log-likelihood per ogni password sotto PassGPT.
    Score piu' alto = piu' "umana" / probabile.
    Restituisce dict {password: score normalizzato 0-1 (rispetto al massimo)}.

    Per efficienza, processa in batch.
    """
    if not passwords:
        return {}
    model, tok = _ensure_loaded()
    import torch
    raw_scores: dict[str, float] = {}
    pwds = list({p for p in passwords if 2 <= len(p) <= 30})  # dedupe + filter

    for i in range(0, len(pwds), batch_size):
        batch = pwds[i:i + batch_size]
        # Costruisci input <s>password
        texts = ["<s>" + p for p in batch]
        try:
            enc = tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=_MAX_LEN)
            with torch.no_grad():
                outputs = model(**enc, labels=enc["input_ids"])
            # outputs.loss e' la cross-entropy media sul batch — non per-sample
            # Per per-sample, calcoliamo manualmente
            logits = outputs.logits  # [B, T, V]
            shift_logits = logits[:, :-1, :].contiguous()
            shift_labels = enc["input_ids"][:, 1:].contiguous()
            loss_fct = torch.nn.CrossEntropyLoss(reduction="none", ignore_index=tok.pad_token_id or 1)
            flat_loss = loss_fct(
                shift_logits.view(-1, shift_logits.size(-1)),
                shift_labels.view(-1),
            )
            # Reshape back e media per riga (per password)
            per_token = flat_loss.view(shift_labels.size())
            # Mask out padding
            mask = (shift_labels != (tok.pad_token_id or 1)).float()
            per_pwd_loss = (per_token * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
            for pwd, l in zip(batch, per_pwd_loss.tolist()):
                # log-likelihood = -loss; convertiamo a positive score
                raw_scores[pwd] = -l
        except Exception as e:
            logger.warning(f"PassGPT scoring batch fallito: {e}")
            continue

    if not raw_scores:
        return {}
    # Normalizza 0-1 (min-max scaling)
    vals = list(raw_scores.values())
    lo, hi = min(vals), max(vals)
    rng = max(hi - lo, 1e-6)
    return {p: round((v - lo) / rng, 4) for p, v in raw_scores.items()}


def is_available() -> bool:
    """Check leggero senza caricare il modello — solo presence delle lib."""
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False
