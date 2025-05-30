# gui/main_window.py
from PyQt6.QtWidgets import ( 
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QPushButton, QLabel
)
from .kohd_canvas import KohdCanvasWidget 
from kohd_core.glyph_builder import KohdGlyphBuilder 

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Kohd Translator")
        self.setGeometry(100, 100, 450, 500)

        # Create canvas first to get its properties
        self.kohd_canvas = KohdCanvasWidget()

        # Pass canvas properties to GlyphBuilder
        self.glyph_builder = KohdGlyphBuilder(
            node_radius=self.kohd_canvas.node_radius, # Or a more direct way to get this
            get_ring_radius_method=self.kohd_canvas._get_radius_for_specific_ring_level # Pass the method
        )

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)

        input_layout = QHBoxLayout()
        self.input_label = QLabel("Enter English Text:")
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Type a word (e.g., MOTHERBOARD)...")
        self.finalize_button = QPushButton("Finalize Word")

        input_layout.addWidget(self.input_label)
        input_layout.addWidget(self.text_input)
        input_layout.addWidget(self.finalize_button)
        
        main_layout.addLayout(input_layout)
        main_layout.addWidget(self.kohd_canvas) # Add canvas to layout

        self.text_input.textChanged.connect(self._on_text_changed)
        self.finalize_button.clicked.connect(self._on_finalize_clicked)

    def _on_text_changed(self, current_text: str):
        self.glyph_builder.reset() 
        if current_text:
            for letter_char in current_text.upper(): 
                if not self.glyph_builder.add_letter(letter_char):
                    break 
        
        self.kohd_canvas.update_display_data(
            glyph_elements=self.glyph_builder.get_glyph_elements(),
            active_node_name=self.glyph_builder.active_node_name, 
            is_finalized=self.glyph_builder.is_finalized
        )

    def _on_finalize_clicked(self):
        self.glyph_builder.finalize_word()
        self.kohd_canvas.update_display_data(
            glyph_elements=self.glyph_builder.get_glyph_elements(),
            active_node_name=self.glyph_builder.active_node_name, 
            is_finalized=self.glyph_builder.is_finalized
        )
        print("Word finalized. Glyph elements:", self.glyph_builder.get_glyph_elements())