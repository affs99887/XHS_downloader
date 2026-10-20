"""Conservative, local CLIP classification of visible legs and hosiery.

Cosine similarities are ranking scores, not calibrated probabilities. Black
hosiery classification is experimental and ambiguous cases require review.
"""

from pathlib import Path

from spider.image_filter import ImageDecision, download_verified


CLIP_REVISION = "d15189d7028b43f1d3e65039190477f6af591c2a"
CLIP_REPO = "Xenova/clip-vit-base-patch32"
CLIP_ASSETS = {
    "vision": ("onnx/vision_model_quantized.onnx", "583fd1110a514667812fee7d684952aaf82a99b959760c8d7dca7e0ab9839299", 89117001),
    "text": ("onnx/text_model_quantized.onnx", "73baab855d406190da9faa498cfedf65f15cf309f4cc7385b7b032e6d08e5c3a", 64504507),
    "tokenizer": ("tokenizer.json", "f7f3b7af117d467b58374797691a6438d3e6b9e9cef800dfd5dced7f697a90cd", 2224119),
}
EMBEDDINGS_PATH = Path(__file__).with_name("clothing_text_embeddings.npz")
FASHION_REVISION = "c56244cc94f92419e8369fa71efdaf403b124ce8"
FASHION_REPO = "Marqo/marqo-fashionSigLIP"
FASHION_ASSETS = {
    "vision": ("onnx/vision_model_quantized.onnx", "f1009cfce0eedd409f601e8351eedab72e8529641105eee6517821a9a634a2f4", 93973443),
    "text": ("onnx/text_model_quantized.onnx", "f5a7995e029c6ee9346fa46857661c4a171d28b164fa7703b85a527d73adf170", 111125229),
    "tokenizer": ("tokenizer.json", "5bc9b16db0e7adf5c9a2bd57f8f9c8e6ebdaabe75679cc956d007f78036d5b4a", 2421300),
}
FASHION_EMBEDDINGS_PATH = Path(__file__).with_name("fashion_text_embeddings.npz")

PROMPTS = {
    "black_hosiery": [
        "a photo of a person wearing sheer black pantyhose.",
        "a close-up photo of human legs in sheer black nylon stockings.",
        "a photo of a person wearing black tights and a skirt.",
    ],
    "bare_legs": [
        "a photo of a person with bare legs and no stockings.",
        "a close-up photo of bare human legs.",
        "a photo of a person wearing shorts with bare legs.",
    ],
    "black_pants": [
        "a photo of a person wearing black trousers.",
        "a photo of a person wearing long black pants.",
        "a close-up photo of legs wearing black dress pants.",
    ],
    "black_leggings": [
        "a photo of a person wearing opaque black sports leggings.",
        "a photo of a person wearing black yoga pants.",
        "a photo of a person wearing tight black athletic leggings.",
    ],
    "white_hosiery": [
        "a photo of a person wearing white stockings.",
        "a photo of human legs in white pantyhose.",
        "a photo of a person wearing white tights.",
    ],
    "nude_hosiery": [
        "a photo of a person wearing nude beige pantyhose.",
        "a photo of human legs in skin colored nylon stockings.",
        "a photo of a person wearing tan tights.",
    ],
    "other_legwear": [
        "a photo of a person wearing colorful tights.",
        "a photo of a person wearing blue jeans.",
        "a photo of a person wearing long boots.",
    ],
    "visible_legs": [
        "a photograph of a person with their legs visible.",
        "a cropped photograph showing human legs and feet.",
        "a photograph of a seated person showing their legs.",
    ],
    "portrait": [
        "a close-up portrait of a person's face.",
        "a photo showing only a person's head and shoulders.",
        "a selfie of a person's upper body, no legs in the picture.",
    ],
    "landscape": [
        "a photo of a landscape without people.",
        "a photo of buildings and city scenery without people.",
        "a photo of nature scenery without people.",
    ],
    "food": [
        "a photo of food and drinks on a table.",
        "a photo of a meal without people.",
        "a photo of desserts and fruit.",
    ],
    "product": [
        "a photo of packaged stockings for sale, nobody wearing them.",
        "a flat lay photo of clothing products without a person.",
        "a photo of an object on a table without people.",
    ],
    "text": [
        "a screenshot of text and a chart.",
        "a picture of a written document.",
        "a screenshot of a shopping app product listing.",
    ],
}
LEG_LABELS = {"black_hosiery", "bare_legs", "black_pants", "black_leggings", "white_hosiery",
              "nude_hosiery", "other_legwear", "visible_legs"}
NON_PERSON_LABELS = {"landscape", "food", "product", "text"}


def ensure_clip_asset(kind, *, fashion=False):
    assets = FASHION_ASSETS if fashion else CLIP_ASSETS
    repo, revision = (FASHION_REPO, FASHION_REVISION) if fashion else (CLIP_REPO, CLIP_REVISION)
    relative, digest, size = assets[kind]
    url = f"https://huggingface.co/{repo}/resolve/{revision}/{relative}"
    name = ("fashion_" if fashion else "") + Path(relative).name
    return download_verified(name, digest, size, [url])


def create_session(path):
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    return ort.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])


def decide_from_scores(scores, mode="stockings", *, known_legs=False, backend="clip-vit-base-patch32-int8"):
    leg_score = max(scores[label] for label in LEG_LABELS)
    non_person_score = max(scores[label] for label in NON_PERSON_LABELS)
    non_leg_score = max(non_person_score, scores["portrait"])
    detail = {key: round(value, 5) for key, value in scores.items()}

    def result(action, reason, person=None, legs=None, margin=None):
        return ImageDecision(action, reason, person, legs, backend=backend, similarities=detail, margin=margin)

    if mode == "person":
        margin = max(leg_score, scores["portrait"]) - non_person_score
        if margin >= 0.035:
            return result("keep", "语义模型检测到人物或人物局部", True, margin=margin)
        if margin <= -0.035:
            return result("discard", "语义模型更接近非人物内容", False, margin=margin)
        return result("review", "人物语义判断不确定", margin=margin)

    margin = leg_score - non_leg_score
    if not known_legs and margin <= -0.04:
        return result("discard", "语义模型更接近无腿部人物或非人物内容", legs=False, margin=margin)
    if not known_legs and margin < 0.025:
        return result("review", "局部人物或腿部是否可见不确定", margin=margin)
    if mode == "legs":
        return result("keep", "语义模型检测到人物及可见腿部（含腿部特写）", True, True, margin)

    negatives = [scores[label] for label in LEG_LABELS - {"black_hosiery", "visible_legs"}]
    black_margin = scores["black_hosiery"] - max(negatives)
    positive_margin = 0.015 if backend == "marqo-fashionSigLIP-int8" else 0.035
    if black_margin >= positive_margin:
        return result("keep", "实验模型更接近黑丝袜", True, True, black_margin)
    if black_margin <= -0.045:
        return result("discard", "实验模型更接近其他腿部服饰或光腿", True, True, black_margin)
    return result("review", "黑丝袜与其他服饰相似，需人工复核", True, True, black_margin)


class ClipClothingClassifier:
    def __init__(self, *, fashion=False):
        import numpy as np

        self.fashion = fashion
        revision = FASHION_REVISION if fashion else CLIP_REVISION
        with np.load(FASHION_EMBEDDINGS_PATH if fashion else EMBEDDINGS_PATH, allow_pickle=False) as data:
            if str(data["revision"]) != revision:
                raise ValueError("CLIP 文本向量与图像模型版本不一致")
            self.labels = list(data["labels"])
            self.embeddings = data["embeddings"]
        self.session = create_session(ensure_clip_asset("vision", fashion=fashion))

    def scores(self, path):
        import numpy as np
        from PIL import Image, ImageOps

        with Image.open(path) as source:
            source = ImageOps.exif_transpose(source).convert("RGB")
            # Preserve the whole scene; a standard center crop can cut off feet.
            image = (source.resize((224, 224), Image.Resampling.BICUBIC) if self.fashion
                     else ImageOps.pad(source, (224, 224), method=Image.Resampling.BICUBIC, color=(123, 117, 104)))
            pixels = np.asarray(image, dtype=np.float32) / 255.0
        mean = np.array([0.5] * 3 if self.fashion else [0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
        std = np.array([0.5] * 3 if self.fashion else [0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
        pixels = ((pixels - mean) / std).transpose(2, 0, 1)[None, ...]
        feature = self.session.run(["image_embeds"], {"pixel_values": pixels})[0][0]
        feature = feature / np.linalg.norm(feature)
        values = self.embeddings @ feature
        return {str(label): float(value) for label, value in zip(self.labels, values)}

    def classify(self, path, mode="stockings", *, known_legs=False):
        backend = "marqo-fashionSigLIP-int8" if self.fashion else "clip-vit-base-patch32-int8"
        return decide_from_scores(self.scores(path), mode, known_legs=known_legs, backend=backend)
