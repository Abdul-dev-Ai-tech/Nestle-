export type PPEItem = 'uniform' | 'hair_cap' | 'face_mask' | 'beard_net' | 'safety_shoes';
export const PPE_ITEMS: PPEItem[] = ['uniform', 'hair_cap', 'face_mask', 'beard_net', 'safety_shoes'];
export const PPE_LABELS: Record<PPEItem, string> = {
  uniform: 'Uniform', hair_cap: 'Hair Cap', face_mask: 'Face Mask', beard_net: 'Beard Net', safety_shoes: 'Safety Shoes',
};

export interface Page<T> { items: T[]; total: number; page: number; page_size: number }

export interface User {
  id: number; email: string; full_name: string; is_active: boolean; factory_id: number | null;
  roles: { id: number; name: string }[]; role: string; last_login_at: string | null; created_at: string;
}
export interface Me {
  user: User; permissions: string[]; is_superuser: boolean; environment: string;
  session: { id: number; expires_at: string; idle_minutes: number };
}
export interface Role {
  id: number; name: string; description: string; is_system: boolean; is_superuser: boolean; rank: number;
  permissions: string[]; user_count: number;
}
export interface Permission { code: string; category: string; description: string }
export interface Shift { code: string; start: string; end: string }
export interface Factory { id: number; name: string; code: string; address: string; timezone: string; shifts: Shift[]; is_active: boolean }
export interface EntryPoint { id: number; name: string; module_id: number; is_active: boolean }
export interface Module {
  id: number; factory_id: number; name: string; code: string; description: string; color: string; is_active: boolean;
  ppe: Record<PPEItem, { required: boolean; min_confidence: number | null }>; entry_points: EntryPoint[];
}
export interface EmployeeStats { entries: number; violations: number; compliance: number | null; last_entry_at: string | null }
export interface Employee {
  id: number; factory_id: number; employee_code: string; full_name: string; designation: string; shift: string;
  beard_net_applicable: boolean; status: 'active' | 'inactive'; has_photo: boolean; module_id: number | null;
  module: { id: number; name: string; color: string } | null; department_id: number | null; department: string | null;
  stats_30d?: EmployeeStats; stats_all?: EmployeeStats;
}
export interface EmployeeBrief { id: number; employee_code: string; full_name: string; designation: string; department: string | null; shift: string; has_photo: boolean }
export interface Camera {
  id: number; name: string; type: 'browser' | 'usb' | 'rtsp' | 'onvif'; source: string; has_credentials: boolean;
  is_active: boolean; status: 'unknown' | 'online' | 'offline'; last_seen_at: string | null; last_error: string;
  resolution: string; entry_point_id: number | null; entry_point: string | null; module_id: number | null;
}
export interface Door {
  id: number; name: string; entry_point_id: number; entry_point: string; module_id: number; adapter: string;
  config: Record<string, unknown>; unlock_seconds: number; fail_mode: string; auto_open: boolean;
  state: 'locked' | 'unlocked' | 'held' | 'fault'; online: boolean; hardware_active: boolean; hardware_approved_at: string | null;
}
export interface Entry {
  id: number; occurred_at: string; passed: boolean; decision: string; missing_items: PPEItem[]; missing_labels: string[];
  shift: string | null; source: 'live' | 'simulation' | 'sample'; has_evidence: boolean; employee: EmployeeBrief | null;
  module: { id: number; name: string; color: string }; entry_point: string | null; camera: string | null;
}
export interface ItemResult {
  item: PPEItem; label: string; required: boolean; detected: boolean; confidence: number; threshold: number;
  status: 'pass' | 'fail' | 'not_required'; reason: string; bbox: [number, number, number, number] | null;
}
export interface Violation {
  id: number; created_at: string; status: 'open' | 'under_review' | 'escalated' | 'resolved';
  severity: 'medium' | 'high' | 'critical'; is_repeat: boolean; missing_items: PPEItem[]; missing_labels: string[];
  employee: EmployeeBrief | null; module: { id: number; name: string; color: string }; entry_point: string | null;
  camera: string | null; entry_id: number; source: string; has_evidence: boolean;
  notes?: { id: number; author: string; text: string; created_at: string }[];
  detections?: { item: PPEItem; label: string; detected: boolean; confidence: number; simulated: boolean }[];
  item_results?: ItemResult[]; employee_violation_count?: number;
}
export interface Alert {
  id: number; type: string; severity: 'medium' | 'high' | 'critical'; title: string; detail: string;
  ref_type: string | null; ref_id: number | null; created_at: string; read: boolean; acknowledged: boolean;
}
export interface AccessEvent { id: number; occurred_at: string; type: string; reason: string; simulated: boolean; door: string; actor: string }
export interface Totals { entries: number; passed: number; failed: number; compliance: number | null }
export interface SeriesPoint extends Totals { date: string; label: string }
export interface DashboardSummary {
  factory: Factory; generated_at: string; today: Totals; yesterday_same_time: Totals; open_violations: number;
  alerts: { unacknowledged: number; critical: number; unread: number; items: Alert[] };
  daily: SeriesPoint[];
  by_module: { module_id: number; name: string; color: string; entries: number; failed: number; compliance: number | null }[];
  missing_ppe: { item: PPEItem; label: string; missing: number }[];
  cameras: Camera[]; doors: Door[]; recent_entries: Entry[]; recent_violations: Violation[];
  data_sources: Record<string, number>; ai_mode: string; door_mode: string;
}
export interface AiStatus {
  mode: string; available: boolean; simulated: boolean; model_name: string | null; model_version: string | null;
  error?: string; classes: Record<PPEItem, { status: string; detail: string }>; door_mode: string; can_force_scenario: boolean;
}
export interface CheckResult {
  entry: Entry; passed: boolean; decision: string; items: ItemResult[]; missing_items: PPEItem[]; missing_labels: string[];
  threshold: number; employee: EmployeeBrief | null;
  detector: { model_name: string; model_version: string; simulated: boolean; notes: string[] };
  door: Door | null; door_result: { action: string; simulated: boolean; message: string }; violation_id: number | null;
}
export interface FactorySettings {
  factory_id: number; confidence_threshold: number; evidence_policy: 'violations' | 'all'; retention_days: number;
  repeat_threshold: number; repeat_window_days: number; notifications: Record<string, Record<string, boolean>>;
  system: { environment: string; ai_mode: string; door_mode: string; hardware_doors_enabled: boolean;
    session_idle_minutes: number; session_absolute_hours: number; max_upload_mb: number; smtp_configured: boolean };
}
