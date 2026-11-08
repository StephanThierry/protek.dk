"""Align the head scan onto the face of the TRELLIS bust.

The scan is turned about 20 degrees (the head was not square to the orbit), so the yaw is undone first (nose tip and the
middle between the ears give the facing direction), then a similarity transform (scale, rotation, translation) is found:
first from the nose tips and the face heights, then by trimmed ICP on the face region.

The face windows below are specific to this bust: the TRELLIS head built by build_bust() in scene.py (face between
z = 1.55 and 3.05, x within +-0.75, in front of y = -0.6) and the scan's face (z = -0.45 .. 0.62 in scan units).

Usage (Python with numpy, scipy, trimesh):
  python align_face.py SCAN_PLY OLD_BUST_COORDS_NPY OUT_XFORM_NPZ

OLD_BUST_COORDS_NPY is written from Blender by hybrid_bust.export_old_bust_coords() after build_bust().
OUT_XFORM_NPZ (Rz, Msc, R, s, t) is read by hybrid_bust.py and photo_features.py:
  bust = s * ((scan - Msc) @ Rz.T) @ R.T + t
"""
import sys

import numpy as np
import trimesh
from scipy.spatial import cKDTree


def umeyama(X, Y):
    """Best similarity transform taking points X onto Y (scale, rotation, translation)."""
    mx, my = X.mean(0), Y.mean(0)
    Xc, Yc = X - mx, Y - my
    U, D, Vt = np.linalg.svd(Yc.T @ Xc / len(X))
    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[2, 2] = -1
    R = U @ S @ Vt
    s = (D * np.diag(S)).sum() / ((Xc ** 2).sum() / len(X))
    return s, R, my - s * R @ mx


def main(scan_ply, old_npy, out_npz):
    v = np.asarray(trimesh.load(scan_ply, process=False).vertices, dtype=np.float64)
    old = np.load(old_npy).astype(np.float64)

    # scan landmarks and yaw
    sel = (v[:, 2] > -0.2) & (v[:, 2] < 0.3)
    N = v[sel][np.argmin(v[sel][:, 1])]                                    # nose tip
    ear = v[(v[:, 2] > 0.15) & (v[:, 2] < 0.45)]
    le, re = ear[np.argmin(ear[:, 0])], ear[np.argmax(ear[:, 0])]
    M = np.array([(le[0] + re[0]) / 2, (le[1] + re[1]) / 2, 0.0])          # middle between the ears
    d = (N - M)[:2]
    d /= np.linalg.norm(d)
    yaw = np.arctan2(d[0], -d[1])
    c, s_ = np.cos(-yaw), np.sin(-yaw)
    Rz = np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1]])
    vr = (v - M) @ Rz.T
    Nr = (N - M) @ Rz.T
    print('yaw', np.degrees(yaw).round(1), 'deg')

    sf = vr[(vr[:, 2] > -0.45) & (vr[:, 2] < 0.62) & (vr[:, 1] < Nr[1] * 0.45) & (np.abs(vr[:, 0] - Nr[0]) < 0.5)]
    of = old[(old[:, 2] > 1.55) & (old[:, 2] < 3.05) & (old[:, 1] < -0.6) & (np.abs(old[:, 0]) < 0.75)]
    old_nose = of[np.argmin(of[:, 1])]

    s = (3.05 - 1.55) / (0.62 + 0.45)
    R = np.eye(3)
    t = old_nose - s * (R @ Nr)
    tree = cKDTree(of)
    for _ in range(60):                                                    # trimmed ICP
        dist, idx = tree.query(s * (sf @ R.T) + t)
        keep = dist <= np.quantile(dist, 0.8)                              # hairline and chin need not match
        s, R, t = umeyama(sf[keep], of[idx[keep]])
    dist, _ = tree.query(s * (sf @ R.T) + t)
    print(f'scale {s:.3f}  median distance {np.median(dist):.4f}  90th percentile {np.quantile(dist, 0.9):.4f}')
    np.savez(out_npz, Rz=Rz, Msc=M, R=R, s=s, t=t)


if __name__ == '__main__':
    main(*sys.argv[1:4])
