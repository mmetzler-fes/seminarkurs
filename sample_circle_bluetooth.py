import tkinter as tk
from bleak import BleakClient, BleakScanner, BleakError
import asyncio
import json
import threading
from queue import Queue

# UUIDs für den BLE-Service und die Charakteristik
SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

# Game settings
WIN_WIDTH = 1000
WIN_HEIGHT = 600
BALL_SIZE = 20
PLAYER_SPEED = 5
FG_COLOR = "black"
BG_COLOR = "white"

class Ball:
    def __init__(self, canvas):
        self.canvas = canvas
        self.ball = canvas.create_oval(WIN_WIDTH // 2 - BALL_SIZE // 2, WIN_HEIGHT // 2 - BALL_SIZE // 2,
                                       WIN_WIDTH // 2 + BALL_SIZE // 2, WIN_HEIGHT // 2 + BALL_SIZE // 2, fill=FG_COLOR)
        self.x_velocity = 0
        self.y_velocity = 0

    def move(self):
        self.canvas.move(self.ball, self.x_velocity, self.y_velocity)
        self.check_wall_collision()

    def check_wall_collision(self):
        pos = self.canvas.coords(self.ball)
        if pos[0] < 0:
            self.canvas.move(self.ball, -pos[0], 0)
        if pos[1] < 0:
            self.canvas.move(self.ball, 0, -pos[1])
        if pos[2] > WIN_WIDTH:
            self.canvas.move(self.ball, WIN_WIDTH - pos[2], 0)
        if pos[3] > WIN_HEIGHT:
            self.canvas.move(self.ball, 0, WIN_HEIGHT - pos[3])

    def setSpeedX(self, speedX):
        self.x_velocity = speedX 

    def setSpeedY(self, speedY):
        self.y_velocity = speedY 
        
    def reset(self):
        self.canvas.coords(self.ball, WIN_WIDTH // 2 - BALL_SIZE // 2, WIN_HEIGHT // 2 - BALL_SIZE // 2,
                           WIN_WIDTH // 2 + BALL_SIZE // 2, WIN_HEIGHT // 2 + BALL_SIZE // 2)

class ExampleGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Ball Control Game")
        self.canvas = tk.Canvas(root, width=WIN_WIDTH, height=WIN_HEIGHT, bg=BG_COLOR)
        self.canvas.pack()

        self.ball = Ball(self.canvas)

        self.root.bind("<KeyPress>", self.key_press)
        self.root.bind("<KeyRelease>", self.key_release)

        self.button = tk.Button(root, text="Gerät suchen...", command=self.start_scan)
        self.button.pack()

        self.connect_button = tk.Button(root, text="Verbinden", command=self.start_connection, state=tk.DISABLED)
        self.connect_button.pack()

        self.status_label = tk.Label(root, text="Status: Nicht verbunden", fg="red")
        self.status_label.pack()

        self.ble_queue = Queue()
        self.ble_device_address = None
        self.connected = False

        self.update_game()
        self.root.after(100, self.check_ble_queue)
        self.ble_buffer = b""  # Puffer für empfangene Daten

    def check_ble_queue(self):
        try:
            while not self.ble_queue.empty():
                #print("Queue not empty")
                data = self.ble_queue.get_nowait()
                self.process_ble_data(data)
        except Exception as e:
            print(f"⚠️ Fehler beim Verarbeiten der BLE-Daten: {e}")
        finally:
            self.root.after(100, self.check_ble_queue)

    def process_ble_data(self, json_str):
        try:
            json_data = json.loads(json_str)
            ax = json_data.get("Ax", 0)
            ay = json_data.get("Ay", 0)
            self.ball.setSpeedX(ax * PLAYER_SPEED)
            self.ball.setSpeedY(ay * PLAYER_SPEED)
        except json.JSONDecodeError as e:
            print(f"⚠️ Fehler beim Parsen der JSON-Daten: {e}")
        except Exception as e:
            print(f"⚠️ Fehler beim Verarbeiten der BLE-Daten: {e}")

    def notification_handler(self, sender, data):
        self.ble_buffer += data  # Füge die empfangenen Daten zum Puffer hinzu
        while b"\n" in self.ble_buffer:  # Suche nach dem Trennzeichen
            # Trenne die Nachricht am ersten Trennzeichen
            json_str, self.ble_buffer = self.ble_buffer.split(b"\n", 1)
            try:
                # Dekodiere die Nachricht und verarbeite sie
                json_str = json_str.decode('utf-8')
                self.ble_queue.put(json_str)
            except UnicodeDecodeError as e:
                print(f"⚠️ Fehler beim Dekodieren der Daten: {e}")
            except Exception as e:
                print(f"⚠️ Fehler beim Verarbeiten der BLE-Daten: {e}")

    def start_scan(self):
        """Startet das Scannen nach BLE-Geräten in einem separaten Thread."""
        self.button.config(text="Suche läuft...", state=tk.DISABLED)
        scan_thread = threading.Thread(target=self.run_ble_scan, daemon=True)
        scan_thread.start()

    def run_ble_scan(self):
        """Scan-Prozess läuft in eigenem Thread mit neuer asyncio-Schleife."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.scan_ble_devices())

    async def scan_ble_devices(self):
        """Asynchrones Scannen nach BLE-Geräten."""
        try:
            devices = await BleakScanner.discover(timeout=10.0)  # Timeout von 10 Sekunden
            for device in devices:
                if SERVICE_UUID.lower() in (device.metadata.get("uuids", []) or []):  # Prüft, ob die Service-UUID vorhanden ist
                    self.ble_device_address = device.address
                    print(f"✅ Gefundenes ESP32-Gerät: {self.ble_device_address}")
                    self.root.after(0, self.enable_connect_button, device.name)
                    return
            self.root.after(0, self.show_no_device_found)
        except Exception as e:
            print(f"⚠️ Fehler beim Scannen: {e}")
            self.root.after(0, self.show_no_device_found)

    def enable_connect_button(self, device_name):
        self.connect_button.config(state=tk.NORMAL, text=f"Verbinden mit {device_name}")
        self.status_label.config(text=f"Status: Gerät gefunden - {device_name}", fg="green")

    def show_no_device_found(self):
        self.button.config(text="Kein Gerät gefunden! Erneut versuchen", state=tk.NORMAL)
        self.status_label.config(text="Status: Kein Gerät gefunden", fg="red")

    def start_connection(self):
        """Startet die Verbindung mit dem gefundenen ESP32-Gerät in einem separaten Thread."""
        if not self.ble_device_address:
            print("⚠️ Kein Gerät zum Verbinden gefunden!")
            return

        self.connect_button.config(text="Verbinde...", state=tk.DISABLED)
        ble_thread = threading.Thread(target=self.run_ble_connection, daemon=True)
        ble_thread.start()

    def run_ble_connection(self):
        """Startet die BLE-Verbindung mit eigenem asyncio-Loop."""
        print("Event-Loop für BLE-Verbindung starten...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.connect_ble_device())

    async def connect_ble_device(self):
        """Asynchrone Verbindung zum BLE-Gerät."""
        try:
            async with BleakClient(self.ble_device_address) as client:
                print("✅ Verbindung zu ESP32 hergestellt!")
                self.connected = True
                self.root.after(0, self.update_status, "Status: Verbunden", "green")
                await client.start_notify(CHARACTERISTIC_UUID, self.notification_handler)
                print("notifying...")
                await asyncio.Event().wait()  # Run forever
        except BleakError as e:
            print(f"❌ BLE-Verbindungsfehler: {e}")
            self.root.after(0, self.enable_reconnect_button)

    def enable_reconnect_button(self):
        self.connect_button.config(text="Erneut verbinden", state=tk.NORMAL)
        self.status_label.config(text="Status: Verbindung fehlgeschlagen", fg="red")

    def update_status(self, text, color):
        self.status_label.config(text=text, fg=color)

    def key_press(self, event):
        if event.keysym == "Up":
            self.ball.setSpeedY(-PLAYER_SPEED)
        elif event.keysym == "Down":
            self.ball.setSpeedY(PLAYER_SPEED)
        elif event.keysym == "Left":
            self.ball.setSpeedX(-PLAYER_SPEED)
        elif event.keysym == "Right":
            self.ball.setSpeedX(PLAYER_SPEED)

    def key_release(self, event):
        if event.keysym in ["Left", "Right"]:
            self.ball.setSpeedX(0)
        elif event.keysym in ["Up", "Down"]:
            self.ball.setSpeedY(0)

    def update_game(self):
        self.ball.move()
        self.root.after(20, self.update_game)

def main():
    root = tk.Tk()
    game = ExampleGame(root)
    root.mainloop()

if __name__ == "__main__":
    main()