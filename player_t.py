import yt_dlp
import ffmpeg 
import threading
from threading import Thread
import subprocess
import curses
import sys
from curses import panel
from curses import textpad
from curses import wrapper
import os
import signal

#playlist = []

# if youtube url, use yt-dlp
# if m3u or radio: ffplay (ffplay -nodisp -vn)

# TODO: add play next setting, auto-download

URLS = ['https://www.youtube.com/watch?v=se5NYYkuzoM']

# media = {"name":"video_name","file":"filename","url":"www..."}

playlist = []

# Main screen (attrs : title, subpanels-objects)
# Panel
# Textbox

class Window():
    def __init__(self, title=None, debug=None):
        # calculate window size
        # 80x25 :
        # 80x1 : title
        # 80x25-4 : list
        # 80x1 : input box
        # 80x1 : play bar
        # 80x1 : info bar (status, ...)
        self.stdscr = curses.initscr() # setup intial window
        # ctrl / type url
        self.mode = "CTRL"
        #x = curses.LINES
        #y = curses.COLS
        self.x, self.y =  self.stdscr.getmaxyx()
        #self.x, self.y = 25, 80
        # todo: set fixed status bar
        self.list_pos = 0
        self.auto_dl = False
        self.auto_play = False

        curses.noecho() # dont echo keystrokes
        curses.cbreak() # dont wait for enter, handle keys immediately
        self.stdscr.keypad(1) # use aliases for special keys
        curses.start_color()

        if title is not None:
            self.stdscr.addstr(0,0, title)

        self.inputbox = None
        # threads to run
        self.play_t = None
        self.pbox_t = threading.Thread(target=self.update_playlist())
        #status_t = Threading.Thread(target=self.show_status())
        self.pbox_t.start()

        #inputbox window
        

        self.stdscr.addstr(int(self.x) - 3, 0, "URL: ")
        #inputbox object
        self.stdscr.addstr(int(self.x) - 2, 0, "info bar")

        # Refresh the screen
        self.stdscr.refresh()

        #self.input_t = threading.Thread(target=self.enable_input())
        #self.key_t = threading.Thread(target=self.key_listener())

        # Thread managing input box
        #if self.mode == "TYPE":
            
        #    if self.key_t.is_alive():
        #        self.key_t.join()
        #else:
            # Keystrokes
        #    self.key_t.start()
        #    if self.input_t.is_alive():
        #        self.disable_input()

        while True:
            k = self.stdscr.getch()
            if k == ord('n'):
                self.enable_input()
            if k == ord('q'):
                curses.nocbreak()
                self.stdscr.keypad(False)
                curses.echo()
                curses.endwin()
                exit()
            if k == ord('d'):
                self.start_download()
            if k == curses.KEY_UP:
                self.up_element()
            if k == curses.KEY_DOWN:
                self.down_element()
            if k == ord('g'):
                self.get_playlist_elem()
            if k == ord('p'):
                if self.play_t is not None:
                    # rewrite function
                    os.kill(self.play_t_pid, signal.SIGTERM)
                else:
                    #self.play_l = threading.Lock()
                    self.play_t_pid = None
                    self.play_t = threading.Thread(target=self.play_media(), args=())
                    self.play_t.start()
                    # debug
                    self.show_status("pid " + str(self.play_t_pid))
            if k == ord('s'):
                if self.play_t is not None:
                    try:
                        os.kill(self.play_t_pid, signal.SIGTERM)
                        #debug
                        self.show_status("pid " + str(self.play_t_pid) + "killed")
                    except:
                        self.show_status("failed to kill pid " + str(self.play_t_pid))
            if k == ord('a'):
                self.set_autodl()
            if k == ord('A'):
                self.set_autoplay()
        wrapper(self.__init__())

    def get_stdscr(self):
        return self.stdscr

    def get_list_pos(self):
        return self.list_pos   

    def enable_input(self):
        self.inputbox = curses.newwin(1, self.y, int(self.x) - 3, 5)
        curses.echo()
        inptData = self.inputbox.getstr(0, 0, 255)
        if len(inptData) > 2:
            self.add_to_playlist(inptData.decode('utf8') + '\n')
            #self.list_pos = len(playlist)
        self.stdscr.move(self.list_pos + 1, 0)
        self.disable_input()

    def set_autoplay(self):
        if self.auto_play is False:
            self.auto_play = True
        else:
            self.auto_play = False

    def set_autodl(self):
        if self.auto_dl is False:
            self.auto_dl = True
        else: 
            self.auto_dl = False
    
    def disable_input(self):
        self.inputbox = None
        curses.noecho()

    def update_playlist(self):
        #if self.panelbox is not None:
        #    self.panelbox = None
        self.panelbox = curses.newwin(10, 80, 1, 0)
        for line in playlist:
            if type(line) == dict:
                self.panelbox.addstr(line['name'] + '\n')
            else:
                self.panelbox.addstr(line + '\n')
        self.panelbox.chgat(self.list_pos, 0, curses.A_BOLD)
        self.panelbox.refresh()
        self.stdscr.move(self.list_pos + 1, 0)

    def up_element(self):
        if self.list_pos > 0:
            self.panelbox.chgat(self.list_pos, 0, curses.A_NORMAL)
            self.list_pos = self.list_pos - 1
            # shifting the cursor because of title
            self.stdscr.move(self.list_pos + 1, 0)
            self.panelbox.chgat(self.list_pos, 0, curses.A_BOLD)
        else:
            self.show_status("this is the first element")
        self.panelbox.refresh()

    def down_element(self):
        if self.list_pos < len(playlist) - 1:
            self.panelbox.chgat(self.list_pos, 0, curses.A_NORMAL)
            self.list_pos = self.list_pos + 1
            self.stdscr.move(self.list_pos + 1, 0)
            self.panelbox.chgat(self.list_pos, 0, curses.A_BOLD)
        else:
            self.show_status("this is the last element")
        self.panelbox.refresh()

    def show_status(self, message):
        self.stdscr.addstr(int(self.x) - 2, 10, message)

    def add_to_playlist(self, data):
        playlist.append(data.strip('\n'))
        self.list_pos = len(playlist) - 1
        self.update_playlist()
        if self.auto_dl is True:
            self.start_download()
    
    def get_playlist_elem(self):
        self.stdscr.addstr(int(self.x) - 2, 10, playlist[self.list_pos])
        self.stdscr.refresh()
        return playlist[self.list_pos]

    def start_download(self):
        url = self.get_playlist_elem()
        m = Media(url.strip('\n'))
        m.run()
        # update screen to show title once downloaded ...
        self.update_playlist()
        #if self.auto_play is True:
        #    self.play_media(get_playlist_elem().media['filename'])

    def play_media(self):
        file = playlist[self.list_pos]['filename']
        self.stdscr.addstr(int(self.x) - 2, 10, file)
        self.play_t_pid = Media.play_media(file)

class Media(Thread):
    def  __init__(self, url):
        self.url = url
        self.media = {}
        #sys.stdout = None
        self._target = self.yt_download()
        self._args = ()
        self._kwargs = {}
        
    def play_media(file):
        null = open('/dev/null', 'w')
        #todo : play length (stdout to buffer)
        p = subprocess.Popen(["/usr/bin/ffplay", "-vn", "-nodisp", file], stdin=null, stdout=null, stderr=null)
        return p.pid

    def get_metadata(self, d):
        if d['status'] == 'finished':
            file = d['filename']
            title = file.strip('.m4a')
            self.media = {"id": 0, "name":title, "filename":file, "url":self.url}
            idx = playlist.index(self.url)
            self.media['id'] = idx
            playlist[idx] = self.media
        
    def yt_download(self):
        #get_metadata = self.get_metadata(d)
        ydl_opts = {
            'format': 'm4a/bestaudio/best',
            #"outtmpl": "./cache/",
            "progress_hooks":[self.get_metadata],
            'quiet': True
        }
        #sys.stderr = None
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download(self.url)

if __name__ == "__main__":
        title = "WebPlayer 1.0"
        win = Window(title, debug=True)
        # define objects as {"name":[obj, type], ...}

        m = Media(URLS[0])
        #t = threading.Thread(target=m.yt_download())
        #t.run()
        m.run()

