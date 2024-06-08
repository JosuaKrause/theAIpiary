import os

import torch
from diffusers import DiffusionPipeline


text = input("prompt: ")
with open("study/.model", "r", encoding="utf-8") as fin:
    model = fin.readline().strip()
    iters = int(fin.readline().strip())
    n_per = int(fin.readline().strip())
pipeline = DiffusionPipeline.from_pretrained(model)
pipeline = pipeline.to(torch.device("mps"))
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
        while os.path.exists(f"study/img_{ix}.jpg"):
            ix += 1
        img.save(f"study/img_{ix}.jpg")

# accelerate
# diffusers
