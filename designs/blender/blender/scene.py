# Builds every 3D element for protek.dk/blender in Blender and renders them.
# Driven from Claude Code via the Blender MCP server:
#   exec(open(r'<repo>/designs/blender/blender/scene.py').read()); build_all(); render_all()
# Each element lives in its own collection; render_one() shows only that collection.
# Renders are written as transparent WEBP to designs/blender/public/renders/,
# the live star is exported as GLB to designs/blender/public/models/.
import bpy, bmesh, math, os
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if '__file__' in globals() else r'D:\dev\github.com\protek.dk\designs\blender'
OUT_RENDERS = os.path.join(ROOT, 'public', 'renders')
OUT_MODELS = os.path.join(ROOT, 'public', 'models')

TAU = math.pi * 2

# Palette shared with the particle front page and the Plakat star.
PAL = {
    'blue_d': '#3f7a8f', 'blue_m': '#4f96aa', 'blue_l': '#5ba9bf',
    'mint': '#7CF0C2', 'ice': '#E9F0EE', 'teal': '#2BB3A6', 'deep': '#1C5E6B',
    'coral': '#FF8A5B', 'gold': '#FFD27A', 'violet': '#9B8CFF',
}


def lin(h):
    """sRGB hex -> linear RGBA for Blender colour sockets."""
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c) + (1.0,)


# ---------------------------------------------------------------- scene setup

def reset():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.curves, bpy.data.lights, bpy.data.cameras):
        for b in list(block):
            if b.users == 0:
                block.remove(b)


def setup_render(samples=256, res=(1600, 1600)):
    s = bpy.context.scene
    s.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.refresh_devices()
    for d in prefs.devices:
        d.use = d.type == 'OPTIX'
    s.cycles.device = 'GPU'
    s.cycles.samples = samples
    s.cycles.use_denoising = True
    s.cycles.denoiser = 'OPTIX'
    s.render.film_transparent = True
    s.render.resolution_x, s.render.resolution_y = res
    s.render.resolution_percentage = 100
    s.view_settings.view_transform = 'AgX'
    s.view_settings.look = 'AgX - Medium High Contrast'
    s.render.image_settings.file_format = 'WEBP'
    s.render.image_settings.color_mode = 'RGBA'
    s.render.image_settings.quality = 84

    # Dark world with a faint teal horizon: shows up only in reflections.
    w = bpy.data.worlds.get('World') or bpy.data.worlds.new('World')
    s.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[0].color = lin('#05090B')
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = lin('#1C3F47')
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = 0.6
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    nt.links.new(sep.outputs['Z'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    nt.links.new(bg.outputs[0], out.inputs[0])


def coll(name):
    c = bpy.data.collections.get(name)
    if not c:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


def link(obj, c):
    for uc in obj.users_collection:
        uc.objects.unlink(obj)
    c.objects.link(obj)
    return obj


def lights():
    c = coll('Lights')

    def area(name, loc, size, energy, color='#FFFFFF'):
        L = bpy.data.lights.new(name, 'AREA')
        L.shape = 'DISK'
        L.size = size
        L.energy = energy
        L.color = lin(color)[:3]
        o = bpy.data.objects.new(name, L)
        o.location = loc
        o.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        c.objects.link(o)

    area('Key', (-6, -7, 9), 7, 2400, '#FFF4E8')
    area('Rim', (7, 6, 4), 4, 1800, '#9FDDF7')
    area('Fill', (-8, 2, -3), 6, 300, '#7CF0C2')
    area('Top', (0, 0, 12), 10, 500)


def camera():
    cam = bpy.data.objects.get('Cam')
    if not cam:
        cd = bpy.data.cameras.new('Cam')
        cam = bpy.data.objects.new('Cam', cd)
        coll('Lights').objects.link(cam)
    bpy.context.scene.camera = cam
    return cam


def aim(cam, loc, target=(0, 0, 0), lens=70):
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens


# ---------------------------------------------------------------- materials

def mat(name, color, metallic=0.0, rough=0.3, coat=0.0, emission=None, strength=0.0,
        transmission=0.0, ior=1.45, thin_film=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = lin(color)
    b.inputs['Metallic'].default_value = metallic
    b.inputs['Roughness'].default_value = rough
    b.inputs['Coat Weight'].default_value = coat
    b.inputs['Transmission Weight'].default_value = transmission
    b.inputs['IOR'].default_value = ior
    if emission:
        b.inputs['Emission Color'].default_value = lin(emission)
        b.inputs['Emission Strength'].default_value = strength
    if thin_film and 'Thin Film Thickness' in b.inputs:
        b.inputs['Thin Film Thickness'].default_value = thin_film
        b.inputs['Thin Film IOR'].default_value = 1.4
    return m


def x_gradient_mat(name, c0, c1, xmin, xmax, metallic=0.2, rough=0.25, coat=0.6):
    """Colour ramp along object X (helix strands go teal -> violet)."""
    m = mat(name, c0, metallic, rough, coat)
    nt = m.node_tree
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = xmin
    mr.inputs['From Max'].default_value = xmax
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = lin(c0)
    ramp.color_ramp.elements[1].color = lin(c1)
    nt.links.new(tc.outputs['Object'], sep.inputs[0])
    nt.links.new(sep.outputs['X'], mr.inputs['Value'])
    nt.links.new(mr.outputs['Result'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
    return m


def pla_mat(name, color, layer=0.06):
    """Matte PLA with printed layer lines (bump from a wave texture along Z)."""
    m = mat(name, color, 0.0, 0.42, 0.15)
    nt = m.node_tree
    tc = nt.nodes.new('ShaderNodeTexCoord')
    wave = nt.nodes.new('ShaderNodeTexWave')
    wave.bands_direction = 'Z'
    wave.inputs['Scale'].default_value = 1.0 / layer / 6.0
    wave.inputs['Distortion'].default_value = 0.4
    wave.inputs['Detail'].default_value = 1.0
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.35
    bump.inputs['Distance'].default_value = 0.02
    nt.links.new(tc.outputs['Object'], wave.inputs['Vector'])
    nt.links.new(wave.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], nt.nodes['Principled BSDF'].inputs['Normal'])
    return m


def bed_mat(name):
    """Textured PEI print plate that fades out radially (so it sits on the page background)."""
    m = mat(name, '#20262A', 0.6, 0.55)
    m.blend_method = 'BLEND' if hasattr(m, 'blend_method') else None
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 900
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.25
    nt.links.new(tc.outputs['Object'], noise.inputs['Vector'])
    nt.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], b.inputs['Normal'])
    # radial fade -> alpha
    grad = nt.nodes.new('ShaderNodeTexGradient')
    grad.gradient_type = 'SPHERICAL'
    mapn = nt.nodes.new('ShaderNodeMapping')
    mapn.inputs['Scale'].default_value = (0.24, 0.24, 0.24)
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    ramp.color_ramp.elements[1].position = 0.6
    ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    nt.links.new(tc.outputs['Object'], mapn.inputs['Vector'])
    nt.links.new(mapn.outputs['Vector'], grad.inputs['Vector'])
    nt.links.new(grad.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], b.inputs['Alpha'])
    return m


# ---------------------------------------------------------------- geometry helpers

def mesh_obj(name, verts, faces, c, material=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    me.update()
    o = bpy.data.objects.new(name, me)
    c.objects.link(o)
    if material:
        me.materials.append(material)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return o


def bevel(o, width=0.03, segments=3, harden=True):
    m = o.modifiers.new('Bevel', 'BEVEL')
    m.width = width
    m.segments = segments
    m.limit_method = 'ANGLE'
    m.harden_normals = harden
    if harden:
        for p in o.data.polygons:
            p.use_smooth = True
    return m


def offset_poly(p, d):
    """Offset a CCW polygon outward by d (miter, clamped). Emulates the SVG stroke on the star."""
    n = len(p)
    if sum((p[i][0] * p[(i + 1) % n][1] - p[(i + 1) % n][0] * p[i][1]) for i in range(n)) < 0:
        p = p[::-1]
    out = []
    for i in range(n):
        a, b, c = Vector(p[i - 1]), Vector(p[i]), Vector(p[(i + 1) % n])
        e0, e1 = (b - a).normalized(), (c - b).normalized()
        n0, n1 = Vector((e0.y, -e0.x)), Vector((e1.y, -e1.x))
        m = (n0 + n1)
        if m.length < 1e-6:
            m = n0
        m.normalize()
        k = min(d / max(m.dot(n0), 0.25), d * 3)
        out.append(tuple(b + m * k))
    return out


def prism_from_poly(name, poly, ztop, zbot, c, material):
    """Extrude a 2D polygon; ztop(x, y) gives a per-vertex top height (lets the star tips lift)."""
    n = len(poly)
    verts = [(x, y, zbot) for x, y in poly] + [(x, y, ztop(x, y)) for x, y in poly]
    faces = [list(range(n))[::-1], list(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j, n + i])
    return mesh_obj(name, verts, faces, c, material)


def curve_tube(name, pts, radius, c, material, cyclic=False, res=4):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = radius
    cu.bevel_resolution = res
    cu.use_fill_caps = True
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts):
        p.co = (q[0], q[1], q[2], 1)
    sp.use_cyclic_u = cyclic
    o = bpy.data.objects.new(name, cu)
    c.objects.link(o)
    cu.materials.append(material)
    return o


def cylinder_between(name, a, b, r, c, material, r2=None, verts=24):
    a, b = Vector(a), Vector(b)
    d = b - a
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r, radius2=r if r2 is None else r2,
                                    depth=d.length, location=(a + b) / 2)
    o = bpy.context.active_object
    o.name = name
    o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    o.data.materials.append(material)
    link(o, c)
    return o


def sphere(name, loc, r, c, material, seg=48):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=seg // 2, radius=r, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    link(o, c)
    return o


# ---------------------------------------------------------------- the Protek star

# Shards straight from the SVG logo (viewBox 1000, centre 520,490), tone d/m/l.
STAR_SVG = [
    ('d', [(257, 197), (468, 378), (520, 490), (420, 412)]),
    ('d', [(177, 684), (450, 490), (520, 490), (420, 585)]),
    ('d', [(717, 694), (610, 537), (520, 490), (580, 582)]),
    ('m', [(424, 45), (540, 430), (505, 500), (462, 400)]),
    ('m', [(283, 880), (465, 520), (520, 490), (500, 575)]),
    ('m', [(925, 538), (585, 458), (520, 490), (612, 538)]),
    ('l', [(117, 352), (512, 430), (520, 490), (485, 528)]),
    ('l', [(640, 980), (572, 488), (520, 470), (485, 528)]),
    ('l', [(731, 242), (572, 488), (520, 490), (512, 430)]),
]
STAR_SCALE = 6.4 / 1000          # same world scale as the particle star
STAR_STROKE = 11 * STAR_SCALE    # half of the SVG stroke-width 22


def star_shards():
    """Shards as (tone, polygon) in world units, y up, centred on the core."""
    out = []
    for tone, pts in STAR_SVG:
        poly = [((x - 520) * STAR_SCALE, -(y - 490) * STAR_SCALE) for x, y in pts]
        out.append((tone, offset_poly(poly, STAR_STROKE)))
    return out


def star_top(x, y):
    # flat back; the top rises toward the tips, so the star reads as a faceted relief
    return 0.16 + 0.11 * math.hypot(x, y)


def build_star(name='Star', c=None, with_rings=True, materials=None):
    c = c or coll(name)
    mats = materials or {
        'd': mat('Star_d', '#2E6578', 0.0, 0.22, 1.0),
        'm': mat('Star_m', PAL['blue_m'], 0.0, 0.2, 1.0),
        'l': mat('Star_l', '#79C3D6', 0.0, 0.18, 1.0),
    }
    objs = []
    for i, (tone, poly) in enumerate(star_shards()):
        o = prism_from_poly(f'{name}_shard{i}', poly, star_top, 0.0, c, mats[tone])
        bevel(o, 0.025, 3)
        objs.append(o)
    core = sphere(f'{name}_core', (0, 0, 0.3), 26 * STAR_SCALE * 1.3, c,
                  mat('Core', '#FFFFFF', emission='#FFFFFF', strength=12))
    objs.append(core)
    if with_rings:
        ring_m = mat('Ring', PAL['mint'], 0.0, 0.3, emission=PAL['mint'], strength=2.5)
        ring_m2 = mat('Ring_in', PAL['blue_l'], 0.0, 0.3, emission=PAL['blue_l'], strength=1.6)
        # flush with the logo: in its plane, crossing the shards like the rings in the SVG
        for rn, R, m in ((f'{name}_ring', 470 * STAR_SCALE, ring_m), (f'{name}_ring_in', 330 * STAR_SCALE, ring_m2)):
            bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=0.03, major_segments=256, minor_segments=12, location=(0, 0, 0))
            r = bpy.context.active_object
            r.name = rn
            r.location.z = 0.12
            r.data.materials.append(m)
            bpy.ops.object.shade_smooth()
            link(r, c)
            objs.append(r)
    return objs


# ---------------------------------------------------------------- other elements

def build_helix():
    """Career helix: two strands along X, rungs, one glowing node per workplace (10)."""
    c = coll('Helix')
    L, R, k = 9.0, 0.9, 1.1
    sm = x_gradient_mat('Strand', PAL['teal'], PAL['violet'], -L / 2, L / 2)
    for off, nm in ((0, 'A'), (math.pi, 'B')):
        pts = [(x, math.cos(x * k + off) * R, math.sin(x * k + off) * R)
               for x in (-L / 2 - 0.5 + i * (L + 1) / 400 for i in range(401))]
        curve_tube(f'Strand{nm}', pts, 0.075, c, sm)
    rm = mat('Rung', PAL['deep'], 0.3, 0.3, 0.5)
    x = -L / 2
    i = 0
    while x <= L / 2:
        a = x * k
        cylinder_between(f'Rung{i}', (x, math.cos(a) * R, math.sin(a) * R),
                         (x, -math.cos(a) * R, -math.sin(a) * R), 0.025, c, rm, verts=12)
        x += 0.42
        i += 1
    for n in range(10):
        t = n / 9
        col = PAL['mint'] if n == 9 else '#%02X%02X%02X' % tuple(
            round(int(PAL['gold'][j:j + 2], 16) * (1 - t) + int(PAL['coral'][j:j + 2], 16) * t) for j in (1, 3, 5))
        nx = -L / 2 + (n + 0.5) * L / 10
        sphere(f'Node{n}', (nx, 0, 0), 0.26 if n == 9 else 0.19, c,
               mat(f'Node{n}', col, emission=col, strength=1.0 if n == 9 else 0.5))


def build_ghstar():
    """GitHub star: a five-pointed gem in brushed gold."""
    c = coll('GhStar')
    Ro, Ri = 2.2, 0.95
    rim = []
    for i in range(10):
        a = math.pi / 2 + i * math.pi / 5
        r = Ro if i % 2 == 0 else Ri
        rim.append((math.cos(a) * r, math.sin(a) * r))
    verts = [(x, y, 0.0) for x, y in rim] + [(x, y, -0.28) for x, y in rim] + [(0, 0, 0.62), (0, 0, -0.28)]
    top, bot = 20, 21
    faces = []
    for i in range(10):
        j = (i + 1) % 10
        faces.append([i, j, top])
        faces.append([i + 10, j + 10, j, i][::-1])
        faces.append([j + 10, i + 10, bot])
    o = mesh_obj('GhStar', verts, faces, c, mat('Gold', PAL['gold'], 1.0, 0.22, 0.3))
    bevel(o, 0.02, 2, harden=False)


def build_knot():
    """(2,3) torus knot with an iridescent thin-film finish. Everything is connected."""
    c = coll('Knot')
    pts = []
    for i in range(600):
        t = TAU * i / 600
        r = 2.0 + 0.8 * math.cos(3 * t)
        pts.append((r * math.cos(2 * t), r * math.sin(2 * t), 0.8 * math.sin(3 * t)))
    curve_tube('Knot', pts, 0.42, c, mat('Iridescent', '#9AA8B0', 1.0, 0.14, 0.5, thin_film=420), cyclic=True, res=8)


def build_prism():
    """One white beam (legacy) splits into five colours (the five AI designs)."""
    c = coll('Prism')
    A, B, C = (0, 1.3), (-1.35, -1.05), (1.35, -1.05)
    glass = mat('Glass', '#FFFFFF', 0.0, 0.02, transmission=1.0, ior=1.5)
    o = prism_from_poly('Prism', [A, B, C], lambda x, y: 0.6, -0.6, c, glass)
    bevel(o, 0.04, 3)
    lerp = lambda p, q, t: (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
    pin, pout = lerp(A, B, 0.55), lerp(A, C, 0.6)
    white = mat('BeamW', '#FFFFFF', emission='#FFFFFF', strength=4)
    cylinder_between('BeamIn', (-4.2, -0.9, 0), (pin[0], pin[1], 0), 0.035, c, white)
    cylinder_between('BeamGlass', (pin[0], pin[1], 0), (pout[0], pout[1], 0), 0.05, c,
                     mat('BeamG', '#FFFFFF', emission='#E9F0EE', strength=3))
    rays = ['#E8452C', '#C9F27A', '#7CF0C2', '#4FA3B5', '#6C7BE0']
    for i, col in enumerate(rays):
        a = math.radians(-6 - i * 7)
        end = (pout[0] + math.cos(a) * 4.2, pout[1] + math.sin(a) * 4.2, 0)
        cylinder_between(f'Ray{i}', (pout[0], pout[1], 0), end, 0.03, c,
                         mat(f'Ray{i}', col, emission=col, strength=2.2), r2=0.11)


# Speech bubble outline, standing upright (x across, z up), flat on the bed so it prints without support:
# the tail runs from the left edge (z = tail_z) down to the bed at x = tail_tip (60 deg, no overhang).
# Mirrored in src/views.js (bubbleSpan) for the nozzle path.
BUBBLE = dict(w=3.2, z1=2.2, r=0.55, tail_z=0.9, tail_tip=-2.15, tail_base=-1.0, depth=0.5)


def bubble_outline(seg=10):
    w, z1, r = BUBBLE['w'], BUBBLE['z1'], BUBBLE['r']
    hx = w / 2
    pts = []

    def arc(cx, cz, a0, a1):
        for i in range(seg + 1):
            a = a0 + (a1 - a0) * i / seg
            pts.append((cx + math.cos(a) * r, cz + math.sin(a) * r))

    # counter-clockwise from the bottom edge where the tail starts
    pts.append((BUBBLE['tail_base'], 0.0))
    arc(hx - r, r, -math.pi / 2, 0)
    arc(hx - r, z1 - r, 0, math.pi / 2)
    arc(-hx + r, z1 - r, math.pi / 2, math.pi)
    pts.append((-hx, BUBBLE['tail_z']))
    pts.append((BUBBLE['tail_tip'], 0.0))
    return pts


def build_contact():
    """Former contact element (replaced by the bust, kept for reference): a speech bubble with '...' that the page 3D-prints live, plus the hotend and the print bed."""
    c = coll('Contact')
    pla = pla_mat('PLA_contact', PAL['mint'])
    d = BUBBLE['depth']
    o = prism_from_poly('Bubble', bubble_outline(), lambda x, y: d / 2, -d / 2, c, pla)
    bevel(o, 0.03, 2)
    o.rotation_euler = (math.radians(90), 0, 0)   # stand it up: outline in XZ, depth along Y
    # the typing dots, pressed out of the front face
    dot_m = mat('Dot', PAL['deep'], 0.0, 0.35, 0.3)
    zc = BUBBLE['z1'] / 2 + 0.1
    for i, x in enumerate((-0.75, 0.0, 0.75)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.22, depth=0.12, location=(x, -d / 2 - 0.04, zc),
                                            rotation=(math.radians(90), 0, 0))
        dot = bpy.context.active_object
        dot.name = f'Dot{i}'
        dot.data.materials.append(dot_m)
        bevel(dot, 0.03, 3)
        link(dot, c)
    # hotend: aluminium heater block + brass nozzle, origin at the nozzle tip
    hot = bpy.data.objects.new('Nozzle', None)
    c.objects.link(hot)
    hot.location = (0.6, 0, BUBBLE['z1'] + 0.9)
    alu = mat('Alu', '#B8C2C8', 1.0, 0.32)
    brass = mat('Brass', '#C9A24A', 1.0, 0.25)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.42))
    blk = bpy.context.active_object
    blk.name = 'Nozzle_block'
    blk.scale = (0.62, 0.42, 0.34)
    bpy.ops.object.transform_apply(scale=True)
    blk.data.materials.append(alu)
    bevel(blk, 0.03, 2)
    link(blk, c)
    blk.parent = hot
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.09, depth=0.5, location=(0, 0, 0.85))
    tube = bpy.context.active_object
    tube.name = 'Nozzle_tube'
    tube.data.materials.append(alu)
    link(tube, c)
    tube.parent = hot
    bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.03, radius2=0.14, depth=0.25, location=(0, 0, 0.125))
    tip = bpy.context.active_object
    tip.name = 'Nozzle_tip'
    tip.data.materials.append(brass)
    link(tip, c)
    tip.parent = hot
    # print bed
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.04))
    bed = bpy.context.active_object
    bed.name = 'Bed'
    bed.scale = (4.6, 1.8, 0.08)
    bpy.ops.object.transform_apply(scale=True)
    bed.data.materials.append(mat('PEI_flat', '#20262A', 0.5, 0.6))
    bevel(bed, 0.02, 2)
    link(bed, c)


def build_print_bed():
    """The star as a finished print: mint PLA with layer lines on a textured plate."""
    c = coll('PrintBed')
    pla = pla_mat('PLA', PAL['mint'])
    build_star('Printed', c, with_rings=False, materials={'d': pla, 'm': pla, 'l': pla})
    bpy.data.objects['Printed_core'].data.materials[0] = pla
    bpy.data.objects['Printed_core'].location.z = 0.12
    bpy.ops.mesh.primitive_plane_add(size=11, location=(0, 0, -0.001))
    bed = bpy.context.active_object
    bed.name = 'Bed'
    bed.data.materials.append(bed_mat('PEI'))
    link(bed, c)


def build_print_layers(layers=8, gap=0.24):
    """'Slicer' view: the same star cut into horizontal layers and pulled apart."""
    c = coll('PrintLayers')
    zmax = max(star_top(x, y) for _, p in star_shards() for x, y in p)
    h = zmax / layers
    for li in range(layers):
        z0, z1 = li * h, (li + 1) * h
        t = li / (layers - 1)
        col = '#%02X%02X%02X' % tuple(
            round(int(PAL['deep'][j:j + 2], 16) * (1 - t) + int(PAL['mint'][j:j + 2], 16) * t) for j in (1, 3, 5))
        m = mat(f'Layer{li}', col, 0.0, 0.35, 0.4, emission=col, strength=0.25)
        for si, (tone, poly) in enumerate(star_shards()):
            o = prism_from_poly(f'L{li}_{si}', poly, star_top, 0.0, c, m)
            bm = bmesh.new()
            bm.from_mesh(o.data)
            for co, no, clear_inner in ((z1, (0, 0, 1), False), (z0, (0, 0, 1), True)):
                geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
                res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, co), plane_no=no,
                                             clear_outer=not clear_inner, clear_inner=clear_inner)
                cut = [e for e in res['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
                if cut:
                    bmesh.ops.holes_fill(bm, edges=cut)
            bm.to_mesh(o.data)
            bm.free()
            if len(o.data.vertices) == 0:
                bpy.data.objects.remove(o, do_unlink=True)
                continue
            o.location.z = li * gap
            bevel(o, 0.008, 1)


# ---------------------------------------------------------------- shots

# name -> (collection, camera location, target, lens, resolution)
SHOTS = {
    'star':    ('Star',        (2.0, -7.0, 9.0),  (0, 0, 0.2),  40, (1600, 1600)),
    'helix':   ('Helix',       (0.5, -12, 3.4),   (0, 0, 0),    40, (2000, 1000)),
    'ghstar':  ('GhStar',      (1.5, -5.2, 5.4),  (0, 0, 0),    55, (1400, 1400)),
    'knot':    ('Knot',        (0, -8.5, 6.5),    (0, 0, 0),    50, (1400, 1400)),
    'prism':   ('Prism',       (0.5, -3.4, 11.5), (0.5, -0.7, 0), 45, (2000, 1250)),
    'print':   ('PrintBed',    (3.5, -8.0, 5.6),  (0, 0, 0.0),  45, (1600, 1200)),
    'layers':  ('PrintLayers', (4.0, -8.0, 6.2),  (0, 0, 1.0),  50, (1600, 1200)),
}


def build_all():
    reset()
    setup_render()
    lights()
    camera()
    build_star()
    build_helix()
    build_ghstar()
    build_knot()
    build_prism()
    build_print_bed()
    build_print_layers()
    build_dancers()
    return [c.name for c in bpy.data.collections]


def show_only(name):
    for c in bpy.context.scene.collection.children:
        vis = c.name in (name, 'Lights')
        c.hide_render = not vis
        c.hide_viewport = not vis


def render_one(key, samples=None, path=None, percent=100):
    cname, loc, target, lens, res = SHOTS[key]
    s = bpy.context.scene
    show_only(cname)
    aim(camera(), loc, target, lens)
    s.render.resolution_x, s.render.resolution_y = res
    s.render.resolution_percentage = percent
    if samples:
        s.cycles.samples = samples
    os.makedirs(OUT_RENDERS, exist_ok=True)
    s.render.filepath = path or os.path.join(OUT_RENDERS, f'{key}.webp')
    bpy.ops.render.render(write_still=True)
    return s.render.filepath


def render_all(samples=256):
    return [render_one(k, samples) for k in SHOTS]


def union_star(include_core=True, name='Star_union'):
    """Merge the evaluated shards (+ core) into one closed mesh with an exact boolean union.
    Used for the print check and for the live GLB: overlapping shards z-fight in real time."""
    dg = bpy.context.evaluated_depsgraph_get()
    src = [o for o in bpy.data.collections['Star'].objects
           if 'shard' in o.name or (include_core and o.name == 'Star_core')]
    copies = []
    for o in src:
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        c = bpy.data.objects.new('tmp_' + o.name, me)
        c.matrix_world = o.matrix_world.copy()
        bpy.context.scene.collection.objects.link(c)
        copies.append(c)
    base = copies[0]
    for c in copies[1:]:
        m = base.modifiers.new('U', 'BOOLEAN')
        m.operation, m.solver, m.object = 'UNION', 'EXACT', c
        m.material_mode = 'TRANSFER'
        with bpy.context.temp_override(object=base, active_object=base):
            bpy.ops.object.modifier_apply(modifier=m.name)
    for c in copies[1:]:
        bpy.data.objects.remove(c, do_unlink=True)
    base.name = name
    return base


def export_star_glb():
    """Export the star for the live Three.js hero: one merged mesh (no core sphere) + the two rings."""
    show_only('Star')
    u = union_star(include_core=False)
    # flat facets: smooth shading blends the neighbouring shard tops into smudged highlights
    for poly in u.data.polygons:
        poly.use_smooth = False
    bpy.ops.object.select_all(action='DESELECT')
    u.select_set(True)
    for o in bpy.data.collections['Star'].objects:
        if 'ring' in o.name:
            o.select_set(True)
    os.makedirs(OUT_MODELS, exist_ok=True)
    path = os.path.join(OUT_MODELS, 'star.glb')
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True,
                              export_apply=True, export_yup=True, export_animations=False)
    bpy.data.objects.remove(u, do_unlink=True)
    return path


def check_print(target_mm=80.0):
    """Printability check of the star, as quoted on the page.
    Measures the merged star at target_mm across: non-manifold edges, size, volume,
    downward-facing area steeper than 45 deg (overhang) and the flat base."""
    base = union_star(include_core=True, name='Star_check')
    bm = bmesh.new()
    bm.from_mesh(base.data)
    dims = base.dimensions.copy()
    k = target_mm / max(dims.x, dims.y)
    res = {
        'nonmanifold': sum(1 for e in bm.edges if not e.is_manifold),
        'dims_mm': tuple(round(v * k, 1) for v in dims),
        'volume_cm3': round(bm.calc_volume() * k ** 3 / 1000, 2),
        'overhang_mm2': round(sum(f.calc_area() for f in bm.faces
                                  if f.normal.z < -0.7071 and f.calc_center_median().z > 0.01) * k * k, 1),
        'base_mm2': round(sum(f.calc_area() for f in bm.faces
                              if f.normal.z < -0.999 and f.calc_center_median().z <= 0.01) * k * k, 1),
    }
    bm.free()
    bpy.data.objects.remove(base, do_unlink=True)
    return res


# ---------------------------------------------------------------- the three AI dancers

DANCE_FRAMES = 96   # 4 s loop at 24 fps
DANCE_U = 0.045     # world units per SVG unit


def box(name, x0, y0, x1, y1, depth, c, material, pivot, parent=None):
    """Block from SVG rect coords (y down), centred in depth, with its origin at `pivot` (SVG coords).
    With a parent, the block is placed relative to the body centre (32, 22)."""
    u = DANCE_U
    px, py = pivot
    X0, X1 = (x0 - px) * u, (x1 - px) * u
    Z0, Z1 = -(y1 - py) * u, -(y0 - py) * u
    d = depth * u / 2
    v = [(X0, -d, Z0), (X1, -d, Z0), (X1, d, Z0), (X0, d, Z0),
         (X0, -d, Z1), (X1, -d, Z1), (X1, d, Z1), (X0, d, Z1)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    o = mesh_obj(name, v, f, c, material)
    bevel(o, 0.012, 2)
    if parent:
        o.parent = parent
        o.location = ((px - 32) * u, 0, -(py - 22) * u)
    return o


def key(o, frame, loc=None, rot=None, scale=None):
    if loc is not None:
        o.location = loc
        o.keyframe_insert('location', frame=frame)
    if rot is not None:
        o.rotation_euler = [math.radians(a) for a in rot]
        o.keyframe_insert('rotation_euler', frame=frame)
    if scale is not None:
        o.scale = (scale,) * 3 if isinstance(scale, (int, float)) else scale
        o.keyframe_insert('scale', frame=frame)


def build_claude(c, x):
    """The pixel Claude from the site's SVG (64x44 grid) as blocks, with a 4 s dance:
    groove with bounce and sway, arms waving, legs stepping, then a hop with a full spin."""
    orange = mat('ClaudeOrange', '#D97757', 0.0, 0.45, 0.2)
    dark = mat('ClaudeEyes', '#1A0F0B', 0.0, 0.3)
    root = bpy.data.objects.new('Claude', None)
    c.objects.link(root)
    body = box('Claude_body', 10, 5, 54, 30, 18, c, orange, (32, 22))
    body.parent = root
    for ex in (20, 39):
        box(f'Claude_eye{ex}', ex, 12, ex + 5, 21, 19, c, dark, (32, 22)).parent = body
    arm_l = box('Claude_arm_l', 3, 14, 12, 21, 8, c, orange, (12, 17), body)
    arm_r = box('Claude_arm_r', 52, 14, 61, 21, 8, c, orange, (52, 17), body)
    legs = [box(f'Claude_leg{i}', lx, 29, lx + 5, 38, 6, c, orange, (lx + 2.5, 29), body)
            for i, lx in enumerate((14, 22, 37, 45))]
    leg_z = legs[0].location.z
    root.location = (x, 0, 0)

    F = DANCE_FRAMES
    # groove (0..48): bounce on every beat, sway and twist side to side
    for f in range(0, 49, 6):
        side = (f // 6) % 2
        key(root, f, loc=(x + (0.12 if side else -0.12), 0, 0.0 if f % 12 == 0 else 0.18),
            rot=(0, 0, 14 if side else -14))
    # hop with a full spin (48..80), land, settle back into the groove pose (96 == 0)
    key(root, 60, loc=(x, 0, 0.75), rot=(0, 0, 166))
    key(root, 72, loc=(x, 0, 0.75), rot=(0, 0, 346))
    key(root, 80, loc=(x, 0, -0.04), rot=(0, 0, 346))
    key(root, 88, loc=(x, 0, 0.12), rot=(0, 0, 346))
    key(root, F, loc=(x - 0.12, 0, 0.0), rot=(0, 0, 346))
    # squash on landing
    for f, s in ((0, (1, 1, 1)), (78, (1, 1, 1)), (80, (1.12, 1.12, 0.84)), (86, (1, 1, 1)), (F, (1, 1, 1))):
        key(body, f, scale=s)
    # arms wave in opposition (rotation around the depth axis, Y); up during the spin
    for f in range(0, F + 1, 6):
        up = (f // 6) % 2 == 0
        if 54 <= f <= 78:
            key(arm_l, f, rot=(0, 55, 0)); key(arm_r, f, rot=(0, -55, 0))
        else:
            key(arm_l, f, rot=(0, 35 if up else -20, 0)); key(arm_r, f, rot=(0, 20 if up else -35, 0))
    # legs step alternately
    for f in range(0, F + 1, 6):
        a = (f // 6) % 2 == 0
        for i, lg in enumerate(legs):
            lift = 0.13 if ((i % 2 == 0) == a and not 54 <= f <= 78) else 0.0
            key(lg, f, loc=(lg.location.x, 0, leg_z + lift))
    return root


def build_openai(c, x, img_path):
    """A coin carrying the OpenAI mark (texture from openai.jpg) that hops and flips on the beat."""
    m = mat('OpenAICoin', '#FFFFFF', 0.0, 0.35, 0.6)
    nt = m.node_tree
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(img_path, check_existing=True)
    nt.links.new(tex.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
    rim = mat('OpenAIRim', '#E9F0EE', 1.0, 0.25)
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=0.95, depth=0.14, location=(0, 0, 0))
    coin = bpy.context.active_object
    coin.name = 'OpenAI'
    coin.rotation_euler = (math.radians(90), 0, 0)
    bpy.ops.object.transform_apply(rotation=True)
    me = coin.data
    me.materials.append(rim)
    me.materials.append(m)
    # the caps get the logo (flat projection, back mirrored so it reads correctly), the side is metal
    uv = me.uv_layers.active or me.uv_layers.new()
    for p in me.polygons:
        cap = abs(p.normal.y) > 0.9
        p.material_index = 1 if cap else 0
        sx = -1 if p.normal.y > 0 else 1
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (0.5 + sx * co.x / 1.9 * 0.86, 0.5 + co.z / 1.9 * 0.86) if cap else (0.0, 0.0)
    bevel(coin, 0.02, 2, harden=False)
    link(coin, c)
    F = DANCE_FRAMES
    # little hops while rocking (0..48), a big double flip with Claude's spin, land with a squash
    for f in range(0, 49, 12):
        key(coin, f, loc=(x, 0, 0), rot=(0, 0, (f / 48) * 60 - 30), scale=(1, 1, 1))
        if f < 48:
            key(coin, f + 6, loc=(x, 0, 0.25), rot=(0, 0, (f + 6) / 48 * 60 - 30), scale=(0.96, 0.96, 1.05))
    key(coin, 66, loc=(x, 0, 0.9), rot=(360, 0, 30))
    key(coin, 80, loc=(x, 0, 0), rot=(720, 0, 30), scale=(1, 1, 1))
    key(coin, 84, loc=(x, 0, 0), rot=(720, 0, 30), scale=(1.06, 1.06, 0.92))
    key(coin, F, loc=(x, 0, 0), rot=(720, 0, -30), scale=(1, 1, 1))
    return coin


GEMINI_PATH = [  # the sparkle from the site's SVG (viewBox 64): tip, ctrl1, ctrl2, next tip
    ((32, 6), (33.5, 21), (43, 30.5), (58, 32)),
    ((58, 32), (43, 33.5), (33.5, 43), (32, 58)),
    ((32, 58), (30.5, 43), (21, 33.5), (6, 32)),
    ((6, 32), (21, 30.5), (30.5, 21), (32, 6)),
]


def build_gemini(c, x):
    """The Gemini sparkle extruded, with its blue -> violet -> rose gradient as vertex colours."""
    u = 0.045
    pts = []
    for p0, c1, c2, p1 in GEMINI_PATH:
        for i in range(24):
            t = i / 24
            q = [(1 - t) ** 3 * p0[k] + 3 * (1 - t) ** 2 * t * c1[k] + 3 * (1 - t) * t * t * c2[k] + t ** 3 * p1[k]
                 for k in (0, 1)]
            pts.append(((q[0] - 32) * u, -(q[1] - 32) * u))
    n = len(pts)
    d = 0.12
    verts = [(px, -d, pz) for px, pz in pts] + [(px, d, pz) for px, pz in pts] + [(0, -d - 0.14, 0), (0, d + 0.14, 0)]
    fc, bc = 2 * n, 2 * n + 1
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append((j, i, fc))            # front, domed toward the centre
        faces.append((n + i, n + j, bc))    # back
        faces.append((i, j, n + j, n + i))  # side
    g = mesh_obj('Gemini', verts, faces, c, None)
    me = g.data
    ca = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
    c0, c1_, c2_ = lin('#4285F4'), lin('#9B72CB'), lin('#D96570')
    for vi, v in enumerate(me.vertices):
        t = max(0.0, min(1.0, (v.co.x + v.co.z) / (2 * 26 * u) + 0.5))  # bottom-left -> top-right
        a, b, tt = (c0, c1_, t / 0.55) if t < 0.55 else (c1_, c2_, (t - 0.55) / 0.45)
        ca.data[vi].color = tuple(a[k] + (b[k] - a[k]) * tt for k in range(3)) + (1.0,)
    m = mat('GeminiGrad', '#FFFFFF', 0.0, 0.25, 0.8)
    nt = m.node_tree
    an = nt.nodes.new('ShaderNodeVertexColor')
    an.layer_name = 'Col'
    nt.links.new(an.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
    me.materials.append(m)
    me.validate()
    F = DANCE_FRAMES
    # twinkle: pulse on the beat while turning slowly; a flip with Claude's spin
    for f in range(0, 49, 6):
        big = (f // 6) % 2 == 0
        key(g, f, loc=(x, 0, 0.05 if big else 0), rot=(0, f * 1.5, 0), scale=1.0 if big else 0.82)
    key(g, 66, loc=(x, 0, 0.45), rot=(0, 162, 180), scale=1.15)
    key(g, 80, loc=(x, 0, 0), rot=(0, 144, 360), scale=0.9)
    key(g, F, loc=(x, 0, 0.05), rot=(0, 144, 360), scale=1.0)
    return g


def build_dancers():
    c = coll('Dancers')
    scn = bpy.context.scene
    scn.frame_start, scn.frame_end = 0, DANCE_FRAMES
    scn.render.fps = 24
    build_claude(c, -3.0)
    build_openai(c, 0.0, os.path.join(ROOT, 'blender', 'openai.jpg'))
    build_gemini(c, 3.0)
    scn.frame_set(0)
    return [o.name for o in c.objects]


def export_dancers_glb():
    """All three dancers in one GLB with a single 4 s animation clip."""
    show_only('Dancers')
    bpy.ops.object.select_all(action='DESELECT')
    for o in bpy.data.collections['Dancers'].objects:
        o.select_set(True)
    os.makedirs(OUT_MODELS, exist_ok=True)
    path = os.path.join(OUT_MODELS, 'dancers.glb')
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_apply=True,
                              export_yup=True, export_animations=True, export_animation_mode='SCENE',
                              export_frame_range=True, export_force_sampling=True,
                              export_image_format='WEBP')
    # the particle front page (site/) plays the same animation
    import shutil
    site = os.path.normpath(os.path.join(ROOT, '..', '..', 'site', 'public', 'models'))
    os.makedirs(site, exist_ok=True)
    shutil.copyfile(path, os.path.join(site, 'dancers.glb'))
    return path


SHOTS['dancers'] = ('Dancers', (0, -12, 1.2), (0, 0, 0.3), 38, (1600, 640))


# ---------------------------------------------------------------- GLB export of every element (live, rotating on the page)

def _export(objs, filename, animations=False):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    os.makedirs(OUT_MODELS, exist_ok=True)
    path = os.path.join(OUT_MODELS, filename)
    # meshopt keeps the curve-heavy models (helix, knot) small; three.js decodes it with MeshoptDecoder
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_apply=True,
                              export_yup=True, export_animations=animations,
                              export_meshopt_compression_enable=True)
    return path


def _join(objs, name):
    """Evaluated copies of objs joined into one mesh (curves, text and modifiers applied)."""
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    mats = []
    for o in objs:
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        me.transform(o.matrix_world)
        offset = len(mats)
        for m in me.materials:
            mats.append(m)
        for p in me.polygons:
            p.material_index += offset
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def export_element_glbs():
    """helix, ghstar, knot, prism and layers (one node per layer). The printed star reuses star.glb."""
    for c in bpy.context.scene.collection.children:
        c.hide_viewport = False
    out = {}
    for key_, cname in (('helix', 'Helix'), ('ghstar', 'GhStar'), ('knot', 'Knot'), ('prism', 'Prism')):
        out[key_] = _export(list(bpy.data.collections[cname].objects), f'{key_}.glb')
    # slicer view: one node per layer (named L0..), so the page can pull them apart and together
    layers = {}
    for o in bpy.data.collections['PrintLayers'].objects:
        layers.setdefault(o.name.split('_')[0], []).append(o)
    joined = [_join(v, k) for k, v in sorted(layers.items(), key=lambda kv: int(kv[0][1:]))]
    out['layers'] = _export(joined, 'layers.glb')
    for o in joined:
        bpy.data.objects.remove(o, do_unlink=True)
    return out


# ---------------------------------------------------------------- the marble bust (head from TRELLIS, finished here)

def marble_mat(name='Marble'):
    """Carrara-like marble for Cycles: warm white, faint grey veins, a touch of subsurface."""
    m = mat(name, '#ECE8E1', 0.0, 0.28, 0.25)
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    b.inputs['Subsurface Weight'].default_value = 0.12
    b.inputs['Subsurface Radius'].default_value = (0.3, 0.25, 0.2)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 1.4
    noise.inputs['Detail'].default_value = 8
    noise.inputs['Distortion'].default_value = 2.5
    wave = nt.nodes.new('ShaderNodeTexWave')
    wave.inputs['Scale'].default_value = 0.35
    wave.inputs['Distortion'].default_value = 6
    wave.inputs['Detail'].default_value = 6
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    # thin, sparse veins: only the very bottom of the wave turns grey
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = lin('#A8A59F')
    ramp.color_ramp.elements[1].position = 0.1
    ramp.color_ramp.elements[1].color = lin('#ECE8E1')
    nt.links.new(tc.outputs['Object'], noise.inputs['Vector'])
    nt.links.new(noise.outputs['Color'], wave.inputs['Vector'])
    nt.links.new(wave.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], b.inputs['Base Color'])
    return m


def bust_plinth(o, c, wf=0.82, df=0.95):
    """Dark stone plinth with a brass plaque reading the name, sized to the bust `o`."""
    bb = [Vector(v) for v in o.bound_box]
    w = (max(v.x for v in bb) - min(v.x for v in bb)) * wf
    dpt = (max(v.y for v in bb) - min(v.y for v in bb)) * df
    stone = mat('Plinth', '#2A3135', 0.0, 0.42, 0.3)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.45))
    pl = bpy.context.active_object
    pl.name = 'Plinth'
    pl.scale = (w, dpt, 0.9)
    bpy.ops.object.transform_apply(scale=True)
    pl.data.materials.append(stone)
    bevel(pl, 0.05, 3)
    link(pl, c)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -dpt / 2 - 0.01, -0.45))
    plate = bpy.context.active_object
    plate.name = 'Plaque'
    plate.scale = (w * 0.72, 0.03, 0.36)
    bpy.ops.object.transform_apply(scale=True)
    brass = mat('PlaqueBrass', '#C9A24A', 1.0, 0.3)
    plate.data.materials.append(brass)
    bevel(plate, 0.012, 2)
    link(plate, c)
    cu = bpy.data.curves.new('PlaqueText', 'FONT')
    cu.body = 'STEPHAN THIERRY'
    cu.size = 0.2
    cu.extrude = 0.01
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    t = bpy.data.objects.new('PlaqueText', cu)
    c.objects.link(t)
    t.location = (0, -dpt / 2 - 0.035, -0.45)
    t.rotation_euler = (math.radians(90), 0, 0)
    cu.materials.append(mat('PlaqueInk', '#1A1410', 0.4, 0.5))


def build_bust(ply, height=3.6, voxel=0.009, smooth=3, faces=110000):
    """Import the TRELLIS mesh, close and smooth it like sculpted stone, decimate for the web, add the plinth."""
    c = coll('Bust')
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.wm.ply_import(filepath=ply)
    o = bpy.context.selected_objects[0]
    link(o, c)
    o.name = 'Bust'
    # scale to `height`, stand it on z = 0, centred in x/y
    bpy.context.view_layer.update()
    bb = [o.matrix_world @ Vector(v) for v in o.bound_box]
    h = max(v.z for v in bb) - min(v.z for v in bb)
    o.scale = (height / h,) * 3
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.ops.object.transform_apply(scale=True)
    bb = [Vector(v) for v in o.bound_box]
    cx = (max(v.x for v in bb) + min(v.x for v in bb)) / 2
    cy = (max(v.y for v in bb) + min(v.y for v in bb)) / 2
    o.data.transform(__import__('mathutils').Matrix.Translation((-cx, -cy, -min(v.z for v in bb))))
    # stone finish: voxel remesh closes the flaky hair strands, a gentle smooth reads as chiselled and polished
    r = o.modifiers.new('Remesh', 'REMESH')
    r.mode = 'VOXEL'
    r.voxel_size = voxel
    s = o.modifiers.new('Smooth', 'CORRECTIVE_SMOOTH')
    s.iterations = smooth
    s.smooth_type = 'LENGTH_WEIGHTED'
    s.use_only_smooth = True
    # the hair: the generated strands are flaky, so smooth the top of the head hard into sculpted stone hair
    with bpy.context.temp_override(object=o, active_object=o):
        bpy.ops.object.modifier_apply(modifier='Remesh')
    vg = o.vertex_groups.new(name='Hair')
    for v in o.data.vertices:
        t = (v.co.z / height - 0.76) / 0.07
        if t > 0:
            vg.add([v.index], min(1.0, t), 'REPLACE')
    # thin double-sided flakes survive smoothing, so pull the hair region onto a calm hair volume instead:
    # a coarse voxel copy of the head, smoothed hard, used as a shrinkwrap target
    proxy = o.copy()
    proxy.data = o.data.copy()
    proxy.name = 'HairProxy'
    c.objects.link(proxy)
    pr = proxy.modifiers.new('Remesh', 'REMESH')
    pr.mode = 'VOXEL'
    pr.voxel_size = 0.06
    ps = proxy.modifiers.new('Smooth', 'SMOOTH')
    ps.factor = 1.0
    ps.iterations = 40
    hs = o.modifiers.new('HairSmooth', 'SHRINKWRAP')
    hs.target = proxy
    hs.wrap_method = 'NEAREST_SURFACEPOINT'
    hs.vertex_group = 'Hair'
    hs2 = o.modifiers.new('HairBlend', 'CORRECTIVE_SMOOTH')
    hs2.iterations = 8
    hs2.vertex_group = 'Hair'
    hs2.use_only_smooth = True
    # a final fine remesh welds the shrinkwrapped hair (no overlapping faces), then a light smooth
    cr = o.modifiers.new('Clean', 'REMESH')
    cr.mode = 'VOXEL'
    cr.voxel_size = voxel
    cs = o.modifiers.new('CleanSmooth', 'CORRECTIVE_SMOOTH')
    cs.iterations = 2
    cs.use_only_smooth = True
    d = o.modifiers.new('Decimate', 'DECIMATE')
    bpy.context.view_layer.update()
    n = len(o.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.polygons)
    d.ratio = min(1.0, faces / max(n, 1))
    for mname in ('Smooth', 'HairSmooth', 'HairBlend', 'Clean', 'CleanSmooth', 'Decimate'):
        with bpy.context.temp_override(object=o, active_object=o):
            bpy.ops.object.modifier_apply(modifier=mname)
    bpy.data.objects.remove(proxy, do_unlink=True)
    # last touch: drop tiny loose fragments and sand down any nub left at the very top of the hair
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.verts.ensure_lookup_table()
    seen, small = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, isl = [v], []
        seen.add(v.index)
        while stack:
            x = stack.pop()
            isl.append(x)
            for e in x.link_edges:
                w = e.other_vert(x)
                if w.index not in seen:
                    seen.add(w.index)
                    stack.append(w)
        if len(isl) < 500:
            small += isl
    bmesh.ops.delete(bm, geom=small, context='VERTS')
    # spikes: compare the top of the head with a heavily smoothed copy; whatever sticks out the most gets sanded down
    hair = [v for v in bm.verts if v.co.z > height * 0.74]
    orig = {v.index: v.co.copy() for v in hair}
    for _ in range(30):
        bmesh.ops.smooth_vert(bm, verts=hair, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    smooth_co = {v.index: v.co.copy() for v in hair}
    for v in hair:
        v.co = orig[v.index]
    spikes = {v for v in hair if (orig[v.index] - smooth_co[v.index]).length > 0.035}
    for _ in range(4):  # grow the selection a few rings so the sanding blends in
        spikes |= {e.other_vert(v) for v in list(spikes) for e in v.link_edges}
    spikes = list(spikes)
    for _ in range(60):
        bmesh.ops.smooth_vert(bm, verts=spikes, factor=0.6, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    # a blunt nub at the crown is too wide for that test: flatten the area around the highest point hard
    top = max(bm.verts, key=lambda v: v.co.z).co.copy()
    crown = [v for v in bm.verts if (v.co - top).length < 0.3]
    for _ in range(300):
        bmesh.ops.smooth_vert(bm, verts=crown, factor=0.7, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    # needles: single thin spikes whose faces point in opposite directions; sand them away too
    bm.normal_update()
    needles = {v for v in bm.verts if v.co.z > height * 0.6 and
               any(f1.normal.dot(f2.normal) < -0.3 for f1 in v.link_faces for f2 in v.link_faces)}
    for _ in range(3):
        needles |= {e.other_vert(v) for v in list(needles) for e in v.link_edges}
    needles = list(needles)
    for _ in range(120):
        bmesh.ops.smooth_vert(bm, verts=needles, factor=0.6, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.to_mesh(o.data)
    bm.free()
    for p in o.data.polygons:
        p.use_smooth = True
    o.data.materials.clear()
    o.data.materials.append(marble_mat())
    bust_plinth(o, c)
    return {'faces': len(o.data.polygons), 'size': tuple(round(x, 3) for x in o.dimensions)}


def _boundary_loops(bm):
    """Ordered vertex loops of the open boundary of `bm` (edges with a single face)."""
    edges = [e for e in bm.edges if len(e.link_faces) == 1]
    nxt = {}
    for e in edges:
        for v in e.verts:
            nxt.setdefault(v, []).append(e.other_vert(v))
    loops, seen = [], set()
    for v0 in nxt:
        if v0 in seen:
            continue
        loop, v, prev = [v0], v0, None
        seen.add(v0)
        while True:
            cand = [w for w in nxt[v] if w is not prev and w not in seen]
            if not cand:
                break
            prev, v = v, cand[0]
            loop.append(v)
            seen.add(v)
        loops.append(loop)
    return loops


def _cap_loop(bm, loop, dome=0.0, rings=14, smooth_iters=0):
    """Close a boundary loop with concentric rings that rise into a dome (dome = height as a fraction of radius)."""
    cen = sum((v.co for v in loop), Vector()) / len(loop)
    rad = sum((v.co - cen).xy.length for v in loop) / len(loop)
    ztop = max(v.co.z for v in loop) + dome * rad
    prev = loop
    new_verts = []
    for k in range(1, rings):
        t = k / rings
        s = math.sqrt(1 - (1 - t) ** 2)  # ellipsoid: rises steeply from the rim and rounds off at the top
        ring = [bm.verts.new((cen.x + (v.co.x - cen.x) * (1 - t), cen.y + (v.co.y - cen.y) * (1 - t),
                              v.co.z + (ztop - v.co.z) * s)) for v in loop]
        new_verts += ring
        for i in range(len(loop)):
            j = (i + 1) % len(loop)
            bm.faces.new((prev[i], prev[j], ring[j], ring[i]))
        prev = ring
    top = bm.verts.new((cen.x, cen.y, ztop))
    new_verts.append(top)
    for i in range(len(loop)):
        bm.faces.new((prev[i], prev[(i + 1) % len(loop)], top))
    if smooth_iters:  # relax the radial ribs; the rim stays pinned
        for _ in range(smooth_iters):
            bmesh.ops.smooth_vert(bm, verts=new_verts, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)


def _loft_base(bm, loop, half_w, half_d, drop_a, drop_b, rings_a=16, rings_b=4):
    """Grow a rounded shoulder block under a boundary loop (the neck): a quarter-ellipse profile flares the loop
    out to an ellipse of half_w x half_d, then the sides run straight down and a flat base closes it."""
    cen = sum((v.co for v in loop), Vector()) / len(loop)
    z0 = cen.z
    info = []
    for v in loop:
        d = (v.co - cen).xy
        r0 = d.length
        dr = d / r0 if r0 > 1e-9 else Vector((1, 0))
        re = 1 / math.sqrt((dr.x / half_w) ** 2 + (dr.y / half_d) ** 2)
        info.append((dr, r0, re, v.co.z))
    prev = loop
    for kk in range(1, rings_a + rings_b + 1):
        if kk <= rings_a:
            th = kk / rings_a * math.pi / 2
            sr = math.sin(th)
            z = z0 - drop_a * (0.6 * (1 - math.cos(th)) + 0.4 * sr)  # sloping shoulder line, rounding off to vertical
        else:
            sr = 1.0
            z = z0 - drop_a - drop_b * (kk - rings_a) / rings_b
        ring = []
        for (dr, r0, re, zv) in info:
            r = r0 + (re - r0) * sr
            zz = z + (zv - z0) * (1 - sr) if kk <= rings_a else z
            ring.append(bm.verts.new((cen.x + dr.x * r, cen.y + dr.y * r, zz)))
        for i in range(len(loop)):
            j = (i + 1) % len(loop)
            bm.faces.new((prev[i], prev[j], ring[j], ring[i]))
        prev = ring
    _cap_loop(bm, prev, dome=0.0, rings=10)


def _taubin(me, iters, lam=0.5, mu=-0.53):
    """Taubin smoothing of mesh `me` in place: relaxes the surface like Laplacian smoothing but does not shrink it."""
    import numpy as np
    n = len(me.vertices)
    v = np.empty(n * 3, np.float32)
    me.vertices.foreach_get('co', v)
    v = v.reshape(-1, 3).astype(np.float64)
    e = np.empty(len(me.edges) * 2, np.int32)
    me.edges.foreach_get('vertices', e)
    e = e.reshape(-1, 2)
    a, b = np.concatenate([e[:, 0], e[:, 1]]), np.concatenate([e[:, 1], e[:, 0]])
    deg = np.maximum(np.bincount(a, minlength=n), 1).astype(np.float64)

    def lap(p):
        out = np.empty_like(p)
        for ax in range(3):
            out[:, ax] = np.bincount(a, weights=p[b, ax], minlength=n)
        return out / deg[:, None] - p
    for _ in range(iters):
        v += lam * lap(v)
        v += mu * lap(v)
    me.vertices.foreach_set('co', v.astype(np.float32).ravel())
    me.update()


def _hair_masks(co, k, cx, cy, zbase, hairline_z=0.33):
    """Hair-zone masks for vertices `co` (Nx3, bust units), evaluated in the scan's own units so they hold at any scale:
    returns (top, side) in 0..1. top = above the hairline, side = sides and back above the nape, with the face and
    both ears (the head is turned a little, so the ears are not symmetric) left alone."""
    import numpy as np
    ss = lambda t: np.clip(t, 0, 1) ** 2 * (3 - 2 * np.clip(t, 0, 1))
    xo, yo, zo = (co[:, 0] + cx) / k, (co[:, 1] + cy) / k, co[:, 2] / k + zbase
    face = ss((0.0 - yo) / 0.2)
    nape = ss((zo + 0.25) / 0.12)
    ear = (ss((np.abs(xo + 0.075) - 0.30) / 0.08) * ss((yo + 0.12) / 0.1) * ss((0.5 - yo) / 0.1) *
           ss((zo + 0.35) / 0.1) * ss((0.62 - zo) / 0.1))
    top = ss((zo - hairline_z) / 0.04) * (1 - ear) * (1 - face * ss((0.5 - zo) / 0.08))  # no bangs, no ear
    return top, (1 - face) * nape * (1 - ear)


def _hair_locks(o, k, cx, cy, zbase, hairline_z, amp=0.035, count=64, volume=0.05, back_only=False):
    """Carve marble hair: locks that sweep down from a crown swirl, with waviness and clumping. Only the hair zone
    moves (see _hair_masks), along the vertex normals."""
    import numpy as np
    me = o.data
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3).astype(np.float64)
    nor = np.empty(n * 3, np.float32)
    me.vertices.foreach_get('normal', nor)
    nor = nor.reshape(-1, 3).astype(np.float64)
    ss = lambda t: np.clip(t, 0, 1) ** 2 * (3 - 2 * np.clip(t, 0, 1))
    top, side = _hair_masks(co, k, cx, cy, zbase, hairline_z)
    mask = np.maximum(top, side)
    if back_only:  # under a cap: carve only the hair behind the ears, leave sideburns and ears as scanned
        mask = side * ss(((co[:, 1] + cy) / k - 0.5) / 0.15)
    x, y, z = co[:, 0], co[:, 1], co[:, 2]
    hi = co[z > co[:, 2].max() - 0.4]
    ccx, ccy = (hi[:, 0].mean(), hi[:, 1].mean()) if len(hi) else (0.0, 0.0)
    th = np.arctan2(y - ccy, x - ccx)
    rho = np.hypot(x - ccx, y - ccy)
    # generic combed hair: straight, even grooves running down from the crown (no waviness, no clumps, no swirl)
    lock = 0.5 + 0.5 * np.cos(count * th)
    d = amp * (lock ** 1.3 - 0.45)
    d += volume                                    # the hair mass stands proud of the skull, which shows a hairline
    d *= ss(rho / 0.3) * mask                     # no pinwheel singularity at the very top; hair zone only
    co += nor * d[:, None]
    me.vertices.foreach_set('co', co.astype(np.float32).ravel())
    me.update()


def build_hat(c, cx, cy, z, rx, ry, crown_h=0.95, tilt=-5.0):
    """Marble top hat sitting on the head: rolled brim, slightly tapered crown, dark stone band.
    (cx, cy, z) is the centre of the brim plane, rx/ry the half width/depth of the head under it."""
    mm = marble_mat('HatMarble')
    band = mat('HatBand', '#2A3135', 0.0, 0.42, 0.3)
    rc = rx * 1.07                     # crown radius across the head; the crown is stretched to the head's depth below
    rb = rc * 1.42                     # brim radius
    stretch = max(1.0, ry / rx * 1.04)

    def part(name, radius1, radius2, depth, zc, material, bev):
        bpy.ops.mesh.primitive_cone_add(vertices=96, radius1=radius1, radius2=radius2, depth=depth, location=(0, 0, zc))
        p = bpy.context.active_object
        p.name = name
        p.scale = (1.0, stretch, 1.0)
        bpy.ops.object.transform_apply(scale=True)
        p.data.materials.append(material)
        for f in p.data.polygons:
            f.use_smooth = True
        bevel(p, bev, 4, harden=False)
        link(p, c)
        return p
    brim = part('HatBrim', rb, rb, 0.08, 0.0, mm, 0.03)
    crown = part('HatCrown', rc * 1.0, rc * 0.93, crown_h, crown_h / 2 + 0.03, mm, 0.07)
    ribbon = part('HatBand', rc * 1.012, rc * 1.012, 0.22, 0.15, band, 0.012)
    pivot = bpy.data.objects.new('HatPivot', None)
    c.objects.link(pivot)
    pivot.location = (cx, cy, z)
    pivot.rotation_euler = (math.radians(tilt), 0, 0)
    for p in (brim, crown, ribbon):
        p.parent = pivot
    bpy.context.view_layer.update()
    # drop the empty by baking the parent transform into the parts
    for p in (brim, crown, ribbon):
        mw = p.matrix_world.copy()
        p.parent = None
        p.matrix_world = mw
    bpy.data.objects.remove(pivot, do_unlink=True)


def build_cap(c, head, cx, cy, zc, skull, tilt=-19.0, yaw=0.0, text='NY'):
    """Baseball cap in dark stone: a six-panel shell that lies on the head, a bill, a button and a flat embroidered 'NY'
    (about 1 mm proud). The shell starts as a superellipsoid fitted around the skull and is then shrink-wrapped onto
    the head (`head`, a mesh object) so the cloth sits flush with a few millimetres of margin; seams, bill, button and
    lettering are placed on that fitted surface.

    The rim is not level: it sits at the hairline in front, at the ear on the sides and low on the neck behind, so
    `tilt` (degrees about x, negative = front up) lifts the front. `yaw` (radians about z) turns the cap so its centre
    line follows the face. (cx, cy, zc) is the centre of the rim, `skull` the vertices of the head."""
    import numpy as np
    from mathutils import Matrix
    from mathutils.bvhtree import BVHTree
    navy = mat('CapNavy', '#1B2A49', 0.0, 0.5, 0.15)
    white = mat('CapLetters', '#F2EFE8', 0.0, 0.5, 0.05)
    th = math.radians(tilt)
    M = Matrix.Translation((cx, cy, zc)) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(th, 4, 'X')
    Mi = M.inverted()
    A = np.array(Mi.to_3x3())
    P = np.array([p[:] for p in skull], dtype=np.float64) @ A.T + np.array(Mi.translation)
    n_se = 3.0                                         # superellipsoid exponent: a squarer dome hugs a skull better
    se = lambda p: math.copysign(abs(p) ** (2.0 / n_se), p)
    above = P[P[:, 2] > 0.12 * P[:, 2].max()]          # the rim region meets the ears and hair; fit the skull above it
    ax, H = np.abs(above[:, 0]).max(), above[:, 2].max()
    ayf, ayb = -above[:, 1].min(), above[:, 1].max()   # front and back of the skull are fitted separately
    ayv = np.where(above[:, 1] < 0, ayf, ayb)
    nrm = (np.abs(above[:, 0] / ax) ** n_se + np.abs(above[:, 1] / ayv) ** n_se + np.abs(above[:, 2] / H) ** n_se) ** (1 / n_se)
    grow = max(1.0, nrm.max()) * 1.01
    ax, ayf, ayb, H = ax * grow, ayf * grow, ayb * grow, H * grow
    ayy = lambda y: ayf if y < 0 else ayb

    def ell(u, v_, w):
        """Point on the fitted superellipsoid for the unit-sphere direction (u, v_, w), in the cap's frame."""
        return Vector((se(u) * ax, se(v_) * ayy(v_), se(max(w, 0.0)) * H))

    # shell: upper half of the superellipsoid, dense enough to follow the head, moved to world space
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=1.0)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -1e-4], context='VERTS')
    for v in bm.verts:
        v.co = M @ ell(v.co.x, v.co.y, v.co.z)
    me = bpy.data.meshes.new('CapDome')
    bm.to_mesh(me)
    bm.free()
    dome = bpy.data.objects.new('CapDome', me)
    c.objects.link(dome)
    dome.data.materials.append(navy)
    for p in me.polygons:
        p.use_smooth = True
    # lay the cloth on the head: wrap, relax, wrap again (the relax step evens out the rim), then bake. The target is a
    # smoothed copy of the head so the cloth bridges the hair grooves instead of following each one.
    target = head.copy()
    target.data = head.data.copy()
    target.name = 'CapTarget'
    c.objects.link(target)
    rm_ = target.modifiers.new('Remesh', 'REMESH')
    rm_.mode = 'VOXEL'
    rm_.voxel_size = 0.03
    with bpy.context.temp_override(object=target, active_object=target):
        bpy.ops.object.modifier_apply(modifier='Remesh')
    _taubin(target.data, 50)
    for name, kind in (('Fit', 'SHRINKWRAP'), ('Relax', 'SMOOTH'), ('Fit2', 'SHRINKWRAP')):
        m_ = dome.modifiers.new(name, kind)
        if kind == 'SHRINKWRAP':
            m_.target = target
            m_.wrap_method = 'NEAREST_SURFACEPOINT'
            m_.offset = 0.02                            # a couple of mm of air between cloth and head
        else:
            m_.factor = 0.5
            m_.iterations = 12
    for name in ('Fit', 'Relax', 'Fit2'):
        with bpy.context.temp_override(object=dome, active_object=dome):
            bpy.ops.object.modifier_apply(modifier=name)
    bpy.data.objects.remove(target, do_unlink=True)
    so = dome.modifiers.new('Thick', 'SOLIDIFY')
    so.thickness = 0.03                                 # about 3 mm of cloth
    so.offset = 1
    bevel(dome, 0.01, 2, harden=False)
    bpy.context.view_layer.update()
    bvh = BVHTree.FromObject(dome, bpy.context.evaluated_depsgraph_get())

    def on_cloth(world_pt, lift=0.0):
        loc, nor, _i, _d = bvh.find_nearest(world_pt)
        return loc + nor * lift, nor

    # six panels: raised seams from the button down to the rim (the front two panels meet at the centre front)
    seams = []
    for i in range(6):
        phi = math.radians(90 + 60 * i)
        cu = bpy.data.curves.new(f'CapSeam{i}', 'CURVE')
        cu.dimensions = '3D'
        cu.bevel_depth = 0.006
        cu.bevel_resolution = 2
        sp = cu.splines.new('POLY')
        n = 40
        sp.points.add(n - 1)
        for j in range(n):
            t = math.radians(90 * j / (n - 1))              # 0 at the rim, 90 degrees at the button
            q, _n = on_cloth(M @ ell(math.cos(phi) * math.cos(t) * 1.15, math.sin(phi) * math.cos(t) * 1.15, math.sin(t) * 1.15), 0.002)
            sp.points[j].co = (q.x, q.y, q.z, 1)
        ob = bpy.data.objects.new(f'CapSeam{i}', cu)
        c.objects.link(ob)
        cu.materials.append(navy)
        seams.append(ob)
    # bill: rooted on the fitted rim along (almost) the whole front, nearly in the rim plane, curved around the face
    bm = bmesh.new()
    nu, nv = 36, 10
    grid = [[None] * (nv + 1) for _ in range(nu + 1)]
    reach = ayf * 0.62
    R3 = M.to_3x3()
    for i in range(nu + 1):
        u = -1 + 2 * i / nu
        phi = u * math.radians(64)                        # only the front of the rim: the bill ends in a point at the temples
        r_loc = Vector((ax * se(math.sin(phi)), -ayf * se(math.cos(phi)), 0.0))
        nx, ny = math.sin(phi) / ax, -math.cos(phi) / ayf
        nl = math.hypot(nx, ny)
        nx, ny = nx / nl, ny / nl
        root_w = M @ r_loc
        fitted, _n = on_cloth(root_w, 0.0)
        delta = fitted - root_w                       # the shell moved when it was laid on the head: follow it
        for j in range(nv + 1):
            v = j / nv
            lift = (1 - u * u) ** 0.9                       # width runs smoothly out to nothing where the bill meets the shell
            x = r_loc.x + nx * v * reach * lift * 0.3       # almost no sideways flare
            y = r_loc.y + ny * v * reach * lift
            z = -0.01 - 0.10 * reach * v ** 1.5 - 0.16 * reach * u * u * v
            grid[i][j] = bm.verts.new(M @ Vector((x, y, z)) + delta)
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
    up = R3 @ Vector((0, 0, 0.034))
    stitch_rows = [[Vector(grid[i][j].co) + up for i in range(nu + 1)] for j in (3, 5, 7, 9)]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me2 = bpy.data.meshes.new('CapBill')
    bm.to_mesh(me2)
    bm.free()
    bill = bpy.data.objects.new('CapBill', me2)
    c.objects.link(bill)
    bill.data.materials.append(navy)
    for p in me2.polygons:
        p.use_smooth = True
    sb = bill.modifiers.new('Thick', 'SOLIDIFY')
    sb.thickness = 0.06
    sb.offset = 0
    bevel(bill, 0.015, 2, harden=False)
    for r_i, row in enumerate(stitch_rows):
        cu = bpy.data.curves.new(f'CapStitch{r_i}', 'CURVE')
        cu.dimensions = '3D'
        cu.bevel_depth = 0.0035
        sp = cu.splines.new('POLY')
        sp.points.add(len(row) - 1)
        for q, pt in zip(sp.points, row):
            q.co = (pt.x, pt.y, pt.z, 1)
        ob = bpy.data.objects.new(f'CapStitch{r_i}', cu)
        c.objects.link(ob)
        cu.materials.append(navy)
        seams.append(ob)
    # button, sitting on the cloth at the crown
    top, tn = on_cloth(M @ Vector((0, 0, H * 1.2)), 0.012)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.07, location=top)
    btn = bpy.context.active_object
    btn.name = 'CapButton'
    btn.scale = (1, 1, 0.65)
    btn.data.materials.append(navy)
    for p in btn.data.polygons:
        p.use_smooth = True
    link(btn, c)
    # embroidery: flat filled letters on the front panel, snapped onto the cloth and lifted about 1 mm
    zf = 0.5 * H
    yf = -ayf * (1 - (zf / H) ** n_se) ** (1 / n_se)
    alpha = math.atan2((abs(yf) / ayf) ** (n_se - 1) / ayf, (zf / H) ** (n_se - 1) / H)
    cu = bpy.data.curves.new('CapText', 'FONT')
    cu.body = text
    cu.size = ax * 0.5
    cu.extrude = 0.0
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    cu.space_character = 0.92
    cu.materials.append(white)
    letters = bpy.data.objects.new('CapLetters', cu)
    c.objects.link(letters)
    letters.matrix_world = M @ Matrix.Translation((0, yf - 0.06, zf)) @ Matrix.Rotation(alpha, 4, 'X')
    bpy.context.view_layer.objects.active = letters
    bpy.ops.object.select_all(action='DESELECT')
    letters.select_set(True)
    bpy.ops.object.convert(target='MESH')
    letters = bpy.context.active_object
    letters.name = 'CapLetters'
    letters.modifiers.new('Tri', 'TRIANGULATE')
    sub = letters.modifiers.new('Fine', 'SUBSURF')
    sub.subdivision_type = 'SIMPLE'
    sub.levels = 3
    sub.render_levels = 3
    sw = letters.modifiers.new('Snap', 'SHRINKWRAP')
    sw.target = dome
    sw.wrap_method = 'NEAREST_SURFACEPOINT'
    sw.offset = 0.0
    so2 = letters.modifiers.new('Stitch', 'SOLIDIFY')
    so2.thickness = 0.011          # about 1 mm at this scale
    so2.offset = 1


def _layer(c, name, outline, bvh, material, offset, thickness, bevel_w=0.008):
    """A thin raised cloth panel on the front of the body: a flat polygon (x, z pairs) is cut into fine triangles and
    each vertex is cast straight back onto the body surface (`bvh`), lifted by `offset`, then given thickness."""
    bm = bmesh.new()
    vs = [bm.verts.new((x, -2.0, z)) for x, z in outline]
    bm.faces.new(vs)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=9, use_grid_fill=True)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    for v in bm.verts:
        hit = bvh.ray_cast((v.co.x, -3.0, v.co.z), (0, 1, 0))
        if hit[0] is None:
            hit = bvh.find_nearest(v.co)
        v.co = hit[0] + hit[1] * offset
    bm.normal_update()
    # make sure the cloth grows outward (toward the viewer, -y)
    if sum(f.normal.y * f.calc_area() for f in bm.faces) > 0:
        for f in bm.faces:
            f.normal_flip()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    c.objects.link(ob)
    ob.data.materials.append(material)
    for p in me.polygons:
        p.use_smooth = True
    so = ob.modifiers.new('Cloth', 'SOLIDIFY')
    so.thickness = thickness
    so.offset = 1
    if bevel_w:
        bevel(ob, bevel_w, 2, harden=False)
    return ob


def build_suit(c, body, k, zbase, neck_z):
    """Dress the bust in a suit jacket, white shirt and tie. The torso shape stays the carved shoulder block; the
    details are raised cloth layers on it: shirt front, collar, notch lapels, tie with knot, buttons."""
    import numpy as np
    from mathutils.bvhtree import BVHTree
    shirt_m = marble_mat('ShirtMarble')
    jacket_m = marble_mat('JacketMarble')
    tie_m = mat('TieNavy', '#1B2A49', 0.0, 0.45, 0.2)
    button_m = mat('SuitButton', '#2A3135', 0.0, 0.4, 0.3)
    zn = (neck_z - zbase) * k                                  # where the neck meets the shoulders
    co = np.empty(len(body.data.vertices) * 3, np.float32)
    body.data.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    def section(dz):
        sl = co[(np.abs(co[:, 2] - (zn + dz)) < 0.025) & (co[:, 1] > -0.85)]   # the beard and chin are further out
        return ((sl[:, 0].min() + sl[:, 0].max()) / 2, (sl[:, 1].min() + sl[:, 1].max()) / 2,
                (sl[:, 0].max() - sl[:, 0].min()) / 2, (sl[:, 1].max() - sl[:, 1].min()) / 2)
    bx, by, brx, bry = section(0.05)                           # neck at the shoulders
    nx, ny, rx, ry = section(0.22)                             # neck under the chin
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    tip = zn * 0.30                                            # where the lapels meet the closed jacket
    mir = lambda pts: [(-x, z) for x, z in pts][::-1]
    X = lambda pts: [(nx + x, z) for x, z in pts]
    # shirt: the V between the lapels, from the collar down to the first button
    shirt = [(-0.30, zn + 0.04), (0.30, zn + 0.04), (0.05, tip + 0.04), (-0.05, tip + 0.04)]
    _layer(c, 'SuitShirt', X(shirt), bvh, shirt_m, 0.012, 0.02)
    # notch lapels, one per side, standing proud of the shirt and the jacket
    lap = [(0.30, zn + 0.04), (0.60, zn - 0.08), (0.74, zn - 0.22), (0.63, zn - 0.27), (0.60, zn - 0.42),
           (0.20, tip - 0.06), (0.05, tip)]
    _layer(c, 'SuitLapelR', X(lap), bvh, jacket_m, 0.02, 0.045)
    _layer(c, 'SuitLapelL', X(mir(lap)), bvh, jacket_m, 0.02, 0.045)
    # the jacket's front edge below the lapels
    edge = [(-0.012, 0.02), (0.012, 0.02), (0.012, tip), (-0.012, tip)]
    _layer(c, 'SuitFront', X(edge), bvh, jacket_m, 0.02, 0.02, bevel_w=0)
    # tie: narrow at the knot, widening to a pointed end
    blade = [(-0.06, zn + 0.02), (0.06, zn + 0.02), (0.07, zn - 0.14), (0.145, tip + 0.30), (0.0, tip - 0.10),
             (-0.145, tip + 0.30), (-0.07, zn - 0.14)]
    _layer(c, 'SuitTie', X(blade), bvh, tie_m, 0.045, 0.04)

    def on_chest(x, z, lift):
        hit = bvh.ray_cast((x, -3.0, z), (0, 1, 0))
        return (hit[0] + hit[1] * lift) if hit[0] is not None else Vector((x, -1.2, z))
    # shirt collar: a band around the neck, wider at the shoulders, with the tie knot in front
    bpy.ops.mesh.primitive_cone_add(vertices=72, radius1=rx + 0.13, radius2=rx + 0.07, depth=0.22, end_fill_type='NOTHING',
                                    location=(nx, ny, zn + 0.14))
    col = bpy.context.active_object
    col.name = 'SuitCollar'
    col.scale = (1.0, ry / rx, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    col.data.materials.append(shirt_m)
    for p in col.data.polygons:
        p.use_smooth = True
    sc = col.modifiers.new('Cloth', 'SOLIDIFY')
    sc.thickness = 0.05
    sc.offset = 0
    bevel(col, 0.012, 2, harden=False)
    link(col, c)
    kz = zn + 0.0
    kp = on_chest(nx, kz, 0.05)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=kp)
    knot = bpy.context.active_object
    knot.name = 'SuitKnot'
    knot.scale = (0.115, 0.085, 0.10)
    knot.data.materials.append(tie_m)
    for p in knot.data.polygons:
        p.use_smooth = True
    link(knot, c)
    # two buttons below the lapels
    for bz, nm in ((tip - 0.13, 'SuitButton1'), (tip - 0.34, 'SuitButton2')):
        bp = on_chest(nx, bz, 0.03)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.05, location=bp)
        b_ = bpy.context.active_object
        b_.name = nm
        b_.scale = (1, 0.6, 1)
        b_.data.materials.append(button_m)
        for p in b_.data.polygons:
            p.use_smooth = True
        link(b_, c)


def build_bust_scan(ply, height=3.6, dome=0.75, crown_z=0.55, neck_z=-0.62, half_w=1.15, half_d=0.65, drop_a=0.55, drop_b=0.4,
                    voxel=0.008, faces=140000, hairline_z=0.33, hair_voxel=0.07, hair_smooth=1.0, hair_relief=0.035, hat=False, hat_z=0.73, cap=False, cap_z=0.36, suit=False):
    """Bust from the photogrammetry head scan (oriented: face toward -y, z up, see PROCESS.md).
    Keeps head and neck, replaces the torn shirt with a rounded shoulder block, caps the unphotographed crown with
    a dome, remeshes and smooths the hair, then adds marble and the plinth. The result is named 'Bust' like the TRELLIS one so the exporters work unchanged."""
    c = coll('Bust')
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.wm.ply_import(filepath=ply)
    o = bpy.context.selected_objects[0]
    link(o, c)
    o.name = 'Bust'
    zbase = neck_z - drop_a - drop_b
    bm = bmesh.new()
    bm.from_mesh(o.data)
    # keep head and neck: cut at the neck
    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, neck_z), plane_no=(0, 0, 1), clear_inner=True)
    bm.verts.ensure_lookup_table()
    # drop loose fragments (arms, chair), keep the largest piece
    seen, comps = set(), []
    for v in bm.verts:
        if v in seen:
            continue
        stack, comp = [v], []
        seen.add(v)
        while stack:
            x = stack.pop()
            comp.append(x)
            for e in x.link_edges:
                w = e.other_vert(x)
                if w not in seen:
                    seen.add(w)
                    stack.append(w)
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    bmesh.ops.delete(bm, geom=[v for comp in comps[1:] for v in comp], context='VERTS')
    # the crown was never photographed (the orbit was at eye level), so the scan ends in a ragged crater:
    # cut below it at crown_z and close the clean cross-section with a dome
    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, crown_z), plane_no=(0, 0, 1), clear_outer=True)
    loops = [lp for lp in _boundary_loops(bm) if len(lp) >= 12]
    neck = min(loops, key=lambda lp: sum(v.co.z for v in lp) / len(lp))
    for loop in loops:
        if loop is neck:
            _loft_base(bm, loop, half_w, half_d, drop_a, drop_b)
        else:
            _cap_loop(bm, loop, dome=dome, smooth_iters=40)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(o.data)
    bm.free()
    # scale to `height`, stand on z = 0, centre in x/y (measured on the vertices: o.bound_box is stale after data.transform)
    zs = [v.co.z for v in o.data.vertices]
    k = height / (max(zs) - min(zs))
    o.data.transform(__import__('mathutils').Matrix.Scale(k, 4))
    xs = [v.co.x for v in o.data.vertices]
    ys = [v.co.y for v in o.data.vertices]
    zs = [v.co.z for v in o.data.vertices]
    cx = (max(xs) + min(xs)) / 2
    cy = (max(ys) + min(ys)) / 2
    o.data.transform(__import__('mathutils').Matrix.Translation((-cx, -cy, -min(zs))))
    # unify: voxel remesh welds the cap and closes small holes, a light smooth takes off scanner noise
    r = o.modifiers.new('Remesh', 'REMESH')
    r.mode = 'VOXEL'
    r.voxel_size = voxel
    with bpy.context.temp_override(object=o, active_object=o):
        bpy.ops.object.modifier_apply(modifier='Remesh')
    # hair: top of the head (above the hairline) and the back of the head are pulled onto a calm, smoothed copy;
    # the face (front, below the hairline) is left alone so the likeness survives
    import numpy as np
    me = o.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3).astype(np.float64)
    top, side = _hair_masks(co, k, cx, cy, zbase, hairline_z)
    ssn = lambda t: np.clip(t, 0, 1) ** 2 * (3 - 2 * np.clip(t, 0, 1))
    # the top eases from the lightly smoothed hair into the fully smoothed dome
    wtop = top * (hair_smooth + (1 - hair_smooth) * ssn((co[:, 2] / height - 0.84) / 0.1))
    wh = np.maximum(wtop, hair_smooth * side)
    wbody = ssn((neck_z - (co[:, 2] / k + zbase)) / 0.12)  # shoulders: iron out the loft's radial pleats
    vg = o.vertex_groups.new(name='Hair')
    vb = o.vertex_groups.new(name='Body')
    for i in np.nonzero(wh > 0)[0]:
        vg.add([int(i)], float(wh[i]), 'REPLACE')
    for i in np.nonzero(wbody > 0)[0]:
        vb.add([int(i)], float(wbody[i]), 'REPLACE')

    def proxy_of(name, vox, iters):
        p = o.copy()
        p.data = o.data.copy()
        p.name = name
        c.objects.link(p)
        rm = p.modifiers.new('Remesh', 'REMESH')
        rm.mode = 'VOXEL'
        rm.voxel_size = vox
        with bpy.context.temp_override(object=p, active_object=p):
            bpy.ops.object.modifier_apply(modifier='Remesh')
        _taubin(p.data, iters)
        return p
    hair_proxy = proxy_of('HairProxy', hair_voxel, 120)
    body_proxy = proxy_of('BodyProxy', 0.08, 220)
    hs = o.modifiers.new('HairSmooth', 'SHRINKWRAP')
    hs.target = hair_proxy
    hs.wrap_method = 'NEAREST_SURFACEPOINT'
    hs.vertex_group = 'Hair'
    bs = o.modifiers.new('BodySmooth', 'SHRINKWRAP')
    bs.target = body_proxy
    bs.wrap_method = 'NEAREST_SURFACEPOINT'
    bs.vertex_group = 'Body'
    sh = o.modifiers.new('ShoulderSmooth', 'SMOOTH')
    sh.factor = 0.8
    sh.iterations = 60
    sh.vertex_group = 'Body'
    # a fine remesh welds the shrinkwrapped regions (no overlapping faces), then a light smooth
    cr = o.modifiers.new('Clean', 'REMESH')
    cr.mode = 'VOXEL'
    cr.voxel_size = voxel
    cs = o.modifiers.new('Smooth', 'CORRECTIVE_SMOOTH')
    cs.iterations = 2
    cs.use_only_smooth = True
    d = o.modifiers.new('Decimate', 'DECIMATE')
    bpy.context.view_layer.update()
    n = len(o.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.polygons)
    d.ratio = min(1.0, faces / max(n, 1))
    for mname in ('HairSmooth', 'BodySmooth', 'ShoulderSmooth', 'Clean'):
        with bpy.context.temp_override(object=o, active_object=o):
            bpy.ops.object.modifier_apply(modifier=mname)
    _hair_locks(o, k, cx, cy, zbase, hairline_z, amp=hair_relief, volume=0.03 if cap else 0.05, back_only=cap)  # carved hair on the welded, evenly spaced mesh
    for mname in ('Smooth', 'Decimate'):
        with bpy.context.temp_override(object=o, active_object=o):
            bpy.ops.object.modifier_apply(modifier=mname)
    for p_ in (hair_proxy, body_proxy):
        bpy.data.objects.remove(p_, do_unlink=True)
    for p in o.data.polygons:
        p.use_smooth = True
    o.data.materials.clear()
    o.data.materials.append(marble_mat())
    bust_plinth(o, c, wf=1.0, df=1.3)
    if hat:
        zb = hat_z * height
        near = [v.co for v in o.data.vertices if abs(v.co.z - zb) < 0.1]
        x0, x1 = min(v.x for v in near), max(v.x for v in near)
        y0, y1 = min(v.y for v in near), max(v.y for v in near)
        build_hat(c, (x0 + x1) / 2, (y0 + y1) / 2 + 0.05, zb, (x1 - x0) / 2, (y1 - y0) / 2)
    if suit:
        build_suit(c, o, k, zbase, neck_z)
    if cap:
        zc = (cap_z - zbase) * k
        near = [v.co for v in o.data.vertices if abs(v.co.z - zc) < 0.12]
        sx = (min(v.x for v in near) + max(v.x for v in near)) / 2
        sy = (min(v.y for v in near) + max(v.y for v in near)) / 2
        # the head is turned a little: aim the cap along the line from the middle between the ears to the nose tip
        zof = lambda v: v.co.z / k + zbase
        nose = min((v for v in o.data.vertices if -0.2 < zof(v) < 0.3), key=lambda v: v.co.y).co
        ear_h = [v.co for v in o.data.vertices if 0.15 < zof(v) < 0.45]
        le = min(ear_h, key=lambda p: p.x)
        re_ = max(ear_h, key=lambda p: p.x)
        mid = Vector(((le.x + re_.x) / 2, (le.y + re_.y) / 2, 0.0))
        d = Vector((nose.x - mid.x, nose.y - mid.y, 0.0)).normalized()
        yaw = math.atan2(d.x, -d.y)
        along = (Vector((sx, sy, 0.0)) - mid).dot(d)
        centre = mid + d * along                      # on the nose line, at the middle of the head front to back
        skull = [v.co.copy() for v in o.data.vertices if v.co.z > zc - 0.6]
        build_cap(c, o, centre.x, centre.y, zc, skull, yaw=yaw)
    return {'faces': len(o.data.polygons), 'scale': k, 'size': tuple(round(x, 3) for x in o.dimensions)}


def export_bust_glb():
    show_only('Bust')
    return _export(list(bpy.data.collections['Bust'].objects), 'bust.glb')


SHOTS['bust'] = ('Bust', (3.5, -11.0, 3.6), (0, 0, 1.3), 50, (1400, 1600))
