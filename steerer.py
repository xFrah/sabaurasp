import paho.mqtt.client as mqtt
import time
import subprocess
import json

# Callback functions
def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Connected with result code {rc}")
    if rc == 0:
        print("[MQTT] Successfully connected to broker")
    else:
        print("[MQTT] Connection failed, retrying...")

def on_disconnect(client, userdata, rc):
    if rc == 0:
        print("[MQTT] Clean disconnection from broker")
    else:
        print(f"[MQTT] Unexpected disconnection from broker. Return code: {rc}")
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
            print(f"[MQTT] Reconnection failed: {e}")
            time.sleep(5)

# MQTT broker settings
broker_address = "lancionaco.love"
port = 1883
topic = "sensor/moisture"  # Changed topic to be more descriptive

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
print(f"[MQTT] Connecting to broker {broker_address}...")
client.connect(broker_address, port, keepalive=120)

# Start the loop in a non-blocking way
client.loop_start()

# RTL_433 command
rtl_command = ["sudo", "rtl_433", "-f", "868.35M", "-s", "1024k", "-p", "0", "-g", "42", "-Y", "autolevel", "-Y", "squelch=0.35", "-R", "142", "-X", "n=WH51-Optimized,m=FSK_PCM,s=58,l=58,r=2500,preamble=aa2dd4", "-F", "json", "-M", "level", "-M", "noise", "-M", "time:utc"]

# Main loop
try:
    # Start the rtl_433 process
    process = subprocess.Popen(rtl_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    # Read output line by line
    while True:
        line = process.stdout.readline()
        if line:
            try:
                # Parse JSON data
                data = json.loads(line)
                # Publish the JSON data to MQTT
                client.publish(topic, json.dumps(data))
                print(f"[MQTT] Sent: {data}")
            except json.JSONDecodeError as e:
                print(f"[RTL_433] {line}")
                continue

except KeyboardInterrupt:
    print("\nScript terminated by user")
    process.terminate()  # Terminate the rtl_433 process
    client.loop_stop()
    client.disconnect()
except Exception as e:
    print(f"An error occurred: {e}")
    process.terminate()
    client.loop_stop()
    client.disconnect()
