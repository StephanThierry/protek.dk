"""Cut the subject out of every photo (rembg, u2net, CPU) and fill the background with flat grey.

The room is static while the camera orbits the subject, so the room is great for finding the camera poses, but the dense
reconstruction should spend its pixels on the head. Run this on the resized frames, then undistort the *masked* images
with the poses found from the unmasked ones (see README.md).

Usage:  python mask.py IMAGES_DIR OUT_MASKED_DIR OUT_MASKS_DIR
(IMAGES_DIR holds 3000x2000 JPGs; the mask is computed at 1500x1000 and scaled up, then eroded a little.)
"""
import glob
import os
import sys

import rembg
from PIL import Image, ImageFilter

src, masked_dir, masks_dir = sys.argv[1:4]
os.makedirs(masked_dir, exist_ok=True)
os.makedirs(masks_dir, exist_ok=True)
session = rembg.new_session('u2net', providers=['CPUExecutionProvider'])
for f in sorted(glob.glob(os.path.join(src, '*.jpg'))):
    name = os.path.basename(f)
    im = Image.open(f).convert('RGB')
    a = rembg.remove(im.resize((1500, 1000)), session=session, only_mask=True)
    a = a.resize(im.size, Image.LANCZOS).point(lambda v: 255 if v > 128 else 0).filter(ImageFilter.MinFilter(9))
    a.save(os.path.join(masks_dir, name + '.png'))
    bg = Image.new('RGB', im.size, (128, 128, 128))
    bg.paste(im, mask=a.filter(ImageFilter.GaussianBlur(1)))
    bg.save(os.path.join(masked_dir, name), quality=95)
    print(name, flush=True)
