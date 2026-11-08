# Head scan and the hybrid bust

Sources for the marble bust that is built from two heads: the **TRELLIS** head (one portrait photo, see
`../trellis_bust.py`) supplies hair, jacket and body, and a **photogrammetry scan** (102 photos of a 360 degree orbit)
supplies the face. The photos themselves are not in the repo (about 540 MB); everything needed to rebuild the bust is.

```
scan/
  models/trellis_head_studio_s2.ply   TRELLIS head, the input of build_bust() in ../scene.py
  models/head_scan_oriented.ply       the photogrammetry head, upright, face toward -y (prepare_scan.py)
  models/bust_hybrid.glb              the finished hybrid bust (Blender export, meshopt), NOT the live site model
  data/align_xform.npz                scan -> bust transform (align_face.py)
  data/face_feature.npy               per-vertex "darker than its surroundings" from the photos (photo_features.py)
  mask.py  prepare_scan.py  align_face.py  photo_features.py   (plain Python)
  hybrid_bust.py                                               (runs inside Blender)
```

## Rebuild the bust from the repo (Blender 5.2, no photos needed)

```python
exec(open(r'<repo>/designs/blender/blender/scene.py').read())
exec(open(r'<repo>/designs/blender/blender/scan/hybrid_bust.py').read())
build_bust_hybrid()          # strength=0.3 relief from the photos; 0 = plain face swap
export_bust_glb()            # writes public/models/bust.glb (the live model): pass a different OUT_MODELS to keep it
```

`hybrid_bust.build_bust_hybrid()` checks that `data/face_feature.npy` matches the bust's vertex count. If `build_bust()`
changes, redo steps 8 to 10 below.

## How the scan was made

Tools (all local, all outside the repo): COLMAP 4.2.1 (BSD) with CUDA, OpenMVS 2.4.0 (AGPL-3.0, used as a tool),
rembg + u2net (MIT / Apache 2.0), Blender 5.2, Python with numpy, scipy, trimesh, Pillow.

1. **Frames.** Resize the 102 JPGs (6000 x 4000) to 3000 x 2000 into `work/images`.
2. **Poses.** The room is static while the camera orbits, so the whole frame is used for the poses:
   ```
   colmap feature_extractor --database_path db.db --image_path images --ImageReader.single_camera 1
          --ImageReader.camera_model OPENCV --FeatureExtraction.max_image_size 3000
          --SiftExtraction.max_num_features 16384 --SiftExtraction.peak_threshold 0.003
   colmap exhaustive_matcher --database_path db.db
   colmap mapper --database_path db.db --image_path images --output_path sparse     # model 1 had all 102 frames
   ```
   The default SIFT threshold finds only about 2,700 features per frame in a white room; lowering it gave 8,000.
3. **Masks.** `python mask.py images masked masks` cuts the subject out (flat grey background). Dense reconstruction on
   the unmasked frames spent its pixels on the whole room and gave a lumpy, featureless head; masked frames put them on
   the head.
4. **Undistort**, once unmasked (poses and the photos used by `photo_features.py`) and once masked:
   ```
   colmap image_undistorter --image_path images --input_path sparse/1 --output_path undist2 --output_type COLMAP
   colmap image_undistorter --image_path masked --input_path sparse/1 --output_path undist3 --output_type COLMAP
   ```
5. **Dense mesh (OpenMVS, in `undist3`).** 3000 px depth maps crashed in the fusion step on this machine (no pagefile),
   2250 px worked:
   ```
   InterfaceCOLMAP -i . -o scene.mvs --image-folder images
   DensifyPointCloud scene.mvs --resolution-level 0 --max-resolution 2250 --number-views 6
   ReconstructMesh scene_dense.mvs -o mesh_s.ply --min-point-distance 3 --smooth 6 --thickness-factor 2 --quality-factor 2
   ```
   `--smooth 6` is what removes the bumpy skin. `--smooth 3` brings it back, and smoothing the bumpy mesh afterwards
   (Taubin, any number of passes) does not fix it.
6. **Upright head.** `python prepare_scan.py work work/undist3/mesh_s.ply head_scan_oriented.ply` crops to the head,
   finds up and front from the cameras, and writes `orbit.npz`.
7. **Check.** The scan is the real shape of the head but has almost no eyes or lips; that is why steps 8 to 10 exist.

## How the hybrid was made

8. Build the TRELLIS bust in Blender (`build_bust`), then `hybrid_bust.export_old_bust_coords('old_bust_co.npy')`.
   `python align_face.py head_scan_oriented.ply old_bust_co.npy data/align_xform.npz` undoes the scan's 20 degree yaw
   and finds scale (1.48) and position by ICP on the face (median distance 0.018, about 2 mm).
9. `build_bust_hybrid(strength=0)` then `hybrid_bust.export_face_data('face_data.npz')`.
10. `python photo_features.py work face_data.npz data/align_xform.npz orbit.npz data/face_feature.npy` projects every face
    vertex into the 7 most frontal photos and samples a band-pass of the luminance.

The face swap projects the bust's face vertices along y onto the scan (a surface projection to the *nearest* point tore
the surface under the nose and chin). The relief pushes the surface in where the photos are dark; 3.5 mm at strength
1.0 gave heavy, drawn-on brows, so 0.3 is used.

Other bust variants built from the same scan (a marble bust with a baseball cap or a top hat, a jacket and a tie) are
in `build_bust_scan()` in `../scene.py`.
