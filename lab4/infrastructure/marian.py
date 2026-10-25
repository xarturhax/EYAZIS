"""Local Marian generation; no silent source truncation or automatic network calls."""

from typing import Any

from lab4.tools.download_model import MODEL_ID, MODEL_PATH, REVISION


def split_ranges(size: int, limit: int) -> list[tuple[int, int]]:
    return [(start, min(start + limit, size)) for start in range(0, size, limit)]


class MarianTranslator:
    def __init__(self) -> None:
        self.tokenizer: Any = None
        self.model: Any = None

    def prepare(self) -> dict[str, str]:
        import torch
        import transformers
        from transformers import MarianMTModel, MarianTokenizer

        if self.model is None:
            if not (MODEL_PATH / "revision.json").is_file():
                raise ValueError(
                    "Модель отсутствует. Выполните python -m lab4.tools.download_model."
                )
            torch.set_num_threads(2)
            self.tokenizer = MarianTokenizer.from_pretrained(str(MODEL_PATH), local_files_only=True)
            self.model = MarianMTModel.from_pretrained(str(MODEL_PATH), local_files_only=True)
            self.model.eval()
        return {
            "model": MODEL_ID,
            "revision": REVISION,
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "device": "cpu",
            "beams": "4",
        }

    def translate(self, texts: list[str]) -> list[str]:
        import torch

        output = []
        for text in texts:
            ids = self.tokenizer.encode(text, add_special_tokens=False)
            if not ids:
                output.append("")
                continue
            translated = []
            # 384 < the model's 512-token context, leaving room for special tokens.
            for start, end in split_ranges(len(ids), 384):
                chunk = ids[start:end] + [self.tokenizer.eos_token_id]
                batch = torch.tensor([chunk], dtype=torch.long)
                with torch.inference_mode():
                    generated = self.model.generate(
                        input_ids=batch,
                        attention_mask=torch.ones_like(batch),
                        num_beams=4,
                        do_sample=False,
                        max_new_tokens=510,
                        max_length=None,
                    )[0].tolist()
                eos = self.tokenizer.eos_token_id
                # The decoder may start with EOS/PAD; only inspect generated tokens.
                if eos not in generated[1:]:
                    raise ValueError(
                        "Перевод достиг лимита генерации; текст не был сохранён частично."
                    )
                value = self.tokenizer.decode(generated, skip_special_tokens=True).strip()
                if not value:
                    raise ValueError("Модель вернула пустой перевод.")
                translated.append(value)
            output.append(" ".join(translated))
        return output
