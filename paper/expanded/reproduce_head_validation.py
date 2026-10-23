"""E5 / step 2 -- v1284 head v2: build the labelled set, train, and gate by movie holdout.

Labels come from the competition's sparse TRAIN annotation matched to the captured
fused detector centres at the official 7.0 um matching radius. The target is the
displacement the shipped head is asked to output: (gt_grid - det_grid) * 1.625 um,
i.e. isotropic um, exactly the convention in v1284_coordinate_refinement.refine.

Gate: leave-one-movie-out. A head is only worth shipping if it reduces displacement
error on movies it never saw, against BOTH the identity (no head) and the shipped head.
"""
import json, math, sys, argparse, hashlib, platform, time
from pathlib import Path

import numpy as np
import torch
import zarr

HERE = Path(__file__).resolve().parent
CAP = GT = SHIPPED = None
DOWNSAMPLE = np.array([1.0, 4.0, 4.0], dtype=np.float64)   # z, y, x  (predictor downsample)
SPACING = 1.625
RADIUS_UM = 7.0
FILMS = []


def load_gt(stem):
    g = zarr.open_group(str(GT / f"{stem}.geff"), mode="r")
    t = g["nodes/props/t/values"][:].astype(np.float64)
    z = g["nodes/props/z/values"][:].astype(np.float64)
    y = g["nodes/props/y/values"][:].astype(np.float64)
    x = g["nodes/props/x/values"][:].astype(np.float64)
    return t, np.column_stack([z, y, x])          # full-resolution voxels


def build(stem):
    gt_t, gt_xyz = load_gt(stem)
    feats, tgts, dists, dets, tt = [], [], [], [], []
    for f in sorted((CAP / stem).glob("*.npz")):
        d = np.load(f)
        coords = d["coords"].astype(np.float64)   # (N,4) t,z,y,x in DOWNSAMPLED grid
        feats.append(d["features"].astype(np.float32))
        frame = int(coords[0, 0])
        dets.append(coords)
        tt.append(np.full(len(coords), frame, dtype=np.int64))
        sel = np.flatnonzero(gt_t == frame)
        if len(sel) == 0:
            tgts.append(np.full((len(coords), 3), np.nan)); dists.append(np.full(len(coords), np.inf)); continue
        gt_grid = gt_xyz[sel] / DOWNSAMPLE                          # full voxels -> detector grid
        diff = (gt_grid[None, :, :] - coords[:, None, 1:]) * SPACING  # um
        dd = np.linalg.norm(diff, axis=2)
        j = dd.argmin(axis=1); dmin = dd[np.arange(len(coords)), j]
        # uniqueness: second-nearest match must be clearly farther, else the label is ambiguous
        dd2 = dd.copy(); dd2[np.arange(len(coords)), j] = np.inf
        dmin2 = dd2.min(axis=1) if dd.shape[1] > 1 else np.full(len(coords), np.inf)
        tgt = diff[np.arange(len(coords)), j]
        tgt[(dmin > RADIUS_UM) | (dmin2 < 2.0 * dmin + 1e-6)] = np.nan
        tgts.append(tgt); dists.append(dmin)
    return (np.concatenate(feats), np.concatenate(tgts), np.concatenate(dists),
            np.concatenate(dets), np.concatenate(tt))


def bounded(head, x):
    d = head(x)
    return 2.0 * d / (1.0 + torch.linalg.vector_norm(d, dim=-1, keepdim=True))


def make_head(width=32, depth=1):
    layers, ins = [], 224
    for _ in range(depth):
        layers += [torch.nn.Linear(ins, width), torch.nn.SiLU()]; ins = width
    layers += [torch.nn.Linear(ins, 3)]
    h = torch.nn.Sequential(*layers)
    torch.nn.init.zeros_(h[-1].weight); torch.nn.init.zeros_(h[-1].bias)
    return h


def err_um(pred, tgt):
    return np.linalg.norm(pred - tgt, axis=1)


def main():
    global HERE, CAP, GT, SHIPPED, FILMS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root', type=Path, required=True, help='Folder containing capture/, reference_train/ and shipped_v1_head.pt')
    parser.add_argument('--output', type=Path, required=True, help='New absent output directory outside inputs')
    parser.add_argument('--threads', type=int, default=16, help='Historical numerical replay uses 16 CPU threads; changing this can alter trained float32 results')
    parser.add_argument('--expected', type=Path, help='Optional frozen result, read only after training and scoring')
    args = parser.parse_args()
    root = args.input_root.resolve(); HERE = args.output.resolve()
    if HERE == root or root in HERE.parents or HERE.exists(): raise ValueError('Use a new output directory outside inputs')
    if args.threads < 1: raise ValueError('threads must be positive')
    CAP = root/'capture'; GT = root/'reference_train'; SHIPPED = root/'shipped_v1_head.pt'
    FILMS = sorted(p.name for p in CAP.iterdir() if p.is_dir())
    expected_films = ['44b6_12dfb391','44b6_267148e4','6bba_062c8d37','6bba_09961292']
    if FILMS != expected_films: raise ValueError('Expected the four declared held-out movies')
    if hashlib.sha256(SHIPPED.read_bytes()).hexdigest() != '625a0d9340f48193f2ec294fc2d81c5bb3c03087eab78ef0ae998a9c4c7da00c': raise ValueError('Historical shipped-head identity mismatch')
    HERE.mkdir(parents=True,exist_ok=False); (HERE/'folds').mkdir()
    torch.set_num_threads(args.threads)
    started=time.perf_counter()
    print("films:", FILMS, flush=True)
    data = {s: build(s) for s in FILMS}
    for s in FILMS:
        F, T, D, _, _ = data[s]
        ok = np.isfinite(T).all(axis=1)
        print(f"  {s}: detections={len(F)} labelled={int(ok.sum())} ({ok.mean():.1%}) median_match={np.median(D[ok]):.3f}um")

    shipped = torch.load(SHIPPED, map_location="cpu", weights_only=True)
    s_head = make_head(32, 1); s_head.load_state_dict(shipped["state_dict"]); s_head.eval()
    s_mean, s_scale = shipped["mean"], shipped["scale"]

    results = {"identity": {}, "shipped_v1": {}, "v2": {}, "v2_ens": {}}
    fold_report = []
    for hold in FILMS:
        print("TRAIN HOLDOUT",hold,flush=True)
        tr = [s for s in FILMS if s != hold]
        Ftr, Ttr = np.concatenate([data[s][0] for s in tr]), np.concatenate([data[s][1] for s in tr])
        mtr = np.isfinite(Ttr).all(axis=1)
        X, Y = Ftr[mtr], Ttr[mtr]
        mean, scale = X.mean(0), X.std(0) + 1e-6
        Xn = torch.tensor((X - mean) / scale, dtype=torch.float32)
        Yt = torch.tensor(np.clip(Y, -2.0, 2.0), dtype=torch.float32)

        heads = []
        for width, seed in [(32, 0), (64, 1), (128, 2)]:
            torch.manual_seed(seed)
            h = make_head(width, 2 if width >= 64 else 1)
            opt = torch.optim.Adam(h.parameters(), lr=2e-3)
            for ep in range(400):
                opt.zero_grad()
                loss = torch.nn.functional.mse_loss(bounded(h, Xn), Yt)
                loss.backward(); opt.step()
            h.eval(); heads.append(h)

        Fh, Th = data[hold][0], data[hold][1]
        mh = np.isfinite(Th).all(axis=1)
        Xh, Yh = Fh[mh], Th[mh]
        Xhn = torch.tensor((Xh - mean) / scale, dtype=torch.float32)
        with torch.no_grad():
            v2 = bounded(heads[0], Xhn).numpy()
            v2e = np.mean([bounded(h, Xhn).numpy() for h in heads], axis=0)
            v1 = bounded(s_head, torch.tensor((Xh - s_mean.numpy()) / s_scale.numpy(), dtype=torch.float32)).numpy()
        zero = np.zeros_like(Yh)
        for name, pred in (("identity", zero), ("shipped_v1", v1), ("v2", v2), ("v2_ens", v2e)):
            e = err_um(pred, Yh)
            results[name][hold] = {"n": int(mh.sum()), "mean_um": float(e.mean()), "median_um": float(np.median(e))}
        base = err_um(zero, Yh).mean()
        fold_report.append({
            "holdout": hold, "n": int(mh.sum()),
            "identity_mean_um": base,
            "shipped_v1_mean_um": float(err_um(v1, Yh).mean()),
            "v2_mean_um": float(err_um(v2, Yh).mean()),
            "v2_ens_mean_um": float(err_um(v2e, Yh).mean()),
            "v1_vs_identity_pct": float(100 * (1 - err_um(v1, Yh).mean() / base)),
            "v2_vs_identity_pct": float(100 * (1 - err_um(v2, Yh).mean() / base)),
            "v2_ens_vs_identity_pct": float(100 * (1 - err_um(v2e, Yh).mean() / base)),
            "v2_ens_vs_v1_pct": float(100 * (1 - err_um(v2e, Yh).mean() / err_um(v1, Yh).mean())),
        })
        torch.save({'holdout':hold,'training_movies':tr,'mean':mean,'scale':scale,
                    'state_dicts':[h.state_dict() for h in heads], 'widths':[32,64,128],
                    'depths':[1,2,2], 'seeds':[0,1,2], 'epochs':400}, HERE/'folds'/(hold+'.pt'))
        # persist the final head trained on ALL films for the graph-level arms
        if hold == FILMS[-1]:
            Fa, Ta = np.concatenate([data[s][0] for s in FILMS]), np.concatenate([data[s][1] for s in FILMS])
            ma = np.isfinite(Ta).all(axis=1)
            Xa = Fa[ma]; Ya = np.clip(Ta[ma], -2.0, 2.0)
            mu, sd = Xa.mean(0), Xa.std(0) + 1e-6
            Xan = torch.tensor((Xa - mu) / sd, dtype=torch.float32); Yat = torch.tensor(Ya, dtype=torch.float32)
            ens = []
            for width, depth, seed in [(32, 1, 11), (64, 2, 12), (128, 2, 13)]:
                torch.manual_seed(seed)
                h = make_head(width, depth)
                opt = torch.optim.Adam(h.parameters(), lr=2e-3)
                for ep in range(600):
                    opt.zero_grad(); loss = torch.nn.functional.mse_loss(bounded(h, Xan), Yat)
                    loss.backward(); opt.step()
                h.eval(); ens.append(h)
            torch.save({"state_dict": ens[0].state_dict(),
                        "mean": torch.tensor(mu, dtype=torch.float32),
                        "scale": torch.tensor(sd, dtype=torch.float32),
                        "note": "SDY head v2, width=32 depth=1, member 0 of 3",
                        "ensemble_state_dicts": [h.state_dict() for h in ens],
                        "ensemble_widths": [32, 64, 128]},
                       HERE / "v1284_head_v2.pt")
            print("saved", HERE / "v1284_head_v2.pt")

    print()
    print("=== LEAVE-ONE-MOVIE-OUT (displacement error, um) ===")
    hdr = f"{'holdout':<18}{'n':>7}{'identity':>11}{'v1':>11}{'v2':>11}{'v2_ens':>11}{'v1%':>9}{'v2_ens%':>10}{'v2ens_vs_v1%':>14}"
    print(hdr); print("-" * len(hdr))
    for r in fold_report:
        print(f"{r['holdout']:<18}{r['n']:>7}{r['identity_mean_um']:>11.4f}{r['shipped_v1_mean_um']:>11.4f}"
              f"{r['v2_mean_um']:>11.4f}{r['v2_ens_mean_um']:>11.4f}{r['v1_vs_identity_pct']:>8.1f}%"
              f"{r['v2_ens_vs_identity_pct']:>9.1f}%{r['v2_ens_vs_v1_pct']:>13.1f}%")
    wins = sum(1 for r in fold_report if r["v2_ens_vs_v1_pct"] > 0)
    print(f"\nheld-out movies where v2_ens beats the shipped head: {wins}/{len(fold_report)}")
    (HERE / "head_v2_gate.json").write_text(json.dumps({"folds": fold_report, "wins_vs_v1": wins},
                                                        indent=2, default=str), encoding="utf-8")


    # The frozen result does not enter construction, labels, optimization or scoring.
    target=args.expected if args.expected else root/'expected/head_v2_gate.json'
    comparison={'status':'TRAINING_AND_SCORING_COMPLETE','runtime':{'python':platform.python_version(),
                'numpy':np.__version__,'torch':torch.__version__,'zarr':zarr.__version__,
                'threads':args.threads,'seconds':time.perf_counter()-started},
                'heldout_movies':FILMS,'wins_head_vs_shipped':sum(r['v2_mean_um']<r['shipped_v1_mean_um'] for r in fold_report),
                'wins_ensemble_vs_shipped':wins,'numeric_absolute_tolerance_um':0.0001,
                'frozen_result_used_during_training':False,'numeric_differences':[]}
    if target.is_file():
        expected=json.loads(target.read_text(encoding='utf-8-sig'))
        expected_by={r['holdout']:r for r in expected['folds']}
        if set(expected_by)!=set(FILMS):raise ValueError('Frozen cohort differs')
        errors=[]
        for actual in fold_report:
            previous=expected_by[actual['holdout']]
            if actual['n']!=previous['n']:errors.append({'holdout':actual['holdout'],'field':'n','actual':actual['n'],'expected':previous['n']})
            for key in ['identity_mean_um','shipped_v1_mean_um','v2_mean_um','v2_ens_mean_um']:
                delta=float(actual[key])-float(previous[key])
                comparison['numeric_differences'].append({'holdout':actual['holdout'],'field':key,'delta_um':delta})
                if abs(delta)>0.0001:errors.append({'holdout':actual['holdout'],'field':key,'delta_um':delta})
        if wins!=expected['wins_vs_v1']:errors.append({'field':'wins_vs_v1','actual':wins,'expected':expected['wins_vs_v1']})
        comparison['mismatches']=errors
        comparison['status']='HEAD_TRAINING_REPRODUCTION_PASS' if not errors else 'COMPUTATION_COMPLETE_WITH_NUMERIC_DIFFERENCES'
    (HERE/'REPRODUCTION_CHECK.json').write_text(json.dumps(comparison,indent=2),encoding='utf-8')
    print(comparison['status'],flush=True)
    if comparison.get('mismatches'):raise SystemExit(2)


if __name__ == "__main__":
    main()
