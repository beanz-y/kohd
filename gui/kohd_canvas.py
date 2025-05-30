# kohd_translator/gui/kohd_canvas.py
from PyQt6.QtWidgets import QWidget # type: ignore
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont # type: ignore
from PyQt6.QtCore import Qt, QRectF # type: ignore

# Assuming RING_NODE_INSET_FACTOR is for the outermost ring if multiple exist
from kohd_core.kohd_rules import NODE_POSITIONS, RING_NODE_INSET_FACTOR 

MAX_RINGS_TO_DRAW = 2 # Visual limit for concentric rings

class KohdCanvasWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(350, 350)
        self.node_radius = 20
        self.font_size = 10
        
        self.glyph_elements_to_draw = []
        self.current_active_node_name = None
        self.is_drawing_finalized = False

    def update_display_data(self, glyph_elements: list, active_node_name: str = None, is_finalized: bool = False):
        self.glyph_elements_to_draw = glyph_elements
        self.current_active_node_name = active_node_name
        self.is_drawing_finalized = is_finalized
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(Qt.GlobalColor.white))

        nodes_to_render = {} # {name: {'coords':(x,y), 'is_active':bool, 'ring_count':int}}
        for name, coords in NODE_POSITIONS.items(): # Initialize all potential nodes
            nodes_to_render[name] = {'coords': coords, 'is_active': False, 'ring_count': 0, 'name': name}
        
        for element in self.glyph_elements_to_draw:
            if element['type'] == 'node':
                name = element['name']
                if name in nodes_to_render:
                    # 'is_active' is set by the builder for the current typing state
                    # but we override based on current_active_node_name for "live" feedback
                    nodes_to_render[name]['is_active'] = element.get('is_active', False) 
                    nodes_to_render[name]['ring_count'] = element.get('ring_count', 0)
        
        # Ensure live active node is correctly marked if not finalized
        if not self.is_drawing_finalized and self.current_active_node_name and self.current_active_node_name in nodes_to_render:
            for node_info in nodes_to_render.values(): # Deactivate all others first
                node_info['is_active'] = False
            nodes_to_render[self.current_active_node_name]['is_active'] = True
        elif self.is_drawing_finalized : # if finalized, no node should be 'typing active'
             for node_info in nodes_to_render.values():
                node_info['is_active'] = False


        font = QFont()
        font.setPointSize(self.font_size)
        painter.setFont(font)

        for name, data in nodes_to_render.items():
            cx, cy = data['coords']
            base_rect = QRectF(
                cx - self.node_radius, cy - self.node_radius,
                2 * self.node_radius, 2 * self.node_radius
            )

            fill_color = QColor(Qt.GlobalColor.yellow) if data['is_active'] else QColor(Qt.GlobalColor.lightGray)
            painter.setBrush(QBrush(fill_color))
            
            painter.setPen(QPen(QColor(Qt.GlobalColor.black), 2))
            painter.drawEllipse(base_rect)

            # Draw concentric rings
            ring_count_to_draw = min(data.get('ring_count', 0), MAX_RINGS_TO_DRAW)
            if ring_count_to_draw > 0:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(Qt.GlobalColor.darkBlue), 1.5)) # Ring pen
                for i in range(ring_count_to_draw):
                    # Decrease radius for each inner ring
                    # Outermost ring uses RING_NODE_INSET_FACTOR
                    # Inner rings step in further.
                    # Example: ring 0 at 0.7, ring 1 at 0.5 (of node_radius)
                    current_ring_inset_factor = RING_NODE_INSET_FACTOR - (i * 0.2) 
                    if current_ring_inset_factor < 0.1: # Prevent rings from becoming too small/inverted
                        current_ring_inset_factor = 0.1 
                    
                    ring_radius = self.node_radius * current_ring_inset_factor
                    ring_rect = QRectF(
                        cx - ring_radius, cy - ring_radius,
                        2 * ring_radius, 2 * ring_radius
                    )
                    painter.drawEllipse(ring_rect)

            painter.setPen(QPen(QColor(Qt.GlobalColor.black))) # Reset pen for text
            painter.drawText(base_rect, Qt.AlignmentFlag.AlignCenter, name)
        
        # --- TODO: Draw Traces, Indicators, etc. based on self.glyph_elements_to_draw ---
        
        painter.end()