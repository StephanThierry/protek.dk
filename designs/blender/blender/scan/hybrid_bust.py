"""Hybrid marble bust: the TRELLIS bust (hair, jacket, body) with the face of the photogrammetry head scan.

Run inside Blender after scene.py (needs build_bust and _taubin from it):

  exec(open(r'<repo>/designs/blender/blender/scene.py').read())
  exec(open(r'<repo>/designs/blender/blender/scan/hybrid_bust.py').read())
  build_bust_hybrid()                       # builds collection 'Bust'; then export_bust_glb() / render_one('bust')

What it does
  1. build_bust() on the TRELLIS head (models/trellis_head_studio_s2.ply): remesh, hair, marble, plinth.
  2. Brings the oriented scan (models/head_scan_oriented.ply) into the bust's frame with data/align_xform.npz
     (align_face.py): undo the 20 degree yaw, scale 1.48, ICP onto the TRELLIS face.
  3. Face swap: the bust's face vertices (an ellipse in front of the head that fades out before the old hairline) are
     projected along y onto the scan, so the surface keeps the old topology and no seam is torn open. The transition band
     is smoothed and the skin lightly relaxed.
  4. Relief from the photos (data/face_feature.npy, made by photo_features.py): where the skin is darker than its
     surroundings (eyes, brows, nostrils, mouth line) the surface is pushed in, plus an unsharp mask. `strength`
     scales both; 1.0 is 3.5 mm of relief, which is too much, 0.3 is what is used.
  5. The old design's crown has a small horn at the front edge; it is sanded away.
"""
import os

import bmesh
import bpy
import numpy as np


def _find_scan_dir():
    """The folder holding models/ and data/: SCAN_DIR if set, else next to this file, else under scene.py's ROOT."""
    cands = [globals().get('SCAN_DIR')]
    if '__file__' in globals():
        cands.append(os.path.dirname(os.path.abspath(__file__)))
    if 'ROOT' in globals():
        cands.append(os.path.join(ROOT, 'blender', 'scan'))
    cands.append('D:/dev/github.com/protek.dk/designs/blender/blender/scan')
    for c in cands:
        if c and os.path.isdir(os.path.join(c, 'models')):
            return c
    raise RuntimeError('hybrid_bust: cannot find the scan folder; set SCAN_DIR before running this file')


_HERE = _find_scan_dir()

_SS = lambda t: np.clip(t, 0, 1) ** 2 * (3 - 2 * np.clip(t, 0, 1))


def _co(me):
    a = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', a)
    return a.reshape(-1, 3).astype(np.float64)


def face_weights(co):
    """1 on the face of the TRELLIS bust, easing to 0 toward the sides, the chin and the old hairline (~z 2.9)."""
    front = _SS((-co[:, 1] - 0.45) / 0.45)
    lat = 1 - _SS((np.abs(co[:, 0] - 0.014) / 0.64 - 0.70) / 0.45)
    vert = _SS((co[:, 2] - 1.45) / 0.35) * (1 - _SS((co[:, 2] - 2.52) / 0.42))
    return front * lat * vert


def export_old_bust_coords(path):
    """Vertex coordinates of the freshly built TRELLIS bust, the target of align_face.py."""
    np.save(path, _co(bpy.data.objects['Bust'].data).astype(np.float32))


def export_face_data(path):
    """co, nor, w of the hybrid before the relief, the input of photo_features.py."""
    me = bpy.data.objects['Bust'].data
    nor = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('normal', nor)
    co = _co(me)
    np.savez(path, co=co, nor=nor.reshape(-1, 3).astype(np.float64), w=face_weights(co))


def _import_scan(scan_ply, xform_npz):
    bpy.ops.wm.ply_import(filepath=scan_ply)
    sf = bpy.context.selected_objects[0]
    sf.name = 'ScanFace'
    xf = np.load(xform_npz)
    v = _co(sf.data)
    v = float(xf['s']) * (((v - xf['Msc']) @ xf['Rz'].T) @ xf['R'].T) + xf['t']
    sf.data.vertices.foreach_set('co', v.astype(np.float32).ravel())
    sf.data.update()
    for p in sf.data.polygons:
        p.use_smooth = True
    sf.hide_render = sf.hide_viewport = True
    return sf


def _remove_horn(me, cx=-0.385, cy=-0.675):
    """Sand the TRELLIS crown: the very top is flattened a little, and a small horn at the front edge (found from the
    silhouette at about x -0.385, y -0.675) is sanded away, strongest in the middle."""
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    top = max(bm.verts, key=lambda v: v.co.z).co.copy()
    passes = [(lambda v: ((v.co.x - top.x) ** 2 + (v.co.y - top.y) ** 2) ** 0.5, top.z - 0.5, 0.45, 40),
              (lambda v: ((v.co.x - top.x) ** 2 + (v.co.y - top.y) ** 2) ** 0.5, top.z - 0.5, 0.30, 80),
              (lambda v: ((v.co.x - top.x) ** 2 + (v.co.y - top.y) ** 2) ** 0.5, top.z - 0.5, 0.18, 160)]
    passes += [(lambda v: ((v.co.x - cx) ** 2 + (v.co.y - cy) ** 2) ** 0.5, 3.25, r, it)
               for r, it in ((0.40, 30), (0.28, 70), (0.18, 160), (0.10, 240))]
    for rad, zmin, r, it in passes:
        vs = [v for v in bm.verts if rad(v) < r and v.co.z > zmin]
        for _ in range(it):
            bmesh.ops.smooth_vert(bm, verts=vs, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.to_mesh(me)
    bm.free()


def build_bust_hybrid(strength=0.3, remove_horn=True):
    models, data = os.path.join(_HERE, 'models'), os.path.join(_HERE, 'data')
    info = build_bust(os.path.join(models, 'trellis_head_studio_s2.ply'))
    o = bpy.data.objects['Bust']
    me = o.data
    sf = _import_scan(os.path.join(models, 'head_scan_oriented.ply'), os.path.join(data, 'align_xform.npz'))
    feature = np.load(os.path.join(data, 'face_feature.npy')).astype(np.float64)
    if len(feature) != len(me.vertices):
        raise RuntimeError(f'face_feature.npy has {len(feature)} values but the bust has {len(me.vertices)} vertices: '
                           'rebuild it with photo_features.py after changing build_bust()')
    w = face_weights(_co(me))

    # face swap: project along y onto the scan, melt the transition, relax the skin
    vg = o.vertex_groups.new(name='Face')
    for i in np.nonzero(w > 0.002)[0]:
        vg.add([int(i)], float(w[i]), 'REPLACE')
    sw = o.modifiers.new('FaceProject', 'SHRINKWRAP')
    sw.target, sw.wrap_method, sw.vertex_group = sf, 'PROJECT', 'Face'
    sw.use_project_x, sw.use_project_y, sw.use_project_z = False, True, False
    sw.use_positive_direction, sw.use_negative_direction, sw.cull_face = True, True, 'OFF'
    with bpy.context.temp_override(object=o, active_object=o):
        bpy.ops.object.modifier_apply(modifier='FaceProject')
    band = o.vertex_groups.new(name='Band')
    b = np.clip(1 - np.abs(w - 0.45) * 1.6, 0, 1) * (w > 0.003)
    for i in np.nonzero(b > 0.02)[0]:
        band.add([int(i)], float(b[i]), 'REPLACE')
    melt = o.modifiers.new('Melt', 'SMOOTH')
    melt.factor, melt.iterations, melt.vertex_group = 0.7, 60, 'Band'
    with bpy.context.temp_override(object=o, active_object=o):
        bpy.ops.object.modifier_apply(modifier='Melt')
    soft = o.vertex_groups.new(name='FaceSoft')
    for i in np.nonzero(w > 0.5)[0]:
        soft.add([int(i)], 1.0, 'REPLACE')
    skin = o.modifiers.new('Skin', 'SMOOTH')
    skin.factor, skin.iterations, skin.vertex_group = 0.5, 6, 'FaceSoft'
    with bpy.context.temp_override(object=o, active_object=o):
        bpy.ops.object.modifier_apply(modifier='Skin')

    # relief from the photos plus an unsharp mask, both scaled by `strength`
    if strength:
        base = _co(me)
        nor = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get('normal', nor)
        nor = nor.reshape(-1, 3).astype(np.float64)
        n = len(me.vertices)
        e = np.empty(len(me.edges) * 2, np.int32)
        me.edges.foreach_get('vertices', e)
        e = e.reshape(-1, 2)
        a_, b_ = np.concatenate([e[:, 0], e[:, 1]]), np.concatenate([e[:, 1], e[:, 0]])
        deg = np.maximum(np.bincount(a_, minlength=n), 1).astype(float)
        fs = feature.copy()
        for _ in range(3):                                                  # keep pixel noise out of the skin
            fs = 0.5 * fs + 0.5 * np.bincount(a_, weights=fs[b_], minlength=n) / deg
        f = np.clip((fs - 0.15) / 0.85, 0, 1.2) * _SS((w - 0.35) / 0.3)
        tmp = me.copy()
        _taubin(tmp, 10)
        smooth = _co(tmp)
        bpy.data.meshes.remove(tmp)
        dd = (base - smooth) * 3.5 * strength
        nn = np.linalg.norm(dd, axis=1, keepdims=True)
        dd = np.where(nn > 0.05, dd * 0.05 / np.maximum(nn, 1e-9), dd)
        new = base + dd * _SS((w - 0.3) / 0.4)[:, None] - nor * (0.035 * strength * f)[:, None]
        me.vertices.foreach_set('co', new.astype(np.float32).ravel())
        me.update()
    if remove_horn:
        _remove_horn(me)
    for p in me.polygons:
        p.use_smooth = True
    return info
