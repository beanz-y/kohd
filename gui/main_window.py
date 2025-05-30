# kohd_translator/gui/main_window.py
from PyQt6.QtWidgets import ( # type: ignore
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QPushButton, QLabel
)
from .kohd_canvas import KohdCanvasWidget # Relative import

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Kohd Translator")
        # Set a reasonable default size for the main window
        self.setGeometry(100, 100, 450, 500) # x, y, width, height

        # Central widget and layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)

        # Input area
        input_layout = QHBoxLayout()
        self.input_label = QLabel("Enter English Text:")
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Type a word...")
        self.finalize_button = QPushButton("Finalize Word")

        input_layout.addWidget(self.input_label)
        input_layout.addWidget(self.text_input)
        input_layout.addWidget(self.finalize_button)
        
        main_layout.addLayout(input_layout)

        # Kohd Canvas
        self.kohd_canvas = KohdCanvasWidget()
        main_layout.addWidget(self.kohd_canvas)

        # (We will connect signals like text_input.textChanged later)