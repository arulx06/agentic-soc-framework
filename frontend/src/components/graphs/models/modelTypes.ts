import type { Group, Mesh, MeshBasicMaterial } from "three";

export type NodeModelKind =
  | "AccelerometerSensorModel"
  | "AccessPointModel"
  | "Attacker0Model"
  | "Attacker1Model"
  | "Attacker2Model"
  | "Attacker3Model"
  | "Attacker4Model"
  | "Attacker5Model"
  | "BluramsCameraModel"
  | "DekcoCameraModel"
  | "EdgeNodeModel"
  | "FlameSensorModel"
  | "GasSensorModel"
  | "GeeniCameraModel"
  | "IotCloudModel"
  | "LightSensorModel"
  | "MotionSensorModel"
  | "MqttBrokerModel"
  | "MyqCameraModel"
  | "PlugAllCamerasModel"
  | "PlugAllRpbModel"
  | "PlugAllSensorsModel"
  | "PlugCamerasDekcoBluramsModel"
  | "PlugCamerasGeeniModel"
  | "PlugCamerasYiModel"
  | "PlugEdge1Model"
  | "PlugFlameModel"
  | "PlugMotionModel"
  | "PlugMqttModel"
  | "PlugProximityModel"
  | "PlugRfidModel"
  | "PlugVibrationModel"
  | "ProximityCollisionSensorModel"
  | "RfidSensorModel"
  | "RouterModel"
  | "SoilSensorModel"
  | "SoundSensorModel"
  | "SteamSensorModel"
  | "NetworkSwitchModel"
  | "UltrasonicSensorModel"
  | "VibrationSensorModel"
  | "WaterSensorModel"
  | "WeatherSensorModel"
  | "WisenetCameraModel"
  | "YiCameraModel"
  | "GenericDeviceModel"
  | "GenericSensorModel"
  | "GenericCameraModel"
  | "GenericPlugModel"
  | "GenericNetworkDeviceModel"
  | "GenericAttackerModel";

export interface ModelBounds {
  radius: number;
  top: number;
}

export interface ModelBuildContext {
  content: Group;
  stateMeshes: Mesh[];
  accentMeshes: Mesh[];
}

export type ModelBuilder = (ctx: ModelBuildContext) => void;

export interface BuiltNodeModel {
  kind: NodeModelKind;
  content: Group;
  stateMaterials: MeshBasicMaterial[];
  accentMaterials: MeshBasicMaterial[];
  bounds: ModelBounds;
}
