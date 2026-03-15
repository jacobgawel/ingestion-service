"""Constants for the ingestion service."""

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "tiff", "svg"}

IMAGE_MODEL = "gpt-5-mini"

IMAGE_PROMPT = """
You are generating text to index an image for semantic search.

Your goal is to describe the image in a way that maximizes search recall.
Be factual and literal. Do not guess unknown information.

Rules:
- Only include information clearly visible in the image.
- Do not hallucinate text or brands.
- OCR text must match the image exactly.
- Include synonyms in keywords when relevant.
- Be concise but information-dense.
"""
