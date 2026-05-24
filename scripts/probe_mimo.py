"""Ad-hoc проверка: реально ли MiMo принимает наш OpenAI-формат для vision.

Запустить ДО Day 5 (первого реального теста на фото). Если упадёт —
адаптировать MimoProvider под фактический формат их API.

    python scripts/probe_mimo.py path/to/receipt.jpg
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

from packages.llm import OCRResult, RECEIPT_OCR_PROMPT
from packages.llm.providers.mimo import MimoConfig, MimoError, MimoProvider


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/probe_mimo.py <path-to-jpg>")
        sys.exit(1)

    img_path = Path(sys.argv[1])
    if not img_path.exists():
        print(f"Not found: {img_path}")
        sys.exit(1)

    api_key = os.environ.get("MIMO_API_KEY")
    if not api_key:
        print("Set MIMO_API_KEY in env")
        sys.exit(1)

    config = MimoConfig(
        api_key=api_key,
        base_url=os.getenv("MIMO_BASE_URL", "https://token-plan-sgp.xiaomimimo.com/v1"),
        model_vision=os.getenv("MIMO_MODEL_VISION", "mimo-v2-omni"),
    )
    client = httpx.AsyncClient(
        base_url=config.base_url,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    provider = MimoProvider(config, client=client)

    print(f"→ POST {config.base_url}/chat/completions (model={config.model_vision})")
    try:
        result, usage = await provider.vision(
            img_path.read_bytes(),
            RECEIPT_OCR_PROMPT,
            model=config.model_vision,
            response_format=OCRResult,
        )
    except MimoError as exc:
        print(f"❌ MimoError: reason={exc.reason} http={exc.http_status}")
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"❌ {type(exc).__name__}: {exc}")
        raise
    finally:
        await client.aclose()

    print("✅ Parsed OCRResult:")
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    print(f"\nUsage: {usage}")


if __name__ == "__main__":
    asyncio.run(main())
