# criminal_dbms_ui.py
import json
import os
import mysql.connector
import tkinter as tk
from tkinter import messagebox, simpledialog
import ttkbootstrap as tb
from ttkbootstrap.tableview import Tableview
from datetime import datetime

# ------------- CONFIG -------------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "your_password_here",
    "database": "criminal_db"
}
OFFICIAL_FILE = "official_account.json"

# ------------- Globals -------------
root = None
current_user = None  # username of logged-in user

# ------------- DB Helpers (unchanged logic) -------------
def get_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as err:
        messagebox.showerror("Database Error", f"Error connecting: {err}")
        return None

def init_db():
    conn = get_connection()
    if conn is None: 
        return
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(50) NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS criminals (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            age INT,
            gender VARCHAR(10),
            crime VARCHAR(255),
            crime_date DATE,
            status VARCHAR(50)
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS officers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            officer_rank VARCHAR(50),
            department VARCHAR(100)
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS cases (
            id INT AUTO_INCREMENT PRIMARY KEY,
            case_name VARCHAR(100) NOT NULL,
            case_date DATE,
            description TEXT,
            officer_id INT,
            FOREIGN KEY (officer_id) REFERENCES officers(id) ON DELETE SET NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS evidence (
            id INT AUTO_INCREMENT PRIMARY KEY,
            case_id INT,
            evidence_type VARCHAR(100),
            description TEXT,
            FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
        )
    ''')
    # create simple index if missing (non-destructive)
    try:
        cur.execute("""
            SELECT COUNT(1)
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE table_schema=DATABASE() AND table_name='criminals' AND index_name='idx_criminal_name'
        """)
        if cur.fetchone()[0] == 0:
            cur.execute('CREATE INDEX idx_criminal_name ON criminals(name)')
    except Exception:
        pass

    conn.commit()
    cur.close()
    conn.close()

# ------------- UI Helpers -------------
def card_frame(parent, width=420, padx=14, pady=14):
    # outer area with subtle background; inner white card with border
    frame = tk.Frame(parent, bg="#f1f3f4", bd=0)
    card = tk.Frame(frame, bg="white", highlightbackground="#e0e0e0", highlightthickness=1)
    card.pack(padx=0, pady=0)
    inner = tb.Frame(card, padding=(padx, pady))
    inner.pack(fill="both", expand=True)
    if width:
        card.config(width=width)
    return frame, card, inner

def read_official_account():
    if not os.path.exists(OFFICIAL_FILE):
        return None
    try:
        with open(OFFICIAL_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("username")
    except Exception:
        return None

def save_official_account(username):
    try:
        with open(OFFICIAL_FILE, "w", encoding="utf-8") as f:
            json.dump({"username": username}, f)
        return True
    except Exception:
        return False

# ------------- Auth (login / signup) -------------
def signup_user(uname, pwd):
    if not uname or not pwd:
        messagebox.showwarning("Input Error", "Enter username and password")
        return False
    conn = get_connection()
    if conn is None:
        return False
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (username, password) VALUES (%s,%s)", (uname, pwd))
        conn.commit()
        messagebox.showinfo("Success", "User registered! You can login now.")
        return True
    except mysql.connector.Error as e:
        messagebox.showerror("Error", f"Error: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def change_password(username):
    # Simple dialog to change password
    new = simpledialog.askstring("Change Password", "Enter new password:", show="*")
    if not new:
        return
    conn = get_connection()
    if conn is None: return
    cur = conn.cursor()
    try:
        cur.execute("UPDATE users SET password=%s WHERE username=%s", (new, username))
        conn.commit()
        messagebox.showinfo("Success", "Password changed.")
    except Exception as e:
        messagebox.showerror("Error", str(e))
    finally:
        cur.close()
        conn.close()

# ------------- CRUD (UI wrappers preserve DB logic) -------------
def add_record(table_name, fields):
    def save():
        vals = [e.get().strip() for e in entries]
        if not all(vals):
            messagebox.showwarning("Input Error", "Fill all fields")
            return
        # convert dates if field name has Date
        for i,f in enumerate(fields):
            if "Date" in f:
                try:
                    vals[i] = datetime.strptime(vals[i], "%Y-%m-%d").date()
                except Exception:
                    messagebox.showerror("Input Error", f"Invalid date for {f} (use YYYY-MM-DD)")
                    return
        cols = ", ".join([f.lower().replace(" ","_") for f in fields])
        placeholders = ", ".join(["%s"]*len(fields))
        query = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"
        try:
            conn = get_connection()
            if conn is None: return
            cur = conn.cursor()
            cur.execute(query, vals)
            conn.commit()
            messagebox.showinfo("Success", f"{table_name.capitalize()} added.")
            add_win.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            try:
                cur.close(); conn.close()
            except Exception: pass

    add_win = tb.Toplevel(root)
    add_win.title(f"Add {table_name.capitalize()}")
    add_win.geometry("600x640")
    frame, card, container = card_frame(add_win, width=640)
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    tb.Label(container, text=f"Add {table_name.capitalize()}", font=("Segoe UI", 16, "bold")).pack(pady=(6,10))
    entries = []
    for f in fields:
        tb.Label(container, text=f, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(6,2))
        ent = tb.Entry(container)
        ent.pack(fill="x", pady=(0,6))
        entries.append(ent)
    tb.Button(container, text="💾 Save", bootstyle="success", command=save).pack(pady=12)

def view_records(table_name, fields):
    view = tb.Toplevel(root)
    view.title(f"{table_name.capitalize()} Records")
    view.geometry("1100x700")
    frame, card, container = card_frame(view, width=1080)
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    tb.Label(container, text=f"{table_name.capitalize()} Records", font=("Segoe UI", 14, "bold")).pack(pady=(4,8))
    coldata = [{"text":"ID","stretch":False}] + [{"text":f} for f in fields]
    rows = []
    try:
        conn = get_connection()
        if conn is None: return
        cur = conn.cursor()
        cols = ", ".join([f.lower().replace(" ","_") for f in fields])
        cur.execute(f"SELECT id, {cols} FROM {table_name}")
        rows = cur.fetchall()
    except Exception as e:
        messagebox.showerror("Error", str(e))
        return
    finally:
        try: cur.close(); conn.close()
        except: pass

    table = Tableview(container, coldata=coldata, rowdata=rows, paginated=True, pagesize=12, searchable=True)
    table.pack(fill="both", expand=True, padx=6, pady=6)

def delete_record(table_name):
    def do_delete():
        cid = id_entry.get().strip()
        if not cid.isdigit():
            messagebox.showerror("Input Error", "Enter valid ID")
            return
        try:
            conn = get_connection()
            if conn is None: return
            cur = conn.cursor()
            cur.execute(f"DELETE FROM {table_name} WHERE id=%s", (cid,))
            conn.commit()
            messagebox.showinfo("Deleted", f"Record ID {cid} deleted.")
            del_win.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            try: cur.close(); conn.close()
            except: pass

    del_win = tb.Toplevel(root)
    del_win.title(f"Delete {table_name.capitalize()}")
    del_win.geometry("420x220")
    frame, card, container = card_frame(del_win, width=400)
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    tb.Label(container, text=f"Delete {table_name.capitalize()}", font=("Segoe UI", 14, "bold")).pack(pady=(4,8))
    tb.Label(container, text="Enter ID to Delete:", font=("Segoe UI", 11)).pack(anchor="w")
    id_entry = tb.Entry(container)
    id_entry.pack(fill="x", pady=8)
    tb.Button(container, text="🗑 Delete", bootstyle="danger", command=do_delete).pack()

def update_record(table_name, fields):
    def load_data():
        cid = id_entry.get().strip()
        if not cid.isdigit():
            messagebox.showerror("Input Error", "Enter valid ID")
            return
        try:
            conn = get_connection()
            if conn is None: return
            cur = conn.cursor()
            cols = ", ".join([f.lower().replace(" ","_") for f in fields])
            cur.execute(f"SELECT {cols} FROM {table_name} WHERE id=%s", (cid,))
            row = cur.fetchone()
            if not row:
                messagebox.showerror("Not Found", "No record found")
                return
            for i,v in enumerate(row):
                entries[i].delete(0, tk.END)
                entries[i].insert(0, v if v is not None else "")
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            try: cur.close(); conn.close()
            except: pass

    def save_update():
        cid = id_entry.get().strip()
        vals = [e.get().strip() for e in entries]
        if not cid.isdigit():
            messagebox.showerror("Input Error", "Enter valid ID")
            return
        # date conversion
        for i,f in enumerate(fields):
            if "Date" in f:
                try:
                    vals[i] = datetime.strptime(vals[i], "%Y-%m-%d").date()
                except Exception:
                    messagebox.showerror("Input Error", f"Invalid date for {f}")
                    return
        placeholders = ", ".join([f"{f.lower().replace(' ','_')}=%s" for f in fields])
        query = f"UPDATE {table_name} SET {placeholders} WHERE id=%s"
        try:
            conn = get_connection()
            if conn is None: return
            cur = conn.cursor()
            cur.execute(query, (*vals, cid))
            conn.commit()
            messagebox.showinfo("Updated", "Record updated successfully!")
            update_win.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            try: cur.close(); conn.close()
            except: pass

    update_win = tb.Toplevel(root)
    update_win.title(f"Update {table_name.capitalize()}")
    update_win.geometry("640x720")
    frame, card, container = card_frame(update_win, width=620)
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    tb.Label(container, text=f"Update {table_name.capitalize()}", font=("Segoe UI", 14, "bold")).pack(pady=(4,8))
    tb.Label(container, text="Enter Record ID:", font=("Segoe UI", 11)).pack(anchor="w")
    id_entry = tb.Entry(container)
    id_entry.pack(fill="x", pady=(6,10))
    tb.Button(container, text="Load Data", bootstyle="info", command=load_data).pack(pady=(0,10))

    entries = []
    for f in fields:
        tb.Label(container, text=f, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ent = tb.Entry(container)
        ent.pack(fill="x", pady=(4,8))
        entries.append(ent)
    tb.Button(container, text="💾 Save Update", bootstyle="success", command=save_update).pack(pady=10)

# ------------- Dashboard / Management Panel -------------
def get_counts():
    counts = {"criminals":0, "officers":0, "cases":0, "evidence":0}
    try:
        conn = get_connection()
        if conn is None: return counts
        cur = conn.cursor()
        for k in list(counts.keys()):
            try:
                cur.execute(f"SELECT COUNT(1) FROM {k}")
                r = cur.fetchone()
                counts[k] = r[0] if r and r[0] is not None else 0
            except Exception:
                counts[k] = 0
        cur.close()
        conn.close()
    except Exception:
        pass
    return counts

def create_navbar(parent, username=None):
    nav = tb.Frame(parent)
    nav.pack(fill="x", side="top")
    left = tb.Frame(nav)
    left.pack(side="left", padx=12)
    tb.Label(left, text="🔐 Criminal DBMS", font=("Segoe UI", 16, "bold")).pack(side="left")
    right = tb.Frame(nav)
    right.pack(side="right", padx=12)

    def show_profile():
        # Profile popup: username, change password, save as official account
        prof = tb.Toplevel(root)
        prof.title("Profile")
        prof.geometry("360x220")
        f, c, inner = card_frame(prof, width=340, padx=12, pady=12)
        f.pack(fill="both", expand=True, padx=6, pady=6)
        tb.Label(inner, text="Profile", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(2,8))
        tb.Label(inner, text=f"Username: {username}", font=("Segoe UI", 11)).pack(anchor="w", pady=(4,6))

        # show if official
        official = read_official_account()
        status = "Yes" if official == username else "No"
        tb.Label(inner, text=f"Official Account Saved: {status}", font=("Segoe UI", 10)).pack(anchor="w", pady=(0,8))

        tb.Button(inner, text="Change Password", bootstyle="warning", command=lambda: (prof.destroy(), change_password(username))).pack(fill="x", pady=(6,6))
        def save_official_action():
            if save_official_account(username):
                messagebox.showinfo("Saved", f"{username} saved as official account.")
                prof.destroy()
            else:
                messagebox.showerror("Error", "Failed to save official account.")
        tb.Button(inner, text="Save as Official Account", bootstyle="info", command=save_official_action).pack(fill="x", pady=(0,4))
        tb.Button(inner, text="Close", bootstyle="secondary", command=prof.destroy).pack(fill="x", pady=(6,0))

    tb.Button(right, text="👤 Profile", bootstyle="outline", width=10, command=show_profile).pack(side="left", padx=6)
    tb.Button(right, text="Logout", bootstyle="outline", width=10, command=logout).pack(side="left", padx=6)

def logout():
    global current_user
    current_user = None
    for w in root.winfo_children():
        w.destroy()
    frame = tb.Frame(root, padding=24)
    frame.pack(expand=True, fill="both")
    login_screen(frame)

def refresh_dashboard(container, username):
    # simple refresh by re-rendering the main page
    for w in root.winfo_children():
        w.destroy()
    main_page(username)

def main_page(username=None):
    global current_user
    current_user = username
    for w in root.winfo_children():
        w.destroy()
    create_navbar(root, username=username)

    content = tb.Frame(root, padding=16)
    content.pack(fill="both", expand=True)

    tb.Label(content, text="Dashboard", font=("Segoe UI", 18, "bold")).pack(anchor="w")
    tb.Label(content, text=f"Welcome {username or ''} — Overview and quick actions", foreground="#6c757d").pack(anchor="w", pady=(0,8))

    counts = get_counts()
    tiles = tb.Frame(content)
    tiles.pack(fill="x", pady=10)

    def make_tile(parent, title, count, color, target_table=None):
        tile = tk.Frame(parent, bg="white", highlightbackground="#e6e9ee", highlightthickness=1)
        inner = tb.Frame(tile, padding=10)
        inner.pack(fill="both", expand=True)
        tb.Label(inner, text=title, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tb.Label(inner, text=str(count), font=("Segoe UI", 20, "bold"), foreground=color).pack(anchor="w", pady=(6,0))
        if target_table:
            tb.Button(inner, text="Manage →", bootstyle="outline", command=lambda: view_records(target_table, get_fields_for_table(target_table))).pack(anchor="e", pady=(8,0))
        return tile

    t1 = make_tile(tiles, "Criminals", counts.get("criminals",0), "#d9534f", "criminals")
    t2 = make_tile(tiles, "Officers", counts.get("officers",0), "#28a745", "officers")
    t3 = make_tile(tiles, "Cases Filed", counts.get("cases",0), "#f0ad4e", "cases")
    t4 = make_tile(tiles, "Evidence Items", counts.get("evidence",0), "#17a2b8", "evidence")

    t1.grid(row=0, column=0, padx=8, sticky="nsew")
    t2.grid(row=0, column=1, padx=8, sticky="nsew")
    t3.grid(row=0, column=2, padx=8, sticky="nsew")
    t4.grid(row=0, column=3, padx=8, sticky="nsew")
    tiles.columnconfigure(0, weight=1); tiles.columnconfigure(1, weight=1)
    tiles.columnconfigure(2, weight=1); tiles.columnconfigure(3, weight=1)

    # quick actions
    action_row = tb.Frame(content)
    action_row.pack(fill="x", pady=(12,6))
    tb.Button(action_row, text="Open Management Panel", bootstyle="primary", command=lambda: show_management_panel(content)).pack(side="left")
    tb.Button(action_row, text="Refresh", bootstyle="info", command=lambda: refresh_dashboard(content, username)).pack(side="left", padx=8)

    # management panel visible by default
    show_management_panel(content)

def get_fields_for_table(table_name):
    # mapping of display field names for tableview and CRUD forms
    if table_name == "criminals":
        return ["Name","Age","Gender","Crime","Crime Date","Status"]
    if table_name == "officers":
        return ["Name","Officer Rank","Department"]
    if table_name == "cases":
        return ["Case Name","Case Date","Description","Officer ID"]
    if table_name == "evidence":
        return ["Case ID","Evidence Type","Description"]
    return []

def show_management_panel(parent):
    existing = getattr(parent, "_management_panel", None)
    if existing:
        existing.destroy()
    panel = tb.Frame(parent)
    panel.pack(fill="both", expand=True, pady=(10,0))
    parent._management_panel = panel

    tb.Label(panel, text="Management Panel", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0,8))
    cards = tb.Frame(panel)
    cards.pack(fill="both", expand=True)

    buttons_map = {
        "Criminals": ("criminals", get_fields_for_table("criminals")),
        "Officers": ("officers", get_fields_for_table("officers")),
        "Cases": ("cases", get_fields_for_table("cases")),
        "Evidence": ("evidence", get_fields_for_table("evidence")),
    }

    def build_card(parent, title, table, fields, r, c):
        frame, card, inner = card_frame(parent, width=340)
        frame.grid(row=r, column=c, padx=12, pady=12, sticky="nsew")
        tb.Label(inner, text=title, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0,8))
        tb.Button(inner, text=f"➕ Add {title}", bootstyle="success", width=26, command=lambda:add_record(table, fields)).pack(pady=6)
        tb.Button(inner, text=f"✏ Update {title}", bootstyle="warning", width=26, command=lambda:update_record(table, fields)).pack(pady=6)
        tb.Button(inner, text=f"🗑 Delete {title}", bootstyle="danger", width=26, command=lambda:delete_record(table)).pack(pady=6)
        tb.Button(inner, text=f"📋 View {title}", bootstyle="info", width=26, command=lambda:view_records(table, fields)).pack(pady=6)
        return frame

    cards.grid_columnconfigure(0, weight=1)
    cards.grid_columnconfigure(1, weight=1)
    build_card(cards, "Criminals", "criminals", buttons_map["Criminals"][1], 0, 0)
    build_card(cards, "Officers", "officers", buttons_map["Officers"][1], 0, 1)
    build_card(cards, "Cases", "cases", buttons_map["Cases"][1], 1, 0)
    build_card(cards, "Evidence", "evidence", buttons_map["Evidence"][1], 1, 1)

# ------------- Login Screen (clean centered card) -------------
def login_screen(root_frame):
    for w in root_frame.winfo_children():
        w.destroy()
    container = tb.Frame(root_frame)
    container.pack(fill="both", expand=True)
    frame, card, inner = card_frame(container, width=420)
    frame.place(relx=0.5, rely=0.45, anchor="n")

    top = tb.Frame(inner); top.pack(pady=(4,8))
    tb.Label(top, text="🔐", font=("Segoe UI", 20)).pack(side="left")
    tb.Label(top, text="Criminal DBMS", font=("Segoe UI", 20, "bold")).pack(side="left", padx=6)
    tb.Label(inner, text="Sign in to your account", font=("Segoe UI", 10), foreground="#6c757d").pack(pady=(2,8))

    tb.Label(inner, text="Username", font=("Segoe UI", 10, "bold")).pack(anchor="w")
    username_entry = tb.Entry(inner); username_entry.pack(fill="x", pady=(4,8))
    tb.Label(inner, text="Password", font=("Segoe UI", 10, "bold")).pack(anchor="w")
    password_entry = tb.Entry(inner, show="•"); password_entry.pack(fill="x", pady=(4,8))

    btnrow = tb.Frame(inner); btnrow.pack(fill="x", pady=(8,6))

    def do_login():
        uname = username_entry.get().strip()
        pwd = password_entry.get().strip()
        if not uname or not pwd:
            messagebox.showwarning("Input Error", "Enter username and password")
            return
        conn = get_connection()
        if conn is None: return
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (uname, pwd))
        if cur.fetchone():
            cur.close(); conn.close()
            main_page(username=uname)
        else:
            messagebox.showerror("Login Failed", "Invalid username or password")
            cur.close(); conn.close()

    tb.Button(btnrow, text="Login", bootstyle="success", width=14, command=do_login).pack(side="left", padx=(0,6))
    tb.Button(btnrow, text="Signup", bootstyle="info", width=14, command=lambda: signup_user(username_entry.get().strip(), password_entry.get().strip())).pack(side="left")

    tb.Label(inner, text="Tip: Sign up if you don't have an account yet.", font=("Segoe UI", 9), foreground="#6c757d").pack(pady=(12,0))

# ------------- START APP -------------
def setup_styles():
    tb.Style(theme="litera")

def main():
    global root
    root = tb.Window(themename="litera")
    root.title("Criminal DBMS")
    root.geometry("1400x900")
    root.minsize(1200,700)
    setup_styles()
    init_db()
    main_container = tb.Frame(root, padding=12)
    main_container.pack(fill="both", expand=True)
    login_screen(main_container)
    root.mainloop()

if __name__ == "__main__":
    main()
