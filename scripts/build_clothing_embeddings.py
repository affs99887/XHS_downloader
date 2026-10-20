"""Regenerate CLIP prompt prototypes; tokenizers is only a build dependency.

Install tokenizers==0.23.3 in a development environment before running.
Normal downloads use the committed vectors and only need ONNX Runtime.
"""

from pathlib import Path
import argparse
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from tokenizers import Tokenizer

from spider.clip_filter import (CLIP_REVISION, EMBEDDINGS_PATH, PROMPTS, FASHION_REVISION,
                                FASHION_EMBEDDINGS_PATH, create_session, ensure_clip_asset)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fashion", action="store_true")
    fashion = parser.parse_args().fashion
    tokenizer = Tokenizer.from_file(str(ensure_clip_asset("tokenizer", fashion=fashion)))
    if not fashion:
        tokenizer.enable_truncation(max_length=77)
        tokenizer.enable_padding(length=77, pad_id=49407, pad_token="<|endoftext|>")
    session = create_session(ensure_clip_asset("text", fashion=fashion))
    labels, prototypes = [], []
    for label, prompts in PROMPTS.items():
        encoded = tokenizer.encode_batch(prompts)
        ids = np.array([value.ids for value in encoded], dtype=np.int64)
        vectors = session.run(["text_embeds"], {"input_ids": ids})[0]
        vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
        prototype = vectors.mean(axis=0)
        prototype /= np.linalg.norm(prototype)
        labels.append(label)
        prototypes.append(prototype)
    destination = FASHION_EMBEDDINGS_PATH if fashion else EMBEDDINGS_PATH
    np.savez_compressed(destination, revision=np.array(FASHION_REVISION if fashion else CLIP_REVISION),
                        labels=np.array(labels), embeddings=np.array(prototypes, dtype=np.float32))
    print(f"Saved {len(labels)} class prototypes to {destination}")


if __name__ == "__main__":
    main()
