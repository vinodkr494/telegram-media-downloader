import asyncio
import concurrent.futures
import os
import threading
import traceback
import webbrowser
import customtkinter as ctk
from PIL import Image, ImageTk
from dotenv import load_dotenv, set_key
from tkinter import filedialog
import json
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

TASKS_FILE = "active_tasks.json"
APP_VERSION = "2.3.0"

def load_tasks():
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_tasks(tasks):
    try:
        with open(TASKS_FILE, "w") as f:
            json.dump(tasks, f)
    except Exception:
        pass


from core_downloader import (
    load_download_state,
    fetch_channel,
    get_messages_by_type,
    download_in_batches_headless,
    fetch_categorized_media
)

load_dotenv()
DEFAULT_API_ID   = os.getenv("API_ID", "")
DEFAULT_API_HASH = os.getenv("API_HASH", "")
SESSION_NAME     = os.getenv("SESSION_NAME", "default_session")
ENV_FILE         = ".env"

# ── Color palette ──────────────────────────────────────────────────────────────
# Sidebar  – Telegram brand dark
SB_BG        = ("#17212B", "#17212B")   # sidebar background
SB_ACTIVE    = ("#2B5278", "#2B5278")   # active nav item
SB_HOVER     = ("#1E2D3D", "#1E2D3D")   # hover state
SB_ACCENT    = ("#2AABEE", "#2AABEE")   # Telegram blue
SB_TEXT      = ("#FFFFFF", "#FFFFFF")   # sidebar icon/text

# Main area – light / white
MAIN_BG      = ("#F5F7FA", "#0F172A")   # page background
CARD_BG      = ("#FFFFFF", "#1E293B")   # card surface
CARD_BDR     = ("#CCCCCC", "#334155")   # card border
HDR_BG       = ("#FFFFFF", "#1E293B")   # top bar background

# Accent colours
ACCENT_BLUE  = ("#2AABEE", "#2AABEE")   # Telegram blue
ACCENT_GREEN = ("#22C55E", "#22C55E")   # success green
ACCENT_AMBER = ("#F59E0B", "#F59E0B")   # paused / warning
ACCENT_RED   = ("#EF4444", "#EF4444")   # error / remove

# Text
TEXT_DARK    = ("#1E293B", "#F8FAFC")   # primary text on light background
TEXT_MUTED   = ("#64748B", "#94A3B8")   # secondary text
TEXT_LIGHT   = ("#94A3B8", "#64748B")   # placeholder

# Buttons
BTN_PRIMARY  = ("#2AABEE", "#2AABEE")
BTN_HOVER    = ("#229ED9", "#229ED9")

ctk.set_appearance_mode(os.getenv("THEME_MODE", "Light"))
ctk.set_default_color_theme("blue")

# ── Asset paths ────────────────────────────────────────────────────────────────
_ASSETS = os.path.join(os.path.dirname(__file__), "assets")
_ICONS  = os.path.join(_ASSETS, "icons")

def _load_icon(name, size=(26, 26)):
    """Load a PNG from assets/icons/ as a CTkImage, return None on failure."""
    try:
        img = Image.open(os.path.join(_ICONS, name))
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)
    except Exception:
        return None

def _load_logo(size=(36, 36)):
    try:
        img = Image.open(os.path.join(_ASSETS, "logo.png"))
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)
    except Exception:
        return None


class DownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"TG Media Downloader v{APP_VERSION}")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.configure(fg_color=MAIN_BG)
        # Set window icon
        try:
            _icon = Image.open(os.path.join(_ASSETS, "logo.png"))
            _icon_ctk = ctk.CTkImage(light_image=_icon, dark_image=_icon, size=(32, 32))
            self.wm_iconphoto(True, ImageTk.PhotoImage(_icon))
        except Exception:
            pass

        # Settings
        self.download_limit = int(os.getenv("DOWNLOAD_LIMIT", 5))
        self.download_path  = os.getenv("DOWNLOAD_PATH", os.path.abspath("./downloads"))
        
        self.theme_mode     = os.getenv("THEME_MODE", "Light")
        self.proxy_type     = os.getenv("PROXY_TYPE", "None")
        self.proxy_host     = os.getenv("PROXY_HOST", "")
        self.proxy_port     = os.getenv("PROXY_PORT", "")
        self.proxy_user     = os.getenv("PROXY_USER", "")
        self.proxy_pass     = os.getenv("PROXY_PASS", "")
        self.proxy_secret   = os.getenv("PROXY_SECRET", "")
        
        ctk.set_appearance_mode(self.theme_mode)

        # Async state
        self.client               = None
        self.loop                 = asyncio.new_event_loop()
        self.auth_future          = None
        self.downloaded_state     = load_download_state()
        self.active_progress_bars = {}
        self.max_speed_kb = int(os.getenv("MAX_SPEED_KB", "0")) # 0 = Unlimited
        self.channel_cards        = {}
        self.task_cancel_events   = {}
        self.file_list_frames     = {}

        # Permanently-running event loop in background thread
        self._loop_thread = threading.Thread(target=self._run_loop_forever, daemon=True)
        self._loop_thread.start()

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self._check_existing_session()

    def _create_client(self, api_id, api_hash):
        try:
            api_id = int(api_id)
        except ValueError:
            pass
            
        proxy = None
        if hasattr(self, "proxy_type") and self.proxy_type != "None":
            import socks
            proxy_type_map = {
                "SOCKS4": socks.SOCKS4,
                "SOCKS5": socks.SOCKS5,
                "HTTP": socks.HTTP
            }
            if self.proxy_type in proxy_type_map:
                try:
                    proxy_port = int(self.proxy_port) if self.proxy_port else 0
                    if self.proxy_host and proxy_port:
                        proxy = (proxy_type_map[self.proxy_type], self.proxy_host, proxy_port, True, self.proxy_user, self.proxy_pass)
                except Exception:
                    pass
            elif self.proxy_type == "MTProto":
                try:
                    proxy_port = int(self.proxy_port) if self.proxy_port else 0
                    if self.proxy_host and proxy_port and self.proxy_secret:
                        proxy = ("mtproxy", self.proxy_host, proxy_port, self.proxy_secret)
                except Exception:
                    pass
                    
        if proxy:
            return TelegramClient(SESSION_NAME, api_id, api_hash, proxy=proxy, loop=self.loop)
        return TelegramClient(SESSION_NAME, api_id, api_hash, loop=self.loop)

    # ── Event loop ──────────────────────────────────────────────────────────────
    def _run_loop_forever(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def on_closing(self):
        if self.client:
            try:
                self.client.disconnect()
            except Exception:
                pass
        os._exit(0)

    # ── Session check ───────────────────────────────────────────────────────────
    def _check_existing_session(self):
        if DEFAULT_API_ID and DEFAULT_API_HASH and os.path.exists(f"{SESSION_NAME}.session"):
            self.show_loading_screen("Restoring session…")
            self.client = self._create_client(DEFAULT_API_ID, DEFAULT_API_HASH)
            threading.Thread(target=self._run_auto_login, daemon=True).start()
        else:
            self.show_login_screen()

    def _run_auto_login(self):
        future = asyncio.run_coroutine_threadsafe(self._auto_login_coro(), self.loop)
        try:
            future.result()
        except Exception:
            self.after(0, self.show_login_screen)

    async def _auto_login_coro(self):
        try:
            await self.client.connect()
            is_auth = await self.client.is_user_authorized()
            if is_auth:
                self.after(0, self.show_dashboard_screen)
            else:
                self.after(0, self.show_login_screen)
        except Exception:
            self.after(0, self.show_login_screen)

    def clear_container(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def show_loading_screen(self, msg="Loading…"):
        self.clear_container()
        lbl = ctk.CTkLabel(
            self.container, text=msg,
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=TEXT_DARK
        )
        lbl.place(relx=0.5, rely=0.5, anchor="center")

    # ══════════════════════════════════════════════════════════════════════════════
    # LOGIN SCREEN
    # ══════════════════════════════════════════════════════════════════════════════
    def show_login_screen(self):
        self.clear_container()

        bg = ctk.CTkFrame(self.container, fg_color=MAIN_BG)
        bg.place(relx=0, rely=0, relwidth=1, relheight=1)

        card = ctk.CTkFrame(
            bg, fg_color=CARD_BG, corner_radius=20,
            border_width=1, border_color=CARD_BDR
        )
        card.place(relx=0.5, rely=0.5, anchor="center")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=56, pady=48)

        # Brand
        _logo_img = _load_logo((72, 72))
        ctk.CTkLabel(
            inner, text="✈" if not _logo_img else "",
            image=_logo_img if _logo_img else None,
            font=ctk.CTkFont(size=48) if not _logo_img else None,
            text_color=ACCENT_BLUE
        ).pack(pady=(0, 10))
        ctk.CTkLabel(
            inner, text="TG Downloader",
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color=TEXT_DARK
        ).pack(pady=(2, 4))
        ctk.CTkLabel(
            inner, text="Sign in with your Telegram account",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=TEXT_MUTED
        ).pack(pady=(0, 28))

        def entry(ph, show=None):
            e = ctk.CTkEntry(
                inner, placeholder_text=ph, width=320, height=44,
                fg_color="#F8FAFC", border_color=CARD_BDR,
                text_color=TEXT_DARK, placeholder_text_color=TEXT_LIGHT,
                corner_radius=10, show=show or ""
            )
            e.pack(pady=6)
            return e

        self.api_id_entry   = entry("API ID")
        self.api_hash_entry = entry("API Hash")
        self.phone_entry    = entry("Phone Number  (+91…)")

        if DEFAULT_API_ID:   self.api_id_entry.insert(0, DEFAULT_API_ID)
        if DEFAULT_API_HASH: self.api_hash_entry.insert(0, DEFAULT_API_HASH)

        self.login_status = ctk.CTkLabel(
            inner, text="", text_color=ACCENT_RED,
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.login_status.pack(pady=(6, 0))

        self.login_btn = ctk.CTkButton(
            inner, text="Connect  →", width=320, height=46,
            fg_color=BTN_PRIMARY, hover_color=BTN_HOVER,
            text_color="white", corner_radius=10,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            command=self.on_login_click
        )
        self.login_btn.pack(pady=(16, 0))

    def on_login_click(self):
        self.login_status.configure(text="")
        api_id   = self.api_id_entry.get().strip()
        api_hash = self.api_hash_entry.get().strip()
        phone    = self.phone_entry.get().strip()
        if not api_id or not api_hash or not phone:
            self.login_status.configure(text="Please fill all fields")
            return
        self.login_btn.configure(state="disabled", text="Connecting…")
        if not self.client:
            self.client = self._create_client(api_id, api_hash)
        threading.Thread(target=self.run_async_connect, args=(phone,), daemon=True).start()

    def run_async_connect(self, phone):
        cf_future = concurrent.futures.Future()

        async def _wrapper():
            try:
                await self.async_connect_flow(phone)
                cf_future.set_result(True)
            except Exception as e:
                cf_future.set_exception(e)

        asyncio.run_coroutine_threadsafe(_wrapper(), self.loop)
        try:
            cf_future.result()
        except Exception as e:
            print(f"Connect error: {e}")

    async def async_connect_flow(self, phone):
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                await self.client.send_code_request(phone)
                self.after(0, self.prompt_for_code, phone)
                return
            self.after(0, self._handle_successful_login)
        except Exception as e:
            self.after(0, self._login_error, str(e))

    def prompt_for_code(self, phone):
        dialog = ctk.CTkInputDialog(
            text="Enter the 5-digit code sent to your Telegram:",
            title="Verification"
        )
        code = dialog.get_input()
        if code:
            self.login_btn.configure(text="Verifying…")
            asyncio.run_coroutine_threadsafe(self.verify_code(phone, code), self.loop)
        else:
            self._login_error("Code entry cancelled")

    async def verify_code(self, phone, code):
        try:
            await self.client.sign_in(phone, code)
            self.after(0, self._handle_successful_login)
        except SessionPasswordNeededError:
            self.after(0, self.prompt_for_password)
        except Exception as e:
            self.after(0, self._login_error, str(e))

    def prompt_for_password(self):
        dialog = ctk.CTkInputDialog(
            text="2-Step Verification Password:",
            title="Password Required"
        )
        pwd = dialog.get_input()
        if pwd:
            self.login_btn.configure(text="Verifying…")
            asyncio.run_coroutine_threadsafe(self.verify_password(pwd), self.loop)
        else:
            self._login_error("Password entry cancelled")

    async def verify_password(self, pwd):
        try:
            await self.client.sign_in(password=pwd)
            self.after(0, self._handle_successful_login)
        except Exception as e:
            self.after(0, self._login_error, str(e))

    def _login_error(self, msg):
        self.login_status.configure(text=msg)
        self.login_btn.configure(state="normal", text="Connect  →")

    def _handle_successful_login(self):
        try:
            api_id   = self.api_id_entry.get().strip()
            api_hash = self.api_hash_entry.get().strip()
            global DEFAULT_API_ID, DEFAULT_API_HASH
            if api_id and api_hash:
                DEFAULT_API_ID   = api_id
                DEFAULT_API_HASH = api_hash
                if os.path.exists(ENV_FILE):
                    set_key(ENV_FILE, "API_ID",   api_id)
                    set_key(ENV_FILE, "API_HASH", api_hash)
                else:
                    with open(ENV_FILE, "a") as f:
                        f.write(f"\nAPI_ID={api_id}\nAPI_HASH={api_hash}\n")
        except Exception as e:
            print(f"Error saving session credentials: {e}")
        self.show_dashboard_screen()

    # ══════════════════════════════════════════════════════════════════════════════
    # DASHBOARD SHELL
    # ══════════════════════════════════════════════════════════════════════════════
    def show_dashboard_screen(self):
        self.clear_container()

        # ── Sidebar (left) ──
        self.sidebar_frame = ctk.CTkFrame(
            self.container, width=90, corner_radius=0,
            fg_color=SB_BG
        )
        self.sidebar_frame.pack(side="left", fill="y")
        self.sidebar_frame.pack_propagate(False)

        # ── Main view area (right) ──
        self.view_container = ctk.CTkFrame(
            self.container, corner_radius=0, fg_color=MAIN_BG
        )
        self.view_container.pack(side="right", fill="both", expand=True)

        # ── Build all views ──
        self.home_view      = ctk.CTkFrame(self.view_container, fg_color="transparent")
        self.downloads_view = ctk.CTkFrame(self.view_container, fg_color="transparent")
        self.settings_view  = ctk.CTkFrame(self.view_container, fg_color="transparent")
        self.about_view     = ctk.CTkFrame(self.view_container, fg_color="transparent")

        self._build_sidebar()
        self._build_home_view()
        self._build_downloads_view()
        self._build_settings_view()
        self._build_about_view()

        self._active_nav = None
        self.switch_to_view(self.home_view, 0)
        self.after(500, self.restore_tasks)

    # ── Restore persisted tasks ─────────────────────────────────────────────────
    def restore_tasks(self):
        tasks = load_tasks()
        for t in tasks:
            channel_input = t.get("channel_input")
            media_id      = t.get("media_id")
            paused        = t.get("paused", True)
            if channel_input and media_id:
                threading.Thread(
                    target=self.run_async_download,
                    args=(channel_input, media_id, paused),
                    daemon=True
                ).start()

    # ── View switcher ───────────────────────────────────────────────────────────
    ALL_VIEWS = None  # populated in switch_to_view

    def switch_to_view(self, view_frame, nav_index):
        all_views = [self.home_view, self.downloads_view,
                     self.settings_view, self.about_view]
        for v in all_views:
            v.pack_forget()
        view_frame.pack(fill="both", expand=True)
        self._active_nav_idx = nav_index

        # Update active nav highlight
        for i, btn_data in enumerate(self._nav_buttons):
            frame, lbl_icon, lbl_text = btn_data
            if i == nav_index:
                frame.configure(fg_color=SB_ACTIVE)
            else:
                frame.configure(fg_color="transparent")

    # ══════════════════════════════════════════════════════════════════════════════
    # SIDEBAR
    # ══════════════════════════════════════════════════════════════════════════════
    def _build_sidebar(self):
        self._nav_buttons = []

        # Brand logo strip
        logo_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent", height=80, corner_radius=0)
        logo_frame.pack(fill="x")
        logo_frame.pack_propagate(False)
        _logo_img = _load_logo((44, 44))
        ctk.CTkLabel(
            logo_frame,
            image=_logo_img if _logo_img else None,
            text="" if _logo_img else "✈",
            font=ctk.CTkFont(size=34),
            text_color="white"
        ).place(relx=0.5, rely=0.5, anchor="center")

        # Divider
        ctk.CTkFrame(self.sidebar_frame, height=1, fg_color="#1E2D3D").pack(fill="x")

        # Nav items
        nav_items = [
            ("home.png",     "Home",      self.home_view,      0),
            ("download.png", "Downloads", self.downloads_view,  1),
            ("setting.png",  "Settings",  self.settings_view,   2),
            ("info.png",     "About",     self.about_view,      3),
        ]

        nav_top_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        nav_top_frame.pack(fill="x", pady=(8, 0))
        self._active_nav_idx = 0

        for icon, label, view, idx in nav_items:
            self._make_nav_btn(nav_top_frame, icon, label, view, idx)

        # ── Logout pinned at bottom ──
        ctk.CTkFrame(self.sidebar_frame, height=1, fg_color="#1E2D3D").pack(side="bottom", fill="x")
        _logout_img = _load_icon("logout.png", (26, 26))
        ctk.CTkButton(
            self.sidebar_frame,
            text="Logout",
            image=_logout_img,
            compound="top",
            fg_color="transparent",
            hover_color="#3D1320",
            text_color=ACCENT_RED,
            height=72,
            corner_radius=0,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.on_logout_click
        ).pack(side="bottom", fill="x")

    def _make_nav_btn(self, parent, icon_file, label, view, idx):
        frame = ctk.CTkFrame(parent, fg_color="transparent", cursor="hand2", corner_radius=8)
        frame.pack(fill="x", padx=6, pady=3)

        _img = _load_icon(icon_file, (26, 26))
        lbl_icon = ctk.CTkLabel(
            frame,
            image=_img,
            text="" if _img else label[0],   # fallback single char
            font=ctk.CTkFont(size=26),
            text_color=SB_TEXT
        )
        lbl_icon.pack(pady=(12, 2))

        lbl_text = ctk.CTkLabel(
            frame, text=label,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=SB_TEXT
        )
        lbl_text.pack(pady=(0, 8))

        def _enter(e):
            if self._active_nav_idx != idx:
                frame.configure(fg_color=SB_HOVER)
        def _leave(e):
            if self._active_nav_idx != idx:
                frame.configure(fg_color="transparent")
        def _click(e): self.switch_to_view(view, idx)

        for w in [frame, lbl_icon, lbl_text]:
            w.bind("<Enter>", _enter)
            w.bind("<Leave>", _leave)
            w.bind("<Button-1>", _click)

        self._nav_buttons.append((frame, lbl_icon, lbl_text))

    # ══════════════════════════════════════════════════════════════════════════════
    # HOME VIEW  —  Add new channel to queue
    # ══════════════════════════════════════════════════════════════════════════════
    def _build_home_view(self):
        # Header
        hdr = ctk.CTkFrame(self.home_view, fg_color=HDR_BG, corner_radius=0, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkFrame(hdr, fg_color=CARD_BDR, height=1).pack(side="bottom", fill="x")
        ctk.CTkLabel(
            hdr, text="Add Download",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=TEXT_DARK
        ).place(x=28, rely=0.5, anchor="w")

        body = ctk.CTkScrollableFrame(
            self.home_view, fg_color="transparent",
            scrollbar_button_color=SB_ACCENT,
            scrollbar_button_hover_color=BTN_HOVER
        )
        body.pack(fill="both", expand=True, padx=28, pady=20)

        # Card: channel input
        add_card = ctk.CTkFrame(body, fg_color=CARD_BG, corner_radius=14,
                                border_width=1, border_color=CARD_BDR)
        add_card.pack(fill="x", pady=(0, 16))

        inner = ctk.CTkFrame(add_card, fg_color="transparent")
        inner.pack(fill="x", padx=24, pady=20)

        ctk.CTkLabel(
            inner, text="Channel / Group",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=TEXT_DARK
        ).pack(anchor="w", pady=(0, 8))

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x")

        self.search_entry = ctk.CTkEntry(
            row,
            placeholder_text="Enter username or channel ID…",
            height=42,
            fg_color="#F8FAFC", border_color=CARD_BDR,
            text_color=TEXT_DARK, placeholder_text_color=TEXT_LIGHT,
            corner_radius=10,
            font=ctk.CTkFont(family="Segoe UI", size=13)
        )
        self.search_entry.pack(side="left", fill="x", expand=True)

        self.fetch_btn = ctk.CTkButton(
            row,
            text="🔍 Fetch Media",
            width=140, height=42,
            fg_color=BTN_PRIMARY, hover_color=BTN_HOVER,
            text_color="white", corner_radius=10,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self.on_fetch_media_start
        )
        self.fetch_btn.pack(side="left", padx=(10, 0))

        # Info tip
        ctk.CTkLabel(
            inner,
            text="Tip: enter @username, https://t.me/username, or the numeric channel ID",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_LIGHT
        ).pack(anchor="w", pady=(8, 0))

        # Active downloads preview in Home
        self.home_queue_label = ctk.CTkLabel(
            body,
            text="Active Queue",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=TEXT_DARK
        )
        self.home_queue_label.pack(anchor="w", pady=(8, 8))

        self.home_cards_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.home_cards_frame.pack(fill="x")

        # Empty state — hidden when first card is added
        self.home_empty_label = ctk.CTkLabel(
            body,
            text="\U0001F4E5\n\nNo downloads yet\nEnter a channel above and click \"\U0001F50D Fetch Media\" to get started",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=TEXT_MUTED,
            justify="center"
        )
        self.home_empty_label.pack(pady=40)

    # ══════════════════════════════════════════════════════════════════════════════
    # DOWNLOADS VIEW  —  All channels with their downloaded files
    # ══════════════════════════════════════════════════════════════════════════════
    def _build_downloads_view(self):
        hdr = ctk.CTkFrame(self.downloads_view, fg_color=HDR_BG, corner_radius=0, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkFrame(hdr, fg_color=CARD_BDR, height=1).pack(side="bottom", fill="x")
        ctk.CTkLabel(
            hdr, text="Download List",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=TEXT_DARK
        ).place(x=28, rely=0.5, anchor="w")

        self.dl_scroll = ctk.CTkScrollableFrame(
            self.downloads_view, fg_color="transparent",
            scrollbar_button_color=SB_ACCENT,
            scrollbar_button_hover_color=BTN_HOVER
        )
        self.dl_scroll.pack(fill="both", expand=True, padx=28, pady=16)

        self.dl_empty_label = ctk.CTkLabel(
            self.dl_scroll,
            text="No downloads yet.\nAdd a channel from Home to get started.",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=TEXT_MUTED, justify="center"
        )
        self.dl_empty_label.pack(expand=True, pady=80)

    # ══════════════════════════════════════════════════════════════════════════════
    # CHANNEL CARD  (shared between Home and Downloads view)
    # ══════════════════════════════════════════════════════════════════════════════
    def add_channel_card(self, task_id, title, total_items,
                         completed_initial, folder_name,
                         channel_input, media_id, is_paused):

        # Remove old card if re-adding
        if task_id in self.channel_cards:
            for k in ("card_home", "card_dl"):
                if k in self.channel_cards[task_id]:
                    try: self.channel_cards[task_id][k].destroy()
                    except Exception: pass

        # Hide empty state labels when first card is added
        if hasattr(self, 'home_empty_label'):
            try: self.home_empty_label.pack_forget()
            except Exception: pass
        if hasattr(self, 'dl_empty_label'):
            try: self.dl_empty_label.pack_forget()
            except Exception: pass

        MEDIA_LABELS = {1: "🖼 Images", 2: "🎬 Videos", 3: "📄 PDFs",
                        4: "🗜 ZIPs",   5: "🎵 Audio",  6: "📦 All Media"}
        MEDIA_COLORS = {1: "#0EA5E9",   2: "#A855F7",   3: "#F59E0B",
                        4: "#14B8A6",   5: "#EC4899",   6: "#2AABEE"}

        badge_text  = MEDIA_LABELS.get(media_id, "📦 All Media")
        badge_color = MEDIA_COLORS.get(media_id, "#2AABEE")

        # Build one card widget and return references
        def build_card(parent):
            # Simple plain white card
            wrapper = ctk.CTkFrame(
                parent, fg_color=CARD_BG,
                corner_radius=12, border_width=1, border_color=CARD_BDR
            )
            wrapper.pack(fill="x", pady=8)

            # ── Card body ─────────────────────────────────────────────────
            body = ctk.CTkFrame(wrapper, fg_color="transparent")
            body.pack(fill="x", padx=18, pady=(14, 14))

            # Circle icon with media color background
            ICON_LETTERS = {
                "🖼 Images": "IMG", "🎬 Videos": "VID", "📄 PDFs": "PDF",
                "🗜 ZIPs": "ZIP",   "🎵 Audio": "AUD", "📦 All Media": "ALL"
            }
            icon_circle = ctk.CTkFrame(body, width=56, height=56,
                                       fg_color=badge_color, corner_radius=28)
            icon_circle.pack(side="left", padx=(0, 16))
            icon_circle.pack_propagate(False)
            ctk.CTkLabel(
                icon_circle,
                text=ICON_LETTERS.get(badge_text, "ALL"),
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color="white"
            ).place(relx=0.5, rely=0.5, anchor="center")

            # ── Right column ───────────────────────────────────────────────
            right = ctk.CTkFrame(body, fg_color="transparent")
            right.pack(side="left", fill="both", expand=True)

            # Title row with speed badge on right
            title_row = ctk.CTkFrame(right, fg_color="transparent")
            title_row.pack(fill="x", pady=(0, 4))

            ctk.CTkLabel(
                title_row, text=title,
                font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
                text_color=TEXT_DARK, anchor="w"
            ).pack(side="left", fill="x", expand=True)

            spd = ctk.CTkLabel(
                title_row, text="● ― KB/s",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=TEXT_LIGHT
            )
            spd.pack(side="right")

            # Media type tag — use a fixed light bg per type (no alpha hex)
            BADGE_LIGHT = {
                "#0EA5E9": "#E0F2FE", "#A855F7": "#F3E8FF", "#F59E0B": "#FEF3C7",
                "#14B8A6": "#CCFBF1", "#EC4899": "#FCE7F3", "#2AABEE": "#DBEAFE"
            }
            tag_bg = BADGE_LIGHT.get(badge_color, "#E2E8F0")
            ctk.CTkLabel(
                right, text=badge_text,
                fg_color=tag_bg,
                text_color=badge_color,
                corner_radius=4,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                padx=8, pady=2
            ).pack(anchor="w", pady=(0, 6))

            # ── Progress bars ──────────────────────────────────────────────
            pct = completed_initial / total_items if total_items > 0 else 0
            pb = ctk.CTkProgressBar(
                right, height=8,
                progress_color=ACCENT_GREEN if not is_paused else ACCENT_AMBER,
                fg_color="#EEEEEE", corner_radius=4
            )
            pb.set(pct)
            pb.pack(fill="x", pady=(0, 3))

            pb_active = ctk.CTkProgressBar(
                right, height=4,
                progress_color=ACCENT_BLUE, fg_color="#EEEEEE",
                corner_radius=3
            )
            pb_active.set(0)
            pb_active.pack(fill="x", pady=(0, 8))

            # ── Action buttons (own full row) ──────────────────────────────
            btn_row = ctk.CTkFrame(right, fg_color="transparent")
            btn_row.pack(anchor="w", pady=(0, 6))

            def mk_btn(parent, text, fg, hover, cmd):
                return ctk.CTkButton(
                    parent, text=text, height=30, width=100,
                    fg_color=fg, hover_color=hover,
                    text_color="white", corner_radius=7,
                    font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                    command=cmd
                )

            if is_paused:
                btn_pause = mk_btn(btn_row, "▶ Resume", ACCENT_GREEN, "#16A34A",
                                   lambda c=task_id: self.on_resume_channel(c))
            else:
                btn_pause = mk_btn(btn_row, "⏸ Pause", ACCENT_AMBER, "#D97706",
                                   lambda c=task_id: self.on_pause_channel(c))
            btn_pause.pack(side="left", padx=(0, 6))

            mk_btn(btn_row, "📂 Open", ACCENT_BLUE, BTN_HOVER,
                   lambda f=folder_name: os.startfile(f) if os.name == "nt" else None
                   ).pack(side="left", padx=(0, 6))

            mk_btn(btn_row, "✕ Remove", ACCENT_RED, "#DC2626",
                   lambda c=task_id: self.on_remove_channel(c)
                   ).pack(side="left")

            # ── Status label ───────────────────────────────────────────────
            _status_prefix = "Paused at" if is_paused else "Downloaded"
            status_lbl = ctk.CTkLabel(
                right,
                text=f"{_status_prefix}  {completed_initial} / {total_items} files",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=ACCENT_AMBER if is_paused else TEXT_MUTED, anchor="w"
            )
            status_lbl.pack(anchor="w")

            return wrapper, pb, pb_active, spd, status_lbl, btn_pause

        # ── Build card in Home view ──
        card_h, pb_h, pb_a_h, spd_h, sl_h, bp_h = build_card(self.home_cards_frame)

        # ── Build card in Downloads view (hide empty label) ──
        self.dl_empty_label.pack_forget()
        card_d, pb_d, pb_a_d, spd_d, sl_d, bp_d = build_card(self.dl_scroll)

        # ── Also build the file list section under the Downloads card ──
        file_section = ctk.CTkFrame(self.dl_scroll, fg_color=CARD_BG,
                                    corner_radius=12, border_width=1, border_color=CARD_BDR)
        file_section.pack(fill="x", pady=(0, 16))

        # Title bar for toggling
        file_title_frm = ctk.CTkFrame(file_section, fg_color="transparent", cursor="hand2")
        file_title_frm.pack(fill="x")
        
        file_header_lbl = ctk.CTkLabel(
            file_title_frm,
            text=f"  ▼  {title}  — downloaded files (click to toggle)",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=TEXT_MUTED,
            anchor="w"
        )
        file_header_lbl.pack(fill="x", padx=16, pady=10)
        ctk.CTkFrame(file_section, fg_color=CARD_BDR, height=1).pack(fill="x")

        # Container for actual files, initially visible. We hide/show this on click.
        file_container = ctk.CTkFrame(file_section, fg_color="transparent")
        file_container.pack(fill="x", pady=4)
        
        def toggle_files(e):
            if file_container.winfo_ismapped():
                file_container.pack_forget()
                file_header_lbl.configure(text=f"  ▶  {title}  — downloaded files (click to toggle)")
            else:
                file_container.pack(fill="x", pady=4)
                file_header_lbl.configure(text=f"  ▼  {title}  — downloaded files (click to toggle)")

        file_title_frm.bind("<Button-1>", toggle_files)
        file_header_lbl.bind("<Button-1>", toggle_files)

        self.file_list_frames = getattr(self, "file_list_frames", {})
        self.file_list_frames[task_id] = file_container

        self.channel_cards[task_id] = {
            "card_home": card_h,
            "card_dl":   card_d,
            "file_section": file_section,
            "pb":         pb_h,
            "pb_d":       pb_d,
            "pb_active":  pb_a_h,
            "pb_active_d":pb_a_d,
            "badge_speed":spd_h,
            "badge_speed_d":spd_d,
            "status_lbl": sl_h,
            "status_lbl_d":sl_d,
            "btn_pause":  bp_h,
            "btn_pause_d":bp_d,
            "completed":  completed_initial,
            "total":      total_items,
            "channel_input": channel_input,
            "media_id":   media_id,
            "folder_name":folder_name,
        }

    # ── Card actions ─────────────────────────────────────────────────────────────
    def on_resume_channel(self, task_id):
        if task_id not in self.channel_cards:
            return
        cdata = self.channel_cards[task_id]
        for k in ("btn_pause", "btn_pause_d"):
            if k in cdata:
                cdata[k].configure(
                    text="⏸  Pause", text_color=ACCENT_AMBER, border_color=ACCENT_AMBER,
                    command=lambda c=task_id: self.on_pause_channel(c)
                )
        for k in ("badge_speed", "badge_speed_d"):
            if k in cdata:
                cdata[k].configure(text="Starting…", text_color=TEXT_MUTED)
        for k in ("pb", "pb_d"):
            if k in cdata:
                cdata[k].configure(progress_color=ACCENT_GREEN)
        self.save_task_state(cdata["channel_input"], cdata["media_id"], False)
        threading.Thread(
            target=self.run_async_download,
            args=(cdata["channel_input"], cdata["media_id"], False),
            daemon=True
        ).start()

    def on_remove_channel(self, task_id):
        if task_id in self.task_cancel_events:
            self.task_cancel_events[task_id].set()
        if task_id in self.channel_cards:
            cdata = self.channel_cards[task_id]
            tasks = load_tasks()
            tasks = [t for t in tasks if not (
                t.get("channel_input") == cdata["channel_input"] and
                t.get("media_id") == cdata["media_id"]
            )]
            save_tasks(tasks)
            for k in ("card_home", "card_dl", "file_section"):
                if k in cdata:
                    try: cdata[k].destroy()
                    except Exception: pass
            del self.channel_cards[task_id]

    def on_pause_channel(self, task_id):
        if task_id in self.task_cancel_events:
            event = self.task_cancel_events[task_id]
            if not event.is_set():
                event.set()
                if task_id in self.channel_cards:
                    cdata = self.channel_cards[task_id]
                    for k in ("btn_pause", "btn_pause_d"):
                        if k in cdata:
                            cdata[k].configure(
                                text="▶  Resume", text_color=ACCENT_GREEN, border_color=ACCENT_GREEN,
                                command=lambda c=task_id: self.on_resume_channel(c)
                            )
                    self.save_task_state(cdata["channel_input"], cdata["media_id"], True)

    def add_file_to_list(self, task_id, filename):
        """Add a downloaded file entry to the Downloads view card."""
        if task_id not in getattr(self, "file_list_frames", {}):
            return
        section = self.file_list_frames[task_id]
        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(
            row, text="✓", text_color=ACCENT_GREEN,
            font=ctk.CTkFont(size=12, weight="bold"), width=18
        ).pack(side="left")
        ctk.CTkLabel(
            row, text=filename,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_MUTED, anchor="w"
        ).pack(side="left", padx=(4, 0), fill="x")

    # ══════════════════════════════════════════════════════════════════════════════
    # SETTINGS VIEW
    # ══════════════════════════════════════════════════════════════════════════════
    def _build_settings_view(self):
        hdr = ctk.CTkFrame(self.settings_view, fg_color=HDR_BG, corner_radius=0, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkFrame(hdr, fg_color=CARD_BDR, height=1).pack(side="bottom", fill="x")
        ctk.CTkLabel(
            hdr, text="Settings",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=TEXT_DARK
        ).place(x=28, rely=0.5, anchor="w")

        body = ctk.CTkScrollableFrame(
            self.settings_view, fg_color="transparent",
            scrollbar_button_color=SB_ACCENT,
            scrollbar_button_hover_color=BTN_HOVER
        )
        body.pack(fill="both", expand=True, padx=28, pady=20)

        def section(parent, title):
            f = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=14,
                             border_width=1, border_color=CARD_BDR)
            f.pack(fill="x", pady=10)
            ctk.CTkLabel(
                f, text=title,
                font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                text_color=TEXT_DARK
            ).pack(anchor="w", padx=20, pady=(16, 4))
            return f

        # Download limit
        lf = section(body, "Max Concurrent Downloads")
        self.limit_lbl = ctk.CTkLabel(
            lf, text=f"{self.download_limit} files at once",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_MUTED
        )
        self.limit_lbl.pack(anchor="w", padx=20)
        self.limit_slider = ctk.CTkSlider(
            lf, from_=1, to=20, number_of_steps=19,
            command=self.on_limit_slider,
            progress_color=ACCENT_BLUE,
            button_color=ACCENT_BLUE,
            button_hover_color=BTN_HOVER
        )
        self.limit_slider.set(self.download_limit)
        self.limit_slider.pack(fill="x", padx=20, pady=(8, 18))

        # Speed limit
        sf = section(body, "Max Download Speed")
        
        speed_text = f"{self.max_speed_kb // 1024} MB/s" if self.max_speed_kb >= 1024 else (f"{self.max_speed_kb} KB/s" if self.max_speed_kb > 0 else "Unlimited")
        self.speed_lbl = ctk.CTkLabel(
            sf, text=speed_text,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_MUTED
        )
        self.speed_lbl.pack(anchor="w", padx=20)
        
        self.speed_slider = ctk.CTkSlider(
            sf, from_=0, to=10240, number_of_steps=20, # 0 to 10 MB/s limit (step ~500KB/s)
            command=self.on_speed_slider,
            progress_color=ACCENT_GREEN,
            button_color=ACCENT_GREEN,
            button_hover_color=BTN_HOVER
        )
        self.speed_slider.set(self.max_speed_kb)
        self.speed_slider.pack(fill="x", padx=20, pady=(8, 18))

        # Download path
        pf = section(body, "Download Directory")
        p_row = ctk.CTkFrame(pf, fg_color="transparent")
        p_row.pack(fill="x", padx=20, pady=(0, 16))
        self.path_entry = ctk.CTkEntry(
            p_row, state="normal", height=40,
            fg_color="#F8FAFC", border_color=CARD_BDR,
            text_color=TEXT_DARK, corner_radius=8
        )
        self.path_entry.insert(0, self.download_path)
        self.path_entry.configure(state="readonly")
        self.path_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            p_row, text="Browse", width=90, height=40,
            fg_color=BTN_PRIMARY, hover_color=BTN_HOVER,
            corner_radius=8, font=ctk.CTkFont(size=13),
            command=self.on_browse_path
        ).pack(side="left", padx=(10, 0))

        # Appearance Setting
        tf = section(body, "Appearance")
        self.theme_combo = ctk.CTkOptionMenu(
            tf, values=["Light", "Dark", "System"],
            fg_color="#F8FAFC", button_color=BTN_PRIMARY, button_hover_color=BTN_HOVER, text_color=TEXT_DARK,
            command=self.on_theme_change
        )
        self.theme_combo.set(self.theme_mode.capitalize() if self.theme_mode else "Light")
        self.theme_combo.pack(anchor="w", padx=20, pady=(0, 16))

        # Proxy Setting
        proxf = section(body, "Proxy Configuration")
        px_inner = ctk.CTkFrame(proxf, fg_color="transparent")
        px_inner.pack(fill="x", padx=20, pady=(0, 16))
        
        self.proxy_type_var = ctk.StringVar(value=self.proxy_type if self.proxy_type else "None")
        self.proxy_type_combo = ctk.CTkOptionMenu(
            px_inner, values=["None", "SOCKS4", "SOCKS5", "HTTP", "MTProto"],
            variable=self.proxy_type_var,
            fg_color="#F8FAFC", button_color=BTN_PRIMARY, button_hover_color=BTN_HOVER, text_color=TEXT_DARK
        )
        self.proxy_type_combo.pack(anchor="w", pady=(0, 10))
        
        def p_entry(parent, ph, is_pwd=False):
            return ctk.CTkEntry(
                parent, placeholder_text=ph, show="*" if is_pwd else "",
                fg_color="#F8FAFC", border_color=CARD_BDR,
                text_color=TEXT_DARK, placeholder_text_color=TEXT_LIGHT,
                corner_radius=8
            )
            
        proxy_row1 = ctk.CTkFrame(px_inner, fg_color="transparent")
        proxy_row1.pack(fill="x", pady=4)
        self.proxy_host_entry = p_entry(proxy_row1, "Host (e.g. 127.0.0.1)")
        self.proxy_host_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        if self.proxy_host: self.proxy_host_entry.insert(0, self.proxy_host)
        
        self.proxy_port_entry = p_entry(proxy_row1, "Port (e.g. 1080)")
        self.proxy_port_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
        if self.proxy_port: self.proxy_port_entry.insert(0, self.proxy_port)
        
        proxy_row2 = ctk.CTkFrame(px_inner, fg_color="transparent")
        proxy_row2.pack(fill="x", pady=4)
        self.proxy_user_entry = p_entry(proxy_row2, "Username (Optional)")
        self.proxy_user_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        if self.proxy_user: self.proxy_user_entry.insert(0, self.proxy_user)
        
        self.proxy_pass_entry = p_entry(proxy_row2, "Password (Optional)", True)
        self.proxy_pass_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
        if self.proxy_pass: self.proxy_pass_entry.insert(0, self.proxy_pass)

        proxy_row3 = ctk.CTkFrame(px_inner, fg_color="transparent")
        proxy_row3.pack(fill="x", pady=4)
        self.proxy_secret_entry = p_entry(proxy_row3, "Secret (MTProto Only)")
        self.proxy_secret_entry.pack(side="left", fill="x", expand=True)
        if self.proxy_secret: self.proxy_secret_entry.insert(0, self.proxy_secret)

        ctk.CTkButton(
            body, text="💾  Save Settings", height=44,
            fg_color=ACCENT_GREEN, hover_color="#16A34A",
            text_color="white", corner_radius=10,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            command=self.on_save_settings
        ).pack(pady=(10, 4), anchor="w")

        self.save_status = ctk.CTkLabel(
            body, text="",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=ACCENT_GREEN
        )
        self.save_status.pack(anchor="w")

    def on_limit_slider(self, val):
        self.download_limit = int(val)
        self.limit_lbl.configure(text=f"{self.download_limit} files at once")

    def on_speed_slider(self, val):
        self.max_speed_kb = int(val)
        speed_text = f"{self.max_speed_kb // 1024} MB/s" if self.max_speed_kb >= 1024 else (f"{self.max_speed_kb} KB/s" if self.max_speed_kb > 0 else "Unlimited")
        self.speed_lbl.configure(text=speed_text)

    def on_browse_path(self):
        new_path = filedialog.askdirectory(initialdir=self.download_path, title="Select Download Folder")
        if new_path:
            self.download_path = new_path
            self.path_entry.configure(state="normal")
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, self.download_path)
            self.path_entry.configure(state="readonly")

    def on_theme_change(self, choice):
        self.theme_mode = choice
        ctk.set_appearance_mode(choice)

    def on_save_settings(self):
        self.proxy_type = self.proxy_type_var.get()
        self.proxy_host = self.proxy_host_entry.get().strip()
        self.proxy_port = self.proxy_port_entry.get().strip()
        self.proxy_user = self.proxy_user_entry.get().strip()
        self.proxy_pass = self.proxy_pass_entry.get().strip()
        self.proxy_secret = self.proxy_secret_entry.get().strip()
        
        os.environ["DOWNLOAD_LIMIT"] = str(self.download_limit)
        os.environ["MAX_SPEED_KB"]   = str(self.max_speed_kb)
        os.environ["DOWNLOAD_PATH"]  = self.download_path
        os.environ["THEME_MODE"]     = self.theme_mode
        os.environ["PROXY_TYPE"]     = self.proxy_type
        os.environ["PROXY_HOST"]     = self.proxy_host
        os.environ["PROXY_PORT"]     = self.proxy_port
        os.environ["PROXY_USER"]     = self.proxy_user
        os.environ["PROXY_PASS"]     = self.proxy_pass
        os.environ["PROXY_SECRET"]   = self.proxy_secret
        
        keys_to_save = {
            "DOWNLOAD_LIMIT": str(self.download_limit),
            "MAX_SPEED_KB": str(self.max_speed_kb),
            "DOWNLOAD_PATH": self.download_path,
            "THEME_MODE": self.theme_mode,
            "PROXY_TYPE": self.proxy_type,
            "PROXY_HOST": self.proxy_host,
            "PROXY_PORT": self.proxy_port,
            "PROXY_USER": self.proxy_user,
            "PROXY_PASS": self.proxy_pass,
            "PROXY_SECRET": self.proxy_secret
        }
        
        if os.path.exists(ENV_FILE):
            for k, v in keys_to_save.items():
                set_key(ENV_FILE, k, v)
        else:
            with open(ENV_FILE, "a") as f:
                for k, v in keys_to_save.items():
                    f.write(f"\n{k}={v}")
                    
        self.save_status.configure(text="✓  Settings saved successfully! (Proxy changes require restart/reconnect)")
        self.after(3000, lambda: self.save_status.configure(text=""))

    # ══════════════════════════════════════════════════════════════════════════════
    # ABOUT VIEW
    # ══════════════════════════════════════════════════════════════════════════════
    def _build_about_view(self):
        hdr = ctk.CTkFrame(self.about_view, fg_color=HDR_BG, corner_radius=0, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkFrame(hdr, fg_color=CARD_BDR, height=1).pack(side="bottom", fill="x")
        ctk.CTkLabel(
            hdr, text="About",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=TEXT_DARK
        ).place(x=28, rely=0.5, anchor="w")

        body = ctk.CTkFrame(self.about_view, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=28, pady=20)

        card = ctk.CTkFrame(body, fg_color=CARD_BG, corner_radius=20,
                            border_width=1, border_color=CARD_BDR)
        card.pack(fill="x")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=40, pady=36)

        _about_logo = _load_logo((64, 64))
        ctk.CTkLabel(
            inner,
            image=_about_logo if _about_logo else None,
            text="" if _about_logo else "✈",
            font=ctk.CTkFont(size=56),
            text_color=ACCENT_BLUE
        ).pack()
        ctk.CTkLabel(
            inner, text="TG Media Downloader",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=TEXT_DARK
        ).pack(pady=(4, 2))
        ctk.CTkLabel(
            inner, text=f"Version {APP_VERSION}  •  Built with Telethon & CustomTkinter",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=TEXT_MUTED
        ).pack()

        ctk.CTkFrame(inner, fg_color=CARD_BDR, height=1).pack(fill="x", pady=24)

        features = [
            ("📥", "Media Browser — browse & filter by category before downloading"),
            ("⚡", "Parallel fetch — all category filters load simultaneously"),
            ("🔄", "Smart deduplication — skips already-downloaded files automatically"),
            ("⏸", "Concurrent downloads with pause / resume & persistent queue"),
            ("🔍", "Real-time search filter inside the Media Browser"),
            ("🔔", "Toast notifications when a download queue completes"),
            ("📁", "Custom download directories & speed cap per session"),
            ("🔒", "Secure Telegram session — credentials never stored in plain text"),
        ]
        for icon, text in features:
            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=icon, font=ctk.CTkFont(size=18), width=32).pack(side="left")
            ctk.CTkLabel(
                row, text=text,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=TEXT_DARK, anchor="w"
            ).pack(side="left", padx=10, fill="x")

        # Warning / Disclaimer
        ctk.CTkFrame(inner, fg_color=CARD_BDR, height=1).pack(fill="x", pady=20)
        ctk.CTkLabel(
            inner,
            text="⚠️  Responsible Use Reminder",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=ACCENT_AMBER
        ).pack()
        ctk.CTkLabel(
            inner,
            text="Only download content you have permission to access.\n"
                 "Respect Telegram\'s Terms of Service and copyright laws.\n"
                 "The author is not responsible for misuse of this tool.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_MUTED,
            justify="center"
        ).pack(pady=(4, 0))


        # GitHub Repo Link
        ctk.CTkFrame(inner, fg_color=CARD_BDR, height=1).pack(fill="x", pady=24)
        repo_link = ctk.CTkLabel(
            inner,
            text="GitHub Repository",
            font=ctk.CTkFont(family="Segoe UI", size=13, underline=True),
            text_color=BTN_PRIMARY,
            cursor="hand2"
        )
        repo_link.pack()
        repo_link.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/vinodkr494/telegram-media-downloader"))

    # ══════════════════════════════════════════════════════════════════════════════
    # SEARCH / DOWNLOAD FLOW
    # ══════════════════════════════════════════════════════════════════════════════
    def on_fetch_media_start(self):
        channel_input = self.search_entry.get().strip()
        if not channel_input:
            return

        # Full-screen overlay
        self.loading_overlay = ctk.CTkFrame(self, fg_color="#0D1117", corner_radius=0)
        self.loading_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        self._spinner_label = ctk.CTkLabel(
            self.loading_overlay,
            text="⠋  Fetching Channel Media…",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color="#2AABEE"
        )
        self._spinner_label.place(relx=0.5, rely=0.46, anchor="center")

        ctk.CTkLabel(
            self.loading_overlay,
            text="All categories load in parallel — this should be fast ⚡",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#64748B"
        ).place(relx=0.5, rely=0.53, anchor="center")

        self._spinner_running = True
        self._spinner_idx = 0
        self._spinner_tick()

        self.fetch_btn.configure(text="Fetching…", state="disabled")
        threading.Thread(
            target=self.run_fetch_media_thread,
            args=(channel_input,),
            daemon=True
        ).start()

    _SPINNER_CHARS = list("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")

    def _spinner_tick(self):
        if not getattr(self, '_spinner_running', False): return
        if not hasattr(self, '_spinner_label'): return
        try:
            char = self._SPINNER_CHARS[self._spinner_idx % len(self._SPINNER_CHARS)]
            self._spinner_label.configure(text=f"{char}  Fetching Channel Media…")
            self._spinner_idx += 1
            self.after(80, self._spinner_tick)
        except Exception:
            pass

    def _stop_spinner(self):
        self._spinner_running = False
        if hasattr(self, 'loading_overlay') and self.loading_overlay.winfo_exists():
            self.loading_overlay.destroy()
        
    def run_fetch_media_thread(self, channel_input):
        future = asyncio.run_coroutine_threadsafe(
            self.async_fetch_media_flow(channel_input), self.loop
        )
        try:
            future.result()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error fetching channel: {e}")
            self.after(0, lambda: self.fetch_btn.configure(text="🔍 Fetch Media", state="normal"))
            
    async def async_fetch_media_flow(self, channel_input):
        try:
            channel = await fetch_channel(self.client, channel_input)
            categories = await fetch_categorized_media(self.client, channel, limit=500)
            self.after(0, lambda: self.show_media_browser_modal(channel, channel_input, categories))
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Fetch Error: {e}")
            self.after(0, self._stop_spinner)
            self.after(0, lambda: self.fetch_btn.configure(text="🔍 Fetch Media", state="normal"))
            
    def show_media_browser_modal(self, channel, channel_input, categories):
        self._stop_spinner()
        self.fetch_btn.configure(text="🔍 Fetch Media", state="normal")
        
        modal = ctk.CTkToplevel(self)
        modal.title(f"Media Browser - {channel.title or channel.id}")
        modal.geometry("800x600")
        modal.grab_set()
        
        tabview = ctk.CTkTabview(modal)
        tabview.pack(fill="both", expand=True, padx=20, pady=(20, 5))

        self.selected_media_to_download = {}
        category_vars = {}  # {cat_name: [(var, msg, row_frame, name_lower)]}
        total_across_all = sum(len(msgs) for msgs in categories.values() if msgs)

        # ── Live selection counter (sits between tab and bottom buttons) ──
        selection_lbl = ctk.CTkLabel(
            modal, text=f"0 of {total_across_all} files selected",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_MUTED
        )
        selection_lbl.pack(pady=(0, 2))

        def update_selection_label():
            count = sum(v.get() for entries in category_vars.values() for v, *_ in entries)
            selection_lbl.configure(
                text=f"{count} of {total_across_all} files selected",
                text_color=ACCENT_GREEN if count > 0 else TEXT_MUTED
            )

        for cat_name, msgs in categories.items():
            if not msgs: continue
            tab = tabview.add(f"{cat_name} ({len(msgs)})")
            category_vars[cat_name] = []

            # ── Select All / Clear All ──
            btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
            btn_frame.pack(fill="x", pady=(5, 2))

            def make_select_all(c_name):
                def select_all():
                    for v, *_ in category_vars[c_name]: v.set(1)
                    update_selection_label()
                return select_all

            def make_clear_all(c_name):
                def clear_all():
                    for v, *_ in category_vars[c_name]: v.set(0)
                    update_selection_label()
                return clear_all

            ctk.CTkButton(btn_frame, text="Select All", width=100, command=make_select_all(cat_name)).pack(side="left", padx=(5, 4))
            ctk.CTkButton(btn_frame, text="Clear All",  width=100, fg_color=BTN_HOVER, command=make_clear_all(cat_name)).pack(side="left")

            # ── Search bar ──
            search_var = ctk.StringVar()
            ctk.CTkEntry(
                tab, textvariable=search_var,
                placeholder_text="\U0001F50D  Search files\u2026",
                height=32, corner_radius=8, border_width=1
            ).pack(fill="x", padx=5, pady=(2, 4))

            scroll_frame = ctk.CTkScrollableFrame(tab, fg_color=CARD_BG)
            scroll_frame.pack(fill="both", expand=True, pady=(0, 5))

            rows_in_tab = []

            for m in msgs:
                name = f"Message ID: {m.id}"
                file_size = ""
                if getattr(m, 'document', None):
                    if m.file and m.file.name: name = m.file.name
                    file_size = f" ({m.document.size // 1024} KB)"
                elif getattr(m, 'video', None):
                    file_size = f" ({m.video.size // 1024} KB)"
                elif getattr(m, 'photo', None):
                    file_size = " (Photo)"

                display_text = f"{name}{file_size}\n{m.date.strftime('%Y-%m-%d %H:%M')}"
                var = ctk.IntVar(value=0)

                row_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
                row_frame.pack(fill="x", pady=2, padx=5)

                def on_check(update=update_selection_label):
                    update()

                chk = ctk.CTkCheckBox(row_frame, text="", variable=var, command=on_check, width=24)
                chk.pack(side="left", padx=(0, 5), pady=8)

                lbl = ctk.CTkLabel(row_frame, text=display_text, justify="left", anchor="w", font=ctk.CTkFont(size=12))
                lbl.pack(side="left", fill="x", expand=True, pady=4)

                category_vars[cat_name].append((var, m, row_frame, name.lower()))
                rows_in_tab.append((row_frame, name.lower()))

            # ── Search filter binding ──
            def make_filter(rows, svar):
                def do_filter(*_):
                    q = svar.get().lower().strip()
                    for rf, nm in rows:
                        try:
                            if not q or q in nm: rf.pack(fill="x", pady=2, padx=5)
                            else: rf.pack_forget()
                        except Exception: pass
                return do_filter
            search_var.trace_add("write", make_filter(rows_in_tab, search_var))


        # Bottom Actions
        bottom_frame = ctk.CTkFrame(modal, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=20, pady=10)
        
        def on_download_clicked():
            download_btn.configure(text="Starting Download...", state="disabled")
            for child in bottom_frame.winfo_children():
                if child != download_btn: child.configure(state="disabled")
                
            selected_msgs = []
            for cat_msgs in category_vars.values():
                for var, msg, *_ in cat_msgs:  # var, msg, row_frame, name_lower
                    if var.get() == 1:
                        selected_msgs.append(msg)
            
            if not selected_msgs:
                download_btn.configure(text="Download Selected", state="normal")
                for child in bottom_frame.winfo_children():
                    if child != download_btn: child.configure(state="normal")
                return
                
            modal.destroy()
            threading.Thread(
                target=self.run_async_download_selected,
                args=(channel, channel_input, selected_msgs),
                daemon=True
            ).start()
            
        download_btn = ctk.CTkButton(bottom_frame, text="Download Selected", fg_color=ACCENT_GREEN, hover_color="#20A050", command=on_download_clicked)
        download_btn.pack(side="right")
        ctk.CTkButton(bottom_frame, text="Cancel", fg_color=BTN_HOVER, command=modal.destroy).pack(side="right", padx=10)

    def run_async_download_selected(self, channel, channel_input, messages_to_download):
        future = asyncio.run_coroutine_threadsafe(
            self.async_download_selected_flow(channel, channel_input, messages_to_download), self.loop
        )
        try:
            future.result()
        except Exception as e:
            print(f"Error in async download runner: {e}")

    def save_task_state(self, channel_input, media_id, is_paused, min_id=None, max_id=None):
        tasks = load_tasks()
        found = False
        for t in tasks:
            if t.get("channel_input") == channel_input and t.get("media_id") == media_id:
                t["paused"] = is_paused
                found = True
                break
        if not found:
            tasks.append({"channel_input": channel_input, "media_id": media_id, "paused": is_paused, "min_id": min_id, "max_id": max_id})
        save_tasks(tasks)

    async def async_download_selected_flow(self, channel, channel_input, messages_to_download):
        try:
            # Re-filter downloaded state
            messages_to_download = [m for m in messages_to_download if m.id not in self.downloaded_state]
            if not messages_to_download:
                return
                
            total_items = len(messages_to_download)
            completed_initial = 0

            # Store in 'channel_title/selected_media' directory
            folder_name = os.path.join(
                self.download_path,
                channel.title or str(channel.id),
                "selected_media"
            )
            os.makedirs(folder_name, exist_ok=True)

            # Generate a unique task_id with timestamp to avoid reusing a stale paused event
            import time as _time
            task_id = f"{channel.id}_custom_{int(_time.time())}"
            title = f"{channel.title or channel.id} (Custom Selection)"

            # Always start with a fresh, un-set cancel event
            global_cancel_event = asyncio.Event()
            global_cancel_event.clear()
            self.task_cancel_events[task_id] = global_cancel_event
            
            # Using 7 as a pseudo media_id for 'Custom Selection' memory
            media_id = 7
            
            self.after(0, self.save_task_state, channel_input, media_id, False)
            self.after(0, self.add_channel_card,
                       task_id, title, total_items, completed_initial,
                       folder_name, channel_input, media_id, False)

            if os.path.exists(folder_name):
                def populate_existing():
                    try:
                        for f in os.listdir(folder_name):
                            if os.path.isfile(os.path.join(folder_name, f)):
                                self.add_file_to_list(task_id, f)
                    except Exception:
                        pass
                self.after(100, populate_existing)

            self.after(0, lambda: self.fetch_btn.configure(text="🔍 Fetch Media", state="normal"))

            completed_count = [0]

            def on_file_complete(msg_id, paused=False, filepath=None):
                if not paused:
                    completed_count[0] += 1
                    self.after(0, self._update_channel_progress,
                               task_id, completed_count[0], total_items, paused)
                    if filepath:
                        filename = os.path.basename(filepath)
                        self.after(0, self.add_file_to_list, task_id, filename)
                else:
                    self.after(0, self._update_channel_progress,
                               task_id, completed_count[0], total_items, paused)

            def on_file_progress(msg_id, current, total, speed_str="0 KB/s"):
                pct = current / total if total > 0 else 0
                self.after(0, self._update_active_file_progress, task_id, pct, speed_str)

            await download_in_batches_headless(
                messages=messages_to_download,
                folder_name=folder_name,
                batch_size=self.download_limit,
                downloaded_state=self.downloaded_state,
                progress_cb=on_file_progress,
                complete_cb=on_file_complete,
                task_cancel_event=global_cancel_event,
                max_speed_kb=self.max_speed_kb if self.max_speed_kb > 0 else None
            )

        except Exception as e:
            print(f"Download Error: {e}")
            traceback.print_exc()
            self.after(0, lambda: self.fetch_btn.configure(text="🔍 Fetch Media", state="normal"))

    # ── Backward compatibility for resumed tasks ──────────────────────────────
    def run_async_download(self, channel_input, media_id=None, is_paused=False, min_id=None, max_id=None):
        future = asyncio.run_coroutine_threadsafe(
            self.async_download_flow(channel_input, media_id, is_paused, min_id, max_id), self.loop
        )
        try:
            future.result()
        except Exception as e:
            print(f"Error in async download runner: {e}")

    async def async_download_flow(self, channel_input, media_id=None, is_paused=False, min_id=None, max_id=None):
        try:
            if media_id is None:
                media_id = 6 # Default to All Media

            channel  = await fetch_channel(self.client, channel_input)
            messages = await get_messages_by_type(self.client, channel, media_id, min_id, max_id)

            all_messages_count   = len(messages)
            messages_to_download = [m for m in messages if m.id not in self.downloaded_state]
            total_items          = all_messages_count
            completed_initial    = all_messages_count - len(messages_to_download)

            base_folder = {1: "images", 2: "videos", 3: "pdfs",
                           4: "zips",   5: "audio",  6: "all_media", 7: "selected_media"}
            folder_name = os.path.join(
                self.download_path,
                channel.title or str(channel.id),
                base_folder.get(media_id, "all_media")
            )
            os.makedirs(folder_name, exist_ok=True)

            task_id = f"{channel.id}_{media_id}"
            title   = channel.title or f"Channel ID: {channel.id}"

            global_cancel_event = asyncio.Event()
            global_cancel_event.clear()  # Always start fresh
            self.task_cancel_events[task_id] = global_cancel_event
            if is_paused:
                global_cancel_event.set()

            self.after(0, self.save_task_state, channel_input, media_id, is_paused)
            self.after(0, self.add_channel_card,
                       task_id, title, total_items, completed_initial,
                       folder_name, channel_input, media_id, is_paused)

            if os.path.exists(folder_name):
                def populate_existing():
                    try:
                        for f in os.listdir(folder_name):
                            if os.path.isfile(os.path.join(folder_name, f)):
                                self.add_file_to_list(task_id, f)
                    except Exception:
                        pass
                self.after(100, populate_existing)

            completed_count = [completed_initial]

            def on_file_complete(msg_id, paused=False, filepath=None):
                if not paused:
                    completed_count[0] += 1
                    self.after(0, self._update_channel_progress,
                               task_id, completed_count[0], total_items, paused)
                    if filepath:
                        filename = os.path.basename(filepath)
                        self.after(0, self.add_file_to_list, task_id, filename)
                else:
                    self.after(0, self._update_channel_progress,
                               task_id, completed_count[0], total_items, paused)

            def on_file_progress(msg_id, current, total, speed_str="0 KB/s"):
                pct = current / total if total > 0 else 0
                self.after(0, self._update_active_file_progress, task_id, pct, speed_str)

            if not messages_to_download:
                self.after(0, self._update_channel_progress, task_id, total_items, total_items, False)
                return

            if not is_paused:
                await download_in_batches_headless(
                    messages=messages_to_download,
                    folder_name=folder_name,
                    batch_size=self.download_limit,
                    downloaded_state=self.downloaded_state,
                    progress_cb=on_file_progress,
                    complete_cb=on_file_complete,
                    task_cancel_event=global_cancel_event,
                    max_speed_kb=self.max_speed_kb if self.max_speed_kb > 0 else None
                )
            else:
                self.after(0, self._update_channel_progress,
                           task_id, completed_count[0], total_items, True)

        except Exception as e:
            print(f"Download Error: {e}")
            traceback.print_exc()

    # ── Progress updates ────────────────────────────────────────────────────────
    def _update_active_file_progress(self, task_id, pct, speed_str):
        if task_id not in self.channel_cards:
            return
        el = self.channel_cards[task_id]
        for k in ("pb_active", "pb_active_d"):
            if k in el: el[k].set(pct)
        if speed_str != "0 KB/s":
            for k in ("badge_speed", "badge_speed_d"):
                if k in el: el[k].configure(text=speed_str, text_color=ACCENT_GREEN)

    def _update_channel_progress(self, task_id, completed, total, paused):
        if task_id not in self.channel_cards:
            return
        el  = self.channel_cards[task_id]
        pct = completed / total if total > 0 else 0

        for pk in ("pb", "pb_d"):
            if pk in el: el[pk].set(pct)
        for ak in ("pb_active", "pb_active_d"):
            if ak in el: el[ak].set(0)

        if paused:
            for pk in ("pb", "pb_d"):
                if pk in el: el[pk].configure(progress_color=ACCENT_AMBER)
            for sk in ("badge_speed", "badge_speed_d"):
                if sk in el: el[sk].configure(text="Paused", text_color=ACCENT_AMBER)
            for lk in ("status_lbl", "status_lbl_d"):
                if lk in el: el[lk].configure(
                    text=f"Paused at {completed} / {total} files", text_color=ACCENT_AMBER
                )
        elif completed >= total:
            for pk in ("pb", "pb_d"):
                if pk in el: el[pk].configure(progress_color=ACCENT_GREEN)
            for sk in ("badge_speed", "badge_speed_d"):
                if sk in el: el[sk].configure(text="\u2713 Done", text_color=ACCENT_GREEN)
            for bk in ("btn_pause", "btn_pause_d"):
                if bk in el: el[bk].configure(state="disabled", text="\u2713 Done")
            for lk in ("status_lbl", "status_lbl_d"):
                if lk in el: el[lk].configure(
                    text=f"Complete!  {completed} files downloaded", text_color=ACCENT_GREEN
                )
            # Fire toast notification
            title = el.get("channel_input", "Download")
            self.show_toast(f"\u2705  {el.get('channel_input', 'Download')} — all {completed} files complete!")
        else:
            for pk in ("pb", "pb_d"):
                if pk in el: el[pk].configure(progress_color=ACCENT_GREEN)
            for sk in ("badge_speed", "badge_speed_d"):
                if sk in el: el[sk].configure(text_color=TEXT_MUTED)
            for lk in ("status_lbl", "status_lbl_d"):
                if lk in el: el[lk].configure(
                    text=f"Downloaded  {completed} / {total} files", text_color=TEXT_MUTED
                )

    # ── Toast Notification ───────────────────────────────────────────────────────────────
    def show_toast(self, message, duration_ms=3000):
        """Show a brief success notification in the bottom-right corner."""
        toast = ctk.CTkFrame(
            self, fg_color="#1E293B", corner_radius=12,
            border_width=1, border_color="#334155"
        )
        ctk.CTkLabel(
            toast, text=message,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#F8FAFC",
            padx=16, pady=10
        ).pack()
        toast.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=-20)
        self.after(duration_ms, lambda: toast.destroy() if toast.winfo_exists() else None)

    # ══════════════════════════════════════════════════════════════════════════════
    # LOGOUT
    # ══════════════════════════════════════════════════════════════════════════════
    def on_logout_click(self):
        if self.client:
            threading.Thread(target=self._async_logout, daemon=True).start()

    def _async_logout(self):
        future = asyncio.run_coroutine_threadsafe(self._logout_coro(), self.loop)
        try:
            future.result()
        except Exception:
            pass

    async def _logout_coro(self):
        try:
            await self.client.log_out()
            await self.client.disconnect()
        except Exception:
            pass
        session_file = f"{SESSION_NAME}.session"
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
            except Exception:
                pass
        self.client = None
        self.after(0, self.show_login_screen)


if __name__ == "__main__":
    app = DownloaderApp()
    app.mainloop()
