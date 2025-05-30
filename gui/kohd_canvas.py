# kohd_translator/gui/kohd_canvas.py
import math
from PyQt6.QtWidgets import QWidget # type: ignore
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPalette, QPainterPath # type: ignore
from PyQt6.QtCore import Qt, QRectF, QPointF, QLineF # type: ignore

from kohd_core.kohd_rules import NODE_POSITIONS, RING_NODE_INSET_FACTOR, SUBNODE_RADIUS

MAX_RINGS_TO_DRAW = 2

class KohdCanvasWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(Qt.GlobalColor.white))
        self.setPalette(palette)

        self.setMinimumSize(350, 350)
        self.node_radius = 20.0
        self.font_size = 10
        self.trace_pen_width = 1.5
        
        self.subnode_dot_radius = float(SUBNODE_RADIUS) 
        # User has this set to self.subnode_dot_radius * 4.0 locally
        self.subnode_trace_start_to_first_dot_center_padding = self.subnode_dot_radius * 4.0 
        
        self.subnode_intra_group_center_to_center_spacing = self.subnode_dot_radius * 2.5
        self.subnode_inter_group_center_to_center_spacing = self.subnode_dot_radius * 4.0

        self.node_outline_pen_width = 2.0
        self.ring_pen_width = 1.5

        self.indicator_symbol_base_size = self.node_radius * 0.5
        
        self.glyph_elements_to_draw = []
        self.current_active_node_name = None
        self.is_drawing_finalized = False

    # ... (update_display_data, _get_radius_for_specific_ring_level, _calculate_connection_point, _draw_subnodes_on_line are UNCHANGED from previous version) ...
    def update_display_data(self, glyph_elements: list, active_node_name: str = None, is_finalized: bool = False):
        self.glyph_elements_to_draw = glyph_elements
        self.current_active_node_name = active_node_name
        self.is_drawing_finalized = is_finalized
        self.update()

    def _get_radius_for_specific_ring_level(self, ring_level: int) -> float:
        if ring_level == 0: return self.node_radius
        elif ring_level > 0:
            actual_ring_to_calc = min(ring_level, MAX_RINGS_TO_DRAW)
            inset_factor = RING_NODE_INSET_FACTOR - ((actual_ring_to_calc - 1) * 0.25)
            return self.node_radius * max(0.1, inset_factor)
        return self.node_radius

    def _calculate_connection_point(self, line_origin_center: QPointF, line_target_center: QPointF, connection_node_center: QPointF, connection_ring_level: int) -> QPointF:
        radius_to_connect = self._get_radius_for_specific_ring_level(connection_ring_level)
        other_end_of_line = line_target_center if connection_node_center == line_origin_center else line_origin_center
        vec = other_end_of_line - connection_node_center
        if vec.isNull():
            if line_origin_center == line_target_center and connection_node_center == line_origin_center :
                 return QPointF(connection_node_center.x(), connection_node_center.y() + radius_to_connect)
            return connection_node_center 
        line_length = math.sqrt(vec.x()**2 + vec.y()**2)
        if line_length == 0 or line_length < radius_to_connect : return connection_node_center
        unit_vec_x = vec.x() / line_length; unit_vec_y = vec.y() / line_length
        return QPointF(connection_node_center.x() + unit_vec_x * radius_to_connect, connection_node_center.y() + unit_vec_y * radius_to_connect)

    def _draw_subnodes_on_line(self, painter: QPainter, start_pos: QPointF, end_pos: QPointF, subnode_groups: list, trace_origin_ring_level: int):
        if not subnode_groups: return
        main_trace_line = QLineF(start_pos, end_pos); trace_length = main_trace_line.length()
        if trace_length < 1.0: return
        painter.setPen(QPen(Qt.GlobalColor.black, 1)); painter.setBrush(QBrush(Qt.GlobalColor.black))
        effective_start_padding = self.subnode_trace_start_to_first_dot_center_padding 
        if trace_origin_ring_level > 0:
            radius_of_origin_ring = self._get_radius_for_specific_ring_level(trace_origin_ring_level)
            min_padding_to_clear = (self.node_radius - radius_of_origin_ring) + self.subnode_dot_radius 
            effective_start_padding = max(self.subnode_trace_start_to_first_dot_center_padding, (min_padding_to_clear if min_padding_to_clear > 0 else 0) + self.subnode_dot_radius * 0.5) 
        current_distance_along_trace = effective_start_padding
        for group_idx, group_info in enumerate(subnode_groups):
            num_dots_in_group = group_info['count']
            if num_dots_in_group == 0: continue
            for dot_idx in range(num_dots_in_group):
                if current_distance_along_trace + self.subnode_dot_radius > trace_length + 1e-6 : return 
                dot_center_fraction = current_distance_along_trace / trace_length if trace_length > 0 else 0
                if dot_center_fraction > 1.0: return 
                dot_pos = main_trace_line.pointAt(dot_center_fraction)
                painter.drawEllipse(dot_pos, self.subnode_dot_radius, self.subnode_dot_radius)
                if dot_idx < num_dots_in_group - 1: current_distance_along_trace += self.subnode_intra_group_center_to_center_spacing
            if group_idx < len(subnode_groups) - 1: current_distance_along_trace += self.subnode_inter_group_center_to_center_spacing
    

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.palette().color(QPalette.ColorRole.Window))

        nodes_render_data = {} 
        for name, coords in NODE_POSITIONS.items():
            nodes_render_data[name] = {'coords': QPointF(coords[0], coords[1]), 'is_active': False, 'ring_count': 0, 'name': name}
        
        node_elements_from_builder = [el for el in self.glyph_elements_to_draw if el['type'] == 'node']
        for el_node_data in node_elements_from_builder:
            name = el_node_data['name']
            if name in nodes_render_data:
                nodes_render_data[name]['is_active'] = el_node_data.get('is_active', False) 
                nodes_render_data[name]['ring_count'] = el_node_data.get('ring_count', 0)
        
        if not self.is_drawing_finalized and self.current_active_node_name and self.current_active_node_name in nodes_render_data:
            for node_info in nodes_render_data.values(): node_info['is_active'] = False
            nodes_render_data[self.current_active_node_name]['is_active'] = True
        elif self.is_drawing_finalized:
             for node_info in nodes_render_data.values(): node_info['is_active'] = False

        # --- Draw Order ---
        # 1. Fills, 2. Outlines, 3. Rings (no change)
        for name, data in nodes_render_data.items(): # Fills
            cx, cy = data['coords'].x(), data['coords'].y(); base_rect = QRectF(cx - self.node_radius, cy - self.node_radius, 2 * self.node_radius, 2 * self.node_radius)
            fill_color = QColor(Qt.GlobalColor.yellow) if data['is_active'] else self.palette().color(QPalette.ColorRole.Window);
            if fill_color == self.palette().color(QPalette.ColorRole.Window): fill_color = QColor(Qt.GlobalColor.lightGray)
            painter.setBrush(QBrush(fill_color)); painter.setPen(Qt.PenStyle.NoPen); painter.drawEllipse(base_rect)
        for name, data in nodes_render_data.items(): # Outlines
            cx, cy = data['coords'].x(), data['coords'].y(); base_rect = QRectF(cx - self.node_radius, cy - self.node_radius, 2 * self.node_radius, 2 * self.node_radius)
            painter.setBrush(Qt.BrushStyle.NoBrush); painter.setPen(QPen(QColor(Qt.GlobalColor.black), self.node_outline_pen_width)); painter.drawEllipse(base_rect)
        for name, data in nodes_render_data.items(): # Rings
            cx, cy = data['coords'].x(), data['coords'].y(); ring_count_to_display = min(data.get('ring_count', 0), MAX_RINGS_TO_DRAW)
            if ring_count_to_display > 0:
                painter.setBrush(Qt.BrushStyle.NoBrush); painter.setPen(QPen(QColor(Qt.GlobalColor.darkBlue), self.ring_pen_width))
                for i in range(ring_count_to_display):
                    actual_ring_level = i + 1; ring_r = self._get_radius_for_specific_ring_level(actual_ring_level)
                    ring_rect = QRectF(cx - ring_r, cy - ring_r, 2 * ring_r, 2 * ring_r); painter.drawEllipse(ring_rect)
        
        # --- 4. Trace Lines and their Subnodes (no change to this part's logic) ---
        last_trace_to_ground_visual_endpoint = None 
        for element in self.glyph_elements_to_draw:
            if element['type'] == 'trace' or element['type'] == 'trace_to_ground':
                from_node_name = element['from_node_name']; subnodes_list = element.get('subnodes_on_trace', [])
                if from_node_name not in nodes_render_data: continue
                from_node_center = nodes_render_data[from_node_name]['coords']; connect_from_ring_level = element.get('connect_from_ring_level', 0)
                visual_start_point, visual_end_point = QPointF(), QPointF()
                if element['type'] == 'trace':
                    to_node_name = element['to_node_name']
                    if to_node_name not in nodes_render_data: continue
                    to_node_center = nodes_render_data[to_node_name]['coords']; connect_to_level = element.get('connect_to_ring_level', 0)
                    visual_start_point = self._calculate_connection_point(from_node_center, to_node_center, from_node_center, connect_from_ring_level)
                    visual_end_point = self._calculate_connection_point(to_node_center, from_node_center, to_node_center, connect_to_level)
                elif element['type'] == 'trace_to_ground':
                    num_final_dots = sum(item['count'] for item in subnodes_list)
                    required_subnode_span = 0
                    if num_final_dots > 0:
                        effective_start_pad = self.subnode_trace_start_to_first_dot_center_padding
                        if connect_from_ring_level > 0: # Recalculate for ground trace specifically
                            radius_of_origin_ring = self._get_radius_for_specific_ring_level(connect_from_ring_level)
                            min_padding_to_clear = (self.node_radius - radius_of_origin_ring) + self.subnode_dot_radius
                            effective_start_pad = max(self.subnode_trace_start_to_first_dot_center_padding, (min_padding_to_clear if min_padding_to_clear > 0 else 0) + self.subnode_dot_radius * 0.5)
                        required_subnode_span = effective_start_pad + (num_final_dots - 1) * self.subnode_intra_group_center_to_center_spacing + self.subnode_dot_radius
                        if len(subnodes_list) > 1: required_subnode_span += (len(subnodes_list) - 1) * self.subnode_inter_group_center_to_center_spacing
                    min_ground_trace_len = self.indicator_symbol_base_size * 2; ground_trace_visual_length = max(min_ground_trace_len, required_subnode_span + self.subnode_dot_radius)
                    conceptual_ground_end = QPointF(from_node_center.x(), from_node_center.y() + self.node_radius + ground_trace_visual_length)
                    visual_start_point = self._calculate_connection_point(from_node_center, conceptual_ground_end, from_node_center, connect_from_ring_level)
                    visual_end_point = QPointF(visual_start_point.x(), visual_start_point.y() + ground_trace_visual_length)
                    last_trace_to_ground_visual_endpoint = visual_end_point
                painter.setPen(QPen(QColor(Qt.GlobalColor.black), self.trace_pen_width)); painter.drawLine(visual_start_point, visual_end_point)
                self._draw_subnodes_on_line(painter, visual_start_point, visual_end_point, subnodes_list, connect_from_ring_level)

        # --- 5. Indicators (Charge, Ground) ---
        indicator_pen = QPen(QColor(Qt.GlobalColor.black), self.trace_pen_width * 0.8)

        for element in self.glyph_elements_to_draw:
            if element['type'] == 'charge_indicator':
                node_name = element['node_name']
                if node_name in nodes_render_data:
                    node_center = nodes_render_data[node_name]['coords']
                    
                    # *** FIXED: Charge indicator ALWAYS connects to main node (ring_level 0) ***
                    charge_connect_ring_level = 0 
                    
                    conceptual_left_point = QPointF(node_center.x() - self.node_radius * 2, node_center.y())
                    start_on_circumference = self._calculate_connection_point(
                        node_center, conceptual_left_point, 
                        node_center, charge_connect_ring_level # Use ring_level 0
                    )
                    
                    line_to_zigzag_end = QPointF(start_on_circumference.x() - self.indicator_symbol_base_size * 0.5, start_on_circumference.y())
                    
                    painter.setPen(indicator_pen)
                    painter.drawLine(start_on_circumference, line_to_zigzag_end)
                    
                    path = QPainterPath()
                    path.moveTo(line_to_zigzag_end)
                    zigzag_height = self.indicator_symbol_base_size
                    zigzag_width_total = self.indicator_symbol_base_size * 1.5
                    num_zig_points = 7 
                    for i in range(1, num_zig_points):
                        x_offset = (i / (num_zig_points -1)) * zigzag_width_total
                        y_offset = (zigzag_height / 2) * ((i % 2) * 2 - 1) 
                        path.lineTo(line_to_zigzag_end.x() - x_offset, line_to_zigzag_end.y() + y_offset)
                    painter.drawPath(path)

            elif element['type'] == 'ground_indicator':
                indicator_attach_point = last_trace_to_ground_visual_endpoint
                if indicator_attach_point:
                    painter.setPen(indicator_pen)
                    bar_width = self.indicator_symbol_base_size 
                    p1 = QPointF(indicator_attach_point.x() - bar_width / 2, indicator_attach_point.y())
                    p2 = QPointF(indicator_attach_point.x() + bar_width / 2, indicator_attach_point.y())
                    painter.drawLine(p1, p2) 
                    painter.drawLine(p1, QPointF(p1.x(), p1.y() - bar_width * 0.4))
                    painter.drawLine(p2, QPointF(p2.x(), p2.y() - bar_width * 0.4))
                    gap = self.indicator_symbol_base_size * 0.3
                    second_symbol_y = indicator_attach_point.y() + gap + self.indicator_symbol_base_size * 0.1 
                    small_bar_width = bar_width * 0.7; small_leg_height = bar_width * 0.3
                    sp1 = QPointF(indicator_attach_point.x() - small_bar_width / 2, second_symbol_y)
                    sp2 = QPointF(indicator_attach_point.x() + small_bar_width / 2, second_symbol_y)
                    painter.drawLine(sp1, QPointF(sp1.x(), sp1.y() + small_leg_height))
                    painter.drawLine(sp2, QPointF(sp2.x(), sp2.y() + small_leg_height))
                    mid_x = indicator_attach_point.x()
                    painter.drawLine(QPointF(mid_x, second_symbol_y - small_leg_height*0.2), 
                                     QPointF(mid_x, second_symbol_y + small_leg_height*1.2))
        
        # --- 6. Node Names ---
        font = QFont(); font.setPointSize(self.font_size)
        painter.setFont(font); painter.setPen(QPen(QColor(Qt.GlobalColor.black)))
        for name, data in nodes_render_data.items():
            cx, cy = data['coords'].x(), data['coords'].y(); base_rect = QRectF(cx - self.node_radius, cy - self.node_radius, 2 * self.node_radius, 2 * self.node_radius)
            painter.drawText(base_rect, Qt.AlignmentFlag.AlignCenter, name)
            
        painter.end()