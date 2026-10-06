import tkinter as tk 
from tkinter import messagebox

# QUEUE DATA
queue = []

queue_displays = []

client_notifications = {}

def refresh_queue_displays():
    for display in queue_displays[:]:
        if not display.winfo_exists():
            queue_displays.remove(display)
            continue

        display.delete(0, tk.END)

        if not queue:
            display.insert(tk.END, "The queue is currently empty.")
        else:
            for position, client in enumerate(queue, start=1):
                display.insert(
                    tk.END,
                    f"{position}. {client['name']} - {client['issue']} "
                    f"({position - 1} people ahead)"
                )

# ----------------------------
# CLIENT SCREEN
# ----------------------------

def open_client_screen():

    client_window = tk.Toplevel(root)
    client_window.title("Client - IT Help Desk")
    client_window.geometry("700x800")
    client_window.configure(bg="#F4F6F8")
    
    current_client = None 



    # Client page title

    client_title = tk.Label(
        client_window,
        text="IT Support Queue",
        font=("Arial", 26, "bold"),
        bg="#F4F6F8",
        fg="#1F2937"
    )

    client_title.pack(pady=30)


    # Instructions

    instruction_label = tk.Label(
        client_window,
        text="Enter your details to join the queue",
        font=("Arial", 14),
        bg="#F4F6F8",
        fg="#6B7280"
    )

    instruction_label.pack(pady=10)


    # Name label

    name_label = tk.Label(
        client_window,
        text="Your Name:",
        font=("Arial", 13, "bold"),
        bg="#F4F6F8",
        fg="#1F2937"
    )

    name_label.pack(pady=(20, 5))


    # Name entry

    name_entry = tk.Entry(
        client_window,
        font=("Arial", 14),
        width=30
    )

    name_entry.pack(pady=5)


    # Problem label

    problem_label = tk.Label(
        client_window,
        text="Reason for IT Support:",
        font=("Arial", 13, "bold"),
        bg="#F4F6F8",
        fg="#1F2937"
    )

    problem_label.pack(pady=(25, 5))


    # IT support options

    support_options = [
         "Password / Account Issue",
        "Wi-Fi / Network Issue",
        "Software Issue",
        "Hardware Issue",
        "Printing Issue",
        "Email Issue",
        "Other"
    ]


    selected_problem = tk.StringVar()

    selected_problem.set("Select an issue")


    problem_menu = tk.OptionMenu(
        client_window,
        selected_problem,
        *support_options
    )

    problem_menu.config(
        font=("Arial", 12),
        width=25
    )

    problem_menu.pack(pady=5)

        # Notify this client when the admin serves them
    def notify_client():
        nonlocal current_client

        if current_client is None:
            return

        name = current_client["name"]
        current_client = None

        messagebox.showinfo(
            "Your Turn",
            f"{name}, it is now your turn!\n"
            "Please go to the IT help desk.",
            parent=client_window
        )

        # Join Queue function
    def join_queue():
        nonlocal current_client

        if current_client is not None:
            messagebox.showwarning(
                "Already Joined",
                "You are already in the queue.",
                parent=client_window
            )
            return

        name = name_entry.get().strip()
        issue = selected_problem.get()

        if not name:
            messagebox.showwarning(
                "Missing Name",
                "Please enter your name.",
                parent=client_window
            )
            return

        if issue not in support_options:
            messagebox.showwarning(
                "Missing Issue",
                "Please select an IT support issue.",
                parent=client_window
            )
            return

        client = {
            "name": name,
            "issue": issue
        }

        queue.append(client)
        current_client = client
        client_notifications[id(client)] = notify_client
        refresh_queue_displays()

        position = len(queue)
        people_ahead = position - 1

        messagebox.showinfo(
            "Joined Queue",
            f"Name: {name}\n"
            f"IT Support Issue: {issue}\n"
            f"Position: {position}\n"
            f"People ahead: {people_ahead}",
            parent=client_window
        )

        name_entry.delete(0, tk.END)
        selected_problem.set("Select an issue")

    # Leave Queue function
    def leave_queue():
        nonlocal current_client

        if current_client is None:
            messagebox.showwarning(
                "Not in Queue",
                "You are not currently in the queue.",
                parent=client_window
            )
            return

        name = current_client["name"]

        for index, client in enumerate(queue):
            if client is current_client:
                queue.pop(index)
                break

        client_notifications.pop(id(current_client), None)
        current_client = None
        refresh_queue_displays()

        messagebox.showinfo(
            "Left Queue",
            f"{name}, you have left the queue.",
            parent=client_window
        )

    # Join Queue button
    join_button = tk.Button(
        client_window,
        text="Join Queue",
        font=("Arial", 14, "bold"),
        width=20,
        height=2,
        command=join_queue
    )
    join_button.pack(pady=(20, 10))

    # Leave Queue button
    leave_button = tk.Button(
        client_window,
        text="Leave Queue",
        font=("Arial", 14, "bold"),
        width=20,
        height=2,
        command=leave_queue
    )
    leave_button.pack(pady=(0, 20))
        # Current queue heading
    queue_title = tk.Label(
        client_window,
        text="Current Queue",
        font=("Arial", 16, "bold"),
        bg="#F4F6F8",
        fg="#1F2937"
    )
    queue_title.pack(pady=(0, 10))

    # Frame containing the queue and scrollbar
    queue_frame = tk.Frame(client_window, bg="#F4F6F8")
    queue_frame.pack(
        fill=tk.BOTH,
        expand=True,
        padx=30,
        pady=(0, 25)
    )

    queue_scrollbar = tk.Scrollbar(queue_frame)
    queue_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Numbered queue display
    queue_display = tk.Listbox(
        queue_frame,
        font=("Arial", 12),
        bg="white",
        fg="#1F2937",
        height=6,
        activestyle="none",
        yscrollcommand=queue_scrollbar.set
    )
    queue_display.pack(
        side=tk.LEFT,
        fill=tk.BOTH,
        expand=True
    )

    queue_scrollbar.config(command=queue_display.yview)

    # Register this window and show the existing queue
    queue_displays.append(queue_display)
    refresh_queue_displays()                                                       

        # Remove this client and display when the window closes
    def remove_queue_display(event):
        nonlocal current_client

        if event.widget is not client_window:
            return

        if queue_display in queue_displays:
            queue_displays.remove(queue_display)

        if current_client is not None:
            for index, client in enumerate(queue):
                if client is current_client:
                    queue.pop(index)
                    break

            client_notifications.pop(id(current_client), None)
            current_client = None

        refresh_queue_displays()

    client_window.bind(
        "<Destroy>",
        remove_queue_display,
        add="+"
    )

# ----------------------------
# ADMIN SCREEN
# ----------------------------

def open_admin_screen():
    admin_window = tk.Toplevel(root)
    admin_window.title("Admin - IT Help Desk")
    admin_window.geometry("700x600")
    admin_window.configure(bg="#F4F6F8")

    admin_title = tk.Label(
        admin_window,
        text="Manage IT Support Queue",
        font=("Arial", 26, "bold"),
        bg="#F4F6F8",
        fg="#1F2937"
    )
    admin_title.pack(pady=30)

    queue_frame = tk.Frame(admin_window, bg="#F4F6F8")
    queue_frame.pack(
        fill=tk.BOTH,
        expand=True,
        padx=30,
        pady=10
    )

    scrollbar = tk.Scrollbar(queue_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    queue_display = tk.Listbox(
        queue_frame,
        font=("Arial", 12),
        bg="white",
        fg="#1F2937",
        activestyle="none",
        yscrollcommand=scrollbar.set
    )
    queue_display.pack(
        side=tk.LEFT,
        fill=tk.BOTH,
        expand=True
    )

    scrollbar.config(command=queue_display.yview)

    queue_displays.append(queue_display)
    refresh_queue_displays()

    def serve_next():
        if not queue:
            messagebox.showinfo(
                "Queue Empty",
                "There is nobody waiting.",
                parent=admin_window
            )
            return

        client = queue.pop(0)
        notify = client_notifications.pop(id(client), None)

        refresh_queue_displays()

        if notify is not None:
            notify()

        messagebox.showinfo(
            "Client Called",
            f"{client['name']} has been called.\n"
            f"Issue: {client['issue']}",
            parent=admin_window
        )

    serve_button = tk.Button(
        admin_window,
        text="Serve Next",
        font=("Arial", 14, "bold"),
        width=20,
        height=2,
        command=serve_next
    )
    serve_button.pack(pady=25)

    def remove_admin_display(event):
        if event.widget is admin_window:
            if queue_display in queue_displays:
                queue_displays.remove(queue_display)

    admin_window.bind(
        "<Destroy>",
        remove_admin_display,
        add="+"
    )

# MAIN WINDOW

root = tk.Tk()

root.title("Virtual IT Help Desk")

root.geometry("900x600")

root.configure(bg="#F4F6F8")


# ----------------------------
# TITLE
# ----------------------------

title_label = tk.Label(
    root,
    text="Customer Queuing System",
    font=("Arial", 28, "bold"),
    bg="#F4F6F8",
    fg="#1F2937"
)


title_label.pack(pady=50)

description_label = tk.Label(
    root,
    text="An easy way to queue fast.",
    font=("Arial", 16),
    bg="#F4F6F8",
    fg="#6B7280"
)

description_label.pack(pady=5)

# ----------------------------
# CLIENT BUTTON
# ----------------------------

client_button = tk.Button(
    root,
    text="Client",
    font=("Arial", 16, "bold"),
    width=20,
    height=2,
    command=open_client_screen
)

client_button.pack(pady=30)



# ----------------------------
# ADMIN BUTTON
# ----------------------------

admin_button = tk.Button(
    root,
    text="Admin",
    font=("Arial", 16, "bold"),
    width=20,
    height=2,
    command=open_admin_screen
)

admin_button.pack(pady=10)

admin_button.pack(pady=10)

# ----------------------------
# START APPLICATION
# ----------------------------

root.mainloop()

