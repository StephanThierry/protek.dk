"""Image -> 3D mesh with TRELLIS (MIT), mesh output only. Used for the head of the marble bust (build_bust in scene.py).

Usage (TRELLIS checked out at C:/ai/trellis, own venv with torch cu128, xformers, spconv-cu126):
  python trellis_bust.py gen photo.png outdir 1,2,3   (photo with transparent background, see cutout.py)
  python trellis_bust.py dec outdir/photo_s2.slat bust.ply
Stubs the training/rendering-only imports (kaolin, utils3d) so the non-commercial rasterizers are never needed,
and forces xformers onto its cutlass kernels (its Hopper flash kernel fails on Blackwell / RTX 5080).
"""
import os, sys, types
from unittest.mock import MagicMock

os.environ.setdefault('SPARSE_BACKEND', 'spconv')
os.environ.setdefault('ATTN_BACKEND', 'xformers')
os.environ.setdefault('SPCONV_ALGO', 'native')
os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')
sys.path.insert(0, r'C:\ai\trellis')

# --- stubs for imports the mesh path never calls
kaolin = types.ModuleType('kaolin'); kaolin.utils = types.ModuleType('kaolin.utils')
kaolin.utils.testing = types.ModuleType('kaolin.utils.testing'); kaolin.utils.testing.check_tensor = lambda *a, **k: True
sys.modules.update({'kaolin': kaolin, 'kaolin.utils': kaolin.utils, 'kaolin.utils.testing': kaolin.utils.testing})
for name in ('utils3d', 'utils3d.torch', 'plyfile', 'nvdiffrast', 'nvdiffrast.torch', 'open3d', 'pyvista', 'pymeshfix', 'igraph', 'xatlas'):
    sys.modules.setdefault(name, MagicMock())

# --- xformers: cutlass kernels only
import xformers.ops as xops
_orig = xops.memory_efficient_attention
def _mea(*a, **k):
    k.setdefault('op', xops.MemoryEfficientAttentionCutlassOp)
    return _orig(*a, **k)
xops.memory_efficient_attention = _mea

import numpy as np, torch, trimesh
from PIL import Image
import trellis.models as _tm
from trellis.pipelines import TrellisImageTo3DPipeline

# Low-memory loading (this machine has no pagefile, so CPU commit is tight):
# skip the Gaussian / radiance-field decoders the mesh path never uses, and build the rest directly on the GPU.
_orig_fp = _tm.from_pretrained
def _fp(path, **kw):
    if 'dec_gs' in path or 'dec_rf' in path:
        return torch.nn.Identity()
    with torch.device('cuda'):
        return _orig_fp(path, **kw)
_tm.from_pretrained = _fp

from trellis.modules import sparse as sp

# Two stages in separate processes, because GPU allocations on Windows also cost host commit and this machine
# has no pagefile: "gen" samples the structured latent and saves it, "dec" loads only the mesh decoder.
mode, src, out = sys.argv[1], sys.argv[2], sys.argv[3]
if mode == 'gen':
    # src may be several images (comma separated), seeds several values: every image x seed is saved
    pipe = TrellisImageTo3DPipeline.from_pretrained('microsoft/TRELLIS-image-large')
    pipe.cuda()
    seeds = [int(x) for x in (sys.argv[4] if len(sys.argv) > 4 else '1').split(',')]
    for path in src.split(','):
        tag = os.path.splitext(os.path.basename(path))[0]
        pre = pipe.preprocess_image(Image.open(path))  # what the model actually sees
        pre.save(os.path.join(out, f'{tag}_input.png'))
        with torch.no_grad():
            cond = pipe.get_cond([pre])
            for sd in seeds:
                torch.manual_seed(sd)
                coords = pipe.sample_sparse_structure(cond, 1, {'steps': 25, 'cfg_strength': 7.5})
                slat = pipe.sample_slat(cond, coords, {'steps': 25, 'cfg_strength': 3.0})
                f = os.path.join(out, f'{tag}_s{sd}.slat')
                torch.save({'feats': slat.feats.cpu(), 'coords': slat.coords.cpu()}, f)
                print('slat saved', f, tuple(slat.feats.shape), flush=True)
else:
    import json
    from huggingface_hub import hf_hub_download
    dec = _fp('microsoft/TRELLIS-image-large/ckpts/slat_dec_mesh_swin8_B_64l8m256c_fp16').eval()
    d = torch.load(src)
    slat = sp.SparseTensor(feats=d['feats'].cuda(), coords=d['coords'].cuda())
    with torch.no_grad():
        m = dec(slat)[0]
    v = m.vertices.detach().cpu().numpy()
    f = m.faces.detach().cpu().numpy()
    mesh = trimesh.Trimesh(v, f, process=True)
    mesh.export(out)
    print('mesh', out, len(mesh.vertices), 'verts', len(mesh.faces), 'faces', 'watertight', mesh.is_watertight)
