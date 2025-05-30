# kohd_translator/gui/kohd_canvas.py
import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPalette, QPainterPath
from PyQt6.QtCore import Qt, QRectF, QPointF, QLineF

from kohd_core.kohd_rules import NODE_POSITIONS, RING_NODE_INSET_FACTOR, SUBNODE_RADIUS

MAX_RINGS_TO_DRAW = 2
PREFERRED_CHARGE_ANGLES_DEG = [180, 225, 135, 270, 90, 315, 45, 0] 
PREFERRED_GROUND_TRACE_ANGLES_DEG = [270, 225, 315, 180, 0, 135, 45, 90] 
MIN_ANGLE_SEPARATION_DEG = 30
NULL_MODIFIER_SYMBOL_RADIUS_FACTOR = 0.4 # Already present from your file

class KohdCanvasWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True); palette = self.palette(); palette.setColor(QPalette.ColorRole.Window, QColor(Qt.GlobalColor.white)); self.setPalette(palette)
        self.setMinimumSize(350, 350); self.node_radius = 20.0; self.font_size = 10; self.trace_pen_width = 1.5
        self.subnode_dot_radius = float(SUBNODE_RADIUS) 
        # User has this set to self.subnode_dot_radius * 4.0 locally
        self.subnode_trace_start_to_first_dot_center_padding = self.subnode_dot_radius * 4.0 
        self.subnode_intra_group_center_to_center_spacing = self.subnode_dot_radius * 2.5
        self.subnode_inter_group_center_to_center_spacing = self.subnode_dot_radius * 4.0
        self.node_outline_pen_width = 2.0; self.ring_pen_width = 1.5; self.indicator_symbol_base_size = self.node_radius * 0.5
        self.glyph_elements_to_draw = []; self.current_active_node_name = None; self.is_drawing_finalized = False

    def update_display_data(self, glyph_elements: list, active_node_name: str = None, is_finalized: bool = False):
        self.glyph_elements_to_draw = glyph_elements; self.current_active_node_name = active_node_name; self.is_drawing_finalized = is_finalized; self.update()
    
    def _get_radius_for_specific_ring_level(self, ring_level: int) -> float:
        if ring_level == 0: return self.node_radius
        elif ring_level > 0: actual_ring_to_calc = min(ring_level, MAX_RINGS_TO_DRAW); inset_factor = RING_NODE_INSET_FACTOR - ((actual_ring_to_calc - 1) * 0.25); return self.node_radius * max(0.1, inset_factor)
        return self.node_radius

    def _calculate_connection_point_at_angle(self, node_center: QPointF, ring_level: int, angle_deg: float) -> QPointF:
        radius = self._get_radius_for_specific_ring_level(ring_level); rad_angle = math.radians(angle_deg)
        return QPointF(node_center.x() + radius * math.cos(rad_angle), node_center.y() - radius * math.sin(rad_angle))

    def _calculate_connection_point(self, line_origin_center: QPointF, line_target_center: QPointF, connection_node_center: QPointF, connection_ring_level: int) -> QPointF:
        radius_to_connect = self._get_radius_for_specific_ring_level(connection_ring_level); other_end_of_line = line_target_center if connection_node_center == line_origin_center else line_origin_center
        vec = other_end_of_line - connection_node_center
        if vec.isNull():
            if line_origin_center == line_target_center and connection_node_center == line_origin_center : return QPointF(connection_node_center.x(), connection_node_center.y() + radius_to_connect)
            return connection_node_center 
        line_length = math.sqrt(vec.x()**2 + vec.y()**2)
        if line_length < 1e-3 or line_length < radius_to_connect + 1e-3 : return connection_node_center
        unit_vec_x = vec.x() / line_length; unit_vec_y = vec.y() / line_length
        return QPointF(connection_node_center.x() + unit_vec_x * radius_to_connect, connection_node_center.y() + unit_vec_y * radius_to_connect)

    def _find_clear_angle_deg(self, existing_angles_deg: list, preferred_angles_deg: list, min_separation_deg: float) -> float:
        for pref_angle in preferred_angles_deg:
            is_clear = True;
            for exist_angle in existing_angles_deg:
                diff = abs(pref_angle - exist_angle); angle_diff = min(diff, 360 - diff)
                if angle_diff < min_separation_deg: is_clear = False; break
            if is_clear: return pref_angle
        return preferred_angles_deg[0] 

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
        node_actual_trace_angles = {name: [] for name in NODE_POSITIONS.keys()}
        for name, coords in NODE_POSITIONS.items(): nodes_render_data[name] = {'coords': QPointF(coords[0], coords[1]), 'is_active': False, 'ring_count': 0, 'name': name}
        node_elements_from_builder = [el for el in self.glyph_elements_to_draw if el['type'] == 'node']
        for el_node_data in node_elements_from_builder:
            name = el_node_data['name']
            if name in nodes_render_data: nodes_render_data[name]['is_active'] = el_node_data.get('is_active', False); nodes_render_data[name]['ring_count'] = el_node_data.get('ring_count', 0)
        if not self.is_drawing_finalized and self.current_active_node_name and self.current_active_node_name in nodes_render_data:
            for node_info in nodes_render_data.values(): node_info['is_active'] = False
            nodes_render_data[self.current_active_node_name]['is_active'] = True
        elif self.is_drawing_finalized:
             for node_info in nodes_render_data.values(): node_info['is_active'] = False
        for element in self.glyph_elements_to_draw:
            if element['type'] == 'trace':
                from_name = element['from_node_name']; to_name = element['to_node_name']
                if from_name in nodes_render_data and to_name in nodes_render_data:
                    p1 = nodes_render_data[from_name]['coords']; p2 = nodes_render_data[to_name]['coords']; line = QLineF(p1, p2)
                    if line.length() > 1e-3: node_actual_trace_angles[from_name].append(line.angle()); node_actual_trace_angles[to_name].append(QLineF(p2,p1).angle())
        
        charge_indicator_element = next((el for el in self.glyph_elements_to_draw if el['type'] == 'charge_indicator'), None)
        trace_to_ground_element = next((el for el in self.glyph_elements_to_draw if el['type'] == 'trace_to_ground'), None)
        chosen_charge_angle_deg = None
        if charge_indicator_element and charge_indicator_element['node_name'] in nodes_render_data:
            node_name = charge_indicator_element['node_name']; chosen_charge_angle_deg = self._find_clear_angle_deg(node_actual_trace_angles.get(node_name, []), PREFERRED_CHARGE_ANGLES_DEG, MIN_ANGLE_SEPARATION_DEG)
        chosen_ground_trace_angle_deg = 270 
        if trace_to_ground_element and trace_to_ground_element['from_node_name'] in nodes_render_data:
            from_node_name = trace_to_ground_element['from_node_name']; temp_existing_angles = list(node_actual_trace_angles.get(from_node_name, []))
            if charge_indicator_element and charge_indicator_element['node_name'] == from_node_name and chosen_charge_angle_deg is not None: temp_existing_angles.append(chosen_charge_angle_deg)
            chosen_ground_trace_angle_deg = self._find_clear_angle_deg(temp_existing_angles, PREFERRED_GROUND_TRACE_ANGLES_DEG, MIN_ANGLE_SEPARATION_DEG)

        for name, data in nodes_render_data.items(): # Fills
            cx,cy=data['coords'].x(),data['coords'].y();base_rect=QRectF(cx-self.node_radius,cy-self.node_radius,2*self.node_radius,2*self.node_radius);fill_color=QColor(Qt.GlobalColor.yellow) if data['is_active'] else self.palette().color(QPalette.ColorRole.Window);
            if fill_color == self.palette().color(QPalette.ColorRole.Window): fill_color=QColor(Qt.GlobalColor.lightGray)
            painter.setBrush(QBrush(fill_color));painter.setPen(Qt.PenStyle.NoPen);painter.drawEllipse(base_rect)
        for name, data in nodes_render_data.items(): # Outlines
            cx,cy=data['coords'].x(),data['coords'].y();base_rect=QRectF(cx-self.node_radius,cy-self.node_radius,2*self.node_radius,2*self.node_radius);painter.setBrush(Qt.BrushStyle.NoBrush);painter.setPen(QPen(QColor(Qt.GlobalColor.black),self.node_outline_pen_width));painter.drawEllipse(base_rect)
        for name, data in nodes_render_data.items(): # Rings
            cx,cy=data['coords'].x(),data['coords'].y();ring_count_to_display=min(data.get('ring_count',0),MAX_RINGS_TO_DRAW)
            if ring_count_to_display>0:
                painter.setBrush(Qt.BrushStyle.NoBrush);painter.setPen(QPen(QColor(Qt.GlobalColor.darkBlue),self.ring_pen_width))
                for i in range(ring_count_to_display):
                    actual_ring_level=i+1;ring_r=self._get_radius_for_specific_ring_level(actual_ring_level);ring_rect=QRectF(cx-ring_r,cy-ring_r,2*ring_r,2*ring_r);painter.drawEllipse(ring_rect)
        
        last_trace_to_ground_visual_endpoint = None 
        for element in self.glyph_elements_to_draw: # Actual Traces
            if element['type'] == 'trace':
                from_node_name=element['from_node_name'];to_node_name=element['to_node_name']
                if from_node_name in nodes_render_data and to_node_name in nodes_render_data:
                    from_node_center=nodes_render_data[from_node_name]['coords'];to_node_center=nodes_render_data[to_node_name]['coords'];connect_from_level=element.get('connect_from_ring_level',0);connect_to_level=element.get('connect_to_ring_level',0)
                    visual_start_point=self._calculate_connection_point(from_node_center,to_node_center,from_node_center,connect_from_level);visual_end_point=self._calculate_connection_point(to_node_center,from_node_center,to_node_center,connect_to_level)
                    painter.setPen(QPen(QColor(Qt.GlobalColor.black),self.trace_pen_width));painter.drawLine(visual_start_point,visual_end_point);self._draw_subnodes_on_line(painter,visual_start_point,visual_end_point,element.get('subnodes_on_trace',[]),connect_from_level)
        if trace_to_ground_element and trace_to_ground_element['from_node_name'] in nodes_render_data: # Trace To Ground
            from_node_name=trace_to_ground_element['from_node_name'];from_node_center=nodes_render_data[from_node_name]['coords'];connect_from_ring_level=trace_to_ground_element.get('connect_from_ring_level',0);subnodes_list=trace_to_ground_element.get('subnodes_on_trace',[])
            visual_start_point=self._calculate_connection_point_at_angle(from_node_center,connect_from_ring_level,chosen_ground_trace_angle_deg)
            num_final_dots=sum(item['count'] for item in subnodes_list);required_subnode_span=0
            if num_final_dots>0:
                effective_start_pad=self.subnode_trace_start_to_first_dot_center_padding
                if connect_from_ring_level>0:radius_of_origin_ring=self._get_radius_for_specific_ring_level(connect_from_ring_level);min_padding_to_clear=(self.node_radius-radius_of_origin_ring)+self.subnode_dot_radius;effective_start_pad=max(self.subnode_trace_start_to_first_dot_center_padding,(min_padding_to_clear if min_padding_to_clear > 0 else 0)+self.subnode_dot_radius*0.5)
                required_subnode_span=effective_start_pad
                if num_final_dots>0:required_subnode_span+=(num_final_dots-1)*self.subnode_intra_group_center_to_center_spacing if num_final_dots>1 else 0;required_subnode_span+=self.subnode_dot_radius 
                if len(subnodes_list)>1:required_subnode_span+=(len(subnodes_list)-1)*self.subnode_inter_group_center_to_center_spacing
            min_ground_trace_len=self.indicator_symbol_base_size*1.5;ground_trace_visual_length=max(min_ground_trace_len,required_subnode_span+self.subnode_dot_radius) 
            rad_angle=math.radians(chosen_ground_trace_angle_deg)
            visual_end_point=QPointF(visual_start_point.x()+ground_trace_visual_length*math.cos(rad_angle),visual_start_point.y()-ground_trace_visual_length*math.sin(rad_angle))
            last_trace_to_ground_visual_endpoint=visual_end_point
            painter.setPen(QPen(QColor(Qt.GlobalColor.black),self.trace_pen_width));painter.drawLine(visual_start_point,visual_end_point);self._draw_subnodes_on_line(painter,visual_start_point,visual_end_point,subnodes_list,connect_from_ring_level)

        indicator_pen = QPen(QColor(Qt.GlobalColor.black), self.trace_pen_width * 0.8)
        if charge_indicator_element and chosen_charge_angle_deg is not None: 
            node_name=charge_indicator_element['node_name'];node_center=nodes_render_data[node_name]['coords'];start_on_circumference=self._calculate_connection_point_at_angle(node_center,0,chosen_charge_angle_deg);rad_clear_angle=math.radians(chosen_charge_angle_deg)
            line_to_symbol_end_x=start_on_circumference.x()+self.indicator_symbol_base_size*0.5*math.cos(rad_clear_angle);line_to_symbol_end_y=start_on_circumference.y()-self.indicator_symbol_base_size*0.5*math.sin(rad_clear_angle);line_to_zigzag_end=QPointF(line_to_symbol_end_x,line_to_symbol_end_y)
            painter.setPen(indicator_pen);painter.drawLine(start_on_circumference,line_to_zigzag_end);path=QPainterPath();path.moveTo(line_to_zigzag_end)
            zigzag_height=self.indicator_symbol_base_size;zigzag_width_total=self.indicator_symbol_base_size*1.5;num_zig_points=7
            for i in range(1,num_zig_points):
                dist_along_angle=(i/(num_zig_points-1))*zigzag_width_total;perp_offset_val=(zigzag_height/2)*((i%2)*2-1)
                px=line_to_zigzag_end.x()+dist_along_angle*math.cos(rad_clear_angle);py=line_to_zigzag_end.y()-dist_along_angle*math.sin(rad_clear_angle)
                final_x=px+perp_offset_val*math.sin(rad_clear_angle);final_y=py+perp_offset_val*math.cos(rad_clear_angle) 
                path.lineTo(final_x,final_y)
            painter.drawPath(path)
        ground_indicator_element = next((el for el in self.glyph_elements_to_draw if el['type'] == 'ground_indicator'), None)
        if ground_indicator_element and last_trace_to_ground_visual_endpoint is not None: 
            indicator_attach_point=last_trace_to_ground_visual_endpoint;painter.setPen(indicator_pen);bar_width=self.indicator_symbol_base_size 
            painter.save();painter.translate(indicator_attach_point);perp_angle_rad=math.radians(chosen_ground_trace_angle_deg-90)
            p1x=-bar_width/2*math.cos(perp_angle_rad);p1y=bar_width/2*math.sin(perp_angle_rad);p2x=bar_width/2*math.cos(perp_angle_rad);p2y=-bar_width/2*math.sin(perp_angle_rad)
            painter.drawLine(QPointF(p1x,p1y),QPointF(p2x,p2y));leg_len=bar_width*0.4;leg_dx=leg_len*math.cos(math.radians(chosen_ground_trace_angle_deg+180));leg_dy=leg_len*-math.sin(math.radians(chosen_ground_trace_angle_deg+180))
            painter.drawLine(QPointF(p1x,p1y),QPointF(p1x+leg_dx,p1y+leg_dy));painter.drawLine(QPointF(p2x,p2y),QPointF(p2x+leg_dx,p2y+leg_dy));gap=self.indicator_symbol_base_size*0.3
            gap_dx_main=gap*math.cos(math.radians(chosen_ground_trace_angle_deg));gap_dy_main=gap*-math.sin(math.radians(chosen_ground_trace_angle_deg));second_symbol_center_x=gap_dx_main;second_symbol_center_y=gap_dy_main
            small_bar_w=bar_width*0.7;small_leg_h=bar_width*0.3
            sp1x=second_symbol_center_x-small_bar_w/2*math.cos(perp_angle_rad);sp1y=second_symbol_center_y+small_bar_w/2*math.sin(perp_angle_rad);sp2x=second_symbol_center_x+small_bar_w/2*math.cos(perp_angle_rad);sp2y=second_symbol_center_y-small_bar_w/2*math.sin(perp_angle_rad)
            s_leg_dx=small_leg_h*math.cos(math.radians(chosen_ground_trace_angle_deg));s_leg_dy=small_leg_h*-math.sin(math.radians(chosen_ground_trace_angle_deg))
            painter.drawLine(QPointF(sp1x,sp1y),QPointF(sp1x+s_leg_dx,sp1y+s_leg_dy));painter.drawLine(QPointF(sp2x,sp2y),QPointF(sp2x+s_leg_dx,sp2y+s_leg_dy));mid_line_len=small_leg_h*1.4
            m_start_dx=-mid_line_len/2*math.cos(math.radians(chosen_ground_trace_angle_deg));m_start_dy=-mid_line_len/2*-math.sin(math.radians(chosen_ground_trace_angle_deg));m_end_dx=mid_line_len/2*math.cos(math.radians(chosen_ground_trace_angle_deg));m_end_dy=mid_line_len/2*-math.sin(math.radians(chosen_ground_trace_angle_deg))
            painter.drawLine(QPointF(second_symbol_center_x+m_start_dx,second_symbol_center_y+m_start_dy),QPointF(second_symbol_center_x+m_end_dx,second_symbol_center_y+m_end_dy));painter.restore()

        # --- 6. Null Modifier ---
        for element in self.glyph_elements_to_draw:
            if element['type'] == 'null_modifier':
                # node_name = element['node_name'] # This is the corner node for placement
                # Using coords directly as stored by builder
                cx, cy = element['coords'][0], element['coords'][1]
                mod_radius = self.node_radius * NULL_MODIFIER_SYMBOL_RADIUS_FACTOR
                
                painter.setPen(QPen(QColor(Qt.GlobalColor.darkGray), self.ring_pen_width * 0.8)) 
                painter.setBrush(Qt.BrushStyle.NoBrush)
                
                painter.drawEllipse(QPointF(cx, cy), mod_radius, mod_radius)
                offset = mod_radius * 0.707 
                painter.drawLine(QPointF(cx - offset, cy - offset), QPointF(cx + offset, cy + offset))
                painter.drawLine(QPointF(cx - offset, cy + offset), QPointF(cx + offset, cy - offset))
                break 

        # --- 7. Node Names ---
        font = QFont(); font.setPointSize(self.font_size)
        painter.setFont(font); painter.setPen(QPen(QColor(Qt.GlobalColor.black)))
        for name, data in nodes_render_data.items():
            cx, cy = data['coords'].x(), data['coords'].y(); base_rect = QRectF(cx - self.node_radius, cy - self.node_radius, 2 * self.node_radius, 2 * self.node_radius)
            painter.drawText(base_rect, Qt.AlignmentFlag.AlignCenter, name)
            
        painter.end()