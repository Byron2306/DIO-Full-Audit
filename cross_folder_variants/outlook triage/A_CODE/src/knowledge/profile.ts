import fs from "fs/promises";
import path from "path";

const PROFILE_PATH = path.resolve("agent-data", "profile.json");
const CONTACTS_PATH = path.resolve("agent-data", "contacts.json");
const MEMORY_PATH = path.resolve("agent-data", "memory.json");

export interface UserProfile {
  name: string;
  email: string;
  role: string;
  organization: string;
  department: string;
  studentNumber?: string;
  bio: string;
  expertise: string[];
  currentProjects: string[];
  communication: {
    tone: string;
    signOff: string;
    language: string;
  };
  customFolders: string[];
  notes: string;
}

export interface Contact {
  name: string;
  email: string;
  relationship: string;
  context: string;
  lastInteraction?: string;
  notes: string;
}

export interface MemoryEntry {
  id: string;
  timestamp: string;
  type: "email_thread" | "decision" | "context" | "task" | "research" | "document";
  summary: string;
  details: string;
  relatedEmails?: string[];
  tags: string[];
}

const DEFAULT_PROFILE: UserProfile = {
  name: "",
  email: "",
  role: "",
  organization: "",
  department: "",
  bio: "",
  expertise: [],
  currentProjects: [],
  communication: {
    tone: "professional",
    signOff: "Kind regards",
    language: "en",
  },
  customFolders: [],
  notes: "",
};

async function ensureDir() {
  await fs.mkdir(path.resolve("agent-data"), { recursive: true });
}

export async function loadProfile(): Promise<UserProfile> {
  await ensureDir();
  try {
    const data = await fs.readFile(PROFILE_PATH, "utf-8");
    return { ...DEFAULT_PROFILE, ...JSON.parse(data) };
  } catch {
    return { ...DEFAULT_PROFILE };
  }
}

export async function saveProfile(profile: UserProfile): Promise<void> {
  await ensureDir();
  await fs.writeFile(PROFILE_PATH, JSON.stringify(profile, null, 2));
}

export async function loadContacts(): Promise<Contact[]> {
  await ensureDir();
  try {
    const data = await fs.readFile(CONTACTS_PATH, "utf-8");
    return JSON.parse(data);
  } catch {
    return [];
  }
}

export async function saveContacts(contacts: Contact[]): Promise<void> {
  await ensureDir();
  await fs.writeFile(CONTACTS_PATH, JSON.stringify(contacts, null, 2));
}

export async function upsertContact(contact: Contact): Promise<void> {
  const contacts = await loadContacts();
  const idx = contacts.findIndex(
    (c) => c.email.toLowerCase() === contact.email.toLowerCase()
  );
  if (idx >= 0) {
    contacts[idx] = { ...contacts[idx], ...contact };
  } else {
    contacts.push(contact);
  }
  await saveContacts(contacts);
}

export async function findContact(query: string): Promise<Contact | undefined> {
  const contacts = await loadContacts();
  const q = query.toLowerCase();
  return contacts.find(
    (c) =>
      c.name.toLowerCase().includes(q) ||
      c.email.toLowerCase().includes(q) ||
      c.relationship.toLowerCase().includes(q)
  );
}

export async function loadMemory(): Promise<MemoryEntry[]> {
  await ensureDir();
  try {
    const data = await fs.readFile(MEMORY_PATH, "utf-8");
    return JSON.parse(data);
  } catch {
    return [];
  }
}

export async function saveMemory(entries: MemoryEntry[]): Promise<void> {
  await ensureDir();
  await fs.writeFile(MEMORY_PATH, JSON.stringify(entries, null, 2));
}

export async function addMemory(entry: Omit<MemoryEntry, "id" | "timestamp">): Promise<void> {
  const entries = await loadMemory();
  entries.push({
    ...entry,
    id: `mem-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    timestamp: new Date().toISOString(),
  });
  if (entries.length > 500) {
    entries.splice(0, entries.length - 500);
  }
  await saveMemory(entries);
}

export async function searchMemory(query: string, limit = 10): Promise<MemoryEntry[]> {
  const entries = await loadMemory();
  const q = query.toLowerCase();
  return entries
    .filter(
      (e) =>
        e.summary.toLowerCase().includes(q) ||
        e.details.toLowerCase().includes(q) ||
        e.tags.some((t) => t.toLowerCase().includes(q))
    )
    .slice(-limit);
}

export async function getRecentMemory(type?: MemoryEntry["type"], limit = 20): Promise<MemoryEntry[]> {
  const entries = await loadMemory();
  const filtered = type ? entries.filter((e) => e.type === type) : entries;
  return filtered.slice(-limit);
}

export function buildProfileContext(profile: UserProfile): string {
  if (!profile.name) return "";
  const parts = [
    `Name: ${profile.name}`,
    profile.email && `Email: ${profile.email}`,
    profile.role && `Role: ${profile.role}`,
    profile.organization && `Organization: ${profile.organization}`,
    profile.department && `Department: ${profile.department}`,
    profile.studentNumber && `Student Number: ${profile.studentNumber}`,
    profile.bio && `Bio: ${profile.bio}`,
    profile.expertise.length > 0 && `Expertise: ${profile.expertise.join(", ")}`,
    profile.currentProjects.length > 0 && `Current Projects: ${profile.currentProjects.join(", ")}`,
    `Preferred tone: ${profile.communication.tone}`,
    `Sign-off: ${profile.communication.signOff}`,
    profile.notes && `Additional context: ${profile.notes}`,
  ];
  return parts.filter(Boolean).join("\n");
}
