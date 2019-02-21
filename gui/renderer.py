import timeit
import arcade
import pyglet.gl as gl
import numpy as np
from simulation.world import World

# from profilehooks import profile

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 960
ASPECT_RATIO = SCREEN_WIDTH / SCREEN_HEIGHT
SCREEN_TITLE = "Sprite Collect Coins Example"


class GUI(arcade.Window):
    """ Our custom Window Class"""

    def __init__(self, world: World) -> None:
        """ Initializer """
        # Call the parent class initializer
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)

        # save the world ;)
        assert world is not None
        self.world = world

    def setup(self):
        """ Set up the GUI """
        self.viewport = Viewport(-50 * ASPECT_RATIO, 250 * ASPECT_RATIO, -50, 250)

        arcade.set_background_color(arcade.color.BLACK)
        self.set_update_rate(1.0 / 60)

        self.tiles_vbo = None
        self.map_items = None

        # editor
        self.is_editing = False

        # for fps calculations
        self.t0 = timeit.default_timer()
        self.frame_t0 = timeit.default_timer()
        self.frame_count = 0
        self.fps = 0

    def update(self, delta_time):
        """ Update ALL the things! """
        ...

    # @profile
    def build_grid(self):
        # prepare VBO for tiles
        n_vertices = self.world.map.size[0] * self.world.map.size[1] * 6
        points = np.zeros((n_vertices, 2), dtype=np.float32)
        colors = np.zeros((n_vertices, 4), dtype=np.uint8)
        for x in range(self.world.map.size[0]):
            for y in range(self.world.map.size[1]):
                # default color
                color = (0.2, 0.2, 0.2, 1.0)
                # vision modfier
                vision_modifier = self.world.map.vision_modifier[x][y]
                if vision_modifier < 1.0:
                    color = (0, vision_modifier * 0.75, 0, 1.0)
                # wall
                if self.world.map.walls[x][y]:
                    color = (0.8, 0.8, 0.8, 1.0)

                # points.extend([(x, y), (x + 1, y), (x, y + 1), (x, y + 1), (x + 1, y), (x + 1, y + 1)])
                # colors.extend([tuple([int(255 * c) for c in color])] * 6)

                index = (x * self.world.map.size[0] + y) * 6
                points[index:index + 6, :] = ((x, y), (x + 1, y), (x, y + 1), (x, y + 1), (x + 1, y), (x + 1, y + 1))
                colors[index:index + 6, :] = [tuple((int(255 * c) for c in color))] * 6

        self.tiles_vbo = arcade.create_line_generic_with_colors(points, colors, gl.GL_TRIANGLES)

    def build_map_items(self):
        shape_list = arcade.ShapeElementList()
        # targets (blue)
        for target in self.world.map.targets:
            shape_list.append(arcade.create_rectangle_filled(target.x - 0.5, target.y - 0.5, 2, 2, color=(0, 0, 255)))

        # towers (red)
        for tower in self.world.map.towers:
            shape_list.append(arcade.create_rectangle_filled(tower.pos.x - 0.5, tower.pos.y - 0.5, 2, 2, color=(255, 0, 0)))

        # communication markers (circles)
        for marker in self.world.map.markers:
            shape_list.append(arcade.create_ellipse_filled(marker.location.x - 0.5, marker.location.y - 0.5, 1, 1, color=(255, 0, 255)))

        # TODO: self.gates

        self.map_items = shape_list

    def on_draw(self):
        """ Draw everything """
        arcade.start_render()
        self.set_viewport(*self.viewport.as_tuple())

        # build map VBO if necessary
        if self.tiles_vbo is None:
            self.build_grid()

        # render main map tiles
        # fix projection each frame
        with self.tiles_vbo.vao:
            self.tiles_vbo.program['Projection'] = arcade.get_projection().flatten()
        # and draw
        self.tiles_vbo.draw()

        # render stuff on top of the map
        if self.map_items is None:
            self.build_map_items()
        # fix projection each frame
        with self.map_items.program:
            self.map_items.program['Projection'] = arcade.get_projection().flatten()
        # and draw
        self.map_items.draw()

        # change to pixel viewport for text and menu drawing
        self.set_viewport(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT)

        # editor
        if self.is_editing:
            arcade.draw_text("EDITING MODE", 8, SCREEN_HEIGHT - 24 - 18, arcade.color.MAGENTA, 16)

        # FPS timing stuff
        t = timeit.default_timer()
        self.frame_count += 1
        if t - self.t0 > 1:
            self.fps = self.frame_count / (t - self.t0)
            self.t0 = timeit.default_timer()
            self.frame_count = 0
            print(f"FPS: {self.fps:3.1f}", f"({(1 / self.fps) * 1000:3.2f}ms)")

        if t - self.frame_t0 > 0.02:
            print(f"Frame took too long: {(t - self.frame_t0) * 1000:3.2f}ms")
        self.frame_t0 = t
        arcade.draw_text(f"FPS: {self.fps:3.1f}", 8, SCREEN_HEIGHT - 24, arcade.color.WHITE, 16)

    def on_mouse_motion(self, x, y, dx, dy):
        """ Handle Mouse Motion """
        ...

    def on_mouse_press(self, x, y, button, modifiers):
        """ Called when the user presses a mouse button """
        if self.is_editing:
            if button == arcade.MOUSE_BUTTON_LEFT:
                x, y = self.screen_to_map(x, y)
                if x >= 0 and y >= 0 and x < self.world.map.size[0] and y < self.world.map.size[1]:
                    self.world.map.walls[x][y] = True

    def on_mouse_release(self, x, y, button, modifiers):
        """ Called when a user releases a mouse button """
        if button == arcade.MOUSE_BUTTON_LEFT:
            ...

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        self.viewport.zoom(direction=scroll_y, factor=1.2)

    def on_key_press(self, key, modifiers):
        """ Called whenever a key is pressed """

        move_amount = 0.1
        if key == arcade.key.UP or key == arcade.key.W:
            self.viewport.move(0, move_amount)
        elif key == arcade.key.DOWN or key == arcade.key.S:
            self.viewport.move(0, -move_amount)
        elif key == arcade.key.LEFT or key == arcade.key.A:
            self.viewport.move(-move_amount, 0)
        elif key == arcade.key.RIGHT or key == arcade.key.D:
            self.viewport.move(move_amount, 0)
        # Force rebuild tiles VBO
        elif key == arcade.key.B:
            self.build_grid()
            self.build_map_items()
        # toggle editing mode
        elif key == arcade.key.E:
            self.is_editing = not self.is_editing

    def screen_to_map(self, x, y, round=True):
        x = np.interp(x, (0, SCREEN_WIDTH), (self.viewport.bottom_left[0], self.viewport.top_right[0]))
        y = np.interp(y, (0, SCREEN_HEIGHT), (self.viewport.bottom_left[1], self.viewport.top_right[1]))
        if round:
            return (int(x), int(y))
        else:
            return (x, y)


class Viewport:
    def __init__(self, left, right, bottom, top):
        self.bottom_left = np.array((left, bottom), dtype=np.float32)
        self.top_right = np.array((right, top), dtype=np.float32)

    def as_tuple(self):
        return (self.bottom_left[0], self.top_right[0], self.bottom_left[1], self.top_right[1])

    def center(self):
        return np.array(((self.bottom_left[0] + self.top_right[0]) / 2, (self.bottom_left[1] + self.top_right[1]) / 2))

    def width(self):
        return self.top_right[0] - self.bottom_left[0]

    def height(self):
        return self.top_right[1] - self.bottom_left[1]

    def zoom(self, direction=1, factor=1.2):
        center = self.center()
        factor = factor if direction < 0 else (1 / factor)

        self.bottom_left = (self.bottom_left - center) * factor + center
        self.top_right = (self.top_right - center) * factor + center

        print(self)

    def move(self, move_x, move_y):
        """`move_x` and `move_y` represent a percentage of the screen size"""
        offset = np.array((move_x * self.width(), move_y * self.height()))
        self.bottom_left += offset
        self.top_right += offset

    def __str__(self):
        return f"Viewport: (x0,y0)={self.bottom_left}, (x1,y1)={self.top_right}"
