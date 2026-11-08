"""Photogrammetry mesh -> upright head scan.

The camera orbited the seated subject, so the cameras tell where the head is (the point closest to all viewing rays),
which way is up (the cameras' image axes) and which way the face looks (the camera of a frontal frame). The mesh is
cropped to a sphere around the head, the largest piece is kept, and everything is rotated so that +z is up and the
face looks along -y (Blender's front view).

Usage (Python with numpy + trimesh):
  python prepare_scan.py WORK_DIR MESH_PLY OUT_PLY [RADIUS] [FRONT_IMAGE]

WORK_DIR   contains undist2/sparse/images.bin (the COLMAP model the mesh was built from)
RADIUS     crop radius in reconstruction units (default 1.6: head, neck and shoulders)
FRONT_IMAGE a frame in which the subject looks straight into the camera (default img_1531.jpg)

Writes OUT_PLY and orbit.npz next to it (ctr = head centre, M = rotation rows [right, -front, up], used again by
photo_features.py to map bust coordinates back into the reconstruction).
"""
import os
import struct
import sys

import numpy as np
import trimesh


def read_images(path):
    """COLMAP images.bin -> {name: (R, t)} with x_cam = R x + t."""
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


def main(work, mesh_path, out_path, radius=1.6, front='img_1531.jpg'):
    ims = read_images(os.path.join(work, 'undist2', 'sparse', 'images.bin'))
    centres = np.array([-R.T @ t for R, t in ims.values()])
    axes = np.array([R.T @ np.array([0, 0, 1.0]) for R, _ in ims.values()])           # viewing directions
    A, b = np.zeros((3, 3)), np.zeros(3)
    for c, d in zip(centres, axes):                                                      # point closest to all rays
        P = np.eye(3) - np.outer(d, d)
        A += P
        b += P @ c
    ctr = np.linalg.solve(A, b)
    up = np.mean([-R.T[:, 1] for R, _ in ims.values()], axis=0)                          # image "up" in the world
    up /= np.linalg.norm(up)
    fc = -ims[front][0].T @ ims[front][1] - ctr
    fc -= up * (fc @ up)
    fc /= np.linalg.norm(fc)
    M = np.stack([np.cross(up, fc), -fc, up])                                            # new x, y, z (face toward -y)

    m = trimesh.load(mesh_path, process=False)
    keep = np.linalg.norm(m.vertices - ctr, axis=1) < radius
    sub = trimesh.Trimesh(m.vertices, m.faces[keep[m.faces].all(axis=1)], process=False)
    sub.remove_unreferenced_vertices()
    biggest = max(sub.split(only_watertight=False), key=lambda p: len(p.faces))
    out = trimesh.Trimesh((np.asarray(biggest.vertices) - ctr) @ M.T, biggest.faces, process=False)
    out.export(out_path)
    np.savez(os.path.join(os.path.dirname(os.path.abspath(out_path)), 'orbit.npz'), ctr=ctr, M=M, up=up)
    print('orbit centre', ctr.round(3), '| faces', len(out.faces), '| bounds', out.bounds.round(2).tolist())


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], a[1], a[2], float(a[3]) if len(a) > 3 else 1.6, a[4] if len(a) > 4 else 'img_1531.jpg')
