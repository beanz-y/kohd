# kohd_translator/gui/kohd_canvas.py
import math
from PyQt6.QtWidgets import QWidget # type: ignore
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont # type: ignore # Ensure QFont is imported
from PyQt6.QtCore import Qt, QRectF, QPointF, QLineF # type: ignore

from kohd_core.kohd_rules import NODE_POSITIONS, RING_NODE_INSET_FACTOR, SUBNODE_RADIUS

MAX_RINGS_TO_DRAW = 2

class KohdCanvasWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(350, 350)
        self.node_radius = 20.0
        self.font_size = 10 # Defined as an instance attribute
        self.trace_pen_width = 1.5
        self.subnode_dot_radius = float(SUBNODE_RADIUS)
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
        if ring_level == 0:
            return self.node_radius
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
             # Default direction if centers are same (e.g. start of trace_to_ground from single node word)
            if line_origin_center == line_target_center and connection_node_center == line_origin_center : # trace_to_ground start
                # For the start of a trace_to_ground, line usually points "down" from the node.
                # So the vector from node center to circumference point is (0, radius) if ground is below.
                # This function expects 'other_end_of_line' to define direction.
                # If from=to=connection_node, use a default. Let's assume downward for ground.
                 return QPointF(connection_node_center.x(), connection_node_center.y() + radius_to_connect)


            return connection_node_center 

        line_length = math.sqrt(vec.x()**2 + vec.y()**2)
        if line_length == 0 or line_length < radius_to_connect :
            return connection_node_center

        unit_vec_x = vec.x() / line_length
        unit_vec_y = vec.y() / line_length
        
        return QPointF(
            connection_node_center.x() + unit_vec_x * radius_to_connect,
            connection_node_center.y() + unit_vec_y * radius_to_connect
        )

    def _draw_subnodes_on_line(self, painter: QPainter, start_pos: QPointF, end_pos: QPointF, subnodes_on_trace_list: list):
        # --- THIS METHOD IS STILL THE OLD EVEN DISTRIBUTION ---
        # --- WILL BE REPLACED IN THE NEXT STEP FOR GROUPING ---
        total_dots_on_this_segment = sum(item['count'] for item in subnodes_on_trace_list)
        if total_dots_on_this_segment == 0: return
        line = QLineF(start_pos, end_pos)
        if line.length() < self.subnode_dot_radius * 2 * total_dots_on_this_segment : return
        painter.setPen(QPen(Qt.GlobalColor.black, 1)); painter.setBrush(QBrush(Qt.GlobalColor.black))
        for i in range(1, total_dots_on_this_segment + 1):
            dot_pos = line.pointAt(i / (total_dots_on_this_segment + 1))
            painter.drawEllipse(dot_pos, self.subnode_dot_radius, self.subnode_dot_radius)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(Qt.GlobalColor.white))

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
        # 1. Node Fills
        for name, data in nodes_render_data.items():
            cx, cy = data['coords'].x(), data['coords'].y()
            base_rect = QRectF(cx - self.node_radius, cy - self.node_radius, 2 * self.node_radius, 2 * self.node_radius)
            fill_color = QColor(Qt.GlobalColor.yellow) if data['is_active'] else QColor(Qt.GlobalColor.lightGray)
            painter.setBrush(QBrush(fill_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(base_rect)

        # 2. Node Outlines
        for name, data in nodes_render_data.items():
            cx, cy = data['coords'].x(), data['coords'].y()
            base_rect = QRectF(cx - self.node_radius, cy - self.node_radius, 2 * self.node_radius, 2 * self.node_radius)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(Qt.GlobalColor.black), self.node_outline_pen_width))
            painter.drawEllipse(base_rect)

        # 3. Rings
        for name, data in nodes_render_data.items():
            cx, cy = data['coords'].x(), data['coords'].y()
            ring_count_to_display = min(data.get('ring_count', 0), MAX_RINGS_TO_DRAW)
            if ring_count_to_display > 0:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(Qt.GlobalColor.darkBlue), self.ring_pen_width))
                for i in range(ring_count_to_display):
                    actual_ring_level = i + 1
                    ring_r = self._get_radius_for_specific_ring_level(actual_ring_level)
                    ring_rect = QRectF(cx - ring_r, cy - ring_r, 2 * ring_r, 2 * ring_r)
                    painter.drawEllipse(ring_rect)
        
        # 4. Trace Lines and their Subnodes
        painter.setPen(QPen(QColor(Qt.GlobalColor.black), self.trace_pen_width))
        for element in self.glyph_elements_to_draw:
            if element['type'] == 'trace':
                from_node_name = element['from_node_name']
                to_node_name = element['to_node_name']
                
                if from_node_name in nodes_render_data and to_node_name in nodes_render_data:
                    from_node_center = nodes_render_data[from_node_name]['coords']
                    to_node_center = nodes_render_data[to_node_name]['coords']
                    
                    connect_from_level = element.get('connect_from_ring_level', 0)
                    connect_to_level = element.get('connect_to_ring_level', 0)

                    visual_start_point = self._calculate_connection_point(from_node_center, to_node_center, from_node_center, connect_from_level)
                    visual_end_point = self._calculate_connection_point(to_node_center, from_node_center, to_node_center, connect_to_level)
                    
                    painter.setPen(QPen(QColor(Qt.GlobalColor.black), self.trace_pen_width))
                    painter.drawLine(visual_start_point, visual_end_point)
                    self._draw_subnodes_on_line(painter, visual_start_point, visual_end_point, element.get('subnodes_on_trace', []))

            elif element['type'] == 'trace_to_ground':
                from_node_name = element['from_node_name']
                if from_node_name in nodes_render_data:
                    from_node_center = nodes_render_data[from_node_name]['coords']
                    connect_from_level = element.get('connect_from_ring_level', 0)

                    conceptual_ground_end = QPointF(from_node_center.x(), from_node_center.y() + self.node_radius * 2)
                    visual_start_point = self._calculate_connection_point(from_node_center, conceptual_ground_end, from_node_center, connect_from_level)
                    
                    ground_trace_length = self.node_radius * 0.75 
                    actual_ground_end_pos = QPointF(visual_start_point.x(), visual_start_point.y() + ground_trace_length)
                    
                    painter.setPen(QPen(QColor(Qt.GlobalColor.black), self.trace_pen_width))
                    painter.drawLine(visual_start_point, actual_ground_end_pos)
                    self._draw_subnodes_on_line(painter, visual_start_point, actual_ground_end_pos, element.get('subnodes_on_trace', []))

        # 5. Node Names
        # *** FIX: Re-instantiate font object here ***
        font = QFont()
        font.setPointSize(self.font_size)
        painter.setFont(font) 
        painter.setPen(QPen(QColor(Qt.GlobalColor.black)))
        for name, data in nodes_render_data.items():
            cx, cy = data['coords'].x(), data['coords'].y()
            base_rect = QRectF(cx - self.node_radius, cy - self.node_radius, 2 * self.node_radius, 2 * self.node_radius)
            painter.drawText(base_rect, Qt.AlignmentFlag.AlignCenter, name)
            
        # TODO: Draw Indicators (Charge, Ground)
        painter.end()