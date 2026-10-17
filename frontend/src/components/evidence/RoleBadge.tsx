import type { Role } from "../../types";

export default function RoleBadge({ role }: { role: Role }) {
  return <span className={`badge ${role.toLowerCase()}`}>{role}</span>;
}
