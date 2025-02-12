import tkinter as tk
from bleak import BleakClient
import asyncio
import json
import time  # Für Pausen (ineffizient!)

# UUIDs für den BLE-Service und die Charakteristik
SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

# Game settings
WIN_WIDTH = 1000
WIN_HEIGHT = 600
PADDLE_WIDTH = 10
PADDLE_HEIGHT = 100
BALL_SIZE = 20
PLAYER_SPEED = 20
FG_COLOR = "black"
BG_COLOR = "white"

class Paddle:
    def __init__(self, canvas, x, y):
        self.canvas = canvas
        self.rect = canvas.create_rectangle(x, y, x + PADDLE_WIDTH, y + PADDLE_HEIGHT, fill=FG_COLOR)
        self.speed = 0

    def move(self):
        self.canvas.move(self.rect, 0, self.speed)
        self.limit_within_screen()

    def hide(self):
        self.canvas.itemconfig(self.rect, fill=BG_COLOR, outline=BG_COLOR)

    def show(self):
        self.canvas.itemconfig(self.rect, fill=FG_COLOR, outline=FG_COLOR)

    def limit_within_screen(self):
        pos = self.canvas.coords(self.rect)
        if pos[1] < 0:
            self.canvas.move(self.rect, 0, -pos[1])
        elif pos[3] > WIN_HEIGHT:
            self.canvas.move(self.rect, 0, WIN_HEIGHT - pos[3])

    def set_speed(self, speed):
        self.speed = speed

    def get_position(self):
        return self.canvas.coords(self.rect)

class Ball:
    def __init__(self, canvas):
        self.canvas = canvas
        self.oval = canvas.create_oval(WIN_WIDTH // 2 - BALL_SIZE // 2, WIN_HEIGHT // 2 - BALL_SIZE // 2,
                                       WIN_WIDTH // 2 + BALL_SIZE // 2, WIN_HEIGHT // 2 + BALL_SIZE // 2, fill=FG_COLOR)
        self.x_velocity = 5
        self.y_velocity = 5

    def move(self):
        self.canvas.move(self.oval, self.x_velocity, self.y_velocity)
        #self.check_wall_collision()

    def check_wall_collision(self):
        pos = self.canvas.coords(self.oval)
        if pos[1] <= 0 or pos[3] >= WIN_HEIGHT:
            self.y_velocity = -self.y_velocity

    def check_paddle_collision(self, paddle):
        pos = self.canvas.coords(self.oval)
        paddle_pos = paddle.get_position()
        if (paddle_pos[0] < pos[2] < paddle_pos[2] or paddle_pos[0] < pos[0] < paddle_pos[2]) and \
           (paddle_pos[1] < pos[3] < paddle_pos[3] or paddle_pos[1] < pos[1] < paddle_pos[3]):
            self.x_velocity = -self.x_velocity

    def check_right_wall_collision(self):
        pos = self.canvas.coords(self.oval)
        return pos[2] >= WIN_WIDTH

    def reset(self):
        self.canvas.coords(self.oval, WIN_WIDTH // 2 - BALL_SIZE // 2, WIN_HEIGHT // 2 - BALL_SIZE // 2,
                           WIN_WIDTH // 2 + BALL_SIZE // 2, WIN_HEIGHT // 2 + BALL_SIZE // 2)
        self.x_velocity = -self.x_velocity

    def get_position(self):
        return self.canvas.coords(self.oval)

class PongGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Pong Game")
        self.canvas = tk.Canvas(root, width=WIN_WIDTH, height=WIN_HEIGHT, bg=BG_COLOR)
        self.canvas.pack()

        self.left_paddle = Paddle(self.canvas, 10, WIN_HEIGHT // 2 - PADDLE_HEIGHT // 2) # Startposition angepasst
        self.ball = Ball(self.canvas)

        self.ble_client = BleakClient("64:e8:33:88:5e:e2")  # Deine ESP32-C3 BLE Adresse
        self.connected = False  # Flag für den Verbindungsstatus

        self.root.after(100)  # Verzögerte Verbindung


    def connect_ble(self):
        try:
            print("Versuche zu verbinden...")
            self.ble_client.connect()  # Blockiert, bis Verbindung hergestellt ist
            print("Verbunden!")
            self.ble_connected = True
            self.ble_client.start_notify(CHARACTERISTIC_UUID, self.notification_handler) # Start der Benachrichtigung
            print("Benachrichtigungen aktiviert")
        except Exception as e:
            print(f"Verbindungsfehler: {e}")

    def notification_handler(self, sender, data):
        print(f"Daten empfangen: {data}")  # Rohe Daten
        print(f"Daten (Bytes): {len(data)}") # Länge der Daten
        try:
            json_str = data.decode("utf-8")
            print(f"JSON-String: {json_str}")
            joystick_data = json.loads(json_str)
            print(f"Joystick-Daten: {joystick_data}")
            ax = joystick_data["Ax"]
            print(f"Ax: {ax}")
            # ...
        except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as e:
            print(f"Fehler: {e}")  # Detaillierte Fehlermeldung
            print(f"Daten (repr): {repr(data)}") # Repräsentation der Daten

    def update_game(self):
        if self.ble_connected: # Überprüfen ob die Verbindung steht
            self.ball.move()
            self.ball.check_wall_collision()
            self.ball.check_paddle_collision(self.left_paddle)
            if self.ball.check_right_wall_collision():
                self.ball.reset()

            self.left_paddle.move()  # Paddle bewegt sich jetzt durch BLE-Daten

        self.root.after(20, self.update_game) # Ruft sich periodisch selbst auf

root = tk.Tk()
game = PongGame(root)
root.mainloop() # Wichtig: Nur root.mainloop(), keine asynchrone Schleife!
