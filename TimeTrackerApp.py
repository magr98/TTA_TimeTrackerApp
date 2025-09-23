import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime
from tkcalendar import DateEntry

# Database setup
conn = sqlite3.connect("time_tracker.db")
cursor = conn.cursor()

# Ensure fresh schema with work_date column
cursor.execute("DROP TABLE IF EXISTS projects")
cursor.execute("DROP TABLE IF EXISTS work_sessions")

cursor.execute("""
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_number TEXT,
    project_name TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS work_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    work_date TEXT,
    start_time TEXT,
    end_time TEXT,
    duration REAL,
    FOREIGN KEY (project_id) REFERENCES projects (id)
)
""")

conn.commit()

# Functions
def load_projects():
    project_dropdown['values'] = []
    cursor.execute("SELECT id, project_number, project_name FROM projects")
    projects = cursor.fetchall()
    project_dropdown['values'] = [f"{p[0]} - {p[1]}: {p[2]}" for p in projects]


def add_project():
    number = entry_project_number.get().strip()
    name = entry_project_name.get().strip()
    if number and name:
        cursor.execute("INSERT INTO projects (project_number, project_name) VALUES (?, ?)", (number, name))
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

    cursor.execute("INSERT INTO work_sessions (project_id, work_date, start_time, end_time, duration) VALUES (?, ?, ?, ?, ?)",
                   (project_id, work_date, start, end, duration))
    conn.commit()
    messagebox.showinfo("Saved", f"Session saved on {work_date}: {duration:.2f} hours")
    entry_start.delete(0, tk.END)
    entry_end.delete(0, tk.END)
    load_sessions()


def load_sessions():
    for row in session_tree.get_children():
        session_tree.delete(row)
    cursor.execute("""
        SELECT work_sessions.id, projects.project_name, work_sessions.work_date, 
               work_sessions.start_time, work_sessions.end_time, work_sessions.duration
        FROM work_sessions
        JOIN projects ON work_sessions.project_id = projects.id
        ORDER BY work_sessions.work_date DESC
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
    load_sessions()
    messagebox.showinfo("Deleted", "Session deleted successfully.")

# GUI Setup
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

# Calendar Date Picker
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

load_sessions()

root.mainloop()
