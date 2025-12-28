import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import threading
import queue
import os
import re
import signal

# ---------------- Global State ----------------

process = None
download_active = False
cancel_press_count = 0
last_line_was_successful_download = False

output_queue = queue.Queue()

# ---------------- Utilities ----------------

def kill_process_tree(proc):
    if proc and proc.poll() is None:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

def reset_cancel_counter():
    global cancel_press_count
    cancel_press_count = 0

# ---------------- UI Helpers ----------------
def append_output(text):
    global last_line_was_successful_download

    match = re.match(r'Downloaded\s+"([^"]+)"\s*:', text)
    if match:
        output_text.config(state=tk.NORMAL)
        output_text.insert(tk.END, match.group(1) + "\n")
        output_text.see(tk.END)
        output_text.config(state=tk.DISABLED)

        last_line_was_successful_download = True
        return

    if text.strip().startswith("https://music.youtube.com"):
        if last_line_was_successful_download:
            last_line_was_successful_download = False
            return
        

    last_line_was_successful_download = False

    output_text.config(state=tk.NORMAL)
    output_text.insert(tk.END, text)
    output_text.see(tk.END)
    output_text.config(state=tk.DISABLED)

def clear_output():
    output_text.config(state=tk.NORMAL)
    output_text.delete("1.0", tk.END)
    output_text.config(state=tk.DISABLED)

# ---------------- UI Actions ----------------

def browse_folder():
    reset_cancel_counter()
    folder = filedialog.askdirectory()
    if folder:
        download_path.set(folder)

def toggle_output():
    if output_frame.winfo_ismapped():
        output_frame.pack_forget()
        toggle_btn.config(text="Show Details")
    else:
        output_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        toggle_btn.config(text="Hide Details")

def cancel_download():
    global cancel_press_count

    cancel_press_count += 1

    if cancel_press_count == 5:
        messagebox.showinfo("Hi", "Stop cancelling dijju")
        cancel_press_count = 0
        return

    if not download_active:
        return

    kill_process_tree(process)
    status_label.config(text="Download cancelled.")
    reset_ui()

def on_close():
    cancel_download()
    root.destroy()

# ---------------- Download Logic ----------------

def start_download():
    global download_active

    reset_cancel_counter()

    if download_active:
        messagebox.showerror(
            "Download in progress",
            "A download is already running."
        )
        return

    link = spotify_link.get().strip()
    folder = download_path.get().strip()

    if not link.startswith("https://open.spotify.com"):
        messagebox.showerror("Invalid link", "Please enter a valid Spotify link.")
        return

    if not folder:
        messagebox.showerror("Missing folder", "Select a download folder.")
        return

    clear_output()
    download_active = True

    status_label.config(text="Downloading...")
    download_btn.config(state=tk.DISABLED)

    threading.Thread(
        target=run_spotdl,
        args=(link, folder),
        daemon=True
    ).start()

    root.after(200, poll_output)

def run_spotdl(link, folder):
    global process, download_active

    try:
        process = subprocess.Popen(
            ["spotdl", link, "--output", folder],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )

        for line in process.stdout:
            output_queue.put(line)

        exit_code = process.wait()

        if exit_code == 0:
            root.after(0, download_finished)
        else:
            root.after(0, lambda: status_label.config(text="Download failed."))

    except FileNotFoundError:
        root.after(
            0,
            lambda: messagebox.showerror(
                "Error",
                "spotdl not found in PATH.\nActivate the correct environment."
            )
        )
    except Exception as e:
        root.after(0, lambda: messagebox.showerror("Error", str(e)))

    finally:
        download_active = False
        root.after(0, reset_ui)

def poll_output():
    while not output_queue.empty():
        append_output(output_queue.get())

    if download_active:
        root.after(300, poll_output)

def download_finished():
    status_label.config(text="Download completed.")
    messagebox.showinfo("Success", "Download completed successfully.")

# ---------------- UI Reset ----------------

def reset_ui():
    global download_active
    download_active = False
    download_btn.config(state=tk.NORMAL)

# ---------------- UI Layout ----------------

root = tk.Tk()
root.title("Emerson, Lake & Download")
root.geometry("720x500")
root.resizable(False, False)
root.protocol("WM_DELETE_WINDOW", on_close)

spotify_link = tk.StringVar()
download_path = tk.StringVar()

tk.Label(root, text="Spotify Link").pack(pady=5)
tk.Entry(root, textvariable=spotify_link, width=95).pack()

tk.Label(root, text="Download Folder").pack(pady=5)
path_frame = tk.Frame(root)
path_frame.pack()

tk.Entry(path_frame, textvariable=download_path, width=75).pack(side=tk.LEFT)
tk.Button(path_frame, text="Browse", command=browse_folder).pack(side=tk.LEFT, padx=5)

btn_frame = tk.Frame(root)
btn_frame.pack(pady=10)

download_btn = tk.Button(btn_frame, text="Download", width=20, command=start_download)
download_btn.pack(side=tk.LEFT, padx=10)

tk.Button(btn_frame, text="Cancel", width=20, command=cancel_download).pack(side=tk.LEFT)

status_label = tk.Label(root, text="")
status_label.pack(pady=5)

toggle_btn = tk.Button(root, text="Show Details", command=toggle_output)
toggle_btn.pack(pady=5)

output_frame = tk.Frame(root)

scrollbar = tk.Scrollbar(output_frame)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

output_text = tk.Text(
    output_frame,
    height=12,
    state=tk.DISABLED,
    yscrollcommand=scrollbar.set,
    wrap=tk.NONE
)
output_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

scrollbar.config(command=output_text.yview)


root.mainloop()
