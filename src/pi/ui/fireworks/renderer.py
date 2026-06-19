import numpy as np
import moderngl
import pygame
import math


class TextCacheEntry:
    def __init__(self, texture, width, height):
        self.texture = texture
        self.width = width
        self.height = height


class Renderer:
    def __init__(self, ctx):
        self.ctx = ctx

        # Enable blending for additive particles and UI transparency
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (
            moderngl.SRC_ALPHA,
            moderngl.ONE,
        )  # Default: Additive blending

        self.resolution = (1920.0, 1080.0)
        self.target_resolution = (1920, 1080)

        # Cache for rendered text textures
        self.text_cache = {}

        # Shaders
        self._init_shaders()

        # Buffer and VAO setup
        self._init_buffers()

        # Textures
        self.glow_texture = self._create_glow_texture(64)

        # Offscreen rendering target
        self.fb_texture = self.ctx.texture(self.target_resolution, 4)
        self.fb_texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.fb = self.ctx.framebuffer(color_attachments=[self.fb_texture])

    def set_blend_mode(self, mode="additive"):
        if mode == "additive":
            self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)
        elif mode == "alpha":
            self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
        else:
            self.ctx.blend_func = (moderngl.ONE, moderngl.ZERO)

    def _init_shaders(self):
        # 1. Instanced Particle Shader
        particle_vert = """#version 330
        precision highp float;
        in vec2 in_vert;
        in vec2 in_texcoord;
        in vec2 in_pos;
        in float in_size;
        in vec4 in_color;
        
        out vec2 v_texcoord;
        out vec4 v_color;
        
        uniform vec2 u_resolution;
        
        void main() {
            vec2 screen_pos = in_pos + in_vert * in_size;
            vec2 ndc = (screen_pos / u_resolution) * 2.0 - 1.0;
            ndc.y = -ndc.y; // Flip Y to match pygame screen coords
            gl_Position = vec4(ndc, 0.0, 1.0);
            v_texcoord = in_texcoord;
            v_color = in_color;
        }"""

        particle_frag = """#version 330
        precision highp float;
        in vec2 v_texcoord;
        in vec4 v_color;
        
        out vec4 fragColor;
        
        uniform sampler2D u_glow_texture;
        
        void main() {
            float alpha = texture(u_glow_texture, v_texcoord).r;
            fragColor = vec4(v_color.rgb, v_color.a * alpha);
        }"""
        self.particle_program = self.ctx.program(
            vertex_shader=particle_vert, fragment_shader=particle_frag
        )
        self.particle_program["u_resolution"].value = self.resolution

        # 2. Flat Shapes Shader (FIXED: Removed optimized-out texcoords)
        flat_vert = """#version 330
        precision highp float;
        in vec2 in_vert;
        uniform vec2 u_resolution;
        uniform vec2 u_pos;
        uniform vec2 u_size;
        void main() {
            vec2 screen_pos = u_pos + in_vert * u_size;
            vec2 ndc = (screen_pos / u_resolution) * 2.0 - 1.0;
            ndc.y = -ndc.y;
            gl_Position = vec4(ndc, 0.0, 1.0);
        }"""

        flat_frag = """#version 330
        precision highp float;
        uniform vec4 u_color;
        out vec4 fragColor;
        void main() {
            fragColor = u_color;
        }"""
        self.flat_program = self.ctx.program(
            vertex_shader=flat_vert, fragment_shader=flat_frag
        )
        self.flat_program["u_resolution"].value = self.resolution

        # 3. Line Shader
        line_vert = """#version 330
        precision highp float;
        in vec2 in_vert;
        uniform vec2 u_resolution;
        void main() {
            vec2 ndc = (in_vert / u_resolution) * 2.0 - 1.0;
            ndc.y = -ndc.y;
            gl_Position = vec4(ndc, 0.0, 1.0);
        }"""

        line_frag = """#version 330
        precision highp float;
        uniform vec4 u_color;
        out vec4 fragColor;
        void main() {
            fragColor = u_color;
        }"""
        self.line_program = self.ctx.program(
            vertex_shader=line_vert, fragment_shader=line_frag
        )
        self.line_program["u_resolution"].value = self.resolution

        # 4. Ellipse Shader
        ellipse_vert = """#version 330
        precision highp float;
        in vec2 in_vert;
        in vec2 in_texcoord;
        out vec2 v_texcoord;
        uniform vec2 u_resolution;
        uniform vec2 u_pos;
        uniform vec2 u_size;
        void main() {
            vec2 screen_pos = u_pos + in_vert * u_size;
            vec2 ndc = (screen_pos / u_resolution) * 2.0 - 1.0;
            ndc.y = -ndc.y;
            gl_Position = vec4(ndc, 0.0, 1.0);
            v_texcoord = in_texcoord;
        }"""

        ellipse_frag = """#version 330
        precision highp float;
        in vec2 v_texcoord;
        uniform vec4 u_color;
        out vec4 fragColor;
        void main() {
            float dx = v_texcoord.x - 0.5;
            float dy = v_texcoord.y - 0.5;
            float dist = dx*dx + dy*dy;
            float alpha = smoothstep(0.25, 0.24, dist);
            if (alpha <= 0.0) discard;
            fragColor = vec4(u_color.rgb, u_color.a * alpha);
        }"""
        self.ellipse_program = self.ctx.program(
            vertex_shader=ellipse_vert, fragment_shader=ellipse_frag
        )
        self.ellipse_program["u_resolution"].value = self.resolution

        # 5. Textured Quad Shader
        texture_vert = """#version 330
        precision highp float;
        in vec2 in_vert;
        in vec2 in_texcoord;
        out vec2 v_texcoord;
        uniform vec2 u_resolution;
        uniform vec2 u_pos;
        uniform vec2 u_size;
        void main() {
            vec2 screen_pos = u_pos + in_vert * u_size;
            vec2 ndc = (screen_pos / u_resolution) * 2.0 - 1.0;
            ndc.y = -ndc.y;
            gl_Position = vec4(ndc, 0.0, 1.0);
            v_texcoord = in_texcoord;
        }"""

        texture_frag = """#version 330
        precision highp float;
        in vec2 v_texcoord;
        uniform sampler2D u_texture;
        uniform vec4 u_color;
        out vec4 fragColor;
        void main() {
            vec4 tex_color = texture(u_texture, v_texcoord);
            fragColor = tex_color * u_color;
        }"""
        self.texture_program = self.ctx.program(
            vertex_shader=texture_vert, fragment_shader=texture_frag
        )
        self.texture_program["u_resolution"].value = self.resolution

        # 6. Fullscreen Blit Shader
        screen_vert = """#version 330
        precision highp float;
        in vec2 in_vert;
        in vec2 in_texcoord;
        out vec2 v_texcoord;
        void main() {
            gl_Position = vec4(in_vert, 0.0, 1.0);
            v_texcoord = in_texcoord;
        }"""

        screen_frag = """#version 330
        precision highp float;
        in vec2 v_texcoord;
        uniform sampler2D u_texture;
        out vec4 fragColor;
        void main() {
            fragColor = texture(u_texture, v_texcoord);
        }"""
        self.screen_program = self.ctx.program(
            vertex_shader=screen_vert, fragment_shader=screen_frag
        )

    def _init_buffers(self):
        # Centered unit quad for particles (from -0.5 to 0.5)
        centered_quad = np.array(
            [
                -0.5,
                -0.5,
                0.0,
                0.0,
                0.5,
                -0.5,
                1.0,
                0.0,
                -0.5,
                0.5,
                0.0,
                1.0,
                0.5,
                0.5,
                1.0,
                1.0,
            ],
            dtype="f4",
        )
        self.centered_quad_buffer = self.ctx.buffer(centered_quad.tobytes())

        # Top-left aligned unit quad for UI shapes / Text / Ellipse (from 0.0 to 1.0)
        unit_quad = np.array(
            [
                0.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                1.0,
                0.0,
                0.0,
                1.0,
                0.0,
                1.0,
                1.0,
                1.0,
                1.0,
                1.0,
            ],
            dtype="f4",
        )
        self.unit_quad_buffer = self.ctx.buffer(unit_quad.tobytes())

        # VBO for particle instance data: x, y, size, r, g, b, a (7 floats per instance)
        # Pre-allocate for 20000 particles (560 KB)
        self.particle_vbo = self.ctx.buffer(reserve=20000 * 7 * 4)

        # Particle VAO (combines centered quad vertices and instanced particles data)
        self.particle_vao = self.ctx.vertex_array(
            self.particle_program,
            [
                (self.centered_quad_buffer, "2f 2f", "in_vert", "in_texcoord"),
                (self.particle_vbo, "2f 1f 4f/i", "in_pos", "in_size", "in_color"),
            ],
        )

        # VAOs for shapes

        # FIXED: Tell ModernGL to read 2 floats for in_vert, and skip the next 8 bytes (the unused texcoords)
        self.flat_vao = self.ctx.vertex_array(
            self.flat_program,
            [(self.unit_quad_buffer, "2f 8x", "in_vert")],
        )

        self.ellipse_vao = self.ctx.vertex_array(
            self.ellipse_program,
            [(self.unit_quad_buffer, "2f 2f", "in_vert", "in_texcoord")],
        )

        self.texture_vao = self.ctx.vertex_array(
            self.texture_program,
            [(self.unit_quad_buffer, "2f 2f", "in_vert", "in_texcoord")],
        )

        # Line VBO/VAO setup (2 vertices of 2 floats each)
        self.line_vbo = self.ctx.buffer(reserve=2 * 2 * 4)
        self.line_vao = self.ctx.vertex_array(
            self.line_program, [(self.line_vbo, "2f", "in_vert")]
        )

        # Fullscreen quad for final blit
        screen_quad = np.array(
            [
                -1.0,
                -1.0,
                0.0,
                0.0,
                1.0,
                -1.0,
                1.0,
                0.0,
                -1.0,
                1.0,
                0.0,
                1.0,
                1.0,
                1.0,
                1.0,
                1.0,
            ],
            dtype="f4",
        )
        self.screen_quad_buffer = self.ctx.buffer(screen_quad.tobytes())
        self.screen_vao = self.ctx.vertex_array(
            self.screen_program,
            [(self.screen_quad_buffer, "2f 2f", "in_vert", "in_texcoord")],
        )

    def _create_glow_texture(self, size=64):
        data = bytearray(size * size)
        center = (size - 1) / 2.0
        max_dist = size / 2.0
        for y in range(size):
            for x in range(size):
                dx = x - center
                dy = y - center
                dist = math.sqrt(dx * dx + dy * dy)
                if dist >= max_dist:
                    val = 0
                else:
                    t = dist / max_dist
                    # Soft quadratic falloff for beautiful glow
                    val = int(255 * (1.0 - t) * (1.0 - t))
                data[y * size + x] = val

        tex = self.ctx.texture((size, size), 1, data)
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        return tex

    def set_resolution(self, width, height):
        pass

    def start_frame(self):
        self.fb.use()
        self.ctx.viewport = (0, 0, 1920, 1080)
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)

    def end_frame(self, screen_w, screen_h):
        self.ctx.screen.use()
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)

        target_aspect = 1920.0 / 1080.0
        screen_aspect = float(screen_w) / float(screen_h)

        if screen_aspect > target_aspect:
            h = screen_h
            w = h * target_aspect
            x = (screen_w - w) / 2.0
            y = 0.0
        else:
            w = screen_w
            h = w / target_aspect
            x = 0.0
            y = (screen_h - h) / 2.0

        # Handle High-DPI screen scaling (ModernGL physical framebuffer size vs logical window size)
        phys_w, phys_h = self.ctx.screen.size
        raw_ratio_x = float(phys_w) / float(screen_w) if screen_w > 0 else 1.0
        raw_ratio_y = float(phys_h) / float(screen_h) if screen_h > 0 else 1.0

        # Determine actual DPI scaling ratio by rounding to nearest 0.5 to prevent cut-off issues
        # when the window manager constrains the window height (e.g. taskbars/panels)
        ratio_x = round(raw_ratio_x * 2.0) / 2.0
        ratio_y = round(raw_ratio_y * 2.0) / 2.0

        self.ctx.viewport = (
            int(x * ratio_x),
            int(y * ratio_y),
            int(w * ratio_x),
            int(h * ratio_y),
        )
        self.fb_texture.use(0)
        self.screen_program["u_texture"].value = 0

        self.ctx.disable(moderngl.BLEND)
        self.screen_vao.render(moderngl.TRIANGLE_STRIP)
        self.ctx.enable(moderngl.BLEND)

    def clear(self, color=(0.0, 0.0, 0.0, 1.0)):
        # Color input is either indexed color (we should support RGB tuple or unpack)
        r, g, b, *a = color
        alpha = a[0] if a else 1.0
        self.ctx.clear(r, g, b, alpha)

    def draw_particles(self, particles_data):
        if particles_data is None or len(particles_data) == 0:
            return

        num_particles = len(particles_data)
        needed_size = num_particles * 7 * 4

        # Dynamic resize of buffer if we exceed pre-allocated space
        if needed_size > self.particle_vbo.size:
            self.particle_vbo = self.ctx.buffer(reserve=needed_size)
            self.particle_vao = self.ctx.vertex_array(
                self.particle_program,
                [
                    (self.centered_quad_buffer, "2f 2f", "in_vert", "in_texcoord"),
                    (self.particle_vbo, "2f 1f 4f/i", "in_pos", "in_size", "in_color"),
                ],
            )

        # Write data to VBO
        if isinstance(particles_data, np.ndarray):
            data_bytes = particles_data.tobytes()
        else:
            data_bytes = np.array(particles_data, dtype="f4").tobytes()
        self.particle_vbo.write(data_bytes)

        # Use glow texture in unit 0
        self.glow_texture.use(0)
        self.particle_program["u_glow_texture"].value = 0

        # Render instanced particles
        self.particle_vao.render(moderngl.TRIANGLE_STRIP, instances=num_particles)

    def draw_rect(self, x, y, w, h, color, fill=True):
        r, g, b, *a = color
        alpha = a[0] if a else 1.0

        if fill:
            self.flat_program["u_pos"].value = (float(x), float(y))
            self.flat_program["u_size"].value = (float(w), float(h))
            self.flat_program["u_color"].value = (r, g, b, alpha)
            self.flat_vao.render(moderngl.TRIANGLE_STRIP)
        else:
            self.draw_line(x, y, x + w, y, color)
            self.draw_line(x + w, y, x + w, y + h, color)
            self.draw_line(x + w, y + h, x, y + h, color)
            self.draw_line(x, y + h, x, y, color)

    def draw_ellipse(self, x, y, w, h, color):
        r, g, b, *a = color
        alpha = a[0] if a else 1.0

        self.ellipse_program["u_pos"].value = (float(x), float(y))
        self.ellipse_program["u_size"].value = (float(w), float(h))
        self.ellipse_program["u_color"].value = (r, g, b, alpha)
        self.ellipse_vao.render(moderngl.TRIANGLE_STRIP)

    def draw_circle(self, cx, cy, r, color, fill=True):
        # Circle is just a special case of ellipse/rect centered at cx, cy with size 2r
        x = cx - r
        y = cy - r
        w = 2.0 * r
        h = 2.0 * r
        if fill:
            self.draw_ellipse(x, y, w, h, color)
        else:
            # Simple circle outline can be approximated by drawing a few line segments
            # or just drawing an ellipse with a custom outline fragment shader.
            # For the fireworks engine, self.draw_circle(..., fill=False) is only used
            # for the UI circle outline or rings. Let's do a simple 16-point circle approximation.
            num_segments = 16
            points = []
            for i in range(num_segments + 1):
                theta = i * (2.0 * math.pi / num_segments)
                points.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
            for i in range(num_segments):
                self.draw_line(
                    points[i][0],
                    points[i][1],
                    points[i + 1][0],
                    points[i + 1][1],
                    color,
                )

    def draw_line(self, x1, y1, x2, y2, color):
        r, g, b, *a = color
        alpha = a[0] if a else 1.0

        self.line_vbo.write(np.array([x1, y1, x2, y2], dtype="f4").tobytes())
        self.line_program["u_color"].value = (r, g, b, alpha)
        self.line_vao.render(moderngl.LINES)

    def draw_text(self, x, y, text, font, color):
        if not text:
            return

        r, g, b, *a = color
        alpha = a[0] if a else 1.0

        py_color = (int(r * 255), int(g * 255), int(b * 255))
        cache_key = (text, id(font), py_color)

        if cache_key in self.text_cache:
            entry = self.text_cache[cache_key]
        else:
            # Render text to surface with antialias=True to prevent broken characters/symbols
            surf = font.render(text, True, py_color)
            w, h = surf.get_size()

            # Convert surface to texture data
            # Do NOT flip vertically (False) so it is displayed right-side up
            surf_data = pygame.image.tobytes(surf, "RGBA", False)
            tex = self.ctx.texture((w, h), 4, surf_data)
            tex.filter = (moderngl.NEAREST, moderngl.NEAREST)

            entry = TextCacheEntry(tex, w, h)
            self.text_cache[cache_key] = entry

            # Cap cache size to prevent memory leaks
            if len(self.text_cache) > 500:
                self.text_cache = {cache_key: entry}

        # Draw the text texture as a quad (scaled by 1.0x, font sizes are already native)
        entry.texture.use(0)
        self.texture_program["u_pos"].value = (float(x), float(y))
        self.texture_program["u_size"].value = (
            float(entry.width * 1.0),
            float(entry.height * 1.0),
        )
        self.texture_program["u_color"].value = (1.0, 1.0, 1.0, alpha)
        self.texture_program["u_texture"].value = 0
        self.texture_vao.render(moderngl.TRIANGLE_STRIP)
