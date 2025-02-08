import paho.mqtt.client as mqtt
import time

# Callback functions
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    if rc == 0:
        print("Successfully connected to broker")
    else:
        print("Connection failed, retrying...")

def on_disconnect(client, userdata, rc):
    if rc == 0:
        print("Clean disconnection from broker")
    else:
        print(f"Unexpected disconnection from broker. Return code: {rc}")
        # rc meanings:
        # 0: Clean disconnect
        # 1: Protocol version error
        # 2: Invalid client identifier
        # 3: Server unavailable
        # 4: Bad username or password
        # 5: Not authorized
    while True:
        try:
            client.reconnect()
            break
        except Exception as e:
            print(f"Reconnection failed: {e}")
            time.sleep(5)

# MQTT broker settings
broker_address = "lancionaco.ddns.net"
port = 1883
topic = "test/message"

# Create a MQTT client instance
client = mqtt.Client(
    client_id="python_mqtt_client_001", 
    protocol=mqtt.MQTTv311
)

# Set callback functions
client.on_connect = on_connect
client.on_disconnect = on_disconnect

# Enable automatic reconnection

client.reconnect_delay_set(min_delay=1, max_delay=30)

# Connect to the broker
print(f"Connecting to broker {broker_address}...")
client.connect(broker_address, port, keepalive=120)

# Start the loop in a non-blocking way
client.loop_start()

# Main loop
try:
    while True:
        message = "Hello from Python MQTT client!"
        client.publish(topic, message)
        print(f"Message sent to topic '{topic}': {message}")
        time.sleep(0.5)  # Send a message every 5 seconds

except KeyboardInterrupt:
    print("\nScript terminated by user")
    client.loop_stop()
