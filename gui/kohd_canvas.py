# kohd_translator/gui/kohd_canvas.py
import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPalette # Added QPalette
from PyQt6.QtCore import Qt, QRectF, QPointF, QLineF

from kohd_core.kohd_rules import NODE_POSITIONS, RING_NODE_INSET_FACTOR, SUBNODE_RADIUS

MAX_RINGS_TO_DRAW = 2

class KohdCanvasWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # --- Robust White Background Setting ---
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(Qt.GlobalColor.white)) # QPalette.Window is typical for background
        self.setPalette(palette)
        # --- End White Background Setting ---

        self.setMinimumSize(350, 350)
        self.node_radius = 20.0
        self.font_size = 10
        self.trace_pen_width = 1.5
        
        self.subnode_dot_radius = float(SUBNODE_RADIUS) 
        # --- Increased initial padding for the first dot ---
        self.subnode_trace_start_to_first_dot_center_padding = self.subnode_dot_radius * 4.0 # Increased from 2.0
        
        self.subnode_intra_group_center_to_center_spacing = self.subnode_dot_radius * 2.5
        self.subnode_inter_group_center_to_center_spacing = self.subnode_dot_radius * 4.0

        self.node_outline_pen_width = 2.0
        self.ring_pen_width = 1.5
        
        self.glyph_elements_to_draw = []
        self.current_active_node_name = None
        self.is_drawing_finalized = False

    def update_display_data(self, glyph_elements: list, active_node_name: str = None, is_finalized: bool = False):
        self.glyph_elements_to_draw = glyph_elements
        self.current_active_node_name = active_node_name
        self.is_drawing_finalized = is_finalized
        self.update()

    def _get_radius_for_specific_ring_level(self, ring_level: int) -> float:
        # ... (no change) ...
        if ring_level == 0:
            return self.node_radius
        elif ring_level > 0:
            actual_ring_to_calc = min(ring_level, MAX_RINGS_TO_DRAW)
            inset_factor = RING_NODE_INSET_FACTOR - ((actual_ring_to_calc - 1) * 0.25)
            return self.node_radius * max(0.1, inset_factor)
        return self.node_radius

    def _calculate_connection_point(self, line_origin_center: QPointF, line_target_center: QPointF, connection_node_center: QPointF, connection_ring_level: int) -> QPointF:
        # ... (no change) ...
        radius_to_connect = self._get_radius_for_specific_ring_level(connection_ring_level)
        other_end_of_line = line_target_center if connection_node_center == line_origin_center else line_origin_center
        vec = other_end_of_line - connection_node_center
        if vec.isNull():
            if line_origin_center == line_target_center and connection_node_center == line_origin_center :
                 return QPointF(connection_node_center.x(), connection_node_center.y() + radius_to_connect)
            return connection_node_center 
        line_length = math.sqrt(vec.x()**2 + vec.y()**2)
        if line_length == 0 or line_length < radius_to_connect : # Safeguard
            return connection_node_center
        unit_vec_x = vec.x() / line_length
        unit_vec_y = vec.y() / line_length
        return QPointF(
            connection_node_center.x() + unit_vec_x * radius_to_connect,
            connection_node_center.y() + unit_vec_y * radius_to_connect
        )

    def _draw_subnodes_on_line(self, painter: QPainter, 
                               start_pos: QPointF, # Visual start of the trace line
                               end_pos: QPointF, 
                               subnode_groups: list,
                               trace_origin_ring_level: int):
        # ... (logic for effective_start_padding remains the same, but will use the new base padding) ...
        if not subnode_groups: return
        main_trace_line = QLineF(start_pos, end_pos)
        trace_length = main_trace_line.length()
        if trace_length < 1.0: return

        painter.setPen(QPen(Qt.GlobalColor.black, 1)); painter.setBrush(QBrush(Qt.GlobalColor.black))

        effective_start_padding = self.subnode_trace_start_to_first_dot_center_padding
        if trace_origin_ring_level > 0:
            radius_of_origin_ring = self._get_radius_for_specific_ring_level(trace_origin_ring_level)
            min_padding_to_clear_main_node = (self.node_radius - radius_of_origin_ring) + self.subnode_dot_radius 
            if min_padding_to_clear_main_node < 0 : min_padding_to_clear_main_node = 0
            effective_start_padding = max(self.subnode_trace_start_to_first_dot_center_padding, 
                                          min_padding_to_clear_main_node + self.subnode_dot_radius * 0.5) 
        current_distance_along_trace = effective_start_padding

        for group_idx, group_info in enumerate(subnode_groups):
            num_dots_in_group = group_info['count']
            if num_dots_in_group == 0: continue
            for dot_idx in range(num_dots_in_group):
                if current_distance_along_trace + self.subnode_dot_radius > trace_length + 1e-6: # Add tolerance
                    return 
                dot_center_on_line_fraction = current_distance_along_trace / trace_length if trace_length > 0 else 0
                if dot_center_on_line_fraction > 1.0: return 
                dot_pos = main_trace_line.pointAt(dot_center_on_line_fraction)
                painter.drawEllipse(dot_pos, self.subnode_dot_radius, self.subnode_dot_radius)
                if dot_idx < num_dots_in_group - 1:
                    current_distance_along_trace += self.subnode_intra_group_center_to_center_spacing
            if group_idx < len(subnode_groups) - 1:
                current_distance_along_trace += self.subnode_inter_group_center_to_center_spacing
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # autoFillBackground should handle this, but fillRect is a good fallback/override.
        # If autoFillBackground is working, this fillRect might not be strictly necessary
        # but doesn't hurt.
        painter.fillRect(self.rect(), self.palette().color(QPalette.ColorRole.Window))


        # ... (rest of paintEvent: node data prep, drawing nodes, rings, traces, names) ...
        # (No changes to the actual drawing loops themselves from the last version, only the
        #  parameters in __init__ and the `effective_start_padding` logic in _draw_subnodes_on_line
        #  are affected by the request, and the background color handling in __init__/paintEvent.)

        # --- Prepare Node Data (map for easy lookup) ---
        nodes_render_data = {} 
        for name, coords in NODE_POSITIONS.items():
            nodes_render_data[name] = {'coords': QPointF(coords[0], coords[1]), 'is_active': False, 'ring_count': 0, 'name': name}
        
        node_elements_from_builder = [el for el in self.glyph_elements_to_draw if el['type'] == 'node']
        for element_node_data in node_elements_from_builder:
            name = element_node_data['name']
            if name in nodes_render_data:
                nodes_render_data[name]['is_active'] = element_node_data.get('is_active', False) 
                nodes_render_data[name]['ring_count'] = element_node_data.get('ring_count', 0)
        
        if not self.is_drawing_finalized and self.current_active_node_name and self.current_active_node_name in nodes_render_data:
            for node_info in nodes_render_data.values(): node_info['is_active'] = False
            nodes_render_data[self.current_active_node_name]['is_active'] = True
        elif self.is_drawing_finalized:
             for node_info in nodes_render_data.values(): node_info['is_active'] = False

        # --- Draw Order ---
        # 1. Node Fills (Already done by autoFillBackground or the fillRect above if that was used)
        # We will redraw fills here to ensure active node highlighting is on top of the general white bg
        for name, data in nodes_render_data.items(): # Fills
            cx, cy = data['coords'].x(), data['coords'].y(); base_rect = QRectF(cx - self.node_radius, cy - self.node_radius, 2 * self.node_radius, 2 * self.node_radius)
            fill_color = QColor(Qt.GlobalColor.yellow) if data['is_active'] else self.palette().color(QPalette.ColorRole.Window) # Use lightGray if palette not white
            if fill_color == self.palette().color(QPalette.ColorRole.Window) : # If it's same as bg, use lightGray for node
                fill_color = QColor(Qt.GlobalColor.lightGray)

            painter.setBrush(QBrush(fill_color)); painter.setPen(Qt.PenStyle.NoPen); painter.drawEllipse(base_rect)

        # 2. Node Outlines
        for name, data in nodes_render_data.items(): # Outlines
            cx, cy = data['coords'].x(), data['coords'].y(); base_rect = QRectF(cx - self.node_radius, cy - self.node_radius, 2 * self.node_radius, 2 * self.node_radius)
            painter.setBrush(Qt.BrushStyle.NoBrush); painter.setPen(QPen(QColor(Qt.GlobalColor.black), self.node_outline_pen_width)); painter.drawEllipse(base_rect)

        # 3. Rings
        for name, data in nodes_render_data.items(): # Rings
            cx, cy = data['coords'].x(), data['coords'].y(); ring_count_to_display = min(data.get('ring_count', 0), MAX_RINGS_TO_DRAW)
            if ring_count_to_display > 0:
                painter.setBrush(Qt.BrushStyle.NoBrush); painter.setPen(QPen(QColor(Qt.GlobalColor.darkBlue), self.ring_pen_width))
                for i in range(ring_count_to_display):
                    actual_ring_level = i + 1; ring_r = self._get_radius_for_specific_ring_level(actual_ring_level)
                    ring_rect = QRectF(cx - ring_r, cy - ring_r, 2 * ring_r, 2 * ring_r); painter.drawEllipse(ring_rect)
        
        # 4. Trace Lines and their Subnodes
        for element in self.glyph_elements_to_draw:
            if element['type'] == 'trace' or element['type'] == 'trace_to_ground':
                from_node_name = element['from_node_name']
                subnodes_list = element.get('subnodes_on_trace', [])
                if from_node_name not in nodes_render_data: continue
                from_node_center = nodes_render_data[from_node_name]['coords']
                connect_from_ring_level = element.get('connect_from_ring_level', 0)
                visual_start_point = QPointF(); visual_end_point = QPointF()

                if element['type'] == 'trace':
                    to_node_name = element['to_node_name']
                    if to_node_name not in nodes_render_data: continue
                    to_node_center = nodes_render_data[to_node_name]['coords']
                    connect_to_level = element.get('connect_to_ring_level', 0)
                    visual_start_point = self._calculate_connection_point(from_node_center, to_node_center, from_node_center, connect_from_ring_level)
                    visual_end_point = self._calculate_connection_point(to_node_center, from_node_center, to_node_center, connect_to_level)
                elif element['type'] == 'trace_to_ground':
                    conceptual_ground_end = QPointF(from_node_center.x(), from_node_center.y() + self.node_radius * 2)
                    visual_start_point = self._calculate_connection_point(from_node_center, conceptual_ground_end, from_node_center, connect_from_ring_level)
                    ground_trace_length = self.node_radius * 0.75 
                    visual_end_point = QPointF(visual_start_point.x(), visual_start_point.y() + ground_trace_length)

                painter.setPen(QPen(QColor(Qt.GlobalColor.black), self.trace_pen_width))
                painter.drawLine(visual_start_point, visual_end_point)
                self._draw_subnodes_on_line(painter, visual_start_point, visual_end_point, subnodes_list, connect_from_ring_level)

        # 5. Node Names
        font = QFont(); font.setPointSize(self.font_size)
        painter.setFont(font); painter.setPen(QPen(QColor(Qt.GlobalColor.black)))
        for name, data in nodes_render_data.items():
            cx, cy = data['coords'].x(), data['coords'].y()
            base_rect = QRectF(cx - self.node_radius, cy - self.node_radius, 2 * self.node_radius, 2 * self.node_radius)
            painter.drawText(base_rect, Qt.AlignmentFlag.AlignCenter, name)
            
        painter.end()