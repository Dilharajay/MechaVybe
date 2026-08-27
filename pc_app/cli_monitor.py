import argparse
import json
import time
import paho.mqtt.client as mqtt

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"[!] Failed to connect to MQTT Broker. Reason: {reason_code}")
    else:
        print(f"[*] Successfully connected to MQTT Broker.")
        client.subscribe(userdata['topic'])
        print(f"[*] Subscribed to topic: {userdata['topic']}")
        print(f"[*] Waiting for inference data...\n")

def on_message(client, userdata, msg):
    payload = msg.payload.decode('utf-8')
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        data = json.loads(payload)
        status = data.get("status", "unknown")
        score = data.get("score", 0.0)
        
        # Color output based on status
        color_start = "\033[92m" if status == "healthy" else "\033[91m"
        color_end = "\033[0m"
        
        print(f"[{timestamp}] {color_start}STATUS: {status.upper():<10} | ANOMALY SCORE: {score:.4f}{color_end}")
        
        # Optionally log to a file
        if userdata['log_file']:
            with open(userdata['log_file'], 'a') as f:
                f.write(f"{timestamp},{status},{score}\n")
    except json.JSONDecodeError:
        print(f"[{timestamp}] [RAW] {payload}")

def main():
    parser = argparse.ArgumentParser(description="MECHAVYBE Inference CLI Monitor (MQTT)")
    parser.add_argument("--server", type=str, default="broker.hivemq.com", help="MQTT Broker URL")
    parser.add_argument("--port", type=int, default=1883, help="MQTT Broker Port")
    parser.add_argument("--topic", type=str, default="mechavybe/status", help="MQTT Topic to subscribe to")
    parser.add_argument("--log", type=str, default=None, help="Optional CSV file to save the inference logs")
    
    args = parser.parse_args()
    
    print("=========================================")
    print("      MECHAVYBE CLI MONITOR (MQTT)       ")
    print("=========================================")
    print(f"Broker: {args.server}:{args.port}")
    print(f"Topic:  {args.topic}")
    if args.log:
        print(f"Logging to: {args.log}")
        # Initialize log file with header
        with open(args.log, 'a') as f:
            f.write("timestamp,status,score\n")
    print("=========================================\n")
    print("Connecting...")

    # MQTTv5 client
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.user_data_set({"topic": args.topic, "log_file": args.log})
    
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(args.server, args.port, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[*] Exiting CLI Monitor...")
        client.disconnect()
    except Exception as e:
        print(f"\n[!] Error: {e}")

if __name__ == "__main__":
    main()
