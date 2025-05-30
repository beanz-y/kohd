# kohd_translator/gui/main_window.py
from PyQt6.QtWidgets import ( # type: ignore
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QPushButton, QLabel
)
from .kohd_canvas import KohdCanvasWidget # Relative import
from kohd_core.glyph_builder import KohdGlyphBuilder # Import the builder

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Kohd Translator")
        self.setGeometry(100, 100, 450, 500)

        self.glyph_builder = KohdGlyphBuilder() # Create an instance of the builder

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)

        input_layout = QHBoxLayout()
        self.input_label = QLabel("Enter English Text:")
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Type a word (e.g., MOTHERBOARD)...")
        self.finalize_button = QPushButton("Finalize Word") # We'll connect this later

        input_layout.addWidget(self.input_label)
        input_layout.addWidget(self.text_input)
        input_layout.addWidget(self.finalize_button)
        
        main_layout.addLayout(input_layout)

        self.kohd_canvas = KohdCanvasWidget()
        main_layout.addWidget(self.kohd_canvas)

        # Connect signals
        self.text_input.textChanged.connect(self._on_text_changed)
        self.finalize_button.clicked.connect(self._on_finalize_clicked) # Connect finalize button

    def _on_text_changed(self, current_text: str):
        """Called when the text in the QLineEdit changes."""
        self.glyph_builder.reset() # Reset the builder for the new full string
        
        # Process the entire current string letter by letter
        # This handles pasting and complex edits simply for now.
        # The builder's _rebuild_glyph_elements_for_string handles the construction.
        if current_text:
            # Rebuild the word in the builder based on the current text
            for letter_char in current_text.upper(): # Process in uppercase
                # add_letter now just appends to string and calls _rebuild
                if not self.glyph_builder.add_letter(letter_char):
                    # Potentially an invalid character was entered, stop processing this string
                    # Or, display an error to the user
                    break 
        
        # Pass the generated glyph elements and active node to the canvas
        self.kohd_canvas.update_display_data(
            glyph_elements=self.glyph_builder.get_glyph_elements(),
            active_node_name=self.glyph_builder.active_node_name, # Pass current active node
            is_finalized=self.glyph_builder.is_finalized
        )
        # self.kohd_canvas.update() # update_display_data can call self.update()

    def _on_finalize_clicked(self):
        """Called when the 'Finalize Word' button is clicked."""
        self.glyph_builder.finalize_word()
        # Update canvas with finalized state
        self.kohd_canvas.update_display_data(
            glyph_elements=self.glyph_builder.get_glyph_elements(),
            active_node_name=self.glyph_builder.active_node_name, # Active node is usually None after finalize
            is_finalized=self.glyph_builder.is_finalized
        )
        # Optionally clear the text input or prepare for the next word
        # self.text_input.clear()
        print("Word finalized. Glyph elements:", self.glyph_builder.get_glyph_elements())