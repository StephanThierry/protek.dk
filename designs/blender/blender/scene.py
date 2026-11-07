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
    # plinth: dark stone block with a chamfer, brass plaque with the name
    bb = [Vector(v) for v in o.bound_box]
    w = (max(v.x for v in bb) - min(v.x for v in bb)) * 0.82
    dpt = (max(v.y for v in bb) - min(v.y for v in bb)) * 0.95
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
    return {'faces': len(o.data.polygons), 'size': tuple(round(x, 3) for x in o.dimensions)}


def export_bust_glb():
    show_only('Bust')
    return _export(list(bpy.data.collections['Bust'].objects), 'bust.glb')


SHOTS['bust'] = ('Bust', (3.5, -11.0, 3.6), (0, 0, 1.3), 50, (1400, 1600))
