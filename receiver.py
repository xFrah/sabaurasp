import paho.mqtt.client as mqtt
import cv2
import numpy as np
import base64
import threading
import time
import json
from collections import deque
from datetime import datetime

counter = 0
last_time = time.time()
last_move_time = 0
last_position = {"x": 0, "y": 0}

def map_to_range(value):
    # Map from 0-200 to -1 to 1
    return (value - 100) / 100.0

def check_and_send_position():
    global last_move_time, last_position
    
    while StreamReceiver.instance.running:
        current_time = time.time()
        
        # Get current positions and map to -1 to 1
        x_pos = map_to_range(cv2.getTrackbarPos('X Position', 'Camera Control'))
        y_pos = map_to_range(cv2.getTrackbarPos('Y Position', 'Camera Control'))
        
        current_position = {"x": x_pos, "y": y_pos}
        
        # Only send if position changed and rate limit of 1 second
        if (current_position != last_position and 
            current_time - last_move_time >= 1.0):
            
            # Send to MQTT
            StreamReceiver.instance.client.publish(
                "camera/move", 
                json.dumps(current_position)
            )
            print(f"Sending position: x={x_pos:.2f}, y={y_pos:.2f}")
            
            last_position = current_position
            last_move_time = current_time
            
        time.sleep(0.1)  # Small sleep to prevent CPU overuse

class StreamReceiver:
    instance = None
    
    def __init__(self, broker_address="lancionaco.ddns.net", port=1883):
        StreamReceiver.instance = self
        self.client = mqtt.Client(client_id="stream_receiver_client", protocol=mqtt.MQTTv311)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        self.running = True

        print(f"[MQTT] Connecting to broker {broker_address}...")
        self.client.connect(broker_address, port, keepalive=120)

        # Create control window and trackbars
        cv2.namedWindow('Camera Control')
        cv2.createTrackbar('X Position', 'Camera Control', 100, 200, lambda x: None)
        cv2.createTrackbar('Y Position', 'Camera Control', 100, 200, lambda x: None)
        
        # Set initial positions to center (100 = 0.0)
        cv2.setTrackbarPos('X Position', 'Camera Control', 100)
        cv2.setTrackbarPos('Y Position', 'Camera Control', 100)

        # Start position checking thread
        self.position_thread = threading.Thread(target=check_and_send_position)
        self.position_thread.daemon = True
        self.position_thread.start()

    def on_connect(self, client, userdata, flags, rc):
        print(f"[MQTT] Connected with result code {rc}")
        if rc == 0:
            print("[MQTT] Successfully connected to broker")
            client.subscribe("camera/stream")
        else:
            print("[MQTT] Connection failed")

    def on_disconnect(self, client, userdata, rc):
        print(f"[MQTT] Disconnected with result code {rc}")

    def on_message(self, client, userdata, msg):
        global counter, last_time
        try:            
            frame = cv2.imdecode(np.frombuffer(msg.payload, np.uint8), cv2.IMREAD_COLOR)
            cv2.imshow('Camera Control', frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                self.running = False
                self.client.disconnect()
                cv2.destroyAllWindows()

            counter += 1
            if counter % 60 == 0:
                current_time = time.time()
                fps = 60 / (current_time - last_time)
                print(f"Actual FPS: {fps:.2f}")
                last_time = current_time

        except Exception as e:
            print(f"Error processing frame: {e}")

    def start(self):
        try:
            self.client.loop_forever()
        except KeyboardInterrupt:
            print("Stopping receiver...")
            self.running = False
            self.client.disconnect()
            cv2.destroyAllWindows()
            if self.position_thread.is_alive():
                self.position_thread.join()

if __name__ == "__main__":
    receiver = StreamReceiver()
    receiver.start()