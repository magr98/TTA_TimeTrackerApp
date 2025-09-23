import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime
from tkcalendar import DateEntry
import os, sys

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
        # Manually set next id as max + 1 to keep IDs sequential
        cursor.execute("SELECT MAX(id) FROM projects")
        max_id = cursor.fetchone()[0] or 0
        next_id = max_id + 1
        cursor.execute("INSERT INTO projects (id, project_number, project_name) VALUES (?, ?, ?)", (next_id, number, name))
        conn.commit()
        load_projects()
        entry_project_number.delete(0, tk.END)
        entry_project_name.delete(0, tk.END)
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

    # Maintain sequential IDs
    cursor.execute("SELECT MAX(id) FROM work_sessions")
    max_id = cursor.fetchone()[0] or 0
    next_id = max_id + 1

    cursor.execute("INSERT INTO work_sessions (id, project_id, work_date, start_time, end_time, duration) VALUES (?, ?, ?, ?, ?, ?)",
                   (next_id, project_id, work_date, start, end, duration))
    conn.commit()
    messagebox.showinfo("Saved", f"Session saved on {work_date}: {duration:.2f} hours")
    entry_start.delete(0, tk.END)
    entry_end.delete(0, tk.END)
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
        session_tree.insert("", tk.END, values=row)


def delete_session():
    selected = session_tree.selection()
    if not selected:
        messagebox.showwarning("Select Error", "Please select a session to delete.")
        return
    session_id = session_tree.item(selected[0])['values'][0]
    cursor.execute("DELETE FROM work_sessions WHERE id = ?", (session_id,))
    conn.commit()
    # Reorder IDs to stay sequential
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
        summary_tree.insert("", tk.END, values=(project, f"{total_hours:.2f}"))

# ---------------- GUI Setup ----------------
root = tk.Tk()
root.title("Time Tracker")

# Project Management
frame_projects = tk.LabelFrame(root, text="Add Project")
frame_projects.pack(fill="x", padx=10, pady=5)

entry_project_number = tk.Entry(frame_projects)
entry_project_number.pack(side="left", padx=5)
entry_project_number.insert(0, "Project Number")

entry_project_name = tk.Entry(frame_projects)
entry_project_name.pack(side="left", padx=5)
entry_project_name.insert(0, "Project Name")

btn_add_project = tk.Button(frame_projects, text="Add Project", command=add_project)
btn_add_project.pack(side="left", padx=5)

# Time Tracking
frame_sessions = tk.LabelFrame(root, text="Track Work Time")
frame_sessions.pack(fill="x", padx=10, pady=5)

project_dropdown = ttk.Combobox(frame_sessions, state="readonly", width=40)
project_dropdown.pack(pady=5)
load_projects()

date_picker = DateEntry(frame_sessions, width=12, background='darkblue', foreground='white', borderwidth=2)
date_picker.pack(pady=5)

entry_start = tk.Entry(frame_sessions)
entry_start.pack(padx=5, pady=2)
entry_start.insert(0, "Start (HH:MM)")

entry_end = tk.Entry(frame_sessions)
entry_end.pack(padx=5, pady=2)
entry_end.insert(0, "End (HH:MM)")

btn_add_session = tk.Button(frame_sessions, text="Save Session", command=add_session)
btn_add_session.pack(pady=5)

# Session List
frame_list = tk.LabelFrame(root, text="Saved Sessions")
frame_list.pack(fill="both", expand=True, padx=10, pady=5)

columns = ("ID", "Project", "Date", "Start", "End", "Duration")
session_tree = ttk.Treeview(frame_list, columns=columns, show="headings")
for col in columns:
    session_tree.heading(col, text=col)
    session_tree.column(col, anchor="center")
session_tree.pack(fill="both", expand=True)

btn_delete_session = tk.Button(frame_list, text="Delete Selected Session", command=delete_session)
btn_delete_session.pack(pady=5)

# Summary Section
frame_summary = tk.LabelFrame(root, text="Project Summary (Total Hours)")
frame_summary.pack(fill="both", expand=True, padx=10, pady=5)

summary_columns = ("Project", "Total Hours")
summary_tree = ttk.Treeview(frame_summary, columns=summary_columns, show="headings")
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

menu = tk.Menu(root)
root.config(menu=menu)
file_menu = tk.Menu(menu, tearoff=0)
menu.add_cascade(label="File", menu=file_menu)
file_menu.add_command(label="Create build.bat", command=create_build_script)
file_menu.add_separator()
file_menu.add_command(label="Exit", command=root.quit)

# ---------------- Load initial data ----------------
load_sessions()
update_summary()

root.mainloop()