from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

SHIP5 = [
    "gpt-image-2",
    "gemini-3-pro-image",
    "qwen-image-3.0",
    "seedream-5.0-pro",
    "flux-2-pro",
]

CREDIT_COST = {
    "flux-2-pro": 7,
    "qwen-image-3.0": 8,
    "seedream-5.0-pro": 11,
    "gpt-image-2": 11,
    "gemini-3-pro-image": 30,
}


def die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def slug(model: str) -> str:
    return model.removeprefix("orvix/")


def save_image(item: dict, out_dir: Path, stem: str) -> Path | None:
    b64 = item.get("b64_json")
    if isinstance(b64, str) and b64:
        payload = b64
        ext = ".png"
        if payload.startswith("data:"):
            header, _, payload = payload.partition(",")
            if "image/jpeg" in header or "image/jpg" in header:
                ext = ".jpg"
            elif "image/webp" in header:
                ext = ".webp"
        pad = (-len(payload)) % 4
        if pad:
            payload += "=" * pad
        raw = base64.b64decode(payload)
        path = out_dir / f"{stem}{ext}"
        path.write_bytes(raw)
        return path

    url = item.get("url")
    if not isinstance(url, str) or not url:
        return None
    parsed = urlparse(url)
    ext = Path(parsed.path).suffix or ".png"
    if ext.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        ext = ".png"
    path = out_dir / f"{stem}{ext}"
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        path.write_bytes(r.content)
    return path


def generate_one(
    client: httpx.Client,
    base: str,
    key: str,
    model: str,
    prompt: str,
    n: int,
    size: str | None,
    quality: str | None,
    out_dir: Path,
) -> int:
    public = slug(model)
    body: dict = {
        "model": f"orvix/{public}",
        "prompt": prompt,
        "n": n,
    }
    if size:
        body["size"] = size
    if quality:
        body["quality"] = quality

    cost = CREDIT_COST.get(public)
    print(f"=== {body['model']} ===")
    if cost:
        print(f"prepaid debit (catalogue): {cost * n} cr")

    r = client.post(
        f"{base}/v1/images/generations",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json=body,
    )
    print(f"HTTP {r.status_code}")

    try:
        payload = r.json()
    except json.JSONDecodeError:
        print(r.text[:800])
        return 1

    err = payload.get("error")
    if err:
        print("error=", json.dumps(err, ensure_ascii=False)[:800])
        return 1 if r.status_code != 200 else 0

    data = payload.get("data") or []
    print("model=", payload.get("model"), "data_len=", len(data))
    usage = payload.get("usage")
    if usage is not None:
        print("usage=", json.dumps(usage, ensure_ascii=False)[:800])

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    saved = 0
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        stem = f"{public.replace('.', '-')}_{stamp}_{i}"
        try:
            path = save_image(item, out_dir, stem)
        except Exception as e:
            print(f"save failed: {e}")
            continue
        if path:
            print(f"saved {path} ({path.stat().st_size} bytes)")
            saved += 1
        else:
            print("no url/b64_json on item; keys=", sorted(item.keys()))

    if r.status_code != 200 or saved == 0:
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hit Orvix POST /v1/images/generations and save the result."
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("ORV_MODEL", "flux-2-pro"),
        help="catalogue slug or orvix/<slug>. Use 'all' for ship-5.",
    )
    parser.add_argument(
        "--prompt",
        default=os.environ.get("ORV_PROMPT", "a red circle on white"),
    )
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--size", default=os.environ.get("ORV_SIZE") or None)
    parser.add_argument("--quality", default=os.environ.get("ORV_QUALITY") or None)
    parser.add_argument(
        "--out",
        default=os.environ.get("ORV_OUT_DIR", str(ROOT / "outputs")),
    )
    args = parser.parse_args()

    key = os.environ.get("ORV_KEY", "").strip()
    if not key:
        die("ORV_KEY is unset. Copy .env.example → .env and paste a live ai:invoke key.")

    base = os.environ.get("ORV_API_BASE", "https://api.orvix.id").rstrip("/")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.n < 1 or args.n > 4:
        die("n must be 1–4")

    models = SHIP5 if args.model == "all" else [slug(args.model)]
    fail = 0
    with httpx.Client(timeout=180.0) as client:
        for model in models:
            fail |= generate_one(
                client,
                base,
                key,
                model,
                args.prompt,
                args.n,
                args.size,
                args.quality,
                out_dir,
            )
    raise SystemExit(fail)


if __name__ == "__main__":
    main()
