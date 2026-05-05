import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import os
import shutil
from pathlib import Path
import re
import yaml
import pykakasi
import ctypes
from typing import List, Dict, Optional, Any

class OggRenameApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("OGG File Renamer")
        self.root.geometry("1000x800")

        self.input_paths: List[Path] = []
        self.output_dir: Optional[Path] = None
        
        # Kakasi setup
        self.kks = pykakasi.kakasi()

        # Variables
        self.char_limit_var = tk.StringVar(value="63")
        self.filter_long_var = tk.BooleanVar(value=False)
        self.preview_data: List[Dict[str, Any]] = [] 
        self.status_var = tk.StringVar(value="準備完了")
        
        self.setup_styles()
        self.setup_ui()

    def setup_styles(self) -> None:
        style = ttk.Style()
        
        base_font = ("Yu Gothic UI", 10)
        head_font = ("Yu Gothic UI", 12, "bold")
        
        style.configure(".", font=base_font)
        style.configure("Treeview.Heading", font=head_font)
        style.configure("TButton", padding=6)
        style.configure("TLabel", padding=2)
        style.configure("TLabelframe", padding=15)
        style.configure("TLabelframe.Label", font=head_font, foreground="#333333")
        
        # Custom button styles
        style.configure("Action.TButton", font=("Yu Gothic UI", 10, "bold"), foreground="blue")
        style.configure("Run.TButton", font=("Yu Gothic UI", 11, "bold"), padding=10)
        
        # Treeview row height
        style.configure("Treeview", rowheight=28)

    def setup_ui(self) -> None:
        # Main Layout: Sidebar (Left) + Content (Right)
        
        # PanedWindow for resizable split
        self.paned = ttk.PanedWindow(self.root, orient="horizontal")
        self.paned.pack(fill="both", expand=True, padx=10, pady=10)
        
        self._setup_sidebar()
        self._setup_content_area()
        self._setup_status_bar()

    def _setup_sidebar(self) -> None:
        # --- Left Sidebar (Controls) ---
        self.sidebar = ttk.Frame(self.paned, width=300)
        self.paned.add(self.sidebar, weight=1)
        
        # 1. Input Section
        input_group = ttk.LabelFrame(self.sidebar, text="入力設定")
        input_group.pack(fill="x", padx=0, pady=(0, 10))
        
        ttk.Button(input_group, text="📁 フォルダを選択", command=self.select_folder).pack(fill="x", pady=5)
        ttk.Button(input_group, text="📄 ファイルを選択", command=self.select_files).pack(fill="x", pady=5)
        
        self.path_label = ttk.Label(input_group, text="未選択", foreground="gray", wraplength=250)
        self.path_label.pack(fill="x", pady=5)

        # 2. Settings Section
        settings_group = ttk.LabelFrame(self.sidebar, text="変換・警告設定")
        settings_group.pack(fill="x", padx=0, pady=10)
        
        # Limit setting
        lim_frame = ttk.Frame(settings_group)
        lim_frame.pack(fill="x", pady=5)
        ttk.Label(lim_frame, text="文字数警告:").pack(side="left")
        ttk.Entry(lim_frame, textvariable=self.char_limit_var, width=5).pack(side="left", padx=5)
        ttk.Label(lim_frame, text="文字以上").pack(side="left")

        # 3. Output Section
        output_group = ttk.LabelFrame(self.sidebar, text="出力設定")
        output_group.pack(fill="x", padx=0, pady=10)
        
        ttk.Button(output_group, text="📂 出力先を変更", command=self.select_output_folder).pack(fill="x", pady=5)
        self.output_label = ttk.Label(output_group, text="デフォルト\n(入力フォルダ/renamed)", foreground="gray", wraplength=250)
        self.output_label.pack(fill="x", pady=5)

        # 4. Action Section (Bottom of Sidebar)
        action_frame = ttk.Frame(self.sidebar)
        action_frame.pack(fill="x", pady=20, side="bottom")
        
        self.run_btn = ttk.Button(action_frame, text="リネーム実行", command=self.run_rename, style="Run.TButton", state="disabled")
        self.run_btn.pack(fill="x", pady=5)
        
        ttk.Button(action_frame, text="閉じる", command=self.root.destroy).pack(fill="x")

    def _setup_content_area(self) -> None:
        # --- Right Content (Preview) ---
        self.content_area = ttk.Frame(self.paned)
        self.paned.add(self.content_area, weight=3)
        
        # Top bar in content area
        top_bar = ttk.Frame(self.content_area)
        top_bar.pack(fill="x", pady=(0, 10))
        
        ttk.Label(top_bar, text="プレビュー", font=("Yu Gothic UI", 14, "bold")).pack(side="left")
        ttk.Label(top_bar, text="※ファイル名をダブルクリックで編集", font=("Yu Gothic UI", 9), foreground="#666666").pack(side="left", padx=15, pady=(4, 0))
        ttk.Button(top_bar, text="🔄 更新", command=self.update_preview, width=10).pack(side="right")
        
        # Filter option
        ttk.Checkbutton(self.content_area, text="警告ありのみ表示", variable=self.filter_long_var, command=self.refresh_list).pack(anchor="w", pady=(0, 5))

        # Treeview
        tree_frame = ttk.Frame(self.content_area)
        tree_frame.pack(fill="both", expand=True)
        
        columns = ("original", "renamed", "length", "status")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        self.tree.heading("original", text="元のファイル名")
        self.tree.heading("renamed", text="変換後のファイル名")
        self.tree.heading("length", text="文字数")
        self.tree.heading("status", text="ステータス")
        
        self.tree.column("original", width=300)
        self.tree.column("renamed", width=300)
        self.tree.column("length", width=60, anchor="center")
        self.tree.column("status", width=120, anchor="center")
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Tags and bindings
        self.tree.tag_configure("warning", foreground="red", background="#fff0f0")
        self.tree.tag_configure("ok", foreground="black")
        self.tree.bind("<Double-1>", self.on_double_click)

    def _setup_status_bar(self) -> None:
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w", padding=(5, 2))
        self.status_bar.pack(side="bottom", fill="x")

    def select_folder(self) -> None:
        folder = filedialog.askdirectory()
        if folder:
            self.input_paths = []
            try:
                p = Path(folder)
                self.input_paths = list(p.glob("*.ogg"))
                self.path_label.config(text=f"フォルダ: {folder}\n({len(self.input_paths)} files)")
                self.output_dir = p / "renamed"
                self.output_label.config(text=f"{self.output_dir}")
                self.update_preview()
                self.status_var.set(f"フォルダを読み込みました: {folder}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to list files: {e}")

    def select_files(self) -> None:
        files = filedialog.askopenfilenames(filetypes=[("OGG Files", "*.ogg")])
        if files:
            self.input_paths = [Path(f) for f in files]
            if self.input_paths:
                folder = self.input_paths[0].parent
                self.path_label.config(text=f"ファイル: {len(files)}個")
                self.output_dir = folder / "renamed" 
                self.output_label.config(text=f"{self.output_dir}")
                self.update_preview()
                self.status_var.set(f"{len(files)}個のファイルを読み込みました")

    def select_output_folder(self) -> None:
        folder = filedialog.askdirectory()
        if folder:
            self.output_dir = Path(folder)
            self.output_label.config(text=str(folder))

    def convert_filename(self, filename: str) -> str:
        """
        ファイル名を変換するロジック。
        現在はインスタンスメソッドとしてkksを使用するが、将来的には純粋関数化も視野。
        """
        stem = Path(filename).stem
        
        # 1. Jp -> Romaji
        try:
            result = self.kks.convert(stem)
            romaji = "".join([item['hepburn'] for item in result])
        except Exception as e:
            print(f"Conversion error for {stem}: {e}")
            return stem # Fallback

        # 2. To Halfwidth (Zen to Han) - handled mostly by romaji conversion
        # 3. Space to _
        romaji = romaji.replace(" ", "_").replace("　", "_")
        
        # 4. Remove [^A-Za-z0-9_]
        cleaned = re.sub(r'[^A-Za-z0-9_]', '', romaji)
        
        return cleaned

    def update_preview(self) -> None:
        try:
            limit = int(self.char_limit_var.get())
        except ValueError:
            limit = 63
        
        self.preview_data = []
        has_warning = False
        
        for p in self.input_paths:
            try:
                original_name = p.name
                new_stem = self.convert_filename(original_name)
                # Display only stem in renamed column (Extension omitted in UI)
                new_name_display = new_stem 
                
                length = len(new_stem)
                status = "待機中"
                is_warning = False
                
                if length >= limit:
                    status = "警告: 文字数超過"
                    is_warning = True
                    has_warning = True
                
                self.preview_data.append({
                    "original": original_name,
                    "renamed": new_name_display, # No extension
                    "length": length,
                    "status": status,
                    "is_warning": is_warning,
                    "path": p
                })
            except Exception as e:
                print(f"Error processing {p}: {e}")
                self.preview_data.append({
                    "original": p.name,
                    "renamed": "ERROR",
                    "length": 0,
                    "status": f"エラー: {e}",
                    "is_warning": True,
                    "path": p
                })
                has_warning = True
            
        self.refresh_list()
        
        if has_warning:
            self.run_btn.config(state="disabled")
        else:
            self.run_btn.config(state="normal")

    def refresh_list(self) -> None:
        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        try:
            limit = int(self.char_limit_var.get())
        except ValueError:
            limit = 63
            
        show_only_long = self.filter_long_var.get()
        
        for item in self.preview_data:
            if show_only_long and item["length"] < limit:
                continue
                
            tags = ("warning",) if item["is_warning"] else ("ok",)
            self.tree.insert("", "end", values=(
                item["original"],
                item["renamed"],
                item["length"],
                item["status"]
            ), tags=tags)

    @staticmethod
    def generate_yaml_file(mapping: Dict[str, str], output_dir: Path, prefix: str = "mod") -> Path:
        """
        YAMLファイルを生成して保存する静的メソッド
        """
        yaml_path = output_dir / f"{prefix}_l_japanese.yml"
        
        # Define QuotedStr to force double quotes only on values
        class QuotedStr(str): pass
        yaml.add_representer(QuotedStr, lambda dumper, data: dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"'))
        
        # Create mapping with QuotedStr values
        quoted_mapping = {k: QuotedStr(v) for k, v in mapping.items()}
        
        # Structure for localization
        output_data = {"l_japanese": quoted_mapping}

        with open(yaml_path, "w", encoding="utf-8-sig") as f:
            yaml.dump(output_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False, width=float("inf"), indent=1)
            
        return yaml_path

    def run_rename(self) -> None:
        if not self.output_dir:
            messagebox.showwarning("Warning", "出力先フォルダが設定されていません。")
            return
            
        if not self.preview_data:
            messagebox.showwarning("Warning", "対象ファイルがありません。")
            return

        # Double check for warnings
        for item in self.preview_data:
            if item["is_warning"]:
                 messagebox.showerror("Error", "文字数制限を超過しているファイルがあるため実行できません。")
                 return

        out_path = self.output_dir
        try:
            out_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Error", f"出力フォルダの作成に失敗しました: {e}")
            return
            
        mapping = {}
        success_count = 0
        
        for item in self.preview_data:
            src = item["path"]
            dest_stem = item["renamed"]
            # Append suffix for actual file
            dest_name = f"{dest_stem}{src.suffix}"
            dest = out_path / dest_name
            
            try:
                # Copy with metadata
                shutil.copy2(src, dest)
                
                # Add to mapping (No extensions as requested)
                # Key: Renamed (no ext), Value: Original (no ext)
                k = Path(dest_name).stem
                v = Path(item["original"]).stem
                mapping[k] = v
                
                success_count += 1
                
            except Exception as e:
                print(f"Failed to copy {src}: {e}")
        
        # Generate YAML
        prefix = "mod"
        if self.input_paths:
             prefix = self.input_paths[0].parent.name
        
        try:
            yaml_path = self.generate_yaml_file(mapping, out_path, prefix)
            messagebox.showinfo("Success", f"処理完了: {success_count}ファイルをリネームしてコピーしました。\n作成されたファイル: {yaml_path}")
            self.input_paths = []
            self.preview_data = []
            self.refresh_list()
            self.path_label.config(text="処理完了")
            
        except Exception as e:
             messagebox.showerror("Error", f"YAMLファイルの作成に失敗しました: {e}")

    def on_double_click(self, event: Any) -> None:
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
            
        column = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        
        if not row_id:
            return
            
        # Column #2 is "renamed" (columns are #1, #2, #3, ...)
        if column == "#2":
            self.edit_cell(row_id, column)

    def edit_cell(self, row_id: str, column: str) -> None:
        # Get column index
        col_idx = int(column.replace("#", "")) - 1
        
        # Get coordinates
        x, y, w, h = self.tree.bbox(row_id, column=column)
        
        # Get current value
        values = self.tree.item(row_id, "values")
        current_val = values[col_idx]
        
        # Create Entry
        entry = tk.Entry(self.tree, width=w)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, current_val)
        entry.select_range(0, tk.END)
        entry.focus_set()
        
        # Bind events to close
        def save(event: Optional[Any] = None) -> None:
            new_val = entry.get()
            idx = self.tree.index(row_id)
            
            # Update data
            self.preview_data[idx]["renamed"] = new_val
            
            # Recalculate length/warning
            try:
                limit = int(self.char_limit_var.get())
            except ValueError:
                limit = 63
            
            length = len(new_val)
            self.preview_data[idx]["length"] = length
            
            if length >= limit:
                 self.preview_data[idx]["status"] = "警告: 文字数超過"
                 self.preview_data[idx]["is_warning"] = True
            else:
                 self.preview_data[idx]["status"] = "待機中"
                 self.preview_data[idx]["is_warning"] = False
            
            entry.destroy()
            self.refresh_list()
            self.check_overall_warning()

        def cancel(event: Optional[Any] = None) -> None:
            entry.destroy()

        entry.bind("<Return>", save)
        entry.bind("<FocusOut>", save) # Auto save on click away
        entry.bind("<Escape>", cancel)

    def check_overall_warning(self) -> None:
        has_warning = any(item["is_warning"] for item in self.preview_data)
        if has_warning:
            self.run_btn.config(state="disabled")
        else:
            self.run_btn.config(state="normal")

def main() -> None:
    try:
        # Try to set DPI awareness (Windows 8.1+)
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            # Fallback for Windows Vista/7/8
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass # Non-Windows or older Windows

    try:
        root = tk.Tk()
        OggRenameApp(root)
        root.mainloop()
    except Exception as e:
        messagebox.showerror("Critical Error", f"アプリケーションエラー: {e}")

if __name__ == "__main__":
    main()
