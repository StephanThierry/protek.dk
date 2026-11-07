import sys, rembg
from PIL import Image
src, out = sys.argv[1], sys.argv[2]
img = Image.open(src).convert('RGB')
res = rembg.remove(img, session=rembg.new_session('u2net', providers=['CPUExecutionProvider']))
res.save(out)
print(out, res.size, res.mode)
