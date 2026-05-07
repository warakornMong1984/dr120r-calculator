"""
DR-120R Printing Calculator — Kivy Android App
===============================================
- หน้าจอบน: เทปคำนวณ (ScrollView)
- หน้าจอล่าง: แป้นพิมพ์
- พิมพ์ตรงไป Rongta RP326 ผ่าน TCP (ESC/POS)
"""

import socket
import datetime
import threading
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex
from kivy.properties import StringProperty, ListProperty

# ── Colors ──
C_BG        = get_color_from_hex('#1a1a1a')
C_TAPE_BG   = get_color_from_hex('#fffef0')
C_DISPLAY   = get_color_from_hex('#b8c890')
C_DISPLAY_T = get_color_from_hex('#1a2a00')
C_RED       = get_color_from_hex('#8b1a1a')
C_ORANGE    = get_color_from_hex('#8a3e00')
C_GREEN     = get_color_from_hex('#1e4a1a')
C_DARK      = get_color_from_hex('#3d3d3d')
C_TOTAL     = get_color_from_hex('#cc0000')
C_SUBTOTAL  = get_color_from_hex('#0000aa')
C_DIVIDER   = get_color_from_hex('#b85000')
C_WHITE     = get_color_from_hex('#ffffff')
C_BLACK     = get_color_from_hex('#000000')

Window.clearcolor = C_BG

# ══════════════════════════════════════════════
# ESC/POS PRINTER
# ══════════════════════════════════════════════
class RongtaRP326:
    ESC = b'\x1b'
    GS  = b'\x1d'

    def __init__(self, ip, port=9100, timeout=5):
        self.ip, self.port, self.timeout = ip, port, timeout
        self._sock = None
        self._buf  = bytearray()

    def connect(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(self.timeout)
        self._sock.connect((self.ip, self.port))
        return self

    def disconnect(self):
        if self._sock:
            try: self._sock.close()
            except: pass
            self._sock = None

    def __enter__(self): return self.connect()
    def __exit__(self, *_): self.disconnect()

    def write(self, b): self._buf.extend(b); return self
    def text(self, s):
        try: self._buf.extend(s.encode('cp874'))
        except: self._buf.extend(s.encode('ascii', errors='replace'))
        return self
    def lf(self, n=1): self._buf.extend(b'\x0a' * n); return self
    def flush(self):
        data = bytes(self._buf)
        for i in range(0, len(data), 4096):
            self._sock.send(data[i:i+4096])
        self._buf.clear()

    def init(self):      return self.write(self.ESC + b'\x40')
    def bold(self, on):  return self.write(self.ESC + b'\x45' + (b'\x01' if on else b'\x00'))
    def align(self, a):  return self.write(self.ESC + b'\x61' + {
                                 'left':b'\x00','center':b'\x01','right':b'\x02'}[a])
    def big(self):       return self.write(self.ESC + b'\x21\x30')
    def normal(self):    return self.write(self.ESC + b'\x21\x00')
    def cut(self):       return self.write(self.GS  + b'\x56\x00')
    def line(self, c, n=42): return self.text(c * n).lf()

    def print_dr120r_tape(self, tape_items, cols=42):
        now = datetime.datetime.now().strftime("%d/%m/%Y  %H:%M:%S")
        self.init()
        self.align('center').big()
        self.text("CASIO DR-120R").lf()
        self.normal().text("PRINTING CALCULATOR").lf()
        self.line('-', cols).text(now).lf().line('=', cols)
        self.align('left')

        for item in tape_items:
            t = item.get('type', 'normal')
            if t == 'spacer': self.lf(); continue
            if t == 'divider': self.line('-', cols); continue

            op  = (item.get('op', '') or '').ljust(4)
            val = item.get('value', 0)
            num = f"{val:>{cols-4},.2f}"
            row = op + num

            if t == 'total':
                self.bold(True).line('=', cols)
                self.text(row).lf()
                self.line('=', cols).bold(False)
            elif t == 'subtotal':
                self.bold(True).text(row).lf().bold(False)
            else:
                self.text(row).lf()

        self.lf().align('center').line('=', cols)
        self.text("*** END OF TAPE ***").lf(3).cut()
        self.flush()


# ══════════════════════════════════════════════
# CALCULATOR ENGINE
# ══════════════════════════════════════════════
class CalcEngine:
    def __init__(self):
        self.reset()

    def reset(self):
        self.entry       = '0'
        self.result      = 0.0
        self.op          = None
        self.new_entry   = True
        self.decimal     = False
        self.memory      = 0.0
        self.accum       = 0.0
        self.has_accum   = False
        self.md_accum    = 0.0
        self.md_op       = None
        self.in_md       = False
        self.prev_pm_op  = None
        self.grand_total = 0.0
        self.has_gt      = False
        self.tape        = []   # list of dicts

    def fmt(self, n):
        return f"{n:,.2f}"

    def val(self):
        try: return float(self.entry)
        except: return 0.0

    def add_tape(self, op, value, ttype='normal'):
        self.tape.append({'op': op, 'value': value, 'type': ttype})

    def add_divider(self):
        self.tape.append({'type': 'divider'})

    def add_spacer(self):
        self.tape.append({'type': 'spacer'})

    def compute(self, a, op, b):
        if op == '+': return a + b
        if op == '-': return a - b
        if op == '*': return a * b
        if op == '/': return (a / b) if b != 0 else float('nan')
        return b

    OP_SYM = {'+':'+', '-':'−', '*':'×', '/':'÷'}

    def press(self, key):
        """Returns (display_str, tape_changed)"""
        tape_changed = False

        if key in '0123456789':
            if self.new_entry:
                self.entry = '0' if key == '0' else key
                self.new_entry = False
                self.decimal = False
            else:
                if self.decimal:
                    self.entry += key
                elif self.entry == '0':
                    self.entry = key
                else:
                    self.entry += key
            return self.entry, False

        if key == '00':
            if not self.new_entry and self.entry != '0':
                self.entry += '00'
            return self.entry, False

        if key == '.':
            if self.new_entry: self.entry = '0'; self.new_entry = False
            if not self.decimal: self.decimal = True; self.entry += '.'
            return self.entry, False

        if key == 'BS':
            if not self.new_entry and len(self.entry) > 0:
                if self.entry[-1] == '.': self.decimal = False
                self.entry = self.entry[:-1] or '0'
            return self.entry, False

        if key == '+/-':
            v = self.val()
            self.entry = str(-v)
            return self.entry, False

        v = self.val()

        if key == 'CA':
            self.reset()
            return '0', True

        if key == 'C':
            self.entry = '0'; self.new_entry = True; self.decimal = False
            return '0', False

        if key in ('+', '-', '*', '/'):
            is_md = key in ('*', '/')
            is_pm = key in ('+', '-')

            if self.new_entry:
                self.op = key
                if is_md and not self.in_md: self.in_md = True
                return self.fmt(v), False

            if is_md:
                if self.in_md:
                    self.add_tape(self.OP_SYM[self.op], v)
                    res = self.compute(self.md_accum, self.md_op or self.op, v)
                    self.add_divider(); self.add_spacer()
                    self.add_tape('+', res); self.add_spacer()
                    self.md_accum = res; self.md_op = key
                    self.accum += res; self.has_accum = True
                else:
                    self.add_tape(self.OP_SYM[key], v)
                    self.md_accum = v; self.md_op = key; self.in_md = True
                self.op = key; self.new_entry = True
                return self.fmt(v), True

            if is_pm:
                if self.in_md:
                    self.add_tape(self.OP_SYM[self.op], v)
                    res = self.compute(self.md_accum, self.md_op or self.op, v)
                    self.add_divider(); self.add_spacer()
                    self.add_tape('+', res); self.add_spacer()
                    self.accum += res; self.has_accum = True
                    self.in_md = False; self.md_accum = 0; self.md_op = None
                else:
                    self.add_tape(self.OP_SYM.get(key, key), v)
                    self.accum = self.compute(self.accum, key, v) if self.has_accum else v
                    self.has_accum = True
                self.prev_pm_op = key; self.op = key; self.new_entry = True
                return self.fmt(self.accum), True

        if key == '=':
            final = v
            if self.in_md:
                self.add_tape(self.OP_SYM[self.op], v)
                md_res = self.compute(self.md_accum, self.md_op or self.op, v)
                self.add_divider(); self.add_spacer()
                self.add_tape('+', md_res); self.add_spacer()
                final = self.compute(self.accum, self.prev_pm_op or '+', md_res) if self.has_accum else md_res
                self.in_md = False; self.md_accum = 0; self.md_op = None
            elif self.op:
                self.add_tape(self.OP_SYM[self.op], v)
                final = self.compute(self.accum if self.has_accum else self.result, self.op, v)

            self.grand_total += final; self.has_gt = True
            self.add_tape('=', final, 'total')
            self.entry = str(final); self.result = final
            self.op = None; self.new_entry = True
            self.accum = 0; self.has_accum = False; self.prev_pm_op = None
            return self.fmt(final), True

        if key == 'ST':
            stv = self.accum if self.has_accum else (self.md_accum if self.in_md else self.result)
            self.add_tape('ST', stv, 'subtotal')
            self.entry = str(stv); self.new_entry = True
            return self.fmt(stv), True

        if key == 'GT':
            if self.has_gt:
                self.add_tape('GT', self.grand_total, 'total')
                self.entry = str(self.grand_total)
                self.new_entry = True
                gt = self.grand_total
                self.grand_total = 0; self.has_gt = False
                return self.fmt(gt), True
            return self.fmt(v), False

        if key == 'M+':
            self.memory += v
            self.add_tape('M+', v)
            self.new_entry = True
            return self.fmt(v), True

        if key == 'M-':
            self.memory -= v
            self.add_tape('M−', v)
            self.new_entry = True
            return self.fmt(v), True

        if key == 'MRC':
            self.entry = str(self.memory)
            self.new_entry = False
            return self.fmt(self.memory), False

        if key == '%':
            if self.op:
                pct = self.result * (v / 100) if self.op in ('+', '-') else v / 100
                self.add_tape('%', pct)
                self.entry = str(pct); self.new_entry = True
                return self.fmt(pct), True
            return self.fmt(v), False

        return self.entry, False


# ══════════════════════════════════════════════
# KV LAYOUT
# ══════════════════════════════════════════════
KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp
#:import get_color_from_hex kivy.utils.get_color_from_hex

<CalcButton@Button>:
    font_name: 'Roboto'
    font_size: sp(22)
    bold: True
    color: 1,1,1,1
    background_normal: ''
    border: (0,0,0,0)

<RootLayout>:
    orientation: 'vertical'
    spacing: 0

    # ── TAPE SECTION (top 38%) ──
    BoxLayout:
        orientation: 'vertical'
        size_hint_y: 0.38
        canvas.before:
            Color:
                rgba: get_color_from_hex('#fffef0')
            Rectangle:
                pos: self.pos
                size: self.size

        # Toolbar
        BoxLayout:
            size_hint_y: None
            height: dp(40)
            padding: dp(4)
            spacing: dp(6)
            canvas.before:
                Color:
                    rgba: get_color_from_hex('#dddddd')
                Rectangle:
                    pos: self.pos
                    size: self.size
            Button:
                text: 'Print'
                font_size: sp(13)
                bold: True
                background_normal: ''
                background_color: get_color_from_hex('#1a5a1a')
                color: 1,1,1,1
                on_release: app.open_print_dialog()
            Button:
                text: 'JPG'
                font_size: sp(13)
                bold: True
                background_normal: ''
                background_color: get_color_from_hex('#1a3a8a')
                color: 1,1,1,1
                on_release: app.export_jpg()
            Button:
                text: 'ล้างเทป'
                font_size: sp(13)
                background_normal: ''
                background_color: get_color_from_hex('#8a1a1a')
                color: 1,1,1,1
                on_release: app.clear_tape()

        # Tape scroll
        ScrollView:
            id: tape_scroll
            do_scroll_x: False
            GridLayout:
                id: tape_grid
                cols: 1
                size_hint_y: None
                height: self.minimum_height
                padding: dp(8)
                spacing: 0

    # ── CALC SECTION (bottom 62%) ──
    BoxLayout:
        orientation: 'vertical'
        size_hint_y: 0.62
        padding: dp(6)
        spacing: dp(4)
        canvas.before:
            Color:
                rgba: get_color_from_hex('#2a2a2a')
            Rectangle:
                pos: self.pos
                size: self.size

        # Display
        Label:
            id: display
            text: '0.'
            font_size: sp(32)
            bold: True
            halign: 'right'
            valign: 'middle'
            size_hint_y: None
            height: dp(54)
            padding_x: dp(12)
            canvas.before:
                Color:
                    rgba: get_color_from_hex('#b8c890')
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(4)]
            color: get_color_from_hex('#1a2a00')
            text_size: self.size

        # Keypad Grid
        GridLayout:
            cols: 5
            rows: 5
            spacing: dp(5)
            size_hint_y: 1

            # Row 1: CA ÷ × [+↕2] [-↕2]
            CalcButton:
                text: 'CA'
                background_color: get_color_from_hex('#8b1a1a')
                on_release: app.key_press('CA')
            CalcButton:
                text: '÷'
                background_color: get_color_from_hex('#8a3e00')
                on_release: app.key_press('/')
            CalcButton:
                text: '×'
                background_color: get_color_from_hex('#8a3e00')
                on_release: app.key_press('*')
            CalcButton:
                id: btn_plus
                text: '+'
                background_color: get_color_from_hex('#8a3e00')
                size_hint_y: None
                height: dp(0)  # set by code
                on_release: app.key_press('+')
            CalcButton:
                id: btn_minus
                text: '−'
                background_color: get_color_from_hex('#8a3e00')
                size_hint_y: None
                height: dp(0)
                on_release: app.key_press('-')

            # Row 2: 7 8 9 [+ cont] [- cont]
            CalcButton:
                text: '7'
                background_color: get_color_from_hex('#3d3d3d')
                on_release: app.key_press('7')
            CalcButton:
                text: '8'
                background_color: get_color_from_hex('#3d3d3d')
                on_release: app.key_press('8')
            CalcButton:
                text: '9'
                background_color: get_color_from_hex('#3d3d3d')
                on_release: app.key_press('9')
            # + and - continue (spacers)
            Widget:
                size_hint_x: None
                width: dp(0)
            Widget:
                size_hint_x: None
                width: dp(0)

            # Row 3: 4 5 6 [=↕3] [←↕2]
            CalcButton:
                text: '4'
                background_color: get_color_from_hex('#3d3d3d')
                on_release: app.key_press('4')
            CalcButton:
                text: '5'
                background_color: get_color_from_hex('#3d3d3d')
                on_release: app.key_press('5')
            CalcButton:
                text: '6'
                background_color: get_color_from_hex('#3d3d3d')
                on_release: app.key_press('6')
            CalcButton:
                id: btn_eq
                text: '='
                background_color: get_color_from_hex('#1e4a1a')
                size_hint_y: None
                height: dp(0)
                on_release: app.key_press('=')
            CalcButton:
                id: btn_bs
                text: '←'
                background_color: get_color_from_hex('#3d3d3d')
                size_hint_y: None
                height: dp(0)
                on_release: app.key_press('BS')

            # Row 4: 1 2 3 [= cont] [← cont]
            CalcButton:
                text: '1'
                background_color: get_color_from_hex('#3d3d3d')
                on_release: app.key_press('1')
            CalcButton:
                text: '2'
                background_color: get_color_from_hex('#3d3d3d')
                on_release: app.key_press('2')
            CalcButton:
                text: '3'
                background_color: get_color_from_hex('#3d3d3d')
                on_release: app.key_press('3')
            Widget:
                size_hint_x: None
                width: dp(0)
            Widget:
                size_hint_x: None
                width: dp(0)

            # Row 5: 00 0 . [= cont] C
            CalcButton:
                text: '00'
                background_color: get_color_from_hex('#3d3d3d')
                on_release: app.key_press('00')
            CalcButton:
                text: '0'
                background_color: get_color_from_hex('#3d3d3d')
                on_release: app.key_press('0')
            CalcButton:
                text: '.'
                background_color: get_color_from_hex('#3d3d3d')
                on_release: app.key_press('.')
            Widget:
                size_hint_x: None
                width: dp(0)
            CalcButton:
                text: 'C'
                background_color: get_color_from_hex('#3d3d3d')
                on_release: app.key_press('C')

<RootLayout>:
"""

# ══════════════════════════════════════════════
# ROOT LAYOUT WIDGET
# ══════════════════════════════════════════════
class RootLayout(BoxLayout):
    pass


# ══════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════
class DR120RApp(App):
    PRINTER_IP   = '192.168.1.100'
    PRINTER_PORT = 9100
    PAPER_COLS   = 42   # 80mm

    def build(self):
        self.engine = CalcEngine()
        self.root_widget = Builder.load_string(KV)
        self.root_widget = RootLayout()
        Builder.load_string(KV)
        # Re-build properly
        from kivy.uix.boxlayout import BoxLayout as BL
        self._root = Builder.load_string("""
RootLayout:
""")
        Clock.schedule_once(self._fix_spanning_buttons, 0.1)
        return self._root

    def _fix_spanning_buttons(self, dt):
        """
        Kivy GridLayout ไม่รองรับ rowspan โดยตรง
        ใช้วิธี: วางปุ่มแบบ FloatLayout ทับ GridLayout แทน
        """
        pass  # handled in on_start

    def on_start(self):
        """Rebuild UI properly after start"""
        self._root.clear_widgets()
        self._build_ui()

    def _build_ui(self):
        from kivy.uix.floatlayout import FloatLayout
        from kivy.uix.widget import Widget

        root = self._root

        # ── TAPE SECTION ──
        tape_box = BoxLayout(orientation='vertical', size_hint_y=0.38)
        tape_box.canvas.before.clear()
        with tape_box.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*get_color_from_hex('#fffef0'))
            self._tape_rect = Rectangle(pos=tape_box.pos, size=tape_box.size)
        tape_box.bind(pos=self._update_tape_rect, size=self._update_tape_rect)

        # toolbar
        toolbar = BoxLayout(size_hint_y=None, height=dp(40),
                            padding=dp(4), spacing=dp(6))
        with toolbar.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*get_color_from_hex('#dddddd'))
            self._tb_rect = Rectangle(pos=toolbar.pos, size=toolbar.size)
        toolbar.bind(pos=lambda *a: setattr(self._tb_rect, 'pos', toolbar.pos),
                     size=lambda *a: setattr(self._tb_rect, 'size', toolbar.size))

        for txt, color, cb in [
            ('🖨 Print', '#1a5a1a', self.open_print_dialog),
            ('📷 JPG',   '#1a3a8a', self.export_jpg),
            ('🗑 ล้าง',  '#8a1a1a', self.clear_tape),
        ]:
            btn = Button(text=txt, font_size=sp(13), bold=True,
                         background_normal='',
                         background_color=get_color_from_hex(color),
                         color=(1,1,1,1))
            btn.bind(on_release=lambda x, c=cb: c())
            toolbar.add_widget(btn)

        tape_box.add_widget(toolbar)

        # tape scroll
        self.tape_scroll = ScrollView(do_scroll_x=False)
        self.tape_grid = GridLayout(cols=1, size_hint_y=None, padding=dp(6), spacing=0)
        self.tape_grid.bind(minimum_height=self.tape_grid.setter('height'))
        self.tape_scroll.add_widget(self.tape_grid)
        tape_box.add_widget(self.tape_scroll)
        root.add_widget(tape_box)

        # ── CALC SECTION ──
        calc_box = BoxLayout(orientation='vertical', size_hint_y=0.62,
                             padding=dp(6), spacing=dp(4))
        with calc_box.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*get_color_from_hex('#2a2a2a'))
            self._calc_rect = Rectangle(pos=calc_box.pos, size=calc_box.size)
        calc_box.bind(pos=lambda *a: setattr(self._calc_rect, 'pos', calc_box.pos),
                      size=lambda *a: setattr(self._calc_rect, 'size', calc_box.size))

        # display
        self.display_lbl = Label(
            text='0.', font_size=sp(32), bold=True,
            halign='right', valign='middle',
            size_hint_y=None, height=dp(52),
            color=get_color_from_hex('#1a2a00'),
            padding_x=dp(12)
        )
        self.display_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        with self.display_lbl.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            Color(*get_color_from_hex('#b8c890'))
            self._disp_rect = RoundedRectangle(
                pos=self.display_lbl.pos,
                size=self.display_lbl.size, radius=[dp(4)])
        self.display_lbl.bind(
            pos=lambda *a: setattr(self._disp_rect, 'pos', self.display_lbl.pos),
            size=lambda *a: setattr(self._disp_rect, 'size', self.display_lbl.size))
        calc_box.add_widget(self.display_lbl)

        # keypad using FloatLayout inside a sized BoxLayout
        self.keypad_host = BoxLayout()
        self.keypad_fl   = FloatLayout()
        self.keypad_host.add_widget(self.keypad_fl)
        calc_box.add_widget(self.keypad_host)
        root.add_widget(calc_box)

        Clock.schedule_once(self._place_keys, 0.15)

    def _update_tape_rect(self, widget, *args):
        self._tape_rect.pos  = widget.pos
        self._tape_rect.size = widget.size

    def _place_keys(self, dt):
        """Place keys using FloatLayout with proper rowspan"""
        fl = self.keypad_fl
        fl.clear_widgets()
        W = fl.width
        H = fl.height
        cols, rows = 5, 5
        gw = dp(5)   # gap
        bw = (W - gw*(cols-1)) / cols
        bh = (H - gw*(rows-1)) / rows

        def pos_btn(col, row, colspan=1, rowspan=1):
            """col,row 0-indexed from top-left"""
            x = col * (bw + gw)
            # y from bottom
            bot_row = rows - 1 - row - (rowspan - 1)
            y = bot_row * (bh + gw)
            w = bw * colspan + gw * (colspan - 1)
            h = bh * rowspan + gw * (rowspan - 1)
            return x, y, w, h

        def make(text, bg, key, col, row, cs=1, rs=1):
            x, y, w, h = pos_btn(col, row, cs, rs)
            fs = sp(20) if text in ('CA','ST','GT','MRC','M+','M-') else sp(24)
            btn = Button(
                text=text, font_size=fs, bold=True,
                background_normal='',
                background_color=get_color_from_hex(bg),
                color=(1,1,1,1),
                pos=(x, y), size=(w, h), size_hint=(None, None)
            )
            btn.bind(on_release=lambda b, k=key: self.key_press(k))
            fl.add_widget(btn)

        RED  = '#8b1a1a'
        ORG  = '#8a3e00'
        GRN  = '#1e4a1a'
        DRK  = '#3d3d3d'

        # Row 0: CA ÷ × + -
        make('CA',  RED, 'CA',  0, 0)
        make('÷',   ORG, '/',   1, 0)
        make('×',   ORG, '*',   2, 0)
        make('+',   ORG, '+',   3, 0, rs=2)   # rowspan 2
        make('−',   ORG, '-',   4, 0, rs=2)   # rowspan 2

        # Row 1: 7 8 9 (+ cont)(- cont)
        make('7',   DRK, '7',   0, 1)
        make('8',   DRK, '8',   1, 1)
        make('9',   DRK, '9',   2, 1)

        # Row 2: 4 5 6 = ←
        make('4',   DRK, '4',   0, 2)
        make('5',   DRK, '5',   1, 2)
        make('6',   DRK, '6',   2, 2)
        make('=',   GRN, '=',   3, 2, rs=3)   # rowspan 3
        make('←',   DRK, 'BS',  4, 2, rs=2)   # rowspan 2

        # Row 3: 1 2 3 (= cont)(← cont)
        make('1',   DRK, '1',   0, 3)
        make('2',   DRK, '2',   1, 3)
        make('3',   DRK, '3',   2, 3)

        # Row 4: 00 0 . (= cont) C
        make('00',  DRK, '00',  0, 4)
        make('0',   DRK, '0',   1, 4)
        make('.',   DRK, '.',   2, 4)
        make('C',   DRK, 'C',   4, 4)

    def key_press(self, key):
        disp_str, tape_changed = self.engine.press(key)
        # format display nicely
        try:
            n = float(disp_str)
            disp_str = f"{n:,.2f}"
        except: pass
        self.display_lbl.text = disp_str
        if tape_changed:
            self._refresh_tape()

    @mainthread
    def _refresh_tape(self):
        grid = self.tape_grid
        grid.clear_widgets()
        for item in self.engine.tape:
            t = item.get('type', 'normal')
            if t == 'spacer':
                grid.add_widget(Widget(size_hint_y=None, height=dp(10)))
                continue
            if t == 'divider':
                lbl = Label(
                    text='-' * 40,
                    font_name='RobotoMono',
                    color=get_color_from_hex('#b85000'),
                    font_size=sp(12),
                    size_hint_y=None, height=dp(18),
                    halign='left', valign='middle'
                )
                lbl.bind(size=lambda w,s: setattr(w,'text_size',s))
                grid.add_widget(lbl)
                continue

            op  = item.get('op', '')
            val = item.get('value', 0)
            row = BoxLayout(size_hint_y=None, height=dp(26), padding=(dp(4),0))
            color_hex = (
                '#cc0000' if t == 'total' else
                '#0000cc' if t == 'subtotal' else
                '#333333'
            )
            op_lbl = Label(
                text=op, font_size=sp(14),
                color=get_color_from_hex(color_hex),
                size_hint_x=None, width=dp(30),
                halign='left', valign='middle'
            )
            op_lbl.bind(size=lambda w,s: setattr(w,'text_size',s))

            num_lbl = Label(
                text=f"{val:,.2f}",
                font_size=sp(16 if t in ('total','subtotal') else 15),
                bold=(t in ('total','subtotal')),
                color=get_color_from_hex(color_hex),
                halign='right', valign='middle'
            )
            num_lbl.bind(size=lambda w,s: setattr(w,'text_size',s))

            row.add_widget(op_lbl)
            row.add_widget(num_lbl)
            grid.add_widget(row)

        # scroll to bottom
        Clock.schedule_once(lambda dt: setattr(self.tape_scroll, 'scroll_y', 0), 0.05)

    def clear_tape(self):
        self.engine.tape.clear()
        self.tape_grid.clear_widgets()

    def export_jpg(self):
        from kivy.core.image import Image as CoreImage
        from kivy.graphics import RenderContext
        try:
            path = f"/sdcard/DR120R_tape_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            self.tape_scroll.export_to_png(path)
            self._show_msg('บันทึกรูปแล้ว', f'ไฟล์: {path}')
        except Exception as e:
            self._show_msg('Error', str(e))

    # ── PRINT DIALOG ──
    def open_print_dialog(self):
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(14))

        content.add_widget(Label(text='🖨 Rongta RP326 — ESC/POS over LAN',
                                 font_size=sp(14), bold=True, size_hint_y=None,
                                 height=dp(30), color=(0.2,0.6,1,1)))

        ip_box = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        ip_box.add_widget(Label(text='IP:', size_hint_x=None, width=dp(30), font_size=sp(14)))
        self._ip_input = TextInput(text=self.PRINTER_IP, multiline=False,
                                   font_size=sp(18), input_type='text',
                                   background_color=(0.95,0.95,0.95,1))
        ip_box.add_widget(self._ip_input)
        content.add_widget(ip_box)

        port_box = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        port_box.add_widget(Label(text='Port:', size_hint_x=None, width=dp(50), font_size=sp(14)))
        self._port_input = TextInput(text=str(self.PRINTER_PORT), multiline=False,
                                     font_size=sp(18), input_type='number',
                                     background_color=(0.95,0.95,0.95,1))
        port_box.add_widget(self._port_input)
        content.add_widget(port_box)

        self._print_status = Label(text='', font_size=sp(13),
                                   size_hint_y=None, height=dp(30),
                                   color=(0.2,0.8,0.2,1))
        content.add_widget(self._print_status)

        btn_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        test_btn = Button(text='ทดสอบ', background_normal='',
                          background_color=get_color_from_hex('#1a3a8a'),
                          font_size=sp(15), bold=True)
        test_btn.bind(on_release=lambda x: self._do_print(test=True))

        print_btn = Button(text='พิมพ์เทป', background_normal='',
                           background_color=get_color_from_hex('#1a5a1a'),
                           font_size=sp(15), bold=True)
        print_btn.bind(on_release=lambda x: self._do_print(test=False))

        cancel_btn = Button(text='ยกเลิก', background_normal='',
                            background_color=get_color_from_hex('#555555'),
                            font_size=sp(15))
        cancel_btn.bind(on_release=lambda x: self._print_popup.dismiss())

        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(test_btn)
        btn_row.add_widget(print_btn)
        content.add_widget(btn_row)

        self._print_popup = Popup(
            title='Thermal Printer', content=content,
            size_hint=(0.92, None), height=dp(320),
            background_color=get_color_from_hex('#222222'),
            title_color=(1,1,1,1)
        )
        self._print_popup.open()

    def _do_print(self, test=False):
        ip   = self._ip_input.text.strip()
        port = int(self._port_input.text.strip() or '9100')
        self.PRINTER_IP   = ip
        self.PRINTER_PORT = port
        self._set_status('⏳ กำลังเชื่อมต่อ...')
        threading.Thread(target=self._print_thread,
                         args=(ip, port, test), daemon=True).start()

    def _print_thread(self, ip, port, test):
        try:
            with RongtaRP326(ip, port) as p:
                if test:
                    # test page only
                    p.init().align('center').big()
                    p.text("CASIO DR-120R").lf()
                    p.normal().text("CONNECTION OK").lf()
                    p.text(datetime.datetime.now().strftime("%d/%m/%Y %H:%M")).lf(3)
                    p.cut().flush()
                    self._set_status('✅ ทดสอบสำเร็จ!')
                else:
                    if not self.engine.tape:
                        self._set_status('❌ ยังไม่มีรายการในเทป')
                        return
                    p.print_dr120r_tape(self.engine.tape, cols=self.PAPER_COLS)
                    self._set_status('✅ พิมพ์เสร็จสมบูรณ์!')
        except ConnectionRefusedError:
            self._set_status(f'❌ Connection refused ({ip}:{port})')
        except socket.timeout:
            self._set_status('❌ Timeout — เครื่องพิมพ์ไม่ตอบสนอง')
        except Exception as e:
            self._set_status(f'❌ {str(e)[:50]}')

    @mainthread
    def _set_status(self, msg):
        if hasattr(self, '_print_status'):
            ok = msg.startswith('✅')
            self._print_status.color = (0.2,0.8,0.2,1) if ok else (1,0.3,0.3,1)
            self._print_status.text = msg

    def _show_msg(self, title, msg):
        popup = Popup(title=title,
                      content=Label(text=msg, font_size=sp(13)),
                      size_hint=(0.85, None), height=dp(200))
        popup.open()


if __name__ == '__main__':
    DR120RApp().run()
