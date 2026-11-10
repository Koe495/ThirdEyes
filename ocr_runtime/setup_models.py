"""Installation-only downloads. Runtime OCR never invokes this script."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request

SOURCES = {
    "det.tar": "https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_det_infer.tar",
    "vgg_transformer.pth": "https://vocr.vn/data/vietocr/vgg_transformer.pth",
    "base.yml": "https://raw.githubusercontent.com/pbcquoc/vietocr/master/config/base.yml",
    "vgg-transformer.yml": "https://raw.githubusercontent.com/pbcquoc/vietocr/master/config/vgg-transformer.yml",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=Path, required=True)
    args = parser.parse_args()
    root = args.models.resolve()
    root.mkdir(parents=True, exist_ok=True)
    lock_path = Path(__file__).with_name("models.lock.json")
    expected = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.exists() else {}
    manifest = {}
    for name, url in SOURCES.items():
        target = root / name
        if not target.exists():
            bundled = Path(__file__).parent / "model_config" / name
            if bundled.is_file():
                shutil.copyfile(bundled, target)
            else:
                print("Downloading", name, flush=True)
                temporary = target.with_suffix(target.suffix + ".part")
                with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as output:
                    shutil.copyfileobj(response, output)
                temporary.replace(target)
        manifest[name] = {"url": url, "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "bytes": target.stat().st_size}
        if name in expected and manifest[name]["sha256"] != expected[name]["sha256"]:
            raise RuntimeError(f"Model/config checksum mismatch: {name}; refusing to use changed download")
        print(name, target.stat().st_size, "bytes", flush=True)
    (root / "det").mkdir(exist_ok=True)
    with tarfile.open(root / "det.tar") as archive:
        for member in archive.getmembers():
            name = Path(member.name).name
            if member.isfile() and name in {"inference.pdmodel", "inference.pdiparams", "inference.pdiparams.info"}:
                with archive.extractfile(member) as source, (root / "det" / name).open("wb") as output:
                    shutil.copyfileobj(source, output)
    import yaml
    config = yaml.safe_load((root / "base.yml").read_text(encoding="utf-8"))
    config.update(yaml.safe_load((root / "vgg-transformer.yml").read_text(encoding="utf-8")))
    config["weights"] = "vgg_transformer.pth"
    config["device"] = "cpu"
    config["cnn"]["pretrained"] = False
    config["predictor"]["beamsearch"] = False
    (root / "vietocr_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "sources.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Offline models ready.", flush=True)


if __name__ == "__main__":
    main()
