import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
import mysql.connector
from datetime import time, timedelta, datetime

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",          
    "database": "yourhospital",
    "auth_plugin": "mysql_native_password",
}

TIME_SLOTS = [
    "08:00:00", "09:00:00", "10:00:00", "11:00:00",
    "12:00:00", "13:00:00", "14:00:00", "15:00:00",
]

BUILDINGS = ["A", "B", "C", "D"]

def fmt_time(val, *, seconds=False):
    """Μετατρέπει TIME/timedelta σε 'HH:MM' ή 'HH:MM:SS'."""
    if isinstance(val, time):
        return val.strftime("%H:%M:%S" if seconds else "%H:%M")
    if isinstance(val, timedelta):
        tot = int(val.total_seconds())
        h, m = divmod(tot // 60, 60)
        s = tot % 60
        return f"{h:02d}:{m:02d}:{s:02d}" if seconds else f"{h:02d}:{m:02d}"
    return str(val)

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

def query(sql, params=None, *, fetch="all", commit=False):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params or ())
    res = cur.fetchone() if fetch == "one" else cur.fetchall()
    if commit:
        conn.commit()
    cur.close(); conn.close()
    return res

def ensure_beds_schema():
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SHOW COLUMNS FROM beds LIKE 'id_asthenh'")
    if not cur.fetchone():
        cur.execute("ALTER TABLE beds ADD id_asthenh INT NULL")
        conn.commit()
    cur.execute("""
        SELECT 1 FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'beds'
          AND COLUMN_NAME = 'id_asthenh'
          AND REFERENCED_TABLE_NAME = 'users'
    """)
    if not cur.fetchone():
        try:
            cur.execute(
                "ALTER TABLE beds ADD CONSTRAINT fk_bed_patient "
                "FOREIGN KEY (id_asthenh) REFERENCES users(id)"
            ); conn.commit()
        except mysql.connector.Error:
            pass
    cur.close(); conn.close()

def ensure_default_beds():
    for k in BUILDINGS:
        cnt = query("SELECT COUNT(*) AS c FROM beds WHERE ktirio=%s",
                     (k,), fetch="one")["c"]
        for _ in range(max(0, 15 - cnt)):
            query("INSERT INTO beds (ktirio,kathestws) VALUES (%s,'eleuthero')",
                  (k,), commit=True)

def get_available_beds():
    return query("SELECT * FROM beds WHERE kathestws='eleuthero'")

def assign_patient_to_bed(bed_id:int, amka:str):
    user = query("SELECT id FROM users WHERE amka=%s AND role='patient'",
                 (amka,), fetch="one")
    if not user:
        return False, "Δεν βρέθηκε ασθενής!"
    query("UPDATE beds SET kathestws='kleismeno', id_asthenh=%s WHERE id=%s",
          (user["id"], bed_id), commit=True)
    return True, "Το κρεβάτι ανατέθηκε!"

def release_bed(bed_id:int):
    query("UPDATE beds SET kathestws='eleuthero', id_asthenh=NULL WHERE id=%s",
          (bed_id,), commit=True)

def add_or_update_medicine(name:str, qty:int):
    row = query("SELECT id FROM medicine WHERE name=%s", (name,), fetch="one")
    if row:
        query("UPDATE medicine SET posothta=posothta+%s WHERE id=%s",
              (qty, row["id"]), commit=True)
        return "Ενημερώθηκε ποσότητα."
    query("INSERT INTO medicine (name,posothta) VALUES (%s,%s)",
          (name, qty), commit=True)
    return "Προστέθηκε νέο φάρμακο."

def get_doctors():
    return query("SELECT id, amka FROM users WHERE role='doctor'")

def get_available_slots(doc_id:int, date_:str):
    rows = query("SELECT time FROM randevou WHERE id_giatrou=%s AND date=%s",
                 (doc_id, date_))
    taken = {fmt_time(r["time"], seconds=True) for r in rows}
    return [t for t in TIME_SLOTS if t not in taken]

def book_or_insert_slot(doc_id:int, pat_id:int, date_:str, time_:str):
    row = query("""SELECT id,id_asthenh FROM randevou
                   WHERE id_giatrou=%s AND date=%s AND time=%s""",
                (doc_id, date_, time_), fetch="one")
    if row:
        if row["id_asthenh"]:
            return False, "Η ώρα έχει ήδη κλειστεί!"
        query("UPDATE randevou SET id_asthenh=%s WHERE id=%s",
              (pat_id, row["id"]), commit=True)
        return True, "Κλείστηκε ραντεβού!"
    query("INSERT INTO randevou (id_giatrou,id_asthenh,date,time)"
          "VALUES (%s,%s,%s,%s)", (doc_id, pat_id, date_, time_), commit=True)
    return True, "Κλείστηκε ραντεβού!"

def add_availability(doc_id:int, date_:str, time_:str):
    if query("""SELECT 1 FROM randevou
                WHERE id_giatrou=%s AND date=%s AND time=%s""",
             (doc_id, date_, time_), fetch="one"):
        return False, "Η ώρα υπάρχει ήδη!"
    query("INSERT INTO randevou (id_giatrou,id_asthenh,date,time)"
          "VALUES (%s,NULL,%s,%s)", (doc_id, date_, time_), commit=True)
    return True, "Προστέθηκε διαθεσιμότητα!"

def get_patient_appointments(pat_id:int):
    return query("""SELECT r.id, u.amka AS doctor_amka, r.date, r.time
                    FROM randevou r
                    JOIN users u ON u.id=r.id_giatrou
                    WHERE r.id_asthenh=%s
                    ORDER BY r.date,r.time""", (pat_id,))

def get_doctor_appointments(doc_id:int):
    return query("""SELECT r.id, u.amka AS patient_amka, r.date, r.time
                    FROM randevou r
                    JOIN users u ON u.id=r.id_asthenh
                    WHERE r.id_giatrou=%s AND r.id_asthenh IS NOT NULL
                    ORDER BY r.date,r.time""", (doc_id,))

class HospitalApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YourHospital – Hospital Management")
        self.geometry("800x600"); self.resizable(False, False)
        ensure_beds_schema(); ensure_default_beds()
        self.user = None
        self.frames = {}
        for F in (LoginFrame, RegisterFrame, PatientMenu,
                  DoctorMenu, AdminMenu):
            fr = F(self); self.frames[F.__name__] = fr
            fr.place(relwidth=1, relheight=1)
        self.show("LoginFrame")

    def show(self, name):
        f = self.frames[name]; f.tkraise()
        if hasattr(f, "refresh"): f.refresh()

    def logout(self):
        self.user = None; self.show("LoginFrame")

class LoginFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent); self.parent = parent
        tk.Label(self, text="Σύνδεση", font=("Arial",24)).pack(pady=20)
        self.amka_var = tk.StringVar(); self.pw_var = tk.StringVar()
        form = tk.Frame(self); form.pack(pady=10)
        tk.Label(form, text="AMKA:").grid(row=0,column=0,sticky="e")
        tk.Entry(form, textvariable=self.amka_var).grid(row=0,column=1)
        tk.Label(form, text="Κωδικός:").grid(row=1,column=0,sticky="e")
        tk.Entry(form, textvariable=self.pw_var, show="*").grid(row=1,column=1)
        bf = tk.Frame(self); bf.pack(pady=15)
        tk.Button(bf, text="Σύνδεση", command=self.login).grid(row=0,column=0,padx=10)
        tk.Button(bf, text="Εγγραφή νέου ασθενή",
                  command=lambda: parent.show("RegisterFrame")
                  ).grid(row=0,column=1)

    def login(self):
        amka, pw = self.amka_var.get().strip(), self.pw_var.get().strip()
        if not amka or not pw:
            messagebox.showwarning("Σφάλμα","Συμπληρώστε όλα τα πεδία!"); return
        user = query("SELECT * FROM users WHERE amka=%s AND kwdikos=%s",
                     (amka, pw), fetch="one")
        if not user:
            messagebox.showerror("Αποτυχία","Λάθος στοιχεία!"); return
        self.parent.user = user
        self.parent.show("PatientMenu" if user["role"]=="patient"
                         else "DoctorMenu" if user["role"]=="doctor"
                         else "AdminMenu")

class RegisterFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent); self.parent = parent
        tk.Label(self, text="Εγγραφή Ασθενή", font=("Arial",22)).pack(pady=20)
        self.amka_var = tk.StringVar(); self.pw_var = tk.StringVar()
        form = tk.Frame(self); form.pack()
        tk.Label(form,text="AMKA:").grid(row=0,column=0,sticky="e")
        tk.Entry(form,textvariable=self.amka_var).grid(row=0,column=1)
        tk.Label(form,text="Κωδικός:").grid(row=1,column=0,sticky="e")
        tk.Entry(form,textvariable=self.pw_var, show="*").grid(row=1,column=1)
        tk.Button(self, text="Εγγραφή", command=self.register).pack(pady=10)
        tk.Button(self, text="Back",
                  command=lambda: parent.show("LoginFrame")).pack()

    def register(self):
        amka,pw = self.amka_var.get().strip(), self.pw_var.get().strip()
        if not amka or not pw:
            messagebox.showwarning("Σφάλμα","Συμπληρώστε όλα τα πεδία!"); return
        try:
            query("INSERT INTO users (amka,kwdikos,role) VALUES(%s,%s,'patient')",
                  (amka,pw), commit=True)
        except mysql.connector.errors.IntegrityError:
            messagebox.showerror("Υπάρχει","Ο AMKA υπάρχει ήδη!"); return
        messagebox.showinfo("OK","Επιτυχής εγγραφή!")
        self.parent.show("LoginFrame")

class PatientMenu(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent); self.parent=parent
        tk.Label(self,text="Μενού Ασθενή",font=("Arial",20)).pack(pady=15)
        bf=tk.Frame(self); bf.pack(pady=20)
        tk.Button(bf,text="Διαθέσιμα κρεβάτια",width=30,
                  command=self.show_beds).grid(pady=5)
        tk.Button(bf,text="Προβολή ραντεβού",width=30,
                  command=self.show_my_appts).grid(pady=5)
        tk.Button(bf,text="Κλείσιμο ραντεβού",width=30,
                  command=lambda: BookingDialog(self,
                                                self.parent.user["id"])
                  ).grid(pady=5)
        tk.Button(bf,text="Αγορά φαρμάκου",width=30,
                  command=lambda: BuyMedicineDialog(self)).grid(pady=5)
        tk.Button(self,text="Έξοδος",command=self.parent.logout
                  ).pack(side="bottom",pady=15)

    def show_beds(self):
        rows = get_available_beds()
        win=tk.Toplevel(self); win.title("Διαθέσιμα Κρεβάτια")
        cols=("ID","Κτίριο","Κατάσταση")
        tv=ttk.Treeview(win,columns=cols,show="headings")
        for c in cols: tv.heading(c,text=c)
        for r in rows: tv.insert("", "end",
                                 values=(r["id"],r["ktirio"],r["kathestws"]))
        tv.pack(fill="both",expand=True)

    def show_my_appts(self):
        rows = get_patient_appointments(self.parent.user["id"])
        win=tk.Toplevel(self); win.title("Τα ραντεβού μου")
        cols=("ID","Γιατρός","Ημερομηνία","Ώρα")
        tv=ttk.Treeview(win,columns=cols,show="headings")
        for c in cols: tv.heading(c,text=c)
        for r in rows:
            tv.insert("", "end", values=(r["id"],r["doctor_amka"],
                                         r["date"].strftime("%d/%m/%Y"),
                                         fmt_time(r["time"])))
        tv.pack(fill="both",expand=True)

class DoctorMenu(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent); self.parent=parent
        tk.Label(self,text="Μενού Γιατρού",font=("Arial",20)).pack(pady=15)
        bf=tk.Frame(self); bf.pack(pady=20)
        tk.Button(bf,text="Προσθήκη Ραντεβού",width=35,
                  command=lambda: AddAvailabilityDialog(self,
                                                         self.parent.user["id"])
                  ).grid(pady=5)
        tk.Button(bf,text="Προβολή ραντεβού",width=35,
                  command=self.view_appts).grid(pady=5)
        tk.Button(self,text="Έξοδος",command=self.parent.logout
                  ).pack(side="bottom",pady=15)

    def view_appts(self):
        """Λίστα ραντεβού + κουμπί ακύρωσης του επιλεγμένου."""
        rows = get_doctor_appointments(self.parent.user["id"])

        win = tk.Toplevel(self)
        win.title("Προγραμματισμένα ραντεβού")

        cols = ("ID", "Ασθενής", "Ημερομηνία", "Ώρα")
        tree = ttk.Treeview(
            win, columns=cols, show="headings", selectmode="browse"
        )
        for c in cols:
            tree.heading(c, text=c)
        for r in rows:
            tree.insert(
                "", "end",
                values=(
                    r["id"],
                    r["patient_amka"],
                    r["date"].strftime("%d/%m/%Y"),
                    fmt_time(r["time"]),
                ),
            )
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        def cancel_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Επιλογή", "Επιλέξτε ένα ραντεβού.")
                return
            appt_id = tree.item(sel[0])["values"][0]
            if not messagebox.askyesno(
                "Ακύρωση", "Θέλετε σίγουρα να ακυρώσετε το ραντεβού;"
            ):
                return
            query("DELETE FROM randevou WHERE id=%s", (appt_id,), commit=True)
            tree.delete(sel[0])
            messagebox.showinfo("ΟΚ", "Το ραντεβού ακυρώθηκε.")

        tk.Button(win, text="Ακύρωση επιλεγμένου",
                  command=cancel_selected).pack(pady=5)

class AdminMenu(tk.Frame):
    def __init__(self,parent):
        super().__init__(parent); self.parent=parent
        tk.Label(self,text="Μενού Διαχειριστή",font=("Arial",20)).pack(pady=15)
        bf=tk.Frame(self); bf.pack(pady=15)
        tk.Button(bf,text="Διαχείριση φαρμάκων",width=30,
                  command=lambda: ManageMedsDialog(self)).grid(pady=5)
        tk.Button(bf,text="Διαχείριση γιατρών",width=30,
                  command=lambda: AddDoctorDialog(self)).grid(pady=5)
        tk.Button(bf,text="Διαχείριση κρεβατιών",width=30,
                  command=lambda: ManageBedsDialog(self)).grid(pady=5)
        tk.Button(self,text="Έξοδος",command=self.parent.logout
                  ).pack(side="bottom",pady=15)

class BookingDialog(tk.Toplevel):
    def __init__(self, parent, patient_id):
        super().__init__(parent); self.title("Κλείσιμο ραντεβού")
        self.patient_id=patient_id
        tk.Label(self,text="Επιλέξτε γιατρό:").grid(row=0,column=0,pady=5)
        self.doc_var=tk.StringVar()
        docs=get_doctors(); self.doc_map={d["amka"]:d["id"] for d in docs}
        ttk.Combobox(self,values=list(self.doc_map.keys()),
                     textvariable=self.doc_var,
                     state="readonly").grid(row=0,column=1)
        tk.Label(self,text="Ημερομηνία:").grid(row=1,column=0)
        self.date_var=tk.StringVar()
        DateEntry(self,textvariable=self.date_var,
                  date_pattern="yyyy-mm-dd").grid(row=1,column=1)
        tk.Button(self,text="Φόρτωση ωρών",command=self.load_slots
                  ).grid(row=1,column=2,padx=5)
        tk.Label(self,text="Ώρα:").grid(row=2,column=0)
        self.time_var=tk.StringVar()
        self.time_cb=ttk.Combobox(self,textvariable=self.time_var,
                                  state="readonly"); self.time_cb.grid(row=2,column=1)
        tk.Button(self,text="Κλείσιμο",command=self.finish
                  ).grid(row=3,column=0,columnspan=3,pady=10)

    def load_slots(self):
        amka=self.doc_var.get(); date_=self.date_var.get()
        if not amka: return
        slots=get_available_slots(self.doc_map[amka],date_)
        self.time_cb["values"]=slots
        if slots: self.time_cb.current(0)
        else: messagebox.showinfo("Καμία διαθέσιμη ώρα",
                                  "Δεν υπάρχουν διαθέσιμες ώρες.")

    def finish(self):
        amka=self.doc_var.get(); date_=self.date_var.get(); time_=self.time_var.get()
        if not amka or not time_:
            messagebox.showwarning("Σφάλμα","Συμπληρώστε όλα τα πεδία!"); return
        ok,msg=book_or_insert_slot(self.doc_map[amka],
                                   self.patient_id,date_,time_)
        (messagebox.showinfo if ok else messagebox.showerror)("Αποτέλεσμα",msg)
        if ok: self.destroy()

class AddAvailabilityDialog(tk.Toplevel):
    def __init__(self,parent,doc_id):
        super().__init__(parent); self.title("Προσθήκη Διαθεσιμότητας")
        self.doc_id=doc_id
        tk.Label(self,text="Ημερομηνία:").grid(row=0,column=0,pady=5)
        self.date_var=tk.StringVar()
        DateEntry(self,textvariable=self.date_var,
                  date_pattern="yyyy-mm-dd").grid(row=0,column=1)
        tk.Label(self,text="Ώρα:").grid(row=1,column=0)
        self.time_var=tk.StringVar(value=TIME_SLOTS[0])
        ttk.Combobox(self,values=TIME_SLOTS,textvariable=self.time_var,
                     state="readonly").grid(row=1,column=1)
        tk.Button(self,text="Αποθήκευση",command=self.save
                  ).grid(row=2,column=0,columnspan=2,pady=10)

    def save(self):
        ok,msg=add_availability(self.doc_id,
                                self.date_var.get(),self.time_var.get())
        (messagebox.showinfo if ok else messagebox.showerror)("Αποτέλεσμα",msg)
        if ok: self.destroy()

class BuyMedicineDialog(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); self.title("Αγορά Φαρμάκου")
        rows=query("SELECT * FROM medicine")
        self.med_map={f"{r['name']} ({r['posothta']})":r["id"] for r in rows}
        tk.Label(self,text="Φάρμακο:").grid(row=0,column=0,padx=5,pady=5)
        self.sel_var=tk.StringVar()
        ttk.Combobox(self,values=list(self.med_map.keys()),
                     textvariable=self.sel_var,state="readonly"
                     ).grid(row=0,column=1)
        tk.Label(self,text="Ποσότητα:").grid(row=1,column=0)
        self.qty_var=tk.IntVar(value=1)
        tk.Entry(self,textvariable=self.qty_var,width=5).grid(row=1,column=1)
        tk.Button(self,text="Αγορά",command=self.buy).grid(row=2,column=0,
                                                           columnspan=2,pady=10)

    def buy(self):
        sel=self.sel_var.get(); qty=self.qty_var.get()
        if not sel: return
        med_id=self.med_map[sel]
        stock=query("SELECT posothta FROM medicine WHERE id=%s",
                    (med_id,),fetch="one")["posothta"]
        if stock<qty:
            messagebox.showerror("Σφάλμα","Μη επαρκές απόθεμα!"); return
        query("UPDATE medicine SET posothta=posothta-%s WHERE id=%s",
              (qty,med_id),commit=True)
        messagebox.showinfo("OK","Η αγορά ολοκληρώθηκε!"); self.destroy()

class ManageBedsDialog(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); self.title("Διαχείριση Κρεβατιών")
        self.geometry("650x450"); self.refresh_tree()
        ctl=tk.Frame(self); ctl.pack(pady=10)
        tk.Label(ctl,text="Bed ID:").grid(row=0,column=0)
        self.bed_id=tk.IntVar(); tk.Entry(ctl,textvariable=self.bed_id,width=5
                                          ).grid(row=0,column=1)
        tk.Label(ctl,text="Κατάσταση:").grid(row=0,column=2)
        self.stat=tk.StringVar(value="eleuthero")
        ttk.Combobox(ctl,values=["eleuthero","kleismeno"],state="readonly",
                     textvariable=self.stat,width=10).grid(row=0,column=3)
        tk.Button(ctl,text="Ενημέρωση",command=self.update_status
                  ).grid(row=0,column=4,padx=5)
        fr=tk.Frame(self); fr.pack(pady=10)
        tk.Label(fr,text="Bed ID:").grid(row=0,column=0)
        self.bed_assign=tk.IntVar(); tk.Entry(fr,textvariable=self.bed_assign,
                                              width=5).grid(row=0,column=1)
        tk.Label(fr,text="AMKA Ασθενή:").grid(row=0,column=2)
        self.amka=tk.StringVar(); tk.Entry(fr,textvariable=self.amka,
                                           width=15).grid(row=0,column=3)
        tk.Button(fr,text="Ανάθεση",command=self.assign).grid(row=0,column=4,padx=5)
        tk.Button(fr,text="Αποδέσμευση",command=self.release).grid(row=0,column=5)
        add=tk.Frame(self); add.pack()
        tk.Label(add,text="Κτίριο:").grid(row=0,column=0)
        self.bld=tk.StringVar(value="A")
        ttk.Combobox(add,values=BUILDINGS,textvariable=self.bld,
                     width=3,state="readonly").grid(row=0,column=1)
        tk.Button(add,text="Προσθήκη",command=self.add_bed).grid(row=0,column=2,padx=5)

    def refresh_tree(self):
        if hasattr(self,"tv"): self.tv.destroy()
        cols=("ID","Κτίριο","Κατάσταση","AMKA Ασθενή")
        self.tv=ttk.Treeview(self,columns=cols,show="headings")
        for c in cols: self.tv.heading(c,text=c)
        rows=query("""SELECT b.id,b.ktirio,b.kathestws,u.amka
                      FROM beds b
                      LEFT JOIN users u ON u.id=b.id_asthenh
                      ORDER BY b.ktirio,b.id""")
        for r in rows:
            self.tv.insert("", "end", values=(r["id"],r["ktirio"],
                                              r["kathestws"],
                                              r["amka"] or "-"))
        self.tv.pack(fill="both",expand=True)

    def update_status(self):
        if not self.bed_id.get(): return
        query("UPDATE beds SET kathestws=%s WHERE id=%s",
              (self.stat.get(),self.bed_id.get()),commit=True)
        self.refresh_tree()

    def add_bed(self):
        kt=self.bld.get()
        cnt=query("SELECT COUNT(*) AS c FROM beds WHERE ktirio=%s",
                  (kt,),fetch="one")["c"]
        if cnt>=15:
            messagebox.showwarning("Όριο","Ήδη 15 κρεβάτια!"); return
        query("INSERT INTO beds (ktirio,kathestws) VALUES (%s,'eleuthero')",
              (kt,),commit=True); self.refresh_tree()

    def assign(self):
        if not self.bed_assign.get() or not self.amka.get().strip(): return
        ok,msg=assign_patient_to_bed(self.bed_assign.get(),self.amka.get().strip())
        (messagebox.showinfo if ok else messagebox.showerror)("Αποτέλεσμα",msg)
        if ok: self.refresh_tree()

    def release(self):
        if not self.bed_assign.get(): return
        release_bed(self.bed_assign.get()); self.refresh_tree()

class ManageMedsDialog(tk.Toplevel):
    """Απλή διαχείριση φαρμάκων (add/update & λίστα)."""
    def __init__(self,parent):
        super().__init__(parent); self.title("Διαχείριση Φαρμάκων")
        self.geometry("400x400"); self.refresh()
        frm=tk.Frame(self); frm.pack(pady=10)
        tk.Label(frm,text="Όνομα:").grid(row=0,column=0)
        self.name=tk.StringVar(); tk.Entry(frm,textvariable=self.name).grid(row=0,column=1)
        tk.Label(frm,text="Ποσότητα:").grid(row=1,column=0)
        self.qty=tk.IntVar(); tk.Entry(frm,textvariable=self.qty,width=6).grid(row=1,column=1)
        tk.Button(frm,text="Αποθήκευση",command=self.save).grid(row=2,columnspan=2,pady=5)

    def refresh(self):
        if hasattr(self,"tv"): self.tv.destroy()
        self.tv=ttk.Treeview(self,columns=("ID","Όνομα","Qty"),show="headings")
        for c in ("ID","Όνομα","Qty"): self.tv.heading(c,text=c)
        for r in query("SELECT * FROM medicine"):
            self.tv.insert("", "end", values=(r["id"],r["name"],r["posothta"]))
        self.tv.pack(fill="both",expand=True)

    def save(self):
        n=self.name.get().strip(); q=self.qty.get()
        if not n or q<=0: return
        msg=add_or_update_medicine(n,q)
        messagebox.showinfo("OK",msg); self.refresh()

class AddDoctorDialog(tk.Toplevel):
    """Προσθήκη νέου γιατρού (AMKA, κωδικός)."""
    def __init__(self,parent):
        super().__init__(parent); self.title("Προσθήκη Γιατρού")
        tk.Label(self,text="AMKA:").grid(row=0,column=0,padx=5,pady=5)
        self.amka=tk.StringVar(); tk.Entry(self,textvariable=self.amka).grid(row=0,column=1)
        tk.Label(self,text="Κωδικός:").grid(row=1,column=0)
        self.pw=tk.StringVar(); tk.Entry(self,textvariable=self.pw).grid(row=1,column=1)
        tk.Button(self,text="Αποθήκευση",command=self.save).grid(row=2,columnspan=2,pady=10)

    def save(self):
        a,p=self.amka.get().strip(),self.pw.get().strip()
        if not a or not p: return
        try:
            query("INSERT INTO users (amka,kwdikos,role) VALUES (%s,%s,'doctor')",
                  (a,p),commit=True)
        except mysql.connector.errors.IntegrityError:
            messagebox.showerror("Σφάλμα","Υπάρχει ήδη αυτός ο AMKA!"); return
        messagebox.showinfo("OK","Προστέθηκε γιατρός!"); self.destroy()

if __name__ == "__main__":
    app = HospitalApp()
    app.mainloop()

