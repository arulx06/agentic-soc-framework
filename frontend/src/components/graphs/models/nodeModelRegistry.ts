import type { NodeModelKind } from "./modelTypes";

export const KNOWN_NODE_IDS = [
  "accelerometer-sensor",
  "ap",
  "attacker0",
  "attacker1",
  "attacker2",
  "attacker3",
  "attacker4",
  "attacker5",
  "blurams-camera",
  "dekco-camera",
  "edge1",
  "flame-sensor",
  "gas-sensor",
  "geeni-camera",
  "iot-cloud",
  "light-sensor",
  "motion-sensor",
  "mqtt-broker",
  "myq-camera",
  "plug-all-cameras",
  "plug-all-rpb",
  "plug-all-sensors",
  "plug-cameras-dekco-blurams",
  "plug-cameras-geeni",
  "plug-cameras-yi",
  "plug-edge1",
  "plug-flame",
  "plug-motion",
  "plug-mqtt",
  "plug-proximity",
  "plug-rfid",
  "plug-vibration",
  "proximity-collision-sensor",
  "rfid-sensor",
  "router",
  "soil-sensor",
  "sound-sensor",
  "steam-sensor",
  "switch",
  "ultrasonic-sensor",
  "vibration-sensor",
  "water-sensor",
  "weather-sensor",
  "wisenet-camera",
  "yi-camera",
] as const;

export type KnownNodeId = (typeof KNOWN_NODE_IDS)[number];

export const NODE_MODEL_BY_ID: Record<KnownNodeId, NodeModelKind> = {
  "accelerometer-sensor": "AccelerometerSensorModel",
  ap: "AccessPointModel",
  attacker0: "Attacker0Model",
  attacker1: "Attacker1Model",
  attacker2: "Attacker2Model",
  attacker3: "Attacker3Model",
  attacker4: "Attacker4Model",
  attacker5: "Attacker5Model",
  "blurams-camera": "BluramsCameraModel",
  "dekco-camera": "DekcoCameraModel",
  edge1: "EdgeNodeModel",
  "flame-sensor": "FlameSensorModel",
  "gas-sensor": "GasSensorModel",
  "geeni-camera": "GeeniCameraModel",
  "iot-cloud": "IotCloudModel",
  "light-sensor": "LightSensorModel",
  "motion-sensor": "MotionSensorModel",
  "mqtt-broker": "MqttBrokerModel",
  "myq-camera": "MyqCameraModel",
  "plug-all-cameras": "PlugAllCamerasModel",
  "plug-all-rpb": "PlugAllRpbModel",
  "plug-all-sensors": "PlugAllSensorsModel",
  "plug-cameras-dekco-blurams": "PlugCamerasDekcoBluramsModel",
  "plug-cameras-geeni": "PlugCamerasGeeniModel",
  "plug-cameras-yi": "PlugCamerasYiModel",
  "plug-edge1": "PlugEdge1Model",
  "plug-flame": "PlugFlameModel",
  "plug-motion": "PlugMotionModel",
  "plug-mqtt": "PlugMqttModel",
  "plug-proximity": "PlugProximityModel",
  "plug-rfid": "PlugRfidModel",
  "plug-vibration": "PlugVibrationModel",
  "proximity-collision-sensor": "ProximityCollisionSensorModel",
  "rfid-sensor": "RfidSensorModel",
  router: "RouterModel",
  "soil-sensor": "SoilSensorModel",
  "sound-sensor": "SoundSensorModel",
  "steam-sensor": "SteamSensorModel",
  switch: "NetworkSwitchModel",
  "ultrasonic-sensor": "UltrasonicSensorModel",
  "vibration-sensor": "VibrationSensorModel",
  "water-sensor": "WaterSensorModel",
  "weather-sensor": "WeatherSensorModel",
  "wisenet-camera": "WisenetCameraModel",
  "yi-camera": "YiCameraModel",
};

export interface NodeModelHints {
  deviceType?: string | null;
  role?: string | null;
  isAttacker?: boolean;
}

function matchesAny(value: string, needles: string[]): boolean {
  return needles.some((needle) => value.includes(needle));
}

export function resolveNodeModelKind(
  id: string,
  hints?: NodeModelHints
): NodeModelKind {
  const known = NODE_MODEL_BY_ID[id as KnownNodeId];
  if (known) return known;
  const role = (hints?.role ?? "").toLowerCase();
  const deviceType = (hints?.deviceType ?? "").toLowerCase();
  if (hints?.isAttacker) return "GenericAttackerModel";
  if (matchesAny(role, ["camera"]) || matchesAny(deviceType, ["camera"]))
    return "GenericCameraModel";
  if (matchesAny(role, ["sensor"]) || matchesAny(deviceType, ["sensor"]))
    return "GenericSensorModel";
  if (
    matchesAny(role, ["plug", "outlet", "relay"]) ||
    matchesAny(deviceType, ["plug", "outlet", "relay"])
  )
    return "GenericPlugModel";
  if (
    matchesAny(role + " " + deviceType, [
      "router",
      "access point",
      "switch",
      "broker",
      "gateway",
      "cloud",
      "server",
      "edge",
      "network",
    ])
  )
    return "GenericNetworkDeviceModel";
  return "GenericDeviceModel";
}
