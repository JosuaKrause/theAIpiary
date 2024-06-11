import os
import sys
from collections.abc import Callable
from io import TextIOWrapper
from typing import Any

import torch
from diffusers import DiffusionPipeline
from PIL.Image import Image


class PipelineOutput:  # pylint: disable=too-few-public-methods
    images: list[Image]


def readline(fin: TextIOWrapper) -> str | None:
    line = fin.readline()
    if not line:
        return None
    segments = line.split("#", 1)
    return segments[0].strip()


def get_fname(ix: int) -> str:
    return f"study/out/img_{ix}.jpg"


def render(
        pipeline: Callable[..., PipelineOutput],
        text: str,
        iters: int,
        n_per: int) -> None:
    for _ in range(max(1, n_per)):
        imgs = pipeline(
            [text],
            width=512,
            height=512,
            num_inference_steps=iters,
            # negative_prompt=["bad hands"],
            ).images
        for img in imgs:
            ix = 0
            while os.path.exists(get_fname(ix)):
                ix += 1
            exif_data = img.getexif()
            exif_data[270] = text
            img.save(
                get_fname(ix),
                exif=exif_data,
                comment=text)


def run() -> None:
    args = sys.argv
    with open("study/model.txt", "r", encoding="utf-8") as fin:
        model = readline(fin)
        iters = int(readline(fin) or 30)
        n_per = int(readline(fin) or 2)
        safe = int(readline(fin) or 1)
    kwargs: dict[str, Any] = {}
    if safe < 1:
        kwargs["safety_checker"] = None
    pipeline = DiffusionPipeline.from_pretrained(
        model,
        cache_dir="models/hf/",
        **kwargs)
    pipe = pipeline.to(torch.device("mps"))
    if len(args) > 1:
        for arg in args[1:]:
            print(f"reading {arg}")
            with open(arg, "r", encoding="utf-8") as pin:
                while True:
                    text = readline(pin)
                    if text is None:
                        break
                    if text:
                        render(pipe, text, iters, n_per)
    else:
        text = input("prompt: ")
        render(pipe, text, iters, n_per)

    # accelerate
    # diffusers


if __name__ == "__main__":
    run()
