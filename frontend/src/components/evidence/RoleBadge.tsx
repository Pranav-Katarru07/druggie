import type { Role } from "../../types";

const LABEL: Partial<Record<Role, string>> = { After: "After onset" };

export default function RoleBadge({ role }: { role: Role }) {
  return <span className={`badge ${role.toLowerCase()}`}>{LABEL[role] ?? role}</span>;
}
