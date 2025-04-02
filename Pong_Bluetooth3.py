from tkinter import messagebox
import tkinter as tk
from bleak import BleakClient
import asyncio
import json
import threading
import time
import logging

# Logging konfigurieren
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Bluetooth MAC-Adressen
BLUETOOTH_DEVICE1 = "64:E8:33:88:5E:E2"
BLUETOOTH_DEVICE2 = "64:E8:33:88:9E:36"
SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

# Spielfeldgrößen
WIN_WIDTH = 800
WIN_HEIGHT = 600
PADDLE_WIDTH = 10
PADDLE_HEIGHT = 100
BALL_SIZE = 20
BALL_SPEED = 5
PADDLE_SPEED = 4

class Paddle:
    def __init__(self, canvas, x, y, color="white"):
        self.canvas = canvas
        self.id = canvas.create_rectangle(x, y, x + PADDLE_WIDTH, y + PADDLE_HEIGHT, fill=color)
        self.speed = 0
        
    def move(self):
        pos = self.canvas.coords(self.id)
        if 0 <= pos[1] + self.speed <= WIN_HEIGHT - PADDLE_HEIGHT:
            self.canvas.move(self.id, 0, self.speed)
            
    def get_coords(self):
        return self.canvas.coords(self.id)
    
    def set_speed(self, speed):
        self.speed = speed  

class Ball:
    def __init__(self, canvas, x, y, color="white"):
        self.canvas = canvas
        self.id = canvas.create_oval(x - BALL_SIZE // 2, y - BALL_SIZE // 2,
                                   x + BALL_SIZE // 2, y + BALL_SIZE // 2, fill=color)
        self.dx = BALL_SPEED
        self.dy = BALL_SPEED
        
    def move(self):
        self.canvas.move(self.id, self.dx, self.dy)
        
    def get_coords(self):
        return self.canvas.coords(self.id)
    
    def reset(self):
        self.canvas.coords(self.id, WIN_WIDTH // 2 - BALL_SIZE // 2, WIN_HEIGHT // 2 - BALL_SIZE // 2,
                          WIN_WIDTH // 2 + BALL_SIZE // 2, WIN_HEIGHT // 2 + BALL_SIZE // 2)
        self.dx = BALL_SPEED
        self.dy = BALL_SPEED

class BluetoothManager:
    def __init__(self, parent, loop):
        self.parent = parent
        self.loop = loop
        self.client1 = None
        self.client2 = None
        self.device1_connected = False
        self.device2_connected = False
        self.device1_status = "Nicht verbunden"
        self.device2_status = "Nicht verbunden"
        self.stop_event = threading.Event()
        self.device_threads = {}
        self.last_update1 = 0
        self.last_update2 = 0

    def start_device_thread(self, address, device_num):
        thread = threading.Thread(target=self.device_connection_loop, args=(address, device_num), daemon=True)
        thread.name = f"BLE-Device-{device_num}"  # Für bessere Nachverfolgbarkeit
        self.device_threads[device_num] = thread
        thread.start()

    def device_connection_loop(self, address, device_num):
        while not self.stop_event.is_set():
            try:
                asyncio.run_coroutine_threadsafe(self.connect_device(address, device_num), self.loop).result()
                while self.is_device_connected(device_num) and not self.stop_event.is_set():
                    time.sleep(0.05)  # Noch kürzere Wartezeit für schnellere Reaktion
            except Exception as e:
                logger.error(f"Fehler im Gerät-{device_num}-Thread: {e}")
            logger.info(f"Verbindung zu Gerät {device_num} verloren. Erneuter Versuch in 1 Sekunde...")
            time.sleep(1)

    def is_device_connected(self, device_num):
        return self.device1_connected if device_num == 1 else self.device2_connected

    async def connect_device(self, address, device_num):
        try:
            client = BleakClient(address)
            await client.connect(timeout=5.0)
            logger.info(f"Gerät {device_num} verbunden")
            if device_num == 1:
                self.client1 = client
                self.device1_connected = True
            else:
                self.client2 = client
                self.device2_connected = True

            await client.start_notify(CHARACTERISTIC_UUID, 
                                   self.notification_handler1 if device_num == 1 else self.notification_handler2)
            self.update_device_status(device_num, "Verbunden")
        except Exception as e:
            logger.error(f"Fehler beim Verbinden mit Gerät {device_num}: {e}")
            self.update_device_status(device_num, "Verbindung fehlgeschlagen")
            if device_num == 1:
                self.device1_connected = False
            else:
                self.device2_connected = False
            raise

    def update_device_status(self, device_num, status):
        if device_num == 1:
            self.device1_status = status
        else:
            self.device2_status = status
        self.parent.root.after(0, self.parent.update_status_labels)

    def notification_handler1(self, sender, data):
        try:
            current_time = time.time()
            joystick_data = json.loads(data.decode('utf-8'))
            speed = joystick_data.get("Ax", 0) * PADDLE_SPEED
            #logger.debug(f"Spieler 1 - Speed: {speed}, Zeit seit letztem Update: {current_time - self.last_update1:.3f}s")
            self.last_update1 = current_time
            self.parent.root.after(0, lambda: self.parent.set_paddle_speed(1, speed))
        except Exception as e:
            logger.error(f"Fehler bei der Verarbeitung der BLE-Daten für Gerät 1: {e}")

    def notification_handler2(self, sender, data):
        try:
            current_time = time.time()
            joystick_data = json.loads(data.decode('utf-8'))
            speed = joystick_data.get("Ax", 0) * PADDLE_SPEED
            #logger.debug(f"Spieler 2 - Speed: {speed}, Zeit seit letztem Update: {current_time - self.last_update2:.3f}s")
            self.last_update2 = current_time
            self.parent.root.after(0, lambda: self.parent.set_paddle_speed(2, speed))
        except Exception as e:
            logger.error(f"Fehler bei der Verarbeitung der BLE-Daten für Gerät 2: {e}")

    def stop_all_threads(self):
        self.stop_event.set()
        for thread in self.device_threads.values():
            thread.join()

    async def cleanup_connections(self):
        self.stop_all_threads()
        if self.client1 and self.client1.is_connected:
            await self.client1.disconnect()
        if self.client2 and self.client2.is_connected:
            await self.client2.disconnect()
        self.device1_connected = False
        self.device2_connected = False

class PongGame:
    def __init__(self, root, loop):
        self.root = root
        self.loop = loop
        self.root.title("Pong Game")
        self.players = 0
        self.player1_control = "keyboard"
        self.player2_control = "keyboard"
        
        self.main_frame = tk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.status_frame = tk.Frame(self.main_frame, bg="black")
        self.status_frame.pack(fill=tk.X)
        
        self.status_label1 = tk.Label(self.status_frame, text="Spieler 1: Nicht aktiviert", fg="white", bg="black")
        self.status_label1.pack(side=tk.LEFT, padx=10, pady=5)
        
        self.status_label2 = tk.Label(self.status_frame, text="Spieler 2: Nicht aktiviert", fg="white", bg="black")
        self.status_label2.pack(side=tk.RIGHT, padx=10, pady=5)
        
        self.canvas = tk.Canvas(self.main_frame, width=WIN_WIDTH, height=WIN_HEIGHT, bg="black")
        self.canvas.pack()
        
        self.control_frame = tk.Frame(self.main_frame)
        self.control_frame.pack(fill=tk.X, pady=10)
        
        self.bt_manager = BluetoothManager(self, self.loop)
        
        self.game_started = False
        self.running = False
        
        self.player1_lives = 5
        self.player2_lives = 5

        self.lives_label1 = tk.Label(self.status_frame, text="Leben Spieler 1: 5", fg="white", bg="black")
        self.lives_label1.pack(side=tk.LEFT, padx=10, pady=5)

        self.lives_label2 = tk.Label(self.status_frame, text="Leben Spieler 2: 5", fg="white", bg="black")
        self.lives_label2.pack(side=tk.RIGHT, padx=10, pady=5)

        self.show_game_setup()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        logger.info("Anwendung wird geschlossen...")
        self.running = False
        asyncio.run_coroutine_threadsafe(self.bt_manager.cleanup_connections(), self.loop)
        self.root.destroy()

    def show_game_setup(self):
        self.setup_frame = tk.Frame(self.control_frame)
        self.setup_frame.pack(pady=10)
        
        tk.Label(self.setup_frame, text="Spieler:").grid(row=0, column=0, padx=5, pady=5)
        self.player_var = tk.IntVar(value=1)
        tk.Radiobutton(self.setup_frame, text="1 Spieler", variable=self.player_var, value=1, 
                       command=self.update_player_options).grid(row=0, column=1, padx=5, pady=5)
        tk.Radiobutton(self.setup_frame, text="2 Spieler", variable=self.player_var, value=2, 
                       command=self.update_player_options).grid(row=0, column=2, padx=5, pady=5)
        
        tk.Label(self.setup_frame, text="Spieler 1:").grid(row=1, column=0, padx=5, pady=5)
        self.p1_control = tk.StringVar(value="keyboard")
        tk.Radiobutton(self.setup_frame, text="Tastatur", variable=self.p1_control, value="keyboard", 
                       command=lambda: self.handle_control_change(1)).grid(row=1, column=1, padx=5, pady=5)
        tk.Radiobutton(self.setup_frame, text="Bluetooth", variable=self.p1_control, value="bluetooth", 
                       command=lambda: self.handle_control_change(1)).grid(row=1, column=2, padx=5, pady=5)
        
        tk.Label(self.setup_frame, text="Spieler 2:").grid(row=2, column=0, padx=5, pady=5)
        self.p2_control = tk.StringVar(value="keyboard")
        self.p2_kb_radio = tk.Radiobutton(self.setup_frame, text="Tastatur", variable=self.p2_control, value="keyboard", 
                       command=lambda: self.handle_control_change(2))
        self.p2_kb_radio.grid(row=2, column=1, padx=5, pady=5)
        
        self.p2_bt_radio = tk.Radiobutton(self.setup_frame, text="Bluetooth", variable=self.p2_control, value="bluetooth", 
                                         command=lambda: self.handle_control_change(2))
        self.p2_bt_radio.grid(row=2, column=2, padx=5, pady=5)
        
        if self.player_var.get() == 1:
            self.p2_kb_radio.config(state=tk.DISABLED)
            self.p2_bt_radio.config(state=tk.DISABLED)
        
        self.start_button = tk.Button(self.setup_frame, text="Spiel starten", command=self.initialize_game)
        self.start_button.grid(row=3, column=0, columnspan=3, pady=10)
        
        self.update_status_labels()

    def update_player_options(self):
        players = self.player_var.get()
        self.players = players
        
        if players == 1:
            self.p2_kb_radio.config(state=tk.DISABLED)
            self.p2_bt_radio.config(state=tk.DISABLED)
            self.p2_control.set("keyboard")
            self.player2_control = "keyboard"
            self.status_label2.config(text="Spieler 2: Nicht aktiviert")
            if self.bt_manager.device2_connected:
                self.disconnect_player_device(2)
        else:
            self.p2_kb_radio.config(state=tk.NORMAL)
            self.p2_bt_radio.config(state=tk.NORMAL)
            self.handle_control_change(2)

    def handle_control_change(self, player_num):
        if player_num == 1:
            self.player1_control = self.p1_control.get()
            if self.player1_control == "bluetooth":
                self.status_label1.config(text=f"Spieler 1: Wird verbunden...")
                self.connect_player_device(1)
            else:
                self.status_label1.config(text="Spieler 1: Tastatur")
                self.disconnect_player_device(1)
        else:
            if self.player_var.get() == 2:
                self.player2_control = self.p2_control.get()
                if self.player2_control == "bluetooth":
                    self.status_label2.config(text=f"Spieler 2: Wird verbunden...")
                    self.connect_player_device(2)
                else:
                    self.status_label2.config(text="Spieler 2: Tastatur")
                    self.disconnect_player_device(2)
            else:
                self.status_label2.config(text="Spieler 2: Nicht aktiviert")

    def connect_player_device(self, player_num):
        if (player_num == 1 and self.player1_control == "bluetooth") or \
           (player_num == 2 and self.player2_control == "bluetooth"):
            self.bt_manager.start_device_thread(BLUETOOTH_DEVICE1 if player_num == 1 else BLUETOOTH_DEVICE2, player_num)

    def disconnect_player_device(self, player_num):
        if (player_num == 1 and self.player1_control == "bluetooth") or \
           (player_num == 2 and self.player2_control == "bluetooth"):
            asyncio.run_coroutine_threadsafe(
                self.bt_manager.cleanup_connections(),
                self.loop
            )

    def initialize_game(self):
        self.players = self.player_var.get()
        self.player1_control = self.p1_control.get()
        self.player2_control = self.p2_control.get() if self.players == 2 else "keyboard"
        
        self.setup_frame.destroy()
        self.start_game()
        self.update_game()

    def update_status_labels(self):
        if self.player1_control == "bluetooth":
            self.status_label1.config(text=f"Spieler 1: {self.bt_manager.device1_status}")
        else:
            self.status_label1.config(text="Spieler 1: Tastatur")
            
        if self.players == 2:
            if self.player2_control == "bluetooth":
                self.status_label2.config(text=f"Spieler 2: {self.bt_manager.device2_status}")
            else:
                self.status_label2.config(text="Spieler 2: Tastatur")
        else:
            self.status_label2.config(text="Spieler 2: Nicht aktiviert")

    def start_game(self):
        self.paddle1 = Paddle(self.canvas, 20, WIN_HEIGHT // 2 - PADDLE_HEIGHT // 2)
        self.paddle2 = Paddle(self.canvas, WIN_WIDTH - 30, WIN_HEIGHT // 2 - PADDLE_HEIGHT // 2) if self.players == 2 else None
        self.ball = Ball(self.canvas, WIN_WIDTH // 2, WIN_HEIGHT // 2)
        
        self.running = True
        self.game_started = True
        
        if self.player1_control == "keyboard":
            self.root.bind("<Up>", lambda e: self.set_paddle_speed(1, -PADDLE_SPEED))
            self.root.bind("<Down>", lambda e: self.set_paddle_speed(1, PADDLE_SPEED))
            self.root.bind("<KeyRelease-Up>", lambda e: self.set_paddle_speed(1, 0))
            self.root.bind("<KeyRelease-Down>", lambda e: self.set_paddle_speed(1, 0))
            
        if self.players == 2 and self.player2_control == "keyboard":
            self.root.bind("<w>", lambda e: self.set_paddle_speed(2, -PADDLE_SPEED))
            self.root.bind("<s>", lambda e: self.set_paddle_speed(2, PADDLE_SPEED))
            self.root.bind("<KeyRelease-w>", lambda e: self.set_paddle_speed(2, 0))
            self.root.bind("<KeyRelease-s>", lambda e: self.set_paddle_speed(2, 0))
        
        self.reset_button = tk.Button(self.control_frame, text="Neu starten", command=self.reset_game)
        self.reset_button.pack(side=tk.LEFT, padx=10)

    def reset_game(self):
        self.running = False
        self.canvas.delete("all")
        if hasattr(self, 'reset_button'):
            self.reset_button.destroy()
        self.player1_lives = 5
        self.player2_lives = 5
        self.update_lives_labels()
        
        self.paddle1 = Paddle(self.canvas, 20, WIN_HEIGHT // 2 - PADDLE_HEIGHT // 2)
        self.paddle2 = Paddle(self.canvas, WIN_WIDTH - 30, WIN_HEIGHT // 2 - PADDLE_HEIGHT // 2) if self.players == 2 else None
        self.ball = Ball(self.canvas, WIN_WIDTH // 2, WIN_HEIGHT // 2)
        
        self.running = True
        self.game_started = True

    def update_lives_labels(self):
        self.lives_label1.config(text=f"Leben Spieler 1: {self.player1_lives}")
        self.lives_label2.config(text=f"Leben Spieler 2: {self.player2_lives}")

    def set_paddle_speed(self, paddle_num, speed):
        if paddle_num == 1:
            self.paddle1.set_speed(speed)
            #logger.debug(f"Set paddle 1 speed to {speed}")
        elif paddle_num == 2 and self.paddle2:
            self.paddle2.set_speed(speed)
            #logger.debug(f"Set paddle 2 speed to {speed}")

    def update_game(self):
        if self.running:
            self.paddle1.move()
            if self.paddle2:
                self.paddle2.move()
            self.move_ball()
            self.root.after(20, self.update_game)

    def move_ball(self):
        self.ball.move()
        pos = self.ball.get_coords()

        if pos[1] <= 0 or pos[3] >= WIN_HEIGHT:
            self.ball.dy = -self.ball.dy
        if pos[0] <= 0:
            self.player1_loses_life()
        elif pos[2] >= WIN_WIDTH:
            self.player2_loses_life()
        if self.check_collision(self.paddle1, pos) or (self.paddle2 and self.check_collision(self.paddle2, pos)):
            self.ball.dx = -self.ball.dx

    def player1_loses_life(self):
        self.player1_lives -= 1
        self.update_lives_labels()
        if self.player1_lives == 0:
            self.end_game(winner=2)
        else:
            self.ball.reset()

    def player2_loses_life(self):
        self.player2_lives -= 1
        self.update_lives_labels()
        if self.player2_lives == 0:
            self.end_game(winner=1)
        else:
            self.ball.reset()

    def end_game(self, winner):
        self.running = False
        message = f"Spieler {winner} gewinnt! Möchtest du nochmal spielen?"
        if messagebox.askyesno("Spiel beendet", message):
            self.reset_game()
        else:
            self.root.destroy()

    def check_collision(self, paddle, ball_pos):
        paddle_pos = paddle.get_coords()
        return (paddle_pos[0] < ball_pos[2] and paddle_pos[2] > ball_pos[0] and
                paddle_pos[1] < ball_pos[3] and paddle_pos[3] > ball_pos[1])

def run_event_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

def main():
    loop = asyncio.new_event_loop()
    event_loop_thread = threading.Thread(target=run_event_loop, args=(loop,), daemon=True)
    event_loop_thread.start()
    
    root = tk.Tk()
    game = PongGame(root, loop)
    root.mainloop()

if __name__ == "__main__":
    main()