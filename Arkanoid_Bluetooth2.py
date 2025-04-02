import tkinter as tk
from tkinter import messagebox
from bleak import BleakClient
import asyncio
import json
from asyncio import Event
import threading
from queue import Queue
import random

# UUIDs für den BLE-Service und die Charakteristik
SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"
BLUETOOTH_DEVICE1 = "64:E8:33:88:5E:E2"
BLUETOOTH_DEVICE2 = "64:E8:33:88:9E:36"

# Game settings
WIN_WIDTH = 1000
WIN_HEIGHT = 600
PADDLE_WIDTH = 100
PADDLE_HEIGHT = 10
BALL_SIZE = 20
BALL_SPEED = 5
PLAYER_SPEED = 3
BLOCK_WIDTH = 100
BLOCK_HEIGHT = 30
FG_COLOR = "black"
BG_COLOR = "white"
BLOCK_COLORS = ["red", "blue", "green", "yellow", "purple"]
LIVES = 5

class Paddle:
    def __init__(self, canvas, x, y):
        self.canvas = canvas
        self.rect = canvas.create_rectangle(x, y, x + PADDLE_WIDTH, y + PADDLE_HEIGHT, fill=FG_COLOR)
        self.speed = 0
    
    def move(self):
        self.canvas.move(self.rect, self.speed, 0)
        self.limit_within_screen()
    
    def limit_within_screen(self):
        pos = self.canvas.coords(self.rect)
        if pos[0] < 0:
            self.canvas.move(self.rect, -pos[0], 0)
        elif pos[2] > WIN_WIDTH:
            self.canvas.move(self.rect, WIN_WIDTH - pos[2], 0)
    
    def set_speed(self, speed):
        self.speed = speed
    
    def get_position(self):
        return self.canvas.coords(self.rect)

class Ball:
    def __init__(self, canvas):
        self.canvas = canvas
        self.oval = canvas.create_oval(WIN_WIDTH // 2 - BALL_SIZE // 2, WIN_HEIGHT // 2 - BALL_SIZE // 2,
                                     WIN_WIDTH // 2 + BALL_SIZE // 2, WIN_HEIGHT // 2 + BALL_SIZE // 2, fill=FG_COLOR)
        self.x_velocity = BALL_SPEED
        self.y_velocity = -BALL_SPEED
    
    def move(self):
        self.canvas.move(self.oval, self.x_velocity, self.y_velocity)
        self.check_wall_collisions()
    
    def check_wall_collisions(self):
        pos = self.canvas.coords(self.oval)
        
        if pos[0] <= 0 or pos[2] >= WIN_WIDTH:
            self.x_velocity = -self.x_velocity
        if pos[1] <= 0:
            self.y_velocity = -self.y_velocity
    
    def check_paddle_collision(self, paddle):
        pos = self.canvas.coords(self.oval)
        paddle_pos = paddle.get_position()
        
        if pos[3] >= paddle_pos[1] and paddle_pos[0] < pos[2] and paddle_pos[2] > pos[0]:
            self.y_velocity = -self.y_velocity
    
    def check_block_collision(self, blocks, game):
        pos = self.canvas.coords(self.oval)
        for block in blocks[:]:
            block_pos = self.canvas.coords(block)
            if block_pos and block_pos[1] < pos[3] and block_pos[3] > pos[1] and block_pos[0] < pos[2] and block_pos[2] > pos[0]:
                self.canvas.delete(block)
                blocks.remove(block)
                self.y_velocity = -self.y_velocity
                game.increase_score()
                break
    
    def reset(self):
        self.canvas.coords(self.oval, 
                          WIN_WIDTH // 2 - BALL_SIZE // 2,
                          WIN_HEIGHT // 2 - BALL_SIZE // 2,
                          WIN_WIDTH // 2 + BALL_SIZE // 2,
                          WIN_HEIGHT // 2 + BALL_SIZE // 2)
        self.x_velocity = 4
        self.y_velocity = -4

class ArkanoidGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Arkanoid Game")
        self.canvas = tk.Canvas(root, width=WIN_WIDTH, height=WIN_HEIGHT, bg=BG_COLOR)
        self.canvas.pack()
        
        self.start_button = tk.Button(root, text="Start Game", command=self.start_game)
        self.start_button.pack()
        
        #self.score = 0
        #self.lives = LIVES
        self.init_game()
        self.score_label = tk.Label(root, text=f"Score: {self.score}  Lives: {self.lives}")
        self.score_label.pack()
        
        self.running = False
        self.ble_queue = Queue()
        self.connected = False
        
        
        self.ble_thread = threading.Thread(target=self.run_ble_loop)
        self.ble_thread.daemon = True
        self.ble_thread.start()
        
        self.update_game()
        self.root.after(100, self.check_ble_queue)
    
    def start_game(self):
        self.start_button.destroy()
        self.running = True
        self.update_game()
       
    def init_game(self):
        self.score = 0
        self.lives = LIVES
        self.paddle = Paddle(self.canvas, WIN_WIDTH // 2 - PADDLE_WIDTH // 2, WIN_HEIGHT - 50)
        self.ball = Ball(self.canvas)
        self.blocks = self.create_blocks()
        
    def restart_game(self):
        for block in self.blocks:
            self.canvas.delete(block)
        self.paddle.canvas.delete(self.paddle.rect)
        self.ball.canvas.delete(self.ball.oval)
        self.init_game()
        self.running = True
    
    def create_blocks(self):
        blocks = []
        for row in range(5):
            for col in range(WIN_WIDTH // BLOCK_WIDTH):
                x1 = col * BLOCK_WIDTH
                y1 = row * BLOCK_HEIGHT
                x2 = x1 + BLOCK_WIDTH
                y2 = y1 + BLOCK_HEIGHT
                block = self.canvas.create_rectangle(x1, y1, x2, y2, fill=random.choice(BLOCK_COLORS))
                blocks.append(block)
        return blocks

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
            if self.running:
                self.paddle.set_speed(ax * PLAYER_SPEED)
        except Exception as e:
            print(f"Error processing BLE data: {e}")
    
    def notification_handler(self, sender, data):
        self.ble_queue.put(data)
    
    def run_ble_loop(self):
        async def run_ble():
            while True:
                try:
                    async with BleakClient(BLUETOOTH_DEVICE1) as client:
                        print("Connected to BLE device")
                        self.connected = True
                        await client.start_notify(CHARACTERISTIC_UUID, self.notification_handler)
                        await Event().wait()
                except Exception as e:
                    print(f"BLE Error: {e}")
                    self.connected = False
                    await asyncio.sleep(1)
        asyncio.run(run_ble())

    def increase_score(self):
        self.score += 10
        self.score_label.config(text=f"Score: {self.score}  Lives: {self.lives}")
    
    def lose_life(self):
        self.lives -= 1
        self.score_label.config(text=f"Score: {self.score}  Lives: {self.lives}")
        if self.lives == 0:
            self.game_over()
        else:
            self.ball.reset()
    
    def check_win(self):
        if not self.blocks:  # Falls alle Blöcke entfernt wurden
            self.running = False
            if messagebox.askyesno("Game Over - You Win!", "Play again?"):
                self.restart_game()
            else:
                self.root.quit()

    def game_over(self):
        self.running = False
        if messagebox.askyesno("Game Over", "No lives left! Play again?"):
            self.restart_game()
        else:
            self.root.quit()
    
    def update_game(self):
        if self.running:
            self.check_win()
            self.ball.move()
            self.ball.check_paddle_collision(self.paddle)
            self.ball.check_block_collision(self.blocks, self)
            if self.ball.canvas.coords(self.ball.oval)[3] > WIN_HEIGHT:
                self.lose_life()
            self.paddle.move()
            self.root.after(20, self.update_game)

def main():
    root = tk.Tk()
    game = ArkanoidGame(root)
    root.mainloop()

if __name__ == "__main__":
    main()
