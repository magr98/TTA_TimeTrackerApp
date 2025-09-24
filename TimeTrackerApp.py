import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, Menu
import sqlite3
from datetime import datetime
from tkcalendar import DateEntry
import os, sys
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# Ensure DB path is next to the .py or .exe
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

db_path = os.path.join(base_dir, "time_tracker.db")

# Database setup
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_number TEXT,
    project_name TEXT
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS work_sessions (
    id INTEGER PRIMARY KEY,
    project_id INTEGER,
    work_date TEXT,
    start_time TEXT,
    end_time TEXT,
    duration REAL,
    FOREIGN KEY (project_id) REFERENCES projects (id)
)""")

conn.commit()

# ---------------- Functions ----------------
def load_projects():
    project_dropdown['values'] = []
    cursor.execute("SELECT id, project_number, project_name FROM projects")
    projects = cursor.fetchall()
    project_dropdown['values'] = [f"{p[0]} - {p[1]}: {p[2]}" for p in projects]


def add_project():
    number = entry_project_number.get().strip()
    name = entry_project_name.get().strip()
    if number and name:
        cursor.execute("SELECT MAX(id) FROM projects")
        max_id = cursor.fetchone()[0] or 0
        next_id = max_id + 1
        cursor.execute("INSERT INTO projects (id, project_number, project_name) VALUES (?, ?, ?)", (next_id, number, name))
        conn.commit()
        load_projects()
        entry_project_number.delete(0, ctk.END)
        entry_project_name.delete(0, ctk.END)
    else:
        messagebox.showwarning("Input Error", "Please enter both project number and name.")


def add_session():
    project_info = project_dropdown.get()
    start = entry_start.get().strip()
    end = entry_end.get().strip()
    work_date = date_picker.get_date().strftime("%Y-%m-%d")

    if not project_info or not start or not end or not work_date:
        messagebox.showwarning("Input Error", "Please select project, date, and enter times.")
        return

    try:
        start_dt = datetime.strptime(start, "%H:%M")
        end_dt = datetime.strptime(end, "%H:%M")
        if end_dt < start_dt:
            messagebox.showwarning("Input Error", "End time must be after start time.")
            return
        duration = (end_dt - start_dt).seconds / 3600
    except ValueError:
        messagebox.showwarning("Format Error", "Please use HH:MM format for times.")
        return

    project_id = int(project_info.split(" - ")[0])

    cursor.execute("SELECT MAX(id) FROM work_sessions")
    max_id = cursor.fetchone()[0] or 0
    next_id = max_id + 1

    cursor.execute("INSERT INTO work_sessions (id, project_id, work_date, start_time, end_time, duration) VALUES (?, ?, ?, ?, ?, ?)",
                   (next_id, project_id, work_date, start, end, duration))
    conn.commit()
    messagebox.showinfo("Saved", f"Session saved on {work_date}: {duration:.2f} hours")
    entry_start.delete(0, ctk.END)
    entry_end.delete(0, ctk.END)
    load_sessions()
    update_summary()


def load_sessions():
    for row in session_tree.get_children():
        session_tree.delete(row)
    cursor.execute("""
        SELECT work_sessions.id, projects.project_name, work_sessions.work_date, 
               work_sessions.start_time, work_sessions.end_time, work_sessions.duration
        FROM work_sessions
        JOIN projects ON work_sessions.project_id = projects.id
        ORDER BY work_sessions.id ASC
    """)
    for row in cursor.fetchall():
        session_tree.insert("", ctk.END, values=row)


def delete_session():
    selected = session_tree.selection()
    if not selected:
        messagebox.showwarning("Select Error", "Please select a session to delete.")
        return
    session_id = session_tree.item(selected[0])['values'][0]
    cursor.execute("DELETE FROM work_sessions WHERE id = ?", (session_id,))
    conn.commit()
    cursor.execute("SELECT id FROM work_sessions ORDER BY id ASC")
    ids = cursor.fetchall()
    for idx, row in enumerate(ids, start=1):
        cursor.execute("UPDATE work_sessions SET id = ? WHERE id = ?", (idx, row[0]))
    conn.commit()
    load_sessions()
    update_summary()
    messagebox.showinfo("Deleted", "Session deleted successfully.")


def update_summary():
    for row in summary_tree.get_children():
        summary_tree.delete(row)
    cursor.execute("""
        SELECT projects.project_name, SUM(work_sessions.duration)
        FROM work_sessions
        JOIN projects ON work_sessions.project_id = projects.id
        GROUP BY projects.project_name
    """)
    for row in cursor.fetchall():
        project, total_hours = row
        summary_tree.insert("", ctk.END, values=(project, f"{total_hours:.2f}"))


# Export work sessions to PDF
def export_pdf():
    pdf_path = os.path.join(base_dir, "work_sessions.pdf")
    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "Work Sessions Report")

    c.setFont("Helvetica", 10)
    cursor.execute("""
        SELECT work_sessions.id, projects.project_name, work_sessions.work_date,
               work_sessions.start_time, work_sessions.end_time, work_sessions.duration
        FROM work_sessions
        JOIN projects ON work_sessions.project_id = projects.id
        ORDER BY work_sessions.id ASC
    """)
    rows = cursor.fetchall()

    y = height - 80
    for row in rows:
        text = f"ID: {row[0]} | Project: {row[1]} | Date: {row[2]} | {row[3]} - {row[4]} | {row[5]:.2f}h"
        c.drawString(50, y, text)
        y -= 15
        if y < 50:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = height - 50

    c.save()
    messagebox.showinfo("Exported", f"PDF exported successfully to {pdf_path}")

# ---------------- Inline Edit ----------------
def on_double_click(event):
    # Identify the clicked item and column
    item = session_tree.identify_row(event.y)
    column = session_tree.identify_column(event.x)
    if not item or not column:
        return

    col_index = int(column.replace('#', '')) - 1
    # Don't allow editing the ID column (index 0)
    if col_index == 0:
        return

    # Get current value
    values = list(session_tree.item(item, 'values'))
    old_value = values[col_index]

    # Get bounding box for the clicked cell
    bbox = session_tree.bbox(item, column)
    if not bbox:
        return
    x, y, width, height = bbox

    # Use a regular Tk Entry (safer overlay on Treeview)
    edit_var = tk.StringVar(value=old_value)
    entry = tk.Entry(session_tree, textvariable=edit_var)
    entry.place(x=x, y=y, width=width, height=height)
    entry.focus_set()

    def finish(event=None):
        new_value = edit_var.get().strip()
        entry.destroy()

        session_id = values[0]
        try:
            # Column mapping: 0=ID,1=Project,2=Date,3=Start,4=End,5=Duration
            if col_index == 1:  # Project: accept either "id - ..." or exact project name
                pid = None
                if ' - ' in new_value:
                    try:
                        pid = int(new_value.split(' - ')[0])
                    except:
                        pid = None
                if pid is None:
                    cursor.execute("SELECT id FROM projects WHERE project_name = ?", (new_value,))
                    r = cursor.fetchone()
                    if r:
                        pid = r[0]
                    else:
                        messagebox.showerror("Error", "Project not found. Enter existing project id - number: name or exact project name.")
                        load_sessions()
                        return
                # Update work_sessions.project_id
                cursor.execute("UPDATE work_sessions SET project_id = ? WHERE id = ?", (pid, session_id))
                conn.commit()
                cursor.execute("SELECT project_name FROM projects WHERE id = ?", (pid,))
                values[1] = cursor.fetchone()[0]

            elif col_index == 2:  # Date
                try:
                    datetime.strptime(new_value, "%Y-%m-%d")
                except:
                    messagebox.showerror("Format Error", "Date must be YYYY-MM-DD")
                    load_sessions()
                    return
                cursor.execute("UPDATE work_sessions SET work_date = ? WHERE id = ?", (new_value, session_id))
                conn.commit()
                values[2] = new_value

            elif col_index == 3:  # Start
                try:
                    datetime.strptime(new_value, "%H:%M")
                except:
                    messagebox.showerror("Format Error", "Start time must be HH:MM")
                    load_sessions()
                    return
                cursor.execute("UPDATE work_sessions SET start_time = ? WHERE id = ?", (new_value, session_id))
                conn.commit()
                values[3] = new_value

            elif col_index == 4:  # End
                try:
                    datetime.strptime(new_value, "%H:%M")
                except:
                    messagebox.showerror("Format Error", "End time must be HH:MM")
                    load_sessions()
                    return
                cursor.execute("UPDATE work_sessions SET end_time = ? WHERE id = ?", (new_value, session_id))
                conn.commit()
                values[4] = new_value

            elif col_index == 5:  # Duration
                try:
                    dur = float(new_value)
                except:
                    messagebox.showerror("Format Error", "Duration must be a number")
                    load_sessions()
                    return
                cursor.execute("UPDATE work_sessions SET duration = ? WHERE id = ?", (dur, session_id))
                conn.commit()
                values[5] = f"{dur:.2f}"

            # If start or end changed, recalculate duration
            if col_index in (3, 4):
                cursor.execute("SELECT start_time, end_time FROM work_sessions WHERE id = ?", (session_id,))
                s, e = cursor.fetchone()
                try:
                    st = datetime.strptime(s, "%H:%M")
                    et = datetime.strptime(e, "%H:%M")
                    if et > st:
                        new_dur = (et - st).seconds / 3600
                        cursor.execute("UPDATE work_sessions SET duration = ? WHERE id = ?", (new_dur, session_id))
                        conn.commit()
                        values[5] = f"{new_dur:.2f}"
                except:
                    pass

            session_tree.item(item, values=values)
            update_summary()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            load_sessions()

    entry.bind('<Return>', finish)
    entry.bind('<FocusOut>', finish)


# ---------------- GUI Setup ----------------
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.title("Time Tracker")

# Match Treeview background with CTk window background
style = ttk.Style()
style.theme_use("default")
style.configure("Treeview",
                background=root.cget("bg"),
                fieldbackground=root.cget("bg"),
                foreground="white")
style.map("Treeview", background=[("selected", "#1f538d")])

# Project Management
frame_projects = ctk.CTkFrame(root)
frame_projects.pack(fill="x", padx=10, pady=5)

entry_project_number = ctk.CTkEntry(frame_projects, placeholder_text="Project Number")
entry_project_number.pack(side="left", padx=5)

entry_project_name = ctk.CTkEntry(frame_projects, placeholder_text="Project Name")
entry_project_name.pack(side="left", padx=5)

btn_add_project = ctk.CTkButton(frame_projects, text="Add Project", command=add_project)
btn_add_project.pack(side="left", padx=5)

# Time Tracking
frame_sessions = ctk.CTkFrame(root)
frame_sessions.pack(fill="x", padx=10, pady=5)

project_dropdown = ttk.Combobox(frame_sessions, state="readonly", width=40)
project_dropdown.pack(pady=5)
load_projects()

date_picker = DateEntry(frame_sessions, width=12, background='darkblue', foreground='white', borderwidth=2)
date_picker.pack(pady=5)

entry_start = ctk.CTkEntry(frame_sessions, placeholder_text="Start (HH:MM)")
entry_start.pack(padx=5, pady=2)

entry_end = ctk.CTkEntry(frame_sessions, placeholder_text="End (HH:MM)")
entry_end.pack(padx=5, pady=2)

btn_add_session = ctk.CTkButton(frame_sessions, text="Save Session", command=add_session)
btn_add_session.pack(pady=5)

# Session List
frame_list = ctk.CTkFrame(root)
frame_list.pack(fill="both", expand=True, padx=10, pady=5)

columns = ("ID", "Project", "Date", "Start", "End", "Duration")
session_tree = ttk.Treeview(frame_list, columns=columns, show="headings", style="Treeview")
for col in columns:
    session_tree.heading(col, text=col)
    session_tree.column(col, anchor="center")
session_tree.pack(fill="both", expand=True)
session_tree.bind('<Double-1>', on_double_click)

btn_delete_session = ctk.CTkButton(frame_list, text="Delete Selected Session", command=delete_session)
btn_delete_session.pack(pady=5)

# Right-click context menu
session_menu = Menu(root, tearoff=0)
session_menu.add_command(label="Delete", command=lambda: None)

def show_session_menu(event):
    selected = session_tree.identify_row(event.y)
    if selected:
        session_tree.selection_set(selected)
        session_menu.post(event.x_root, event.y_root)

session_tree.bind("<Button-3>", show_session_menu)

# Summary Section
frame_summary = ctk.CTkFrame(root)
frame_summary.pack(fill="both", expand=True, padx=10, pady=5)

summary_columns = ("Project", "Total Hours")
summary_tree = ttk.Treeview(frame_summary, columns=summary_columns, show="headings", style="Treeview")
for col in summary_columns:
    summary_tree.heading(col, text=col)
    summary_tree.column(col, anchor="center")
summary_tree.pack(fill="both", expand=True)

# ---------------- Build Script Menu ----------------
def create_build_script():
    bat_path = os.path.join(base_dir, 'build.bat')
    with open(bat_path, 'w') as f:
        f.write(f'@echo off\n')
        f.write(f'cd /d "{base_dir}"\n')
        f.write(f'"{sys.executable}" -m PyInstaller --onefile --noconsole TimeTrackerApp.py\n')
        f.write(f'pause\n')
    messagebox.showinfo("Build Script Created", f"A build.bat script was created at {bat_path}.\nDouble-click it to build the exe.")

menubar = Menu(root)
file_menu = Menu(menubar, tearoff=0)
file_menu.add_command(label="Export PDF", command=export_pdf)
file_menu.add_separator()
file_menu.add_command(label="Create build.bat", command=create_build_script)
file_menu.add_separator()
file_menu.add_command(label="Exit", command=root.quit)
menubar.add_cascade(label="File", menu=file_menu)
root.config(menu=menubar)

# ---------------- Load initial data ----------------
load_sessions()
update_summary()

root.mainloop()
