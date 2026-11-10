"""Download a reproducible random COCO val2017 subset (no training).

Run with .object-venv. Images/labels/cache stay in an ignored runtime directory.
Does not read or change datasets/objects/data.yaml.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import random
import time
import urllib.request
import zipfile

LABEL_URL = 'https://github.com/ultralytics/assets/releases/download/v0.0.0/coco2017labels.zip'
IMAGE_BASE = 'https://s3.amazonaws.com/images.cocodataset.org/val2017/'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        return
    temporary = path.with_suffix(path.suffix + '.pending')
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as response, temporary.open('wb') as out:
                while block := response.read(1024 * 1024):
                    out.write(block)
            temporary.replace(path)
            return
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--count', type=int, default=300)
    parser.add_argument('--seed', type=int, default=20261110)
    args = parser.parse_args()
    root = args.output.resolve()
    # Refuse to mix samples from different runs in one directory.
    if (root / 'manifest.json').exists():
        raise SystemExit('Output already has a manifest. Reuse it for evaluation or choose a new directory.')
    archive = root / 'coco2017labels.zip'
    download(LABEL_URL, archive)
    with zipfile.ZipFile(archive) as z:
        population = sorted(Path(n).stem for n in z.read('coco/val2017.txt').decode().splitlines() if n.strip())
        if len(population) != 5000 or len(set(population)) != 5000:
            raise ValueError('Expected 5000 unique validation images')
        if not 1 <= args.count <= len(population):
            raise ValueError('count must be between 1 and 5000')
        ids = sorted(random.Random(args.seed).sample(population, args.count))
        label_dir = root / 'labels/validation'
        label_dir.mkdir(parents=True, exist_ok=True)
        members = set(z.namelist())
        for image_id in ids:
            name = f'coco/labels/val2017/{image_id}.txt'
            # The conversion omits label files for images with no usable boxes.
            (label_dir / (image_id + '.txt')).write_bytes(z.read(name) if name in members else b'')
    image_dir = root / 'images/validation'

    def fetch(image_id):
        path = image_dir / (image_id + '.jpg')
        download(IMAGE_BASE + path.name, path)
        from PIL import Image
        with Image.open(path) as image:
            image.verify()
        label = label_dir / (image_id + '.txt')
        return {'id': image_id, 'image_sha256': sha256(path), 'label_sha256': sha256(label)}

    samples = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i, sample in enumerate(pool.map(fetch, ids), 1):
            samples.append(sample)
            if i % 25 == 0 or i == len(ids):
                print(f'Downloaded and verified {i}/{len(ids)} images', flush=True)
    import ultralytics
    import yaml
    config = Path(ultralytics.__file__).parent / 'cfg/datasets/coco.yaml'
    names = yaml.safe_load(config.read_text(encoding='utf-8'))['names']
    # Explicit list prevents stale/unselected images from entering evaluation.
    (root / 'selected.txt').write_text('\n'.join((image_dir / (i + '.jpg')).as_posix() for i in ids) + '\n', encoding='utf-8')
    (root / 'subset.yaml').write_text(yaml.safe_dump({
        'path': root.as_posix(), 'train': 'selected.txt', 'val': 'selected.txt', 'names': names,
    }, sort_keys=False), encoding='utf-8')
    manifest = {
        'dataset': 'COCO 2017 validation, random subset', 'population_images': len(population),
        'selection': 'random.Random(seed).sample(sorted IDs from val2017.txt, count), then sorted; includes empty-label images',
        'seed': args.seed, 'count': args.count, 'labels_url': LABEL_URL,
        'labels_archive_sha256': sha256(archive), 'image_base_url': IMAGE_BASE,
        'labels': 'Ultralytics YOLO bbox conversion; original COCO80 class IDs retained',
        'caveat': 'Public validation benchmark, not an unseen Kinect test set; not used for fine-tuning here.',
        'samples': samples,
    }
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Ready: {root / "subset.yaml"}', flush=True)


if __name__ == '__main__':
    main()
