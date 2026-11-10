"""Evaluate local detection weights with AP and fixed-confidence P/R.

Validated with Ultralytics 8.3.40. Uses its YOLO box evaluator, not pycocotools.
No camera, training, microphone or automatic model download is involved.
"""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import sys


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixed_metrics(tp, fp, fn):
    return {
        'tp': int(tp), 'fp': int(fp), 'fn': int(fn),
        'precision': float(tp / (tp + fp)) if tp + fp else None,
        'recall': float(tp / (tp + fn)) if tp + fn else None,
        'f1': float(2 * tp / (2 * tp + fp + fn)) if 2 * tp + fp + fn else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--imgsz', type=int, default=960)
    parser.add_argument('--confidence', type=float, default=.45)
    parser.add_argument('--nms-iou', type=float, default=.45)
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--split', choices=['val', 'test'], default='val')
    args = parser.parse_args()
    if not args.model.is_file() or not args.data.is_file() or not args.data.stat().st_size:
        parser.error('Local model and non-empty dataset YAML are required')
    if not .001 <= args.confidence <= 1 or not 0 < args.nms_iou <= 1 or args.threads < 1:
        parser.error('Invalid confidence, NMS IoU or thread count')
    root = args.project_root.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    os.environ.update(YOLO_OFFLINE='true', OMP_NUM_THREADS=str(args.threads),
                      MKL_NUM_THREADS=str(args.threads), YOLO_CONFIG_DIR=str(output.parent / 'yolo_config'))
    sys.path.insert(0, str(root))
    from thirdeyes.object_catalog import TARGETS
    import numpy as np
    import torch
    import ultralytics
    from ultralytics import YOLO, settings
    from ultralytics.models.yolo.detect import DetectionValidator
    settings.update({'sync': False})
    records = {}

    class FixedThresholdValidator(DetectionValidator):
        def init_metrics(self, model):
            super().init_metrics(model)
            self.fixed_tp = np.zeros(self.nc, dtype=np.int64)
            self.fixed_pred = np.zeros(self.nc, dtype=np.int64)
            self.fixed_gt = np.zeros(self.nc, dtype=np.int64)
            self.per_image = []

        def update_metrics(self, preds, batch):
            # Re-match after thresholding. Low-confidence boxes must not consume GT matches.
            for si, predictions in enumerate(preds):
                prepared = self._prepare_batch(si, batch)
                cls = prepared['cls']
                pred = predictions[predictions[:, 4] >= args.confidence]
                predn = self._prepare_pred(pred, prepared)
                matched = self._process_batch(predn, prepared['bbox'], cls)[:, 0] if len(pred) and len(cls) else torch.zeros(len(pred), dtype=torch.bool, device=pred.device)
                gt_count = np.bincount(cls.cpu().numpy().astype(int), minlength=self.nc)
                pred_count = np.bincount(pred[:, 5].cpu().numpy().astype(int), minlength=self.nc)
                tp_count = np.bincount(pred[matched, 5].cpu().numpy().astype(int), minlength=self.nc)
                self.fixed_gt += gt_count
                self.fixed_pred += pred_count
                self.fixed_tp += tp_count
                self.per_image.append({'image': Path(batch['im_file'][si]).name,
                                       'counts_by_class_id': {str(c): {'gt': int(gt_count[c]), 'predicted': int(pred_count[c]), 'tp': int(tp_count[c])}
                                                              for c in range(self.nc) if gt_count[c] or pred_count[c]}})
            super().update_metrics(preds, batch)

    def collect(validator):
        box = validator.metrics.box
        ap_index = {int(c): i for i, c in enumerate(box.ap_class_index)}
        vi_names = {v: k for k, v in TARGETS.items()}
        rows = []
        for cls_id, name in validator.names.items():
            tp = int(validator.fixed_tp[cls_id])
            gt = int(validator.fixed_gt[cls_id])
            pred = int(validator.fixed_pred[cls_id])
            idx = ap_index.get(cls_id)
            row = {'class_id': cls_id, 'name': name, 'project_label': vi_names.get(name),
                   'images_with_gt': int(validator.nt_per_image[cls_id]), 'instances': gt,
                   **fixed_metrics(tp, pred - tp, gt - tp),
                   'ap50': float(box.ap50[idx]) if idx is not None else (0.0 if gt else None),
                   'ap50_95': float(box.ap[idx]) if idx is not None else (0.0 if gt else None)}
            rows.append(row)

        def aggregate(selected):
            present = [r for r in selected if r['instances'] > 0]
            aps = [r for r in present if r['ap50'] is not None]
            return {'classes_requested': len(selected), 'classes_with_gt': len(present),
                    'instances': sum(r['instances'] for r in selected),
                    **fixed_metrics(*(sum(r[k] for r in selected) for k in ('tp', 'fp', 'fn'))),
                    'map50': float(np.mean([r['ap50'] for r in aps])) if aps else None,
                    'map50_95': float(np.mean([r['ap50_95'] for r in aps])) if aps else None,
                    'classes_without_gt': [r['name'] for r in selected if not r['instances']]}

        records.update(images_seen=validator.seen, all_model_classes=aggregate(rows),
                       project_classes=aggregate([r for r in rows if r['project_label']]),
                       unsupported_project_targets=[v for v in TARGETS.values() if v not in validator.names.values()],
                       per_class=rows, per_image_fixed_counts=validator.per_image,
                       validator_speed_ms_per_image=validator.speed,
                       ultralytics_summary_at_best_f1={k: float(v) for k, v in validator.metrics.results_dict.items()})

    model = YOLO(str(args.model.resolve()), task='detect')
    model.add_callback('on_val_start', lambda validator: torch.set_num_threads(args.threads))
    model.add_callback('on_val_end', collect)
    model.val(validator=FixedThresholdValidator, data=str(args.data.resolve()), split=args.split,
              imgsz=args.imgsz, conf=.001, iou=args.nms_iou, max_det=300, batch=1,
              device='cpu', workers=0, plots=False, save_json=False, save_txt=False,
              augment=False, half=False, verbose=False, project=str(output.parent / 'validator'), name='run')
    # Assertions prevent publishing counts inconsistent with the evaluated labels.
    assert records['images_seen'] == len(records['per_image_fixed_counts'])
    assert all(r['tp'] + r['fn'] == r['instances'] and r['fp'] >= 0 and r['fn'] >= 0 for r in records['per_class'])
    manifest_path = args.data.parent / 'manifest.json'
    report = {
        'measured_at': datetime.now().astimezone().isoformat(),
        'model': args.model.name, 'model_sha256': sha256(args.model),
        'dataset_yaml_sha256': sha256(args.data),
        'dataset_manifest_sha256': sha256(manifest_path) if manifest_path.is_file() else None,
        'environment': {'python': platform.python_version(), 'ultralytics': ultralytics.__version__,
                        'torch': torch.__version__, 'numpy': np.__version__, 'processor': platform.processor(),
                        'device': 'cpu', 'torch_threads': torch.get_num_threads()},
        'settings': {'imgsz': args.imgsz, 'ap_confidence_floor': .001, 'fixed_confidence': args.confidence,
                     'nms_iou': args.nms_iou, 'match_iou_fixed_metrics': .5, 'ap_iou_range': [.5, .95, .05],
                     'batch': 1, 'max_det': 300, 'split': args.split, 'all_model_classes_detected_together': True},
        'definitions': {
            'precision_recall_f1': 'Micro counts at fixed confidence, class-aware matching at IoU >= 0.5 using Ultralytics validator.',
            'map': 'Macro AP over classes with ground truth; confidence sweep >= 0.001, Ultralytics YOLO evaluator, not official pycocotools COCO AP.',
            'zero_denominators': 'null when undefined; classes with zero GT excluded from mAP, retained in FP counts.',
            'project_classes': 'Select supported ThirdEyes class names from all-class predictions; not complete Object Finder pipeline.',
            'scope': 'Public COCO validation subset; model development may have used COCO validation. Not independent Kinect accuracy.',
            'runtime_difference': 'Application searches one class, max_det=30; benchmark detects all classes, max_det=300. No depth, voice or camera.',
        }, **records,
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'output': str(output), 'project_classes': report['project_classes'],
                      'all_model_classes': report['all_model_classes']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
