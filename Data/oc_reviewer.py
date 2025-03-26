from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QCheckBox, QFileDialog, QMessageBox, QInputDialog, QWidget
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
import fitz  # PyMuPDF
from PIL import Image
import os
import glob
import pandas as pd
import numpy as np
import sys


class PDFReviewerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Reviewer")
        self.setGeometry(100, 100, 1200, 800)

        # Initialize variables
        self.pdf_files = []
        self.current_file_index = 0
        self.pdf_document = None
        self.labels = []
        self.comments = []
        self.review_data = {}
        self.session_number = 1
        self.show_cluster_name = True
        self.df = pd.DataFrame()
        self.selected_label = None  # To track the selected quality label
        try:
            base_path = sys._MEIPASS  # PyInstaller temp folder
        except AttributeError:
            base_path = os.path.abspath(".")

        self.folder_path = os.path.join(base_path, "Data/Iterative_Plots_Compiled")

        # Main layout
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.layout = QHBoxLayout(self.main_widget)

        # PDF display area
        self.pdf_label = QLabel("No PDF loaded")
        self.pdf_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.pdf_label, stretch=3)

        # Control panel
        self.control_panel = QVBoxLayout()
        self.layout.addLayout(self.control_panel, stretch=1)

        # Quality label buttons
        self.control_panel.addWidget(QLabel("Quality Label:"))
        self.quality_buttons = {}
        for label in ["Very Good", "Good", "Acceptable", "Poor"]:
            button = QPushButton(label)
            button.setCheckable(True)
            button.clicked.connect(lambda checked, l=label: self.set_quality_label(l))
            self.control_panel.addWidget(button)
            self.quality_buttons[label] = button

        # Comment entry
        self.comment_box = QTextEdit()
        self.comment_box.setPlaceholderText("Enter your comments here...")
        self.control_panel.addWidget(QLabel("Comments (Optional):"))
        self.control_panel.addWidget(self.comment_box)

        # Navigation buttons
        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self.prev_file)
        self.control_panel.addWidget(self.prev_button)

        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.next_file)
        self.control_panel.addWidget(self.next_button)

        # Close session button
        self.close_button = QPushButton("Close Session")
        self.close_button.clicked.connect(self.close_session)
        self.control_panel.addWidget(self.close_button)

        # Show cluster name checkbox
        self.show_cluster_checkbox = QCheckBox("Show Cluster Name")
        self.show_cluster_checkbox.setChecked(True)
        self.show_cluster_checkbox.stateChanged.connect(self.display_page)
        self.control_panel.addWidget(self.show_cluster_checkbox)

        # Cluster info label
        self.cluster_info_label = QLabel("")
        self.control_panel.addWidget(self.cluster_info_label)

        # Start the application
        self.ask_user_name_or_resume()

    def ask_user_name_or_resume(self):
        choice = QMessageBox.question(
            self, "Session Choice", "Do you want to resume a previous session?",
            QMessageBox.Yes | QMessageBox.No
        )
        if choice == QMessageBox.Yes:
            # Let the user select a previous session file
            csv_file, _ = QFileDialog.getOpenFileName(self, "Select Previous Session", "", "CSV Files (*.csv)")
            if csv_file:
                self.user_name, self.session_number = self.extract_user_and_session(csv_file)
                self.load_reviews(csv_file)
                self.load_folder(self.folder_path)
                self.current_file_index = self.find_first_unreviewed_file()
                self.load_pdf(self.pdf_files[self.current_file_index])
            else:
                QMessageBox.warning(self, "No File Selected", "No session file selected. Starting a new session.")
                self.start_new_session()
        else:
            self.start_new_session()

    def start_new_session(self):
        # Prompt the user to enter their name
        self.user_name, ok = QInputDialog.getText(self, "Enter User Name", "Please enter your name:")
        if not ok or not self.user_name.strip():
            self.user_name = "user_1"  # Default username if none is provided
            QMessageBox.information(self, "Info", "No username entered. Using default username 'user_1'.")
        # lower case the user name
        self.user_name = self.user_name.lower()
        self.session_number = self.get_next_session_number()
        self.load_reviews()
        self.load_folder(self.folder_path)

    def get_next_session_number(self):
        session_files = glob.glob(f"{self.user_name}_oc_review_*.csv")
        # remove files containing "copy" in the name
        session_files = [f for f in session_files if "copy" not in f]
        if session_files:
            session_numbers = [int(f.split("_oc_review_")[1].split(".")[0]) for f in session_files]
            return max(session_numbers) + 1
        return 1

    def extract_user_and_session(self, filename):
        base_name = os.path.basename(filename)
        user_name, session_number = base_name.split("_oc_review_")
        session_number = int(session_number.split(".")[0])
        return user_name, session_number

    def load_folder(self, folder_path):
        self.pdf_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
        if self.pdf_files:
            # randomize the order of the files, random seed is set to 42
            self.pdf_files = np.random.RandomState(42).permutation(self.pdf_files).tolist()
            self.current_file_index = 0
            self.load_reviews()
            self.current_file_index = self.find_first_unreviewed_file()
            self.load_pdf(self.pdf_files[self.current_file_index])
        else:
            QMessageBox.critical(self, "Error", "No PDF files found in the selected folder.")

    def load_reviews(self, csv_file=None):
        if csv_file is None:
            csv_file = f"{self.user_name}_oc_review_{self.session_number}.csv"
        if os.path.isfile(csv_file):
            self.df = pd.read_csv(csv_file)
            # Ensure the Comment column is treated as a string
            if 'Comment' in self.df.columns:
                self.df['Comment'] = self.df['Comment'].astype(str)
            self.review_data = self.df.set_index('File').T.to_dict()
        else:
            self.df = pd.DataFrame(columns=["File", "Label", "Comment"])

    def find_first_unreviewed_file(self):
        for i, pdf_file in enumerate(self.pdf_files):
            file_name = os.path.basename(pdf_file)
            if file_name not in self.df[self.df['Label'].notnull()]['File'].values:
                return i
        return 0

    def load_pdf(self, file_path):
        self.pdf_document = fitz.open(file_path)
        self.display_page()

    def display_page(self):
        if self.pdf_document:
            page = self.pdf_document.load_page(0)
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img.save("temp_image.png")
            pixmap = QPixmap("temp_image.png")
            self.pdf_label.setPixmap(pixmap.scaled(self.pdf_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

            file_name = os.path.basename(self.pdf_files[self.current_file_index])
            if file_name in self.review_data:
                self.set_quality_label(self.review_data[file_name]['Label'])
                # Ensure the comment is a string, even if it's NaN or missing
                comment = self.review_data[file_name].get('Comment', "")
                if pd.isna(comment):  # Check if the comment is NaN
                    comment = ""
                self.comment_box.setText(str(comment))
            else:
                self.set_quality_label(None)
                self.comment_box.clear()

            cluster_info = f"Cluster {self.current_file_index + 1} / {len(self.pdf_files)}"
            if self.show_cluster_checkbox.isChecked():
                cluster_info += f" - {file_name.split('_cmd_lit_prior_final')[0]}"
            self.cluster_info_label.setText(cluster_info)
            # delete the temp image file
            os.remove("temp_image.png")

    def set_quality_label(self, label):
        self.selected_label = label
        for lbl, button in self.quality_buttons.items():
            if lbl == label:
                button.setChecked(True)  # Ensure the button is visually checked
                button.setStyleSheet("background-color: lightblue; font-weight: bold;")  # Highlight selected button
            else:
                button.setChecked(False)  # Ensure the button is visually unchecked
                button.setStyleSheet("")  # Reset appearance for other buttons

    def next_file(self):
        if not self.selected_label:
            QMessageBox.critical(self, "Error", "Please specify a quality label before proceeding.")
            return

        self.save_review()
        if self.current_file_index < len(self.pdf_files) - 1:
            self.current_file_index += 1
            self.load_pdf(self.pdf_files[self.current_file_index])
        else:
            QMessageBox.information(self, "End of Files", "You have reviewed all the files.")

    def prev_file(self):

        self.save_review()
        if self.current_file_index > 0:
            self.current_file_index -= 1
            self.load_pdf(self.pdf_files[self.current_file_index])
        else:
            QMessageBox.information(self, "Start of Files", "You are at the first file.")

    def save_review(self):
        file_name = os.path.basename(self.pdf_files[self.current_file_index])
        self.review_data[file_name] = {
            'Label': self.selected_label,
            'Comment': self.comment_box.toPlainText().strip()
        }

        if file_name not in self.df['File'].values:
            new_row = pd.DataFrame([{'File': file_name, 'Label': self.selected_label, 'Comment': self.comment_box.toPlainText().strip()}])
            self.df = pd.concat([self.df, new_row], ignore_index=True)
        else:
            self.df.loc[self.df['File'] == file_name, 'Label'] = self.selected_label
            self.df.loc[self.df['File'] == file_name, 'Comment'] = self.comment_box.toPlainText().strip()

        # ensure that the comment column is of type string
        # if comment is nan, change it to empty string
        self.df['Comment'] = self.df['Comment'].astype(str)
        self.df.loc[self.df['Comment'] == 'nan', 'Comment'] = ""

        # ensure that the label column is of type string
        self.df['Label'] = self.df['Label'].astype(str)
        self.df.loc[self.df['Label'] == 'nan', 'Label'] = ""

        csv_file = f"{self.user_name}_oc_review_{self.session_number}.csv"
        self.df.to_csv(csv_file, index=False)

    def close_session(self):
        self.save_review()
        self.close()
        # delete the temp image file


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PDFReviewerApp()
    window.show()
    sys.exit(app.exec_())