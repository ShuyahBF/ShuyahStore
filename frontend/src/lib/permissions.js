// Pictogrammes des AUTORISATIONS Android : un dessin représentatif par type d'autorisation (SMS = bulle, appels = combiné, position = repère…).
// Règle 15 du propriétaire : jamais d'information sans pictogramme ; la couleur seule ne suffit pas (le libellé reste écrit à côté).
import {
  Battery, Bell, Bluetooth, Calendar, Camera, Contact, Fingerprint, Flashlight, FolderOpen, Globe, Image, LayoutGrid, Mail, MapPin, MessageSquare, Mic, Music,
  Nfc, Phone, PhoneCall, Play, Power, Send, Shield, Smartphone, Timer, Trash2, UserRound, Video, Vibrate, Volume2, Wifi, Download, Layers, Eye, RefreshCw,
} from "lucide-react";

// Nom court de l'autorisation (après « android.permission. ») → pictogramme
const PAR_NOM = {
  INTERNET: Globe, ACCESS_NETWORK_STATE: Globe, ACCESS_WIFI_STATE: Wifi, CHANGE_WIFI_STATE: Wifi,
  READ_SMS: MessageSquare, RECEIVE_SMS: MessageSquare, SEND_SMS: Send, RECEIVE_MMS: MessageSquare, RECEIVE_WAP_PUSH: MessageSquare,
  CALL_PHONE: PhoneCall, READ_PHONE_STATE: Smartphone, READ_PHONE_NUMBERS: Smartphone, READ_CALL_LOG: Phone, WRITE_CALL_LOG: Phone, ANSWER_PHONE_CALLS: Phone,
  READ_CONTACTS: Contact, WRITE_CONTACTS: Contact, GET_ACCOUNTS: UserRound,
  CAMERA: Camera, RECORD_AUDIO: Mic,
  ACCESS_FINE_LOCATION: MapPin, ACCESS_COARSE_LOCATION: MapPin, ACCESS_BACKGROUND_LOCATION: MapPin,
  READ_EXTERNAL_STORAGE: FolderOpen, WRITE_EXTERNAL_STORAGE: FolderOpen, MANAGE_EXTERNAL_STORAGE: FolderOpen,
  READ_MEDIA_IMAGES: Image, READ_MEDIA_VIDEO: Video, READ_MEDIA_AUDIO: Music,
  READ_CALENDAR: Calendar, WRITE_CALENDAR: Calendar,
  SYSTEM_ALERT_WINDOW: Layers, BIND_ACCESSIBILITY_SERVICE: Eye,
  REQUEST_INSTALL_PACKAGES: Download, REQUEST_DELETE_PACKAGES: Trash2, QUERY_ALL_PACKAGES: LayoutGrid, INSTALL_PACKAGES: Download,
  POST_NOTIFICATIONS: Bell, USE_BIOMETRIC: Fingerprint, USE_FINGERPRINT: Fingerprint, VIBRATE: Vibrate,
  WAKE_LOCK: Power, FOREGROUND_SERVICE: Play, FOREGROUND_SERVICE_DATA_SYNC: RefreshCw, FOREGROUND_SERVICE_SPECIAL_USE: Play, RECEIVE_BOOT_COMPLETED: Power,
  BLUETOOTH_CONNECT: Bluetooth, BLUETOOTH: Bluetooth, BLUETOOTH_SCAN: Bluetooth, NFC: Nfc,
  REQUEST_IGNORE_BATTERY_OPTIMIZATIONS: Battery, SCHEDULE_EXACT_ALARM: Timer, USE_EXACT_ALARM: Timer,
  FLASHLIGHT: Flashlight, MODIFY_AUDIO_SETTINGS: Volume2,
};

/** Pictogramme représentatif d'une autorisation (« android.permission.READ_SMS » → bulle de message). Inconnue : bouclier (jamais un dessin inventé). */
export function pictogrammeAutorisation(nom) {
  const court = String(nom || "").split(".").pop();
  if (PAR_NOM[court]) return PAR_NOM[court];
  if (String(nom).includes("c2dm")) return Mail;                      // notifications poussées (Firebase)
  return Shield;
}
