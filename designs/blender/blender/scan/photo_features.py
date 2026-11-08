"""How much darker than its surroundings is the photographed skin at every face vertex of the bust?

(eyes, brows, nostrils, the line of the mouth: the things a photogrammetry mesh smooths away). Bust vertices are mapped
back into the reconstruction (bust -> scan -> COLMAP world), projected into the frames that look at the face most
squarely, and a band-pass of the luminance is sampled there. The result is one number per vertex, normalised so that the
95th percentile of the face is 1.

Usage (Python with numpy, scipy, Pillow):
  python photo_features.py WORK_DIR FACE_DATA_NPZ XFORM_NPZ ORBIT_NPZ OUT_NPY

WORK_DIR        undist2/sparse (COLMAP PINHOLE model) and undist2/images (undistorted photos); the photos stay
                outside the repo
FACE_DATA_NPZ   co, nor, w of the bust: vertex positions, normals and face weights (hybrid_bust.export_face_data)
XFORM_NPZ       align_face.py output
ORBIT_NPZ       prepare_scan.py output (ctr, M)
OUT_NPY         per-vertex feature; this repo keeps the result in scan/data/face_feature.npy
"""
import os
import struct
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates


def read_images(path):
    out = {}
    with open(path, 'rb') as f:
        n = struct.unpack('<Q', f.read(8))[0]
        for _ in range(n):
            _id, qw, qx, qy, qz, tx, ty, tz, _cam = struct.unpack('<idddddddi', f.read(64))
            name = b''
            while (c := f.read(1)) != b'\x00':
                name += c
            n2 = struct.unpack('<Q', f.read(8))[0]
            f.read(24 * n2)
            R = np.array([[1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
                          [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
                          [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)]])
            out[name.decode()] = (R, np.array([tx, ty, tz]))
    return out


def read_pinhole(path):
    with open(path, 'rb') as f:
        struct.unpack('<Q', f.read(8))
        _cid, model, wd, ht = struct.unpack('<iiQQ', f.read(24))
        n = {0: 3, 1: 4}[model]                                            # SIMPLE_PINHOLE or PINHOLE
        p = struct.unpack('<' + 'd' * n, f.read(8 * n))
    return (p[0], p[0], p[1], p[2], wd, ht) if model == 0 else (*p, wd, ht)


def main(work, face_npz, xform_npz, orbit_npz, out_npy):
    d = np.load(face_npz)
    co, nor, w = d['co'], d['nor'], d['w']
    xf = np.load(xform_npz)
    Rz, Msc, R, s, t = xf['Rz'], xf['Msc'], xf['R'], float(xf['s']), xf['t']
    orbit = np.load(orbit_npz)
    ctr, M = orbit['ctr'], orbit['M']
    ims = read_images(os.path.join(work, 'undist2', 'sparse', 'images.bin'))
    fx, fy, cx, cy, wd, ht = read_pinhole(os.path.join(work, 'undist2', 'sparse', 'cameras.bin'))

    scan = (((co - t) / s) @ R) @ Rz + Msc                                 # bust -> scan (inverse of align_face)
    P = scan @ M + ctr                                                     # scan -> COLMAP world (inverse of prepare_scan)
    Nw = ((nor @ R) @ Rz) @ M

    sel, central = w > 0.3, w > 0.8
    score = []
    for name, (Rm, tv) in ims.items():                                     # frames that look at the face squarely
        vd = (-Rm.T @ tv) - P[central]
        vd /= np.linalg.norm(vd, axis=1, keepdims=True)
        score.append((np.mean(np.sum(Nw[central] * vd, axis=1)), name))
    use = [n for _, n in sorted(score, reverse=True)[:7]]
    print('frames', use)

    acc, wsum = np.zeros(len(co)), np.zeros(len(co))
    for name in use:
        Rm, tv = ims[name]
        vd = (-Rm.T @ tv) - P
        vd /= np.linalg.norm(vd, axis=1, keepdims=True)
        cosv = np.sum(Nw * vd, axis=1)
        Xc = P @ Rm.T + tv
        u, v = fx * Xc[:, 0] / Xc[:, 2] + cx, fy * Xc[:, 1] / Xc[:, 2] + cy
        ok = sel & (cosv > 0.45) & (Xc[:, 2] > 0) & (u > 4) & (u < wd - 4) & (v > 4) & (v < ht - 4)
        img = np.asarray(Image.open(os.path.join(work, 'undist2', 'images', name)).convert('L'), dtype=np.float64) / 255
        band = gaussian_filter(img, 22) - gaussian_filter(img, 2.0)        # positive where darker than the surroundings
        wt = np.clip(cosv[ok] - 0.45, 0, None) ** 2
        acc[ok] += wt * map_coordinates(band, [v[ok], u[ok]], order=1)
        wsum[ok] += wt
    F = np.where(wsum > 0, acc / np.maximum(wsum, 1e-12), 0.0)
    ref = np.percentile(F[w > 0.5], 95)
    np.save(out_npy, np.clip(F / ref, -0.3, 1.5).astype(np.float32))
    print('covered face vertices', int(((wsum > 0) & sel).sum()), 'of', int(sel.sum()))


if __name__ == '__main__':
    main(*sys.argv[1:6])
