import tkinter as tk
from bleak import BleakClient
import asyncio
import json
from asyncio import Event
import threading
from queue import Queue

# UUIDs für den BLE-Service und die Charakteristik
SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

# Game settings
WIN_WIDTH = 1000
WIN_HEIGHT = 600
PADDLE_WIDTH = 10
PADDLE_HEIGHT = 100
BALL_SIZE = 20
PLAYER_SPEED = 5
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
        self.x_velocity = 4
        self.y_velocity = 4
        self.base_speed = 4  # Grundgeschwindigkeit für Normalisierung nach Kollisionen

    def move(self):
        self.canvas.move(self.oval, self.x_velocity, self.y_velocity)
        self.check_wall_collisions()

    def check_wall_collisions(self):
        pos = self.canvas.coords(self.oval)
        
        # Obere und untere Wand
        if pos[1] <= 0:  # Obere Wand
            self.y_velocity = abs(self.y_velocity)  # Erzwinge positive y-Geschwindigkeit
            self.canvas.move(self.oval, 0, -pos[1])  # Verhindere Steckenbleiben
        elif pos[3] >= WIN_HEIGHT:  # Untere Wand
            self.y_velocity = -abs(self.y_velocity)  # Erzwinge negative y-Geschwindigkeit
            self.canvas.move(self.oval, 0, WIN_HEIGHT - pos[3])  # Verhindere Steckenbleiben
        
        # Rechte Wand
        if pos[2] >= WIN_WIDTH:  # Rechte Wand
            self.x_velocity = -abs(self.x_velocity)  # Erzwinge negative x-Geschwindigkeit
            self.canvas.move(self.oval, WIN_WIDTH - pos[2], 0)  # Verhindere Steckenbleiben

    def check_paddle_collision(self, paddle):
        pos = self.canvas.coords(self.oval)
        paddle_pos = paddle.get_position()
        
        if (paddle_pos[0] < pos[2] < paddle_pos[2] or paddle_pos[0] < pos[0] < paddle_pos[2]) and \
           (paddle_pos[1] < pos[3] < paddle_pos[3] or paddle_pos[1] < pos[1] < paddle_pos[3]):
            
            # Berechne Auftreffpunkt relativ zur Paddlemitte
            paddle_center = (paddle_pos[3] + paddle_pos[1]) / 2
            ball_center = (pos[3] + pos[1]) / 2
            relative_intersect = (ball_center - paddle_center) / (PADDLE_HEIGHT / 2)
            
            # Bounce angle zwischen -45 und 45 Grad
            bounce_angle = relative_intersect * 45
            
            # Setze neue Geschwindigkeiten basierend auf dem Bounce Angle
            import math
            self.x_velocity = abs(self.base_speed * math.cos(math.radians(bounce_angle)))
            self.y_velocity = self.base_speed * math.sin(math.radians(bounce_angle))

    def reset(self):
        # Zentriere den Ball
        self.canvas.coords(self.oval, 
                          WIN_WIDTH // 2 - BALL_SIZE // 2,
                          WIN_HEIGHT // 2 - BALL_SIZE // 2,
                          WIN_WIDTH // 2 + BALL_SIZE // 2,
                          WIN_HEIGHT // 2 + BALL_SIZE // 2)
        
        # Setze Geschwindigkeit zurück und starte nach links
        self.x_velocity = -self.base_speed
        self.y_velocity = 0

class PongGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Pong Game")
        self.canvas = tk.Canvas(root, width=WIN_WIDTH, height=WIN_HEIGHT, bg=BG_COLOR)
        self.canvas.pack()

        self.left_paddle = Paddle(self.canvas, 10, WIN_HEIGHT // 2 - PADDLE_HEIGHT // 2)
        self.ball = Ball(self.canvas)
        
        self.ble_queue = Queue()
        self.connected = False
        
        # Start BLE connection in a separate thread
        self.ble_thread = threading.Thread(target=self.run_ble_loop)
        self.ble_thread.daemon = True
        self.ble_thread.start()
        
        # Start game update loop
        self.update_game()
        
        # Check BLE queue periodically
        self.root.after(100, self.check_ble_queue)

    def check_ble_queue(self):
        try:
            while not self.ble_queue.empty():
                data = self.ble_queue.get_nowait()
                self.process_ble_data(data)
        except Exception as e:
            print(f"Error processing BLE queue: {e}")
        finally:
            self.root.after(100, self.check_ble_queue)

    def process_ble_data(self, data):
        try:
            json_str = data.decode('utf-8')
            joystick_data = json.loads(json_str)
            ax = joystick_data.get("Ax", 0)
            self.left_paddle.set_speed(ax * PLAYER_SPEED)
        except Exception as e:
            print(f"Error processing BLE data: {e}")

    def notification_handler(self, sender, data):
        self.ble_queue.put(data)

    def run_ble_loop(self):
        async def run_ble():
            while True:
                try:
                    async with BleakClient("64:e8:33:88:5e:e2") as client:
                        print("Connected to BLE device")
                        self.connected = True
                        await client.start_notify(CHARACTERISTIC_UUID, self.notification_handler)
                        await Event().wait()  # Run forever
                except Exception as e:
                    print(f"BLE Error: {e}")
                    self.connected = False
                    await asyncio.sleep(1)  # Wait before retrying

        asyncio.run(run_ble())

    def update_game(self):
        self.ball.move()
        self.ball.check_paddle_collision(self.left_paddle)
        
        # Ball-Reset wird jetzt nur noch ausgelöst, wenn der Ball die linke Wand berührt
        ball_pos = self.ball.canvas.coords(self.ball.oval)
        if ball_pos[0] <= 0:  # Ball hat linke Wand berührt
            self.ball.reset()

        self.left_paddle.move()
        self.root.after(20, self.update_game)

def main():
    root = tk.Tk()
    game = PongGame(root)
    root.mainloop()

if __name__ == "__main__":
    main()