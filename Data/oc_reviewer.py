import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import fitz  # PyMuPDF
from PIL import Image, ImageTk
import os
import glob
import pandas as pd
import sys


class PDFReviewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Reviewer")
        
        # Initialize variables
        self.pdf_files = []
        self.current_file_index = 0
        self.pdf_document = None
        self.labels = []
        self.comments = []
        self.review_data = {}
        self.session_number = 1
        self.show_cluster_name = tk.BooleanVar(value=True)
        self.df = pd.DataFrame()
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except AttributeError:
            base_path = os.path.abspath(".")

        self.folder_path = os.path.join(base_path,"./Iterative_Plots_Compiled")
        
        # Create widgets
        self.create_widgets()
        
        # Ask for user name or resume session
        self.ask_user_name_or_resume()
        
    def ask_user_name_or_resume(self):
        choice = messagebox.askyesnocancel("Session Choice", "Do you want to resume a previous session?")
        if choice is None:
            return  # Do nothing if the user cancels the dialog
        elif choice:
            csv_file = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
            if csv_file:
                self.user_name, self.session_number = self.extract_user_and_session(csv_file)
                self.load_reviews(csv_file)
                self.load_folder(self.folder_path)  # Load the hardcoded folder path
                self.current_file_index = self.find_first_unreviewed_file()
                self.load_pdf(self.pdf_files[self.current_file_index])
                return
        else:
            self.user_name = simpledialog.askstring("User Name", "Please enter your name:")
            if not self.user_name:
                self.user_name = "user_1"
                messagebox.showinfo("Info", "No username entered. Using default username 'user_1'.")
            self.session_number = self.get_next_session_number()
            self.load_reviews()
            self.load_folder(self.folder_path)  # Load the hardcoded folder path
    
    def get_next_session_number(self):
        session_files = glob.glob('../' + f"{self.user_name}_oc_review_*.csv")
        if session_files:
            session_numbers = [int(f.split("_oc_review_")[1].split(".")[0]) for f in session_files]
            return max(session_numbers) + 1
        return 1
    
    def extract_user_and_session(self, filename):
        base_name = os.path.basename(filename)
        user_name, session_number = base_name.split("_oc_review_")
        session_number = int(session_number.split(".")[0])
        return user_name, session_number
    
    def create_widgets(self):
        # Frame for PDF display and scrollbars
        pdf_frame = tk.Frame(self.root)
        pdf_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Canvas for PDF display
        self.canvas = tk.Canvas(pdf_frame)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbars for canvas
        self.v_scroll = tk.Scrollbar(pdf_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll = tk.Scrollbar(pdf_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.canvas.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)
        
        # Frame for controls
        control_frame = tk.Frame(self.root)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Quality label buttons
        ttk.Label(control_frame, text="Quality Label:").pack(pady=5)
        self.label_var = tk.StringVar()
        self.label_var.set("")
        
        self.style = ttk.Style()
        self.style.configure("TButton", padding=6, relief="flat")
        self.style.map("TButton", background=[("active", "lightgrey")])
        self.style.configure("Selected.TButton", background="red", foreground="black", borderwidth=10, relief="solid")
        
        self.good_button = ttk.Button(control_frame, text="Good", command=lambda: self.set_label("Good"))
        self.good_button.pack(pady=5)
        
        self.average_button = ttk.Button(control_frame, text="Average", command=lambda: self.set_label("Average"))
        self.average_button.pack(pady=5)
        
        self.poor_button = ttk.Button(control_frame, text="Poor", command=lambda: self.set_label("Poor"))
        self.poor_button.pack(pady=5)
        
        # Comment entry
        ttk.Label(control_frame, text="Comments:").pack(pady=5)
        self.comment_entry = tk.Text(control_frame, height=10, width=30)
        self.comment_entry.pack(pady=5)
        
        # Navigation buttons
        self.next_button = ttk.Button(control_frame, text="Next", command=self.next_file)
        self.next_button.pack(pady=5)
        
        self.prev_button = ttk.Button(control_frame, text="Previous", command=self.prev_file)
        self.prev_button.pack(pady=5)
        
        # Close session button
        self.close_button = ttk.Button(control_frame, text="Close Session", command=self.close_session)
        self.close_button.pack(pady=5)
        
        # Show cluster name checkbox
        self.show_cluster_name_check = ttk.Checkbutton(control_frame, text="Show Cluster Name", variable=self.show_cluster_name, command=self.display_page)
        self.show_cluster_name_check.pack(pady=5)
        
        # Cluster info label
        self.cluster_info_label = ttk.Label(control_frame, text="")
        self.cluster_info_label.pack(pady=5)
        
    def set_label(self, label):
        self.label_var.set(label)
        self.update_button_styles()
    
    def update_button_styles(self):
        # Reset styles
        self.good_button.configure(style="TButton")
        self.average_button.configure(style="TButton")
        self.poor_button.configure(style="TButton")
        
        # Highlight the selected button
        if self.label_var.get() == "Good":
            self.good_button.configure(style="Selected.TButton")
        elif self.label_var.get() == "Average":
            self.average_button.configure(style="Selected.TButton")
        elif self.label_var.get() == "Poor":
            self.poor_button.configure(style="Selected.TButton")
    
    def load_folder(self, folder_path):
        self.pdf_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
        
        if self.pdf_files:
            self.current_file_index = 0
            self.load_reviews()  # Ensure reviews are loaded after loading the folder
            self.current_file_index = self.find_first_unreviewed_file()
            print(f"First unreviewed file: {self.pdf_files[self.current_file_index]}")  # For demonstration purposes
            self.load_pdf(self.pdf_files[self.current_file_index])
        else:
            messagebox.showerror("Error", "No PDF files found in the selected folder.")
    
    def load_reviews(self, csv_file=None):
        if csv_file is None:
            csv_file = '../' + f"{self.user_name}_oc_review_{self.session_number}.csv"
        if os.path.isfile(csv_file):
            self.df = pd.read_csv(csv_file)
            self.review_data = self.df.set_index('File').T.to_dict()
        else:
            self.df = pd.DataFrame(columns=["File", "Label", "Comment"])
    
    def find_first_unreviewed_file(self):
        pdf_files = self.pdf_files.copy()
        for i, pdf_file in enumerate(pdf_files):
            file_name = os.path.basename(pdf_file)
            if file_name not in self.df[self.df['Label'].notnull()]['File'].values:
                return i
        return 0
    
    def load_pdf(self, file_path):
        self.pdf_document = fitz.open(file_path)
        self.display_page()
    
    def display_page(self):
        if self.pdf_document:
            page = self.pdf_document.load_page(0)  # Load the first (and only) page
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            self.imgtk = ImageTk.PhotoImage(image=img)
            
            self.canvas.config(scrollregion=(0, 0, pix.width, pix.height))
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.imgtk)
            
            file_name = os.path.basename(self.pdf_files[self.current_file_index])
            if file_name in self.review_data:
                self.label_var.set(self.review_data[file_name]['Label'])
                self.comment_entry.delete(1.0, tk.END)
                self.comment_entry.insert(tk.END, self.review_data[file_name]['Comment'])
            else:
                self.label_var.set("")
                self.comment_entry.delete(1.0, tk.END)
            
            self.update_button_styles()
            
            # Update cluster info
            cluster_info = f"Cluster {self.current_file_index + 1} / {len(self.pdf_files)}"
            if self.show_cluster_name.get():
                cluster_info += f" - {file_name}"
            self.cluster_info_label.config(text=cluster_info)
    
    def next_file(self):
        if not self.label_var.get():
            messagebox.showerror("Error", "Please specify a quality label before proceeding.")
            return

        if self.pdf_document:
            self.save_review()  # Save review after each file
            
            if self.current_file_index < len(self.pdf_files) - 1:
                self.current_file_index += 1
                self.load_pdf(self.pdf_files[self.current_file_index])
            else:
                messagebox.showinfo("End of Files", "You have reviewed all the files.")

    def prev_file(self):
        if not self.label_var.get():
            messagebox.showerror("Error", "Please specify a quality label before proceeding.")
            return

        if self.pdf_document:
            self.save_review()  # Save review after each file
            
            if self.current_file_index > 0:
                self.current_file_index -= 1
                self.load_pdf(self.pdf_files[self.current_file_index])
            else:
                messagebox.showinfo("Start of Files", "You are at the first file.")
    
    def save_review(self):
        # Save the labels and comments for the current file
        file_name = os.path.basename(self.pdf_files[self.current_file_index])
        self.review_data[file_name] = {
            'Label': self.label_var.get(),
            'Comment': self.comment_entry.get(1.0, tk.END).strip()
        }
        
        # Update the dataframe
        if file_name not in self.df['File'].values:
            new_row = pd.DataFrame([{'File': file_name, 'Label': self.label_var.get(), 'Comment': self.comment_entry.get(1.0, tk.END).strip()}])
            self.df = pd.concat([self.df, new_row], ignore_index=True)
        else:
            self.df.loc[self.df['File'] == file_name, 'Label'] = self.label_var.get()
            self.df.loc[self.df['File'] == file_name, 'Comment'] = self.comment_entry.get(1.0, tk.END).strip()
        
        # Save to CSV file
        csv_file = f"{self.user_name}_oc_review_{self.session_number}.csv"
        self.df['Name'] = self.df['File'].apply(lambda x: x.split("_cmd_lit_prior_final.pdf")[0])
        self.df.to_csv('../' + csv_file, index=False)
        
        # print(f"Review saved for {file_name}")  # For demonstration purposes
    
    def close_session(self):
        self.save_review()
        self.root.quit()

if __name__ == "__main__":
    root = tk.Tk()
    app = PDFReviewerApp(root)
    root.mainloop()