# import required modules
from blessed import Terminal
import os
from threading import Thread
import threading
import subprocess
import signal
import re
import time
import sys

term = Terminal()

print(term.home + term.clear + term.move_y(term.height // 2))


class Menu:
    """The main menu."""

    def __init__(self, term: Terminal, main):
        """Set up the menu."""
        self.term = term
        self.OPTIONS = []
        self.selection_index = 0
        self.selected = 0
        self.main = main
        self.draw()
        self.event_loop(1)

    def clear(self):
        print(self.term.home + self.term.clear)

    def draw(self):
        """Render the menu to the terminal."""
        # print(self.term.home + self.term.clear)
        self.main.bar.draw_vol(self.main.volume)
        base_x = self.term.width // 2
        base_y = (self.term.height - len(self.OPTIONS)) // 2
        print(
            self.term.move_xy(base_x - 2, 3)
            + self.term.green_bold
            + "MUSIC PLAYER"
            + self.term.normal
        )
        for index, label in enumerate(self.OPTIONS):
            x = base_x - len(label) // 2
            y = base_y + index
            if index == self.selection_index:
                style = self.term.bold_red_reverse
                if self.selected == self.selection_index:
                    style = self.term.bold_blue_reverse
            elif index == self.selected:
                style = self.term.bold_blue
            else:
                style = self.term.red
            print(self.term.move_xy(x, y) + style + label + self.term.normal)

    def on_key_press(self, key: str):
        """Handle a key being pressed."""
        if key == "down":
            self.selection_index += 1
            self.selection_index %= len(self.OPTIONS)
            self.draw()
        elif key == "up":
            self.selection_index -= 1
            self.selection_index %= len(self.OPTIONS)
            self.draw()
        elif key == "enter":
            self.main.refresh(True)
            self.selected = self.selection_index
        elif key == "right":
            if self.main.volume < 100:
                self.main.bar.draw_vol(self.main.volume)
                self.main.volume += 10
        elif key == "left":
            if self.main.volume > 0:
                self.main.bar.draw_vol(self.main.volume)
                self.main.volume -= 10
        self.draw()

    def event_loop(self, sleep):
        """Wait for keypresses."""
        with self.term.cbreak(), self.term.hidden_cursor():
            key = self.term.inkey(timeout=sleep).name
            if key:
                self.on_key_press(key.removeprefix("KEY_").lower())


class Progress:
    def __init__(self, term: Terminal):
        self.value = 0.3
        self.max_value = 100.345
        self.term = term
        self.chars = ["[", "=", "]", "█"]

    def draw(self):
        """Render the progress bar."""
        x = self.term.width
        y = self.term.height
        base_x = 1
        lens = [len(str(round(self.value))), len(str(self.max_value))]
        filler = (
            self.chars[1] * round(x * (self.value / (self.max_value - lens[1])))
            + ">"
        )
        base_x += lens[0]
        print(
            self.term.move_xy(1, y - 3)
            + str(round(self.value))
            + self.term.normal
        )
        print(
            self.term.move_xy(base_x, y - 3) + self.chars[0] + self.term.normal
        )
        print(self.term.move_xy(base_x + 1, y - 3) + filler + self.term.normal)
        print(
            self.term.move_xy(x - lens[1] - 1, y - 3)
            + self.chars[2]
            + self.term.normal
        )
        print(
            self.term.move_xy(x - len(str(self.max_value)), y - 3)
            + str(self.max_value)
            + self.term.normal
        )

    def draw_vol(self, volume):
        base_x = self.term.width
        base_y = self.term.height
        x = 2
        y = base_y - 4
        for i in range(0, 110, 10):
            y = y - 1
            seg = "|"
            if i <= volume:
                if i == 100:
                    seg += self.term.red
                else:
                    seg += self.term.green
                seg += self.chars[3] + self.term.normal
            else:
                seg += " "
            seg += "|"
            print(self.term.move_xy(x, y) + seg)


class MusicManager:
    def __init__(self, bar: Progress):
        self.dir = sys.argv[1]
        self.selected = ""
        self.bar = bar
        self.volume = 40
        self.songs = []
        self.nowplaying = None
        self.updater_flag = True
        self.updater_process = None
        self.prev_point = 0.0
        self.selector = Menu(term, self)

    def playsong(self, name: str):
        self.nowplaying = None
        name = os.path.join(self.dir, name)
        p = subprocess.Popen(
            [
                "ffprobe "
                + "-show_entries "
                + "format=duration "
                + "-v "
                + "quiet "
                + "-of "
                + 'csv="p=0" '
                + "-i "
                + re.escape(name)
            ],
            stdout=subprocess.PIPE,
            shell=True,
        )
        p.wait()
        out = list(p.stdout)[0]
        duration = float(out)
        self.bar.max_value = duration
        song = subprocess.Popen(
            [
                "ffplay",
                "-nodisp",
                "-autoexit",
                name,
                "-volume",
                str(self.volume),
                "-ss",
                str(round(self.prev_point, 4)),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.nowplaying = song

    def listsongs(self, dir: str):
        self.songs = []
        for root, dirs, files in os.walk(dir, topdown=False):
            for name in files:
                self.songs.append(name)

    def bar_updater(self):
        start = time.time()
        while self.updater_flag:
            self.bar.value = time.time() - start
        self.updater_flag = True

    def refresh(self, save: bool):
        if save:
            self.prev_point = self.bar.value + 10.0
            self.bar.draw_vol(self.volume)
        else:
            self.prev_point = 0
        if self.updater_flag and self.updater_process:
            self.updater_flag = False
            while not self.updater_flag:
                pass
            # self.updater_process.join()
        if self.nowplaying:
            self.nowplaying.send_signal(signal.SIGINT)
        self.playsong(self.songs[self.selector.selected])
        self.updater_process = Thread(target=self.bar_updater)
        self.updater_process.start()

    def mainloop(self):
        self.listsongs(self.dir)
        self.selector.OPTIONS = self.songs
        prev = ""
        self.selector.draw()
        while True:
            if self.selector.selected != prev and len(self.songs) > 0:
                self.selector.clear()
                prev = self.selector.selected
                self.refresh(False)
                self.selector.draw()
            self.selector.event_loop(0.01)
            self.bar.draw()


prog = Progress(term)

mgr = MusicManager(prog)
mgr.mainloop()
