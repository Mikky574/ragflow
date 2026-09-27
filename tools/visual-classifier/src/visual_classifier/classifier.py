from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from PIL import Image

from .taxonomy import VisualClass, decide, flatten_prompts


class SiglipZeroShotClassifier:
    """Small local zero-shot classifier; models load only when prediction starts."""

    def __init__(self, taxonomy: dict[str, VisualClass], model_id: str, device: str):
        self.taxonomy = taxonomy
        self.model_id = model_id
        self.device = device
        self._pipeline = None

    def _load(self):
        if self._pipeline is not None:
            return self._pipeline

        import torch
        from transformers import pipeline

        if self.device.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but torch.cuda.is_available() is false")
        pipeline_device = -1 if self.device == "cpu" else int(self.device.split(":")[-1])
        dtype = torch.float16 if pipeline_device >= 0 else torch.float32
        self._pipeline = pipeline(
            task="zero-shot-image-classification",
            model=self.model_id,
            device=pipeline_device,
            torch_dtype=dtype,
        )
        return self._pipeline

    def classify(self, image_path: str | Path, threshold: float) -> dict[str, Any]:
        classifier = self._load()
        prompts, prompt_to_class = flatten_prompts(self.taxonomy)
        image = Image.open(image_path).convert("RGB")
        raw = classifier(image, candidate_labels=prompts)

        class_scores: dict[str, list[float]] = defaultdict(list)
        for row in raw:
            class_scores[prompt_to_class[row["label"]]].append(float(row["score"]))
        scores = {name: max(values) for name, values in class_scores.items()}
        return decide(scores, self.taxonomy, threshold)
