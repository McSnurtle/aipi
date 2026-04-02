import asyncio
import os
from typing import Any, Literal

import torch
from pydantic import BaseModel, Field
from transformers import pipeline

# variables
_model_timeout: int = int(os.getenv("MODEL_TIMEOUT", "300"))


class Model(BaseModel):
    model_id: str
    remaining: int = _model_timeout
    pipeline_obj: Any = Field(exclude=True)

    def refresh(self) -> None:
        self.remaining = _model_timeout


_models: dict[str, Model] = {}
_watchdog_rate: int = 30


class Watchdog:
    _instance: "Watchdog | None" = None
    _lock = asyncio.Lock()
    """Carefully watches models until they expire, then it kills them."""

    async def start(self) -> None:
        async with self._lock:
            if self._instance is not None:
                return
            Watchdog._instance = self

        try:
            while True:
                model_list: list = list(_models.items())    # rebuild to scan for newly registered models
                if not model_list:  # when empty...
                    break

                for model_id, model in model_list:
                    model.remaining -= _watchdog_rate
                    if model.remaining <= 0:
                        entry = _models.pop(model_id)
                        del entry.pipeline_obj

                await asyncio.sleep(_watchdog_rate)
        finally:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            Watchdog._instance = None

    @classmethod
    def ensure_watchdog(cls) -> None:
        if cls._instance is None:
            asyncio.create_task(cls().start())


# noinspection PyTypeChecker
def load_pipeline(task: str, model_id: str) -> pipeline:
    """Loads and returns a transformers pipeline for `model_id` if it does not exist already."""
    entry: Model = _models.get(model_id)
    if not entry:
        print(f"Loading pipeline for model: {model_id}")
        pipe = pipeline(task, model=model_id)
        entry = Model(**{"model_id": model_id, "pipeline_obj": pipe})
        _models[model_id] = entry

        Watchdog.ensure_watchdog()
    else:
        _models[model_id].refresh()

    return entry.pipeline_obj


def generate(model_id: str, task: (Literal, str), context: dict[str, list[dict]]) -> dict:
    generator = load_pipeline(task, model_id)
    return generator(context)
